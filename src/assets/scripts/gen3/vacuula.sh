#!/bin/sh
set -eux

VACUULA_VERSION=000001

NEATO_VERSION=$(cat /var/app_data/sw_info.txt)
OPERATION=${1}
LOGGER="logger -t ${0}"
FOLDER=/emmc/vacuula/${VACUULA_VERSION}
MODDED_ASTRO=${FOLDER}/astro_mod
ASTRO=/usr/bin/astro

UPLOADER=/usr/lib/libNeatoUploader.so.1
MODDED_UPLOADER=${FOLDER}/libNeatoUploader.so.1
TMP_UPLOADER=/tmp/libNeatoUploader.so.1

BMU=/usr/lib/libNeatoBMU.so
MODDED_BMU=${FOLDER}/libNeatoBMU.so
TMP_BMU=/tmp/libNeatoBMU.so
PORT_PATCH_DIR=/emmc/vacuula/port_patch
GEN3_PORT="$(sed -n '2p' /emmc/vacuula/config)"

log () {
    ${LOGGER} "[vacuula] $1"
    echo "[vacuula] $1" > /dev/ser1

    # save logs of the make_mod
    if [ "${OPERATION}" = "make_mod" ]; then
        echo "[vacuula] $1" >> /emmc/vacuula-init.log
        echo "[vacuula] $1" > /dev/serusb1
    fi
}

run_once () {
    set -C  # Enable noclobber - prevents overwriting files
    
    # Try to create lock file atomically - only succeeds if it doesn't exist
    if echo $$ > /tmp/vacuula_lock 2>/dev/null; then
        log "Acquired lock with PID $$"
        set +C  # Disable noclobber
        return 0
    else
        log "Lock already held, exiting"
        set +C  # Disable noclobber
        exit 0
    fi
}

case "${NEATO_VERSION}" in
    4.5.3-189)
        # Replace nucleo path (446448 == 0x6CFF0)
        NUCLEO_OFFSET=446448
        # Replace beehive path (446484 == 0x6D014)
        BEEHIVE_OFFSET=446484
        # Replace cloudmock path (446520 == 0x6D038)
        CLOUDMOCK_OFFSET=446520
        # gen3 port patch offsets
        PORT_STR_OFFSET=413049                  # 0x64D79: 3 free bytes + "443\0"
        MOVW_R2_OFFSET=173600                   # 0x2A620: movw r2,#443 (checkNucleo)
        MOVW_R1_OFFSET=177712                   # 0x2B630: movw r1,#443 (checkNucleo)
        LIB_MOVW_OFFSETS="21984 23016"          # 0x55E0 0x59E8: movw r2,#443 in libNeatoUploader
        BMU_AUTH_OFFSET=15064                   # 0x3AD8: bl auth_check in NeatoBMU::authenticate()
        BMU_MFG_OFFSETS="9232 9728"             # 0x2410 0x2600: zero mfg_access (+0x54) in read_bmu / read_data_block1
        BMU_SRW_OFFSET1=7348                    # 0x1CB4: retry counter init in smbus_read_word
        BMU_SRW_OFFSET2=7412                    # 0x1CF4: retry loop tail in smbus_read_word
        ;;
    4.6.0-72)
        # Replace nucleo path (446440 == 0x6CFE8)
        NUCLEO_OFFSET=446440
        # Replace beehive path (446476 == 0x6D00C)
        BEEHIVE_OFFSET=446476
        # Replace cloudmock path (446512 == 0x6D030)
        CLOUDMOCK_OFFSET=446512
        # gen3 port patch offsets (same values as 4.5.3-189, verified in both astro binaries)
        PORT_STR_OFFSET=413049
        MOVW_R2_OFFSET=173600
        MOVW_R1_OFFSET=177712
        LIB_MOVW_OFFSETS="21984 23016"
        ;;
    *)
        log "Neato version ${NEATO_VERSION} is not supported, exiting"
        exit 1
esac

