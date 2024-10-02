import os
import schedule
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from dotenv import load_dotenv
import requests

# Загружаем переменные окружения
load_dotenv()

USERNAME = os.getenv("UNIVERSITY_USERNAME")
PASSWORD = os.getenv("UNIVERSITY_PASSWORD")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# Настроим Selenium WebDriver
driver = webdriver.Chrome(executable_path='/path/to/chromedriver')  # Укажите путь к ChromeDriver


# Функция для входа на сайт университета
def login():
    driver.get("https://your-university-site/login")  # Замените на URL сайта университета

    # Находим элементы ввода для логина и пароля
    username = driver.find_element(By.NAME, "username")
    password = driver.find_element(By.NAME, "password")

    username.send_keys(USERNAME)
    password.send_keys(PASSWORD)
    password.send_keys(Keys.RETURN)  # Отправляем форму


# Функция для отметки посещения
def mark_attendance():
    try:
        driver.get("https://your-university-site/attendance")  # URL страницы с посещениями
        attendance_button = driver.find_element(By.ID, "attendance_button_id")  # Укажите правильный ID
        attendance_button.click()
        send_telegram_message("Посещение успешно отмечено!")
        print("Посещение успешно отмечено!")
    except Exception as e:
        send_telegram_message(f"Ошибка при отметке посещения: {e}")
        print(f"Ошибка при отметке посещения: {e}")


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
    login()  # Логинимся один раз перед проверкой
    schedule.every().day.at("07:45").do(mark_attendance)
    schedule.every().day.at("09:30").do(mark_attendance)
    schedule.every().day.at("11:15").do(mark_attendance)
    schedule.every().day.at("13:10").do(mark_attendance)
    schedule.every().day.at("14:55").do(mark_attendance)
    schedule.every().day.at("16:40").do(mark_attendance)


# Запускаем процесс
schedule_check()

while True:
    schedule.run_pending()
    time.sleep(1)
