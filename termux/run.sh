#!/data/data/com.termux/files/usr/bin/bash
# Вызывается cron'ом. Аргументы передаются скрипту (--plan --apply / --only ID).
export PATH=/data/data/com.termux/files/usr/bin:$PATH
cd "$(dirname "$0")/.."
# Пока строится план — не даём телефону уснуть; в конце план сам выставит нужное состояние.
[ "$1" = "--plan" ] && termux-wake-lock 2>/dev/null
LOG=attendance.log
if [ -f "$LOG" ] && [ "$(stat -c%s "$LOG")" -gt 1000000 ]; then mv -f "$LOG" "$LOG.old"; fi
{ echo "=== $(date '+%F %T') $* ==="; /data/data/com.termux/files/usr/bin/python nure_attendance.py "$@"; } >> "$LOG" 2>&1
