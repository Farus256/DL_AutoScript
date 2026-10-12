# Регистрирует задачу в Планировщике Windows:
# Пн–Сб, 06:00–19:00 по местному (немецкому) времени = 07:00–20:00 по Киеву, каждые 15 минут.
# Запуск: правый клик -> "Выполнить с помощью PowerShell"
#   или:  powershell -ExecutionPolicy Bypass -File install_task.ps1
$ErrorActionPreference = "Stop"
$dir    = Split-Path -Parent $MyInvocation.MyCommand.Path
$script = Join-Path $dir "nure_attendance.py"

$py = (& py -3 -c "import sys; print(sys.executable)" 2>$null)
if (-not $py) { $py = (Get-Command python -ErrorAction SilentlyContinue).Source }
if (-not $py) { throw "Python не найден. Установи с python.org (галка 'Add to PATH')." }
$pyw = Join-Path (Split-Path $py) "pythonw.exe"   # без всплывающего окна

& $py -m pip install -q -r (Join-Path $dir "requirements.txt")

$trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday,Tuesday,Wednesday,Thursday,Friday,Saturday -At 06:00
$trigger.Repetition = (New-ScheduledTaskTrigger -Once -At 06:00 `
    -RepetitionInterval (New-TimeSpan -Minutes 15) -RepetitionDuration (New-TimeSpan -Hours 13)).Repetition
$action   = New-ScheduledTaskAction -Execute $pyw -Argument "`"$script`"" -WorkingDirectory $dir
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Minutes 5) -MultipleInstances IgnoreNew

Register-ScheduledTask -TaskName "NURE attendance" -Trigger $trigger -Action $action -Settings $settings -Force | Out-Null
Write-Host "Готово. Задача 'NURE attendance' создана. Лог: $dir\attendance.log"
Write-Host "Проверить сейчас:  Start-ScheduledTask 'NURE attendance'"
Write-Host "Удалить:           Unregister-ScheduledTask 'NURE attendance' -Confirm:`$false"
