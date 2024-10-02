import os
import schedule
import time
from selenium import webdriver
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
chrome_service = Service(r'D:\chromeDriver\chromedriver.exe')  # Укажите путь к ChromeDriver
chrome_options = Options()
driver = webdriver.Chrome(service=chrome_service, options=chrome_options)

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

            # Получаем все строки таблицы с посещениями
            rows = driver.find_elements(By.CSS_SELECTOR, "tr")  # Или уточнить селектор для нужной таблицы

            for row in rows:
                # Проверяем, есть ли кнопка в последнем столбце (remarkscol)
                remarks_cell = row.find_element(By.CLASS_NAME, "remarkscol")
                if remarks_cell.text.strip() == "":  # Если ячейка пуста, значит, можно отметить
                    attendance_button = remarks_cell.find_elements(By.TAG_NAME, "button")  # Найдите кнопку, если она есть
                    if attendance_button:  # Проверяем, есть ли кнопка
                        attendance_button[0].click()  # Клик по первой кнопке, если она есть

                        # Извлекаем информацию о классе
                        date = row.find_element(By.CLASS_NAME, "datecol").text
                        description = row.find_element(By.CLASS_NAME, "desccol").text
                        status = row.find_element(By.CLASS_NAME, "statuscol").text
                        points = row.find_element(By.CLASS_NAME, "pointscol").text

                        # Отправляем информацию о занятии в Telegram
                        send_telegram_message(f"Посещение успешно отмечено для курса: {url}\n"
                                              f"Дата: {date}\n"
                                              f"Описание: {description}\n"
                                              f"Статус: {status}\n"
                                              f"Очки: {points}")
                        print(f"Посещение успешно отмечено для курса: {url}")
                else:
                    print(f"Посещение уже отмечено для курса: {url} на дату {row.find_element(By.CLASS_NAME, 'datecol').text}")

        except Exception as e:
            send_telegram_message(f"Ошибка при отметке посещения для курса {url}: {e}")
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
    login()  # Логинимся один раз перед проверкой
    schedule.every().day.at("07:45").do(mark_attendance)
    schedule.every().day.at("09:30").do(mark_attendance)
    schedule.every().day.at("11:15").do(mark_attendance)
    schedule.every().day.at("13:18").do(mark_attendance)
    schedule.every().day.at("14:55").do(mark_attendance)
    schedule.every().day.at("16:40").do(mark_attendance)

# Запускаем процесс
schedule_check()

while True:
    schedule.run_pending()