start_bmu () {
    if [ -f ${MODDED_BMU} ]; then
        # PowerDaemon starts in start_app.sh before start_mod runs, so on boot it
        # loads the original unpatched library from /usr/lib. We copy the patched
        # library to /tmp and restart it once per boot (marker), so a watchdog tick
        # never restarts a running PowerDaemon. If it dies later we do restart it,
        # as it will then load the patched library anyway.
        if [ ! -f ${TMP_BMU} ]; then
            cp ${MODDED_BMU} ${TMP_BMU} || true
            log "Copied patched NeatoBMU to ${TMP_BMU}"
        fi

        pd_pid=$(pidin -f aN | awk '$NF ~ /PowerDaemon$/ { print $1 }') || true
        if [ -n "$pd_pid" ] && [ ! -f /tmp/.vacuula_bmu_done ]; then
            log "Unpatched PowerDaemon is running with PID ${pd_pid}, killing it"
            slay ${pd_pid} || true
            sleep 1
            pd_pid=""
        fi
        if [ -z "$pd_pid" ]; then
            log "PowerDaemon is not running, starting it"
            # We clear these sticky flags as the orginal libary might have flagged
            # the battery before load or pre-vaccula install, refer to the patch comments.
            qdbc -d /dev/qdb/systemdb "INSERT OR REPLACE INTO IntegerSettings( Name, Value ) VALUES ( 'BATTPERMERROR', 0 );" || true
            qdbc -d /dev/qdb/systemdb "INSERT OR REPLACE INTO IntegerSettings( Name, Value ) VALUES ( 'DEEPDISCHARGE', 0 );" || true
            nice -n-2 PowerDaemon > /dev/null 2>&1 &
            log "Started patched PowerDaemon with PID $!"
            touch /tmp/.vacuula_bmu_done || true
        fi
    fi
}

watchdog () {
    original_pid=$(pidin -f aN | awk '$NF ~ /astro$/ { print $1 }')
    modded_pid=$(pidin -f aN | awk '$NF ~ /astro_mod$/ { print $1 }')

    if [ -n "$original_pid" ]; then
        log "Original astro is running with PID ${original_pid}, killing it"
        slay ${original_pid}

        # if modded was running, make sure it cannot restart and start our cron
        crontab -r || true
        crontab /emmc/vacuula/vacuula.cron || true
    fi

    if [ -n "$modded_pid" ]; then
        log "Modded astro is running with PID ${modded_pid}, nothing to do"
    else
        log "Modded astro is not running, starting it"
        ${MODDED_ASTRO} &
        modded_pid=$!
        log "Started modded astro with PID ${modded_pid}"
    fi

    start_bmu
}

# check_bytes <file> <offset> <expected-bytes-file>. true if file has those bytes at offset
check_bytes () {
    size=$(ls -l "$3" | awk '{print $5}')
    dd if="$1" of=/tmp/vacuula_chk bs=1 skip="$2" count="${size}" 2>/dev/null
    [ "$(openssl sha1 < /tmp/vacuula_chk)" = "$(openssl sha1 < "$3")" ]
}

# patch_at <bytes-file> <target-file> <offset>
patch_at () {
    dd if="$1" of="$2" bs=1 seek="$3" conv=notrunc 2>/dev/null
}

patch_fail () {
    log "[[vacuula-installer-failed]] patches failed: $1"
    echo "[[vacuula-installer-failed]]" > /dev/serusb1
    exit 1
}

