#!/data/data/com.termux/files/usr/bin/bash
# Установка на Android (Termux). Запуск: bash termux/setup.sh
set -e
cd "$(dirname "$0")/.."
DIR="$(pwd)"
BIN=/data/data/com.termux/files/usr/bin

echo "==> Пакеты"
pkg install -y python cronie
pip install -q -r requirements.txt

chmod +x termux/run.sh

echo "==> Расписание cron: Пн–Сб, 06:00–18:45 по времени телефона, каждые 15 минут"
( crontab -l 2>/dev/null | grep -v 'termux/run.sh' || true
  echo "*/15 6-18 * * 1-6 $DIR/termux/run.sh" ) | crontab -

echo "==> Автозапуск после перезагрузки (нужно приложение Termux:Boot)"
mkdir -p ~/.termux/boot
cat > ~/.termux/boot/start-attendance <<BOOT
#!$BIN/sh
termux-wake-lock
pgrep -x crond >/dev/null || crond
BOOT
chmod +x ~/.termux/boot/start-attendance

# И при каждом открытии Termux — на случай если crond убили
grep -q 'pgrep -x crond' ~/.bashrc 2>/dev/null || \
  echo 'pgrep -x crond >/dev/null || crond' >> ~/.bashrc

termux-wake-lock || true
pgrep -x crond >/dev/null || crond

[ -f .env ] || cp .env.example .env
echo
echo "Готово. Дальше:"
echo "  1) nano .env                         — логин, пароль, Telegram"
echo "  2) python nure_attendance.py --dry-run"
echo "  3) crontab -l                        — проверить расписание"
echo "  Лог: $DIR/attendance.log"
