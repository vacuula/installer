#!/bin/sh
# very rudamentary shell just to make it easier to run commands
while true; do
    if read line < /dev/ser1; then
        case "$line" in
            cmd-*)
                CMD=$(echo "$line" | sed 's/^cmd-//' | sed 's/\r//g')

                echo "EXEC: $CMD" > /dev/ser1

                sh -c "$CMD" > /dev/ser1 2>&1

                echo "DONE" > /dev/ser1
                ;;
        esac
    fi
done