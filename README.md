# DL NURE Attendance

Автоматически нажимает «Відмітитися» во всех текущих курсах на dl.nure.ua.
Запускается по расписанию через GitHub Actions — компьютер включать не нужно.

## Как работает

1. Вход по логину/паролю (`/login/index.php`).
2. Список курсов «В процесі» — тот же AJAX-запрос, что и на `/my/courses.php`
   (`core_course_get_enrolled_courses_by_timeline_classification`). Новый семестр подхватывается сам.
3. В каждом курсе — все модули «Відвідування» (`/mod/attendance/index.php?id=<course>`).
4. На странице модуля ищет кнопку `a.btn-primary` → `attendance.php?sessid=…` (только открытые сессии;
   ссылку «Повідомити про майбутню відсутність» не трогает).
5. Если преподаватель включил авто-статус — отметка ставится сразу. Если появляется форма со статусами —
   выбирает «Присутній» и отправляет.
6. Перезагружает страницу и проверяет, что кнопка исчезла. Итог — в Telegram (опционально).
   Если открытых сессий нет — приходит беззвучное «🔍 проверка прошла».

Сессии с QR-кодом или паролем от преподавателя автоматически отметить нельзя — скрипт пришлёт «✋ нужно вручную».

## Где запускать

dl.nure.ua закрыт AWS WAF: с IP дата-центров (GitHub Actions, облака, VPS) вместо сайта приходит
страница «Human Verification» (HTTP 405). С домашнего/мобильного интернета проверки нет — поэтому
скрипт запускается на своём устройстве: **Android-телефоне (рекомендуется, он онлайн 24/7)** или ПК.

## Установка на Android (Termux)

1. Установи из **F-Droid** (не из Play Market — там другая подпись):
   [Termux](https://f-droid.org/packages/com.termux/) и [Termux:Boot](https://f-droid.org/packages/com.termux.boot/).
   Открой Termux:Boot один раз — так он получит разрешение на автозапуск.
2. Настройки Android → Приложения → **Termux** → Батарея → **Без ограничений**
   (на Xiaomi/Samsung ещё включить «Автозапуск» / убрать из «спящих приложений»). Без этого Android усыпит cron.
3. В Termux:
   ```
   pkg install -y git
   git clone https://github.com/Farus256/DL_AutoScript
   cd DL_AutoScript
   bash termux/setup.sh
   nano .env                              # логин, пароль, токен и chat_id; Ctrl+O, Enter, Ctrl+X
   python nure_attendance.py --dry-run    # проверка: в Telegram придёт беззвучное 🔍
   ```
4. Всё. Cron запускает `termux/run.sh` Пн–Сб каждые 15 минут с 06:00 до 18:45 по времени телефона
   (= 07–19:45 по Киеву). В шторке будет висеть уведомление Termux «wake lock held» — так и должно быть.

Полезное:
```
crontab -l                 # расписание
tail -n 30 attendance.log  # что было при последних запусках
termux/run.sh              # запустить прямо сейчас (как cron)
git pull                   # обновить скрипт
```

## Установка на ПК (Windows)

1. Python 3.10+ с [python.org](https://www.python.org/downloads/) — при установке отметь **Add python.exe to PATH**.
2. Склонируй/скачай репозиторий в папку, например `D:\DL_NureAttendance`.
3. Создай `.env` по образцу `.env.example`:
   ```
   NURE_USERNAME=логин
   NURE_PASSWORD=пароль
   TELEGRAM_BOT_TOKEN=123456:ABC...
   TELEGRAM_CHAT_ID=412345678
   ```
4. Проверка (в этой папке, в терминале):
   ```
   py -m pip install -r requirements.txt
   py nure_attendance.py --dry-run
   ```
   Должен вывести курсы, а в Telegram придёт беззвучное 🔍 или 🧪.
5. Расписание: правый клик по `install_task.ps1` → **Выполнить с помощью PowerShell**
   (или `powershell -ExecutionPolicy Bypass -File install_task.ps1`).
   Задача «NURE attendance»: Пн–Сб, 06:00–19:00 по немецкому времени (= 07–20 по Киеву), каждые 15 минут,
   без всплывающих окон. Лог — `attendance.log` рядом со скриптом.

Управление задачей (PowerShell):
```
Start-ScheduledTask 'NURE attendance'                      # запустить сейчас
Get-ScheduledTaskInfo 'NURE attendance'                    # когда запускалась, код возврата
Unregister-ScheduledTask 'NURE attendance' -Confirm:$false # удалить
```

## Telegram

- `TELEGRAM_BOT_TOKEN` — @BotFather → `/mybots` → бот → API Token.
- `TELEGRAM_CHAT_ID` — кому слать: свой числовой ID из [@userinfobot](https://t.me/userinfobot).
  У своего бота обязательно нажми **Start**, иначе он не сможет написать первым.

## Переменные

| Имя | |
|---|---|
| `NURE_USERNAME`, `NURE_PASSWORD` | обязательно; пароль Moodle (не вход через Google) |
| `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` | уведомления, опционально |
| `ATTENDANCE_EXTRA_IDS` / `ATTENDANCE_SKIP_IDS` | id модулей через запятую — добавить/исключить |

`.github/workflows/attendance.yml` оставлен только для ручного запуска — с раннеров GitHub он упрётся в WAF.
