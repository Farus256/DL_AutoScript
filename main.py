import os
import schedule
import time
from selenium import webdriver
from selenium.common import NoSuchElementException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from dotenv import load_dotenv
import requests

# Загружаем переменные окружения
load_dotenv()

USERNAME = os.getenv("UNIVERSITY_USERNAME")
PASSWORD = os.getenv("UNIVERSITY_PASSWORD")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# Настроим Selenium WebDriver
chrome_service = Service(r'E:\chromeDriver\chromedriver.exe')  # Укажите путь к ChromeDriver
chrome_options = Options()
driver = webdriver.Chrome(service=chrome_service, options=chrome_options)

# Список URL страниц посещений для шести курсов
attendance_urls = [
    "https://dl.nure.ua/mod/attendance/view.php?id=566211&view=5",  # МНАВ
    "https://dl.nure.ua/mod/attendance/view.php?id=579505&view=5",  # NoSql
    "https://dl.nure.ua/mod/attendance/view.php?id=566346&view=5",  # JavaScript
    "https://dl.nure.ua/mod/attendance/view.php?id=566231",         # ИАД
    "https://dl.nure.ua/mod/attendance/view.php?id=566186&view=5",  # СА
    "https://dl.nure.ua/mod/attendance/view.php?id=559051&view=5",  # логика
]


# Функция для входа на сайт университета
def login():
    driver.get("https://dl.nure.ua/login/index.php")  # Замените на URL сайта университета

    # Находим элементы ввода для логина и пароля
    username = driver.find_element(By.NAME, "username")
    password = driver.find_element(By.NAME, "password")

    username.send_keys(USERNAME)
    password.send_keys(PASSWORD)
    password.send_keys(Keys.RETURN)  # Отправляем форму


# Функция для отметки посещения на всех курсах
def mark_attendance():
    for url in attendance_urls:
        try:
            driver.get(url)  # Переходим на страницу посещения курса

            # Попробуем найти ссылку с текстом "Відправити відвідуваність"
            try:
                submit_link = driver.find_element(By.XPATH, "//a[contains(text(), 'Відправити відвідуваність')]")
                submit_link.click()  # Нажимаем на ссылку
                print(f"Посещение успішно відзначено для курсу: {url}")

                # Отправляем уведомление в Telegram
                send_telegram_message(f"Посещение успішно відзначено для курсу: {url}")

            except NoSuchElementException:
                print(f"Посещение вже відзначено для курсу: {url} або посилання не знайдено.")

        except Exception as e:
            send_telegram_message(f"Помилка при відзначенні відвідування для курсу {url}: {e}")
            print(f"Помилка при відзначенні відвідування для курсу {url}: {e}")


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
    login()# Логинимся один раз перед проверкой
    mark_attendance()

while True:
    schedule.run_pending()
    time.sleep(1)  # Добавляем задержку для уменьшения нагрузки на CPU
