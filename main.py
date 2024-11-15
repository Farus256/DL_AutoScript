from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
import os
import schedule
import time
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from dotenv import load_dotenv
import requests
from flask import Flask
import threading
from flask import Flask, request
import datetime

# Загружаем переменные окружения
load_dotenv()

USERNAME = os.getenv("UNIVERSITY_USERNAME")
PASSWORD = os.getenv("UNIVERSITY_PASSWORD")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# Проверка переменных окружения
if USERNAME is None or PASSWORD is None:
    raise ValueError(
        "Переменные окружения UNIVERSITY_USERNAME и UNIVERSITY_PASSWORD не загружены."
    )
if TELEGRAM_BOT_TOKEN is None or TELEGRAM_CHAT_ID is None:
    raise ValueError(
        "Переменные окружения TELEGRAM_BOT_TOKEN и TELEGRAM_CHAT_ID не загружены."
    )

# Настройка Firefox WebDriver
options = Options()
options.add_argument("--headless")
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")

driver = webdriver.Firefox(options=options)

# Список URL страниц посещений для шести курсов
attendance_urls = [
    "https://dl.nure.ua/mod/attendance/view.php?id=566211&view=5",  # МНАВ
    "https://dl.nure.ua/mod/attendance/view.php?id=579505&view=5",  # NoSql
    "https://dl.nure.ua/mod/attendance/view.php?id=566346&view=5",  # JavaScript
    "https://dl.nure.ua/mod/attendance/view.php?id=566231",  # ИАД
    "https://dl.nure.ua/mod/attendance/view.php?id=566186&view=5",  # СА
    "https://dl.nure.ua/mod/attendance/view.php?id=559051&view=5",  # логика
]

# Функция для входа на сайт университета
def login():
    try:
        driver.get("https://dl.nure.ua/login/index.php")

        # Вводим логин и пароль
        username = driver.find_element(By.NAME, "username")
        password = driver.find_element(By.NAME, "password")
        username.send_keys(USERNAME)
        password.send_keys(PASSWORD)
        password.send_keys(Keys.RETURN)

        # Задержка после логина, чтобы страница успела загрузиться
        time.sleep(5)
    except Exception as e:
        send_telegram_message(f"Ошибка при входе: {e}")
        print(f"Ошибка при входе: {e}")

# Функция для отметки посещения на всех курсах
def mark_attendance():
    for url in attendance_urls:
        try:
            driver.get(url)

            # Сохраняем скриншот для отладки перед поиском элемента
            screenshot_filename = f"debug_screenshot_{url.split('=')[-1]}.png"
            driver.save_screenshot(screenshot_filename)
            print(f"Скриншот сохранен как {screenshot_filename} для {url}")

            # Увеличенное ожидание, пока ссылка станет кликабельной
            try:
                submit_link = WebDriverWait(driver, 20).until(
                    EC.element_to_be_clickable((
                        By.XPATH,
                        "//a[contains(text(), 'Відправити відвідуваність')]")))
                driver.execute_script("arguments[0].scrollIntoView();",
                                      submit_link)  # Скроллим к элементу

                # Используем JavaScript для клика
                driver.execute_script("arguments[0].click();", submit_link)
                print(f"Посещение успешно отмечено для курса: {url}")
                send_telegram_message(
                    f"Посещение успешно отмечено для курса: {url}")
            except (TimeoutException, NoSuchElementException):
                print(
                    f"Посещение уже отмечено для курса: {url} или ссылка не найдена."
                )
        except Exception as e:
            send_telegram_message(
                f"Ошибка при отметке посещения для курса {url}: {e}")
            print(f"Ошибка при отметке посещения для курса {url}: {e}")

# Функция для отправки сообщений в Telegram
def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = {"chat_id": TELEGRAM_CHAT_ID, "text": message}
    try:
        response = requests.post(url, data=data)
        if response.status_code == 200:
            print("Сообщение отправлено в Telegram")
        else:
            print(f"Ошибка отправки сообщения: {response.status_code}")
    except Exception as e:
        print(f"Ошибка при отправке сообщения: {e}")

# Планируем автоматическую отметку по времени
def schedule_check():
    try:
        login()
        mark_attendance()
    except Exception as e:
        send_telegram_message(f"Ошибка при выполнении расписания: {e}")
        print(f"Ошибка при выполнении расписания: {e}")

# Настройка расписания для запуска функции schedule_check()
schedule.every().day.at("08:00").do(schedule_check)
schedule.every().day.at("10:00").do(schedule_check)
schedule.every().day.at("12:00").do(schedule_check)
schedule.every().day.at("15:30").do(schedule_check)
schedule.every().day.at("17:30").do(schedule_check)

app = Flask('')

@app.route('/')
def home():
    print(f"[{datetime.datetime.now()}] Получен запрос от: {request.remote_addr}")
    return "Bot is running!"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = threading.Thread(target=run)
    t.start()

if __name__ == "__main__":
    keep_alive()
    # Выполнение входа и отметки посещения сразу при запуске
    schedule_check()
    while True:
        schedule.run_pending()
        time.sleep(5)