# move astro (nucleo/beehive) and libNeatoUploader (map/log uploads) from 443 to GEN3_PORT
patch_port () {
    if [ "${GEN3_PORT}" = "443" ]; then
        log "Gen3 port is 443, no port patch needed"
        rm -f ${MODDED_UPLOADER}
        return 0
    fi

    log "Patching astro and NeatoUploader for gen3 port ${GEN3_PORT}"
    # the library is patched in a copy, the original in /usr/lib is never touched
    cp ${UPLOADER} ${MODDED_UPLOADER}

    # verify every location holds the expected original bytes before touching anything
    check_bytes ${MODDED_ASTRO} ${PORT_STR_OFFSET} ${PORT_PATCH_DIR}/o_str || patch_fail "astro string"
    check_bytes ${MODDED_ASTRO} ${MOVW_R2_OFFSET} ${PORT_PATCH_DIR}/o_movw2 || patch_fail "astro movw r2"
    check_bytes ${MODDED_ASTRO} ${MOVW_R1_OFFSET} ${PORT_PATCH_DIR}/o_movw1 || patch_fail "astro movw r1"
    for o in ${LIB_MOVW_OFFSETS}; do
        check_bytes ${MODDED_UPLOADER} $o ${PORT_PATCH_DIR}/o_movw2 || patch_fail "uploader movw $o"
    done

    # astro: new "<port>\0" string in the free bytes before "443\0", pointers moved to it,
    # and the two movw immediates; library: the two movw immediates
    patch_at ${PORT_PATCH_DIR}/p_str ${MODDED_ASTRO} ${PORT_STR_OFFSET}
    patch_at ${PORT_PATCH_DIR}/p_movw2 ${MODDED_ASTRO} ${MOVW_R2_OFFSET}
    patch_at ${PORT_PATCH_DIR}/p_movw1 ${MODDED_ASTRO} ${MOVW_R1_OFFSET}
    for o in ${LIB_MOVW_OFFSETS}; do
        patch_at ${PORT_PATCH_DIR}/p_movw2 ${MODDED_UPLOADER} $o
    done

    # verify the result
    check_bytes ${MODDED_ASTRO} ${MOVW_R2_OFFSET} ${PORT_PATCH_DIR}/p_movw2 || patch_fail "astro verify"
    for o in ${LIB_MOVW_OFFSETS}; do
        check_bytes ${MODDED_UPLOADER} $o ${PORT_PATCH_DIR}/p_movw2 || patch_fail "uploader verify $o"
    done
    log "Gen3 port patch done: $(openssl sha1 ${MODDED_ASTRO} ${MODDED_UPLOADER})"
    rm -f /tmp/vacuula_chk
}

# Patch libNeatoBMU so non-oem battery packs can authenticate and charge:
# 1. authenticate(): sends an SMBus challenge and verifies an HMAC-SHA1 response
#    keyed with a secret only genuine Neato BMS firmware has ('bl' -> 'mov r0, #1').
#    we simply always retun success effectively patching the check out.
# 2. read_bmu() / read_data_block1(): reads SMBus reg 0x00 (ManufacturerAccess) into
#    mfg_access for checkFault/checkPermError. Framed as a fault check (0x0000 when
#    healthy on Neato BMS firmware, bits in 0x00F2 on fault), it also catches clones:
#    standard TI bq40z50 firmware returns status word 0x0387, which overlaps 0x00F2 and
#    sets BATTPERMERROR=1 in systemdb causing the robot to report a "fault" and never 
#    trust the battery no matter its actual health. ('ldrh r2, [fp, #-0x12]' -> 'mov r2, #0')
#    we again simply always return success effectively patching the check out.
# 3. read_smbus_word(): as some clones of the bz40z50 bms sometimes will randomly respond with
#    NAK we patch read_smbus_word to make use of i2c_read_robust instad of one-shot i2c_read
patch_bmu () {
    if [ -z "${BMU_AUTH_OFFSET:-}" ]; then
        log "No BMU patch for ${NEATO_VERSION}, skipping"
        return 0
    fi

    log "Patching NeatoBMU"
    cp ${BMU} ${MODDED_BMU}

    check_bytes ${MODDED_BMU} ${BMU_AUTH_OFFSET} ${PORT_PATCH_DIR}/o_bmu || patch_fail "bmu auth"
    for o in ${BMU_MFG_OFFSETS}; do
        check_bytes ${MODDED_BMU} $o ${PORT_PATCH_DIR}/o_bmu_flt || patch_fail "bmu mfg $o"
    done
    if [ -n "${BMU_SRW_OFFSET1:-}" ]; then
        check_bytes ${MODDED_BMU} ${BMU_SRW_OFFSET1} ${PORT_PATCH_DIR}/o_bmu_srw1 || patch_fail "bmu srw1"
        check_bytes ${MODDED_BMU} ${BMU_SRW_OFFSET2} ${PORT_PATCH_DIR}/o_bmu_srw2 || patch_fail "bmu srw2"
    fi

    patch_at ${PORT_PATCH_DIR}/p_bmu ${MODDED_BMU} ${BMU_AUTH_OFFSET}
    for o in ${BMU_MFG_OFFSETS}; do
        patch_at ${PORT_PATCH_DIR}/p_bmu_flt ${MODDED_BMU} $o
    done
    if [ -n "${BMU_SRW_OFFSET1:-}" ]; then
        patch_at ${PORT_PATCH_DIR}/p_bmu_srw1 ${MODDED_BMU} ${BMU_SRW_OFFSET1}
        patch_at ${PORT_PATCH_DIR}/p_bmu_srw2 ${MODDED_BMU} ${BMU_SRW_OFFSET2}
    fi

    check_bytes ${MODDED_BMU} ${BMU_AUTH_OFFSET} ${PORT_PATCH_DIR}/p_bmu || patch_fail "bmu verify"
    for o in ${BMU_MFG_OFFSETS}; do
        check_bytes ${MODDED_BMU} $o ${PORT_PATCH_DIR}/p_bmu_flt || patch_fail "bmu verify $o"
    done
    if [ -n "${BMU_SRW_OFFSET1:-}" ]; then
        check_bytes ${MODDED_BMU} ${BMU_SRW_OFFSET1} ${PORT_PATCH_DIR}/p_bmu_srw1 || patch_fail "bmu srw1 verify"
        check_bytes ${MODDED_BMU} ${BMU_SRW_OFFSET2} ${PORT_PATCH_DIR}/p_bmu_srw2 || patch_fail "bmu srw2 verify"
    fi
    log "BMU patch done: $(openssl sha1 ${MODDED_BMU})"
    rm -f /tmp/vacuula_chk
}

