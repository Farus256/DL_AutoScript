#!/data/data/com.termux/files/usr/bin/bash
# Вызывается cron'ом. Пишет вывод в attendance.log (ротация на 1 МБ).
cd "$(dirname "$0")/.."
LOG=attendance.log
if [ -f "$LOG" ] && [ "$(stat -c%s "$LOG")" -gt 1000000 ]; then mv -f "$LOG" "$LOG.old"; fi
{ echo "=== $(date '+%F %T') ==="; /data/data/com.termux/files/usr/bin/python nure_attendance.py; } >> "$LOG" 2>&1
