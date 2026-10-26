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
    log "[[vacuula-installer-failed]] gen3 port patch: $1"
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
