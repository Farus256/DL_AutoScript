#!/data/data/com.termux/files/usr/bin/bash
# Установка на Android (Termux). Запуск: bash termux/setup.sh  (повторный запуск безопасен)
set -e
cd "$(dirname "$0")/.."
DIR="$(pwd)"
BIN=/data/data/com.termux/files/usr/bin

echo "==> Пакеты"
pkg install -y python cronie
pip install -q -r requirements.txt
chmod +x termux/run.sh termux/wake.sh

echo "==> cron: планировщик берёт расписание из календаря DL 5 раз в день"
# Убираем старую строку «каждые 15 минут» (если была) и ставим планировщик.
( crontab -l 2>/dev/null | grep -v -e "$DIR/termux/run.sh\$" -e "termux/run.sh --plan" || true
  echo "5 5,8,11,14,17 * * * $DIR/termux/run.sh --plan --apply" ) | crontab -

echo "==> Автозапуск после перезагрузки (Termux:Boot)"
mkdir -p ~/.termux/boot
cat > ~/.termux/boot/start-attendance <<BOOT
#!$BIN/sh
# Wake lock берём только на время построения плана; дальше план сам
# держит его лишь вокруг пар (ATTENDANCE_WAKELOCK=smart).
termux-wake-lock
pgrep -x crond >/dev/null || crond
sleep 60                  # дать телефону поймать сеть
$DIR/termux/run.sh --plan --apply   # он же решит: оставить lock (идёт пара) или снять
BOOT
chmod +x ~/.termux/boot/start-attendance

grep -q 'pgrep -x crond' ~/.bashrc 2>/dev/null || \
  echo 'pgrep -x crond >/dev/null || crond' >> ~/.bashrc

pgrep -x crond >/dev/null || crond
[ -f .env ] || cp .env.example .env

echo
echo "Готово. Дальше:"
echo "  1) nano .env   (если ещё не заполнен)"
echo "  2) termux/run.sh --plan --apply   — построить план (и снять старый постоянный wake lock)"
echo "  3) crontab -l                     — посмотреть, когда будут проверки"
