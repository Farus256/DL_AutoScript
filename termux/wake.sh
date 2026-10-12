#!/data/data/com.termux/files/usr/bin/sh
# termux/wake.sh lock|unlock — вызывается cron'ом вокруг пар.
export PATH=/data/data/com.termux/files/usr/bin:$PATH
case "$1" in
  lock)   termux-wake-lock ;;
  unlock) termux-wake-unlock ;;
esac
echo "=== $(date '+%F %T') wake $1 ===" >> "$(dirname "$0")/../attendance.log"
