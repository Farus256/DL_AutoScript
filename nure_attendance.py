#!/usr/bin/env python3
"""
Автоотметка посещаемости на dl.nure.ua (Moodle, mod_attendance).

За один запуск:
  1. логинится по логину/паролю;
  2. берёт все текущие курсы (как на /my/courses.php, фильтр "В процесі");
  3. в каждом курсе находит модули "Відвідування";
  4. для каждой открытой сессии жмёт "Відмітитися" (attendance.php?sessid=..),
     а если появляется форма со статусами — выбирает "Присутній" и отправляет;
  5. проверяет, что кнопка исчезла, и шлёт итог в Telegram (опционально).

Запуск:
  python nure_attendance.py            # отметиться везде, где сейчас открыто
  python nure_attendance.py --dry-run  # только показать, что нашлось, ничего не нажимать

Переменные окружения (или файл .env рядом):
  NURE_USERNAME, NURE_PASSWORD          — обязательно
  TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID  — опционально, для уведомлений
  ATTENDANCE_EXTRA_IDS                  — опционально, доп. id модулей через запятую
  ATTENDANCE_SKIP_IDS                   — опционально, id модулей, которые не трогать
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse, parse_qs

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

BASE = "https://dl.nure.ua"
TIMEOUT = 30
PRESENT_RE = re.compile(r"присутн|present", re.I)
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/129.0 Safari/537.36")


def load_dotenv(path: str = ".env") -> None:
    """Мини-загрузчик .env, чтобы не тянуть python-dotenv."""
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)), path)
    if not os.path.exists(p):
        return
    with open(p, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def ids_from_env(name: str) -> list[str]:
    return [x.strip() for x in os.getenv(name, "").split(",") if x.strip()]


# --------------------------------------------------------------------------- #
# Чистые функции парсинга (их удобно тестировать на сохранённом HTML)
# --------------------------------------------------------------------------- #

def parse_logintoken(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    inp = soup.select_one('form#login input[name="logintoken"], input[name="logintoken"]')
    return inp["value"] if inp else ""


def parse_sesskey(html: str) -> str | None:
    m = re.search(r'"sesskey":"(\w+)"', html)
    return m.group(1) if m else None


def parse_login_error(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    el = soup.select_one("#loginerrormessage, .loginerrors, .alert-danger")
    return el.get_text(" ", strip=True) if el else "неизвестная ошибка входа"


def parse_attendance_cmids(html: str) -> list[str]:
    """Из /mod/attendance/index.php?id=<course> достаём id модулей."""
    return list(dict.fromkeys(re.findall(r"mod/attendance/view\.php\?id=(\d+)", html)))


@dataclass
class OpenSession:
    sessid: str
    url: str            # attendance.php?sessid=..&sesskey=..
    when: str = ""      # дата/время из таблицы
    descr: str = ""
    needs_qr: bool = False


def parse_open_sessions(html: str, page_url: str) -> list[OpenSession]:
    """
    Открытая сессия рендерится плагином как
      <a class="btn btn-primary" href=".../attendance.php?sessid=N&sesskey=..">Відмітитися</a>
    Ссылка "Повідомити про майбутню відсутність" ведёт туда же, но без btn-primary —
    её специально не трогаем. Сессии с ротацией QR-кода рендерятся как форма с qrpass.
    """
    soup = BeautifulSoup(html, "html.parser")
    found: dict[str, OpenSession] = {}

    for a in soup.select('a.btn-primary[href*="/mod/attendance/attendance.php"]'):
        href = urljoin(page_url, a["href"])
        sessid = parse_qs(urlparse(href).query).get("sessid", [""])[0]
        if not sessid:
            continue
        cells = [td.get_text(" ", strip=True) for td in a.find_parent("tr").find_all("td")] \
            if a.find_parent("tr") else []
        found[sessid] = OpenSession(sessid, href,
                                    when=cells[0] if cells else "",
                                    descr=cells[1] if len(cells) > 1 else "")

    for form in soup.select('form[action*="/mod/attendance/attendance.php"]'):
        if form.select_one('input[name="qrpass"]'):
            sid = form.select_one('input[name="sessid"]')
            if sid and sid.get("value") not in found:
                tr = form.find_parent("tr")
                cells = [td.get_text(" ", strip=True) for td in tr.find_all("td")] if tr else []
                found[sid["value"]] = OpenSession(sid["value"], "", needs_qr=True,
                                                  when=cells[0] if cells else "",
                                                  descr=cells[1] if len(cells) > 1 else "")

    return list(found.values())


@dataclass
class MarkForm:
    action: str
    data: dict = field(default_factory=dict)
    status_label: str = ""
    needs_password: bool = False


def parse_mark_form(html: str, page_url: str) -> MarkForm | None:
    """Форма mod_attendance\\form\\studentattendance: радиокнопки name=status."""
    soup = BeautifulSoup(html, "html.parser")
    radios = soup.select('input[type="radio"][name="status"]')
    if not radios:
        return None
    form = radios[0].find_parent("form")
    action = urljoin(page_url, form.get("action") or page_url)

    data = {}
    for inp in form.select("input[type=hidden]"):
        if inp.get("name"):
            data[inp["name"]] = inp.get("value", "")

    def label_of(r):
        lab = soup.select_one(f'label[for="{r.get("id")}"]') if r.get("id") else None
        lab = lab or r.find_parent("label")
        return lab.get_text(" ", strip=True) if lab else ""

    choices = [(r.get("value"), label_of(r)) for r in radios if not r.has_attr("disabled")]
    if not choices:
        return None
    value, label = next(((v, l) for v, l in choices if PRESENT_RE.search(l)), choices[0])
    data["status"] = value

    btn = form.select_one('input[type=submit][name="submitbutton"], button[name="submitbutton"]')
    data["submitbutton"] = btn.get("value", "Зберегти") if btn else "Зберегти"

    return MarkForm(action, data, label,
                    needs_password=bool(form.select_one('input[name="studentpassword"]')))


def parse_moodle_error(html: str) -> str | None:
    soup = BeautifulSoup(html, "html.parser")
    el = soup.select_one('[data-rel="fatalerror"], .errorbox .errormessage, .errorbox, .alert-danger')
    return el.get_text(" ", strip=True)[:300] if el else None


# --------------------------------------------------------------------------- #
# Клиент
# --------------------------------------------------------------------------- #

class Nure:
    def __init__(self, username: str, password: str):
        self.username, self.password = username, password
        self.s = requests.Session()
        self.s.headers["User-Agent"] = UA
        retry = Retry(total=3, backoff_factor=2, status_forcelist=(500, 502, 503, 504),
                      allowed_methods=frozenset({"GET"}))
        self.s.mount("https://", HTTPAdapter(max_retries=retry))
        self.sesskey: str | None = None

    def get(self, path: str, **kw) -> requests.Response:
        r = self.s.get(urljoin(BASE, path), timeout=TIMEOUT, **kw)
        if r.status_code == 405 and "Human Verification" in r.text:
            raise RuntimeError("AWS WAF показал капчу (IP дата-центра) — запускай с домашнего ПК")
        r.raise_for_status()
        return r

    def login(self) -> None:
        r = self.get("/login/index.php")
        token = parse_logintoken(r.text)
        r = self.s.post(urljoin(BASE, "/login/index.php"), timeout=TIMEOUT, data={
            "anchor": "", "logintoken": token,
            "username": self.username, "password": self.password,
        })
        r.raise_for_status()
        if "/login/index.php" in r.url and "login/logout.php" not in r.text:
            raise RuntimeError(f"Вход не удался: {parse_login_error(r.text)}")
        self.sesskey = parse_sesskey(r.text) or parse_sesskey(self.get("/my/").text)
        if not self.sesskey:
            raise RuntimeError("Вход прошёл, но sesskey не найден")

    def ajax(self, method: str, args: dict):
        r = self.s.post(urljoin(BASE, f"/lib/ajax/service.php?sesskey={self.sesskey}&info={method}"),
                        timeout=TIMEOUT, data=json.dumps([{"index": 0, "methodname": method, "args": args}]),
                        headers={"Content-Type": "application/json"})
        r.raise_for_status()
        res = r.json()[0]
        if res.get("error"):
            raise RuntimeError(f"{method}: {res.get('exception', {}).get('message', res)}")
        return res["data"]

    def current_courses(self) -> list[dict]:
        data = self.ajax("core_course_get_enrolled_courses_by_timeline_classification",
                         {"offset": 0, "limit": 0, "classification": "inprogress", "sort": "fullname"})
        return [{"id": c["id"], "name": c["fullname"]} for c in data["courses"]]

    def attendance_cmids(self, course_id: int) -> list[str]:
        return parse_attendance_cmids(self.get(f"/mod/attendance/index.php?id={course_id}").text)

    def open_sessions(self, cmid: str) -> list[OpenSession]:
        r = self.get(f"/mod/attendance/view.php?id={cmid}&view=5")
        return parse_open_sessions(r.text, r.url)

    def mark(self, cmid: str, sess: OpenSession) -> tuple[bool | None, str]:
        """True — отмечено, False — ошибка, None — нужна ручная отметка (QR/пароль)."""
        if sess.needs_qr:
            return None, "нужен QR-код — отметься вручную"

        r = self.get(sess.url)
        err = parse_moodle_error(r.text)
        if err and "attendance.php" in r.url and not parse_mark_form(r.text, r.url):
            return False, f"ошибка Moodle: {err}"

        info = "авто-статус"
        form = parse_mark_form(r.text, r.url) if "attendance.php" in r.url else None
        if form:
            if form.needs_password:
                return None, "сессия требует пароль от преподавателя — отметься вручную"
            r = self.s.post(form.action, data=form.data, timeout=TIMEOUT)
            r.raise_for_status()
            info = f"статус «{form.status_label}»"
            if "attendance.php" in r.url:
                return False, f"форма не принята: {parse_moodle_error(r.text) or 'без сообщения'}"

        # Проверка: кнопки для этой сессии больше нет
        still_open = any(s.sessid == sess.sessid for s in self.open_sessions(cmid))
        return (not still_open), info if not still_open else "кнопка всё ещё на месте — проверь вручную"


def kyiv_now() -> str:
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("Europe/Kyiv")).strftime("%H:%M")
    except Exception:  # на Windows без пакета tzdata
        return datetime.now(timezone.utc).strftime("%H:%M UTC")


def telegram(text: str, silent: bool = False) -> None:
    """silent=True — сообщение придёт без звука (disable_notification)."""
    token, chat = os.getenv("TELEGRAM_BOT_TOKEN"), os.getenv("TELEGRAM_CHAT_ID")
    if not (token and chat):
        return
    try:
        requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                      data={"chat_id": chat, "text": text, "disable_web_page_preview": "true",
                            "disable_notification": "true" if silent else "false"},
                      timeout=15)
    except requests.RequestException as e:
        print(f"[telegram] {e}", file=sys.stderr)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="ничего не нажимать, только показать")
    args = ap.parse_args()
    if sys.stdout is None:  # запуск через pythonw (Планировщик) — пишем лог в файл
        log = os.path.join(os.path.dirname(os.path.abspath(__file__)), "attendance.log")
        if os.path.exists(log) and os.path.getsize(log) > 1_000_000:
            os.replace(log, log + ".old")
        sys.stdout = sys.stderr = open(log, "a", encoding="utf-8", buffering=1)
        print(f"\n=== {datetime.now():%Y-%m-%d %H:%M:%S} ===")
    load_dotenv()

    user, pwd = os.getenv("NURE_USERNAME"), os.getenv("NURE_PASSWORD")
    if not (user and pwd):
        print("Задай NURE_USERNAME и NURE_PASSWORD (env или .env)", file=sys.stderr)
        return 2

    nure = Nure(user, pwd)
    try:
        nure.login()
    except Exception as e:
        print(f"[login] {e}", file=sys.stderr)
        telegram(f"⚠️ NURE: не удалось войти — {e}")
        return 1

    skip = set(ids_from_env("ATTENDANCE_SKIP_IDS"))
    targets: dict[str, str] = {cm: "доп. модуль" for cm in ids_from_env("ATTENDANCE_EXTRA_IDS")}
    for c in nure.current_courses():
        try:
            cms = nure.attendance_cmids(c["id"])
        except Exception as e:
            print(f"[course {c['id']}] {e}", file=sys.stderr)
            continue
        print(f"Курс {c['id']}: {c['name']} — модули посещаемости: {cms or 'нет'}")
        for cm in cms:
            targets.setdefault(cm, c["name"])

    marked, manual, problems, dry, found = [], [], [], [], 0
    for cm, course in targets.items():
        if cm in skip:
            continue
        try:
            sessions = nure.open_sessions(cm)
        except Exception as e:
            problems.append(f"{course}: не открылась страница ({e})")
            continue
        found += len(sessions)
        for s in sessions:
            label = f"{course} — {s.when} {s.descr}".strip()
            if args.dry_run:
                line = f"{label}{' (QR)' if s.needs_qr else ''}"
                dry.append(line)
                print(f"[dry-run] открыта сессия {s.sessid}: {line}")
                continue
            try:
                ok, info = nure.mark(cm, s)
            except Exception as e:
                ok, info = False, f"исключение: {e}"
            bucket, icon = {True: (marked, "✅"), None: (manual, "✋"), False: (problems, "❌")}[ok]
            bucket.append(f"{label}: {info}")
            print(f"{icon} {label}: {info}")

    checked = f"проверено модулей: {len(targets) - len(skip & targets.keys())}"
    if not found:
        print("Открытых сессий нет.")
        telegram(f"🔍 {kyiv_now()} — проверка прошла, открытых сессий нет ({checked})", silent=True)
    elif dry:
        telegram(f"🧪 {kyiv_now()} — dry-run, открыты:\n" + "\n".join(dry), silent=True)
    msg = "\n".join(
        ([f"✅ Отмечено ({len(marked)}):"] + marked if marked else []) +
        ([f"✋ Нужно вручную ({len(manual)}):"] + manual if manual else []) +
        ([f"❌ Ошибки ({len(problems)}):"] + problems if problems else []))
    if msg:
        telegram("NURE attendance\n" + msg)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