make_mod () {
    log "Making modded astro binary at ${MODDED_ASTRO}"
    log "Copying original astro from ${ASTRO}"
    mkdir -p ${FOLDER}
    cp ${ASTRO} ${MODDED_ASTRO}

    log "Copying certificate files to ${FOLDER}"
    cp /emmc/vacuula/cert.pem ${FOLDER}/___Nucleo.crt
    cp /emmc/vacuula/cert.pem ${FOLDER}/___Beehive.crt
    cp /emmc/vacuula/cert.pem ${FOLDER}/___CloudMock.crt

    # build the strings that should be replaced in modded astro
    log "Building replacement strings for modded astro"
    # /var/server/neato_cloud/Nucleo.crt
    # /emmc/vacuula/XXXXXX/___Nucleo.crt
    echo -n "${FOLDER}/___Nucleo.crt" > ${FOLDER}/nucleo_path
    # /var/server/neato_cloud/Beehive.crt
    # /emmc/vacuula/XXXXXX/___Beehive.crt
    echo -n "${FOLDER}/___Beehive.crt" > ${FOLDER}/beehive_path
    # /var/server/neato_cloud/CloudMock.crt
    # /emmc/vacuula/XXXXXX/___CloudMock.crt
    echo -n "${FOLDER}/___CloudMock.crt" > ${FOLDER}/cloudmock_path

    log "Replacing certificate paths in modded astro binary"
    dd if=${FOLDER}/nucleo_path of=${MODDED_ASTRO} bs=1 seek=${NUCLEO_OFFSET} conv=notrunc
    dd if=${FOLDER}/beehive_path of=${MODDED_ASTRO} bs=1 seek=${BEEHIVE_OFFSET} conv=notrunc
    dd if=${FOLDER}/cloudmock_path of=${MODDED_ASTRO} bs=1 seek=${CLOUDMOCK_OFFSET} conv=notrunc

    # gen3 port: patch astro_mod (and a copy of libNeatoUploader) when GEN3_PORT is not 443
    patch_port

    # non-oem batteries patch
    patch_bmu

    # TODO: verification of all mods!

    log "Modded astro binary created successfully"
    log "$(ls -lah ${FOLDER})"
}

start_mod () {
    # gen3 port != 443: /tmp is cleared at every boot, so copy the patched library again before
    # Robot/fileuploader start; they load libNeatoUploader from /tmp before /usr/lib
    if [ -f ${MODDED_UPLOADER} ]; then
        cp ${MODDED_UPLOADER} ${TMP_UPLOADER}
        log "Copied port-patched NeatoUploader to ${TMP_UPLOADER}"
    fi
    watchdog
    # make shell if file exists
    # [ -f /emmc/vacuula/shell.sh ] && /bin/sh /emmc/vacuula/shell.sh &

    ln -fsP /emmc/vacuula/hosts /etc/hosts
    # ifconfig lo0 alias 8.8.8.8 netmask 255.255.255.255

    # initially, our cron has to run!
    crontab -r || true
    crontab /emmc/vacuula/vacuula.cron || true
    start_bmu
}


case "${OPERATION}" in
    watchdog)
        log "Watchdog called - making sure vacuula is active"
		watchdog
        ;;
    make_mod)
        run_once
        make_mod
        ;;
    start_mod)
        run_once
        start_mod
esac
