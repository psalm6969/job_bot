import html
import json
import os
import re
import threading
import time
import tkinter as tk
from tkinter import messagebox
from tkinter.scrolledtext import ScrolledText
import urllib.parse
import xml.etree.ElementTree as ET
import requests

# ================= ФАЙЛЫ И НАСТРОЙКИ =================
CONFIG_FILE = "bot_config.json"
SEEN_FILE = "seen_vacancies.txt"
CHANNELS_FILE = "channels.txt"

# Сбрасываем старый конфиг, если там остался старый мусор
if os.path.exists(CONFIG_FILE):
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            c = json.load(f)
            if "proxy" in c:
                os.remove(CONFIG_FILE)
    except Exception:
        pass

# Настоящий браузерный заголовок (hh.ru никогда не забанит)
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8",
}

DEFAULT_TG_CHANNELS = [
    "futuretoday",
    "changellenge_global",
    "normrabota",
    "sberseasons",
    "t_start",
    "yandex_intern",
    "vtb_career",
    "alfacareer",
    "internships_ru",
    "data_jobs",
    "juniors_rabota_jobs",
    "theypaygood",
    "analitiki_rabota",
    "yuniorapp",
    "young_june",
    "juno_jobs",
    "offersanalysis",
    "datajob",
    "data_vacancy",
    "runello_rus_datascience",
    "junior_vacancies",
]

# ================= ФИЛЬТРЫ И СПИСКИ СЛОВ =================

# ЦЕЛЕВЫЕ РОЛИ: Аналитика данных, BI, SQL
DATA_ROLES_WHITELIST = [
    "аналитик данных",
    "data analyst",
    "bi аналитик",
    "bi-аналитик",
    "bi разработчик",
    "bi engineer",
    "sql разработчик",
    "разработчик sql",
    "разработчик баз данных",
    "разработчик субд",
    "инженер данных",
    "data engineer",
    "analytics engineer",
    "инженер аналитик",
    "инженер-аналитик",
    "dwh",
    "etl",
    "junior аналитик",
    "стажер аналитик",
    "стажёр аналитик",
    "младший аналитик",
]

# НАГЛУХО ЗАПРЕЩЕННЫЕ РОЛИ
BANNED_ROLES = [
    "системный аналитик",
    "системного аналитика",
    "системный анализ",
    "бизнес-аналитик",
    "продуктовый аналитик",
    "аналитик требований",
    "system analyst",
]

# СТОП-СЛОВА ПО ГРЕЙДАМ
SENIOR_STOP_WORDS = [
    "senior",
    "сеньор",
    "синьор",
    "lead",
    "лид",
    "руководитель",
    "ведущий",
    "главный",
    "middle",
    "мидл",
    "миддл",
    "тимлид",
    "teamlead",
    "principal",
    "архитектор",
    "head",
]

# СТОП-СЛОВА ПО ЗАРУБЕЖНЫМ ЛОКАЦИЯМ И РЕЛОКАЦИИ
FOREIGN_LOCATIONS_STOP = [
    "europe",
    "европ",
    "portugal",
    "португали",
    "armenia",
    "армени",
    "georgia",
    "грузи",
    "cyprus",
    "кипр",
    "poland",
    "польш",
    "germany",
    "германи",
    "turkey",
    "турци",
    "spain",
    "испани",
    "uk",
    "usa",
    "сша",
    "relocation",
    "релокаци",
    "релокация",
    "релокацией",
    "внж",
    "work permit",
    "must reside in",
    "singapore",
    "сингапур",
]

# ПОДРАБОТКА: БЕЛЫЙ СПИСОК (Excel, данные, ИИ)
PART_TIME_WHITELIST = [
    "excel",
    "эксель",
    "таблиц",
    "sheets",
    "ввод данн",
    "оператор пк",
    "оператор баз",
    "обработка информации",
    "ввод информации",
    "набор текст",
    "нейросет",
    "ии",
    "ai",
    "gpt",
    "разметк",
    "датасет",
    "разметчик",
    "асессор",
    "толока",
    "модератор",
    "модерация",
    "транскрибац",
    "расшифровк",
]

# ПОДРАБОТКА: ЧЕРНЫЙ СПИСОК МУСОРА
PART_TIME_BANNED = [
    "врач",
    "медицин",
    "гастроэнтеролог",
    "репетитор",
    "преподаватель",
    "учитель",
    "модель",
    "дизайнер",
    "1с",
    "туризм",
    "банкротств",
    "амбассадор",
    "эссе",
    "автор",
    "наставник",
    "юрист",
    "бухгалтер",
    "агент",
    "недвижимост",
    "риелтор",
    "психолог",
    "клиент",
    "звонк",
    "звон",
    "колл",
    "call",
    "продаж",
    "чат",
    "поддержк",
    "саппорт",
    "привлечен",
    "партнер",
    "экономист",
    "финансист",
    "полная занятость",
    "полный день",
    "5/2",
    "8 часов",
    "fullday",
    "курьер",
    "водитель",
    "маркетолог",
    "телемаркет",
    "обзвон",
]

ENTRY_KEYWORDS = [
    "стажер",
    "стажировк",
    "junior",
    "джун",
    "младший",
    "без опыта",
    "начинающий",
    "intern",
    "trainee",
    "практик",
]

is_running = False


# ================= ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ =================


def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "bot_token": "",
        "chat_id": "",
        "api_url": "https://api.telegram.org",
    }


def save_config(token, chat_id, api_url):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(
                {"bot_token": token, "chat_id": chat_id, "api_url": api_url},
                f,
                ensure_ascii=False,
                indent=2,
            )
    except Exception:
        pass


def load_seen_ids():
    if not os.path.exists(SEEN_FILE):
        return set()
    with open(SEEN_FILE, "r", encoding="utf-8") as f:
        return set(line.strip() for line in f if line.strip())


def save_seen_id(item_id):
    with open(SEEN_FILE, "a", encoding="utf-8") as f:
        f.write(f"{item_id}\n")


def get_channels():
    if not os.path.exists(CHANNELS_FILE):
        return DEFAULT_TG_CHANNELS
    ch_list = []
    with open(CHANNELS_FILE, "r", encoding="utf-8") as f:
        for line in f:
            c = line.strip().replace("@", "").replace("https://t.me/", "")
            if c and not c.startswith("#"):
                ch_list.append(c)
    return ch_list or DEFAULT_TG_CHANNELS


def clean_text_block(text, max_len=350):
    if not text:
        return ""
    clean = re.sub(r"<br\s*/?>", "\n", text)
    clean = re.sub(r"</?(li|p|div|h\d)>", "\n", clean)
    clean = re.sub(r"<.*?>", "", clean)
    clean = html.unescape(clean)
    lines = [l.strip() for l in clean.split("\n") if l.strip()]
    res = "\n".join(lines[:6])
    if len(res) > max_len:
        res = res[:max_len] + "..."
    return html.escape(res)


def is_valid_geo(location_text: str, full_text: str):
    comb = f"{location_text} {full_text}".lower()

    for fl in FOREIGN_LOCATIONS_STOP:
        if fl in comb:
            return False, f"Зарубежная локация ({fl})"

    is_spb = any(
        c in comb
        for c in [
            "санкт-петербург",
            "петербург",
            "спб",
            "питер",
            "st. petersburg",
        ]
    )
    is_remote = any(
        r in comb for r in ["удален", "дистанцион", "remote", "anywhere"]
    )

    if is_spb:
        return True, "Санкт-Петербург"
    if is_remote:
        return True, "Удаленно"

    return False, "Не СПб и не удаленка"


def check_experience_rejection(full_text):
    t = full_text.lower()
    reject_patterns = [
        r"от\s*([2-9]|\d{2})\s*(?:-?х|-?ти|-?го)?\s*(?:лет|года)",
        r"опыт\s*(?:работы)?\s*(?:от|не менее)\s*([2-9]|\d{2})\s*(?:лет|года)",
        r"(?:at least|minimum)\s*([2-9]|\d{2})\s*(?:\+)?\s*years?",
        r"([2-9]|\d{2})\s*\+\s*years?",
        r"([2-9]|\d{2})\s*[-–—]\s*\d+\s*years?",
        r"(?:2|3|4|5)\+?\s*years?\s*of\s*experience",
        r"middle",
        r"senior",
        r"lead",
    ]
    for p in reject_patterns:
        m = re.search(p, t)
        if m:
            start_pos = m.start()
            prefix = t[max(0, start_pos - 6) : start_pos]
            if "0" in prefix or "без" in prefix:
                continue
            return True, m.group(0)
    return False, None


def parse_duties_and_requirements(raw_html):
    text = re.sub(r"<br\s*/?>", "\n", raw_html)
    text = re.sub(r"</?(li|p|div|h\d)>", "\n", text)
    text = re.sub(r"<.*?>", "", text)
    text = html.unescape(text)
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    full_text = "\n".join(lines)

    resp, req = "", ""
    resp_match = re.search(
        r"(?:обязанности|задачи|предстоит делать|чем предстоит заниматься|what you will do)[\s:]*(.+?)(?=(?:требования|мы ждем|ожидания|наш стек|условия|requirements|$))",
        full_text,
        re.IGNORECASE | re.DOTALL,
    )
    if resp_match:
        resp = clean_text_block(resp_match.group(1))

    req_match = re.search(
        r"(?:требования|мы ждем|ожидания|требуемый опыт|skills|requirements)[\s:]*(.+?)(?=(?:условия|предлагаем|мы предлагаем|плюсом будет|benefits|контакты|$))",
        full_text,
        re.IGNORECASE | re.DOTALL,
    )
    if req_match:
        req = clean_text_block(req_match.group(1))

    if not resp:
        resp = clean_text_block(full_text[:300])
    if not req:
        req = "Подробности смотрите в описании вакансии"

    return resp, req


def get_hh_vacancy_details(vac_id):
    url = f"https://hh.ru/vacancy/{vac_id}"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=8)
        if resp.status_code == 200:
            match = re.search(
                r'<template[^>]*id="HH-Lux-InitialState"[^>]*>(.*?)</template>',
                resp.text,
                re.DOTALL,
            )
            if match:
                data = json.loads(html.unescape(match.group(1)))
                v_view = data.get("vacancyView") or {}
                desc_html = v_view.get("description") or ""
                skills = [
                    s.get("name")
                    for s in v_view.get("keySkills", [])
                    if isinstance(s, dict) and s.get("name")
                ]
                duties, requirements = parse_duties_and_requirements(desc_html)
                if skills:
                    requirements += f"\n<b>Ключевые навыки:</b> {', '.join(skills[:8])}"
                return duties, requirements
    except Exception:
        pass
    return "Смотрите в описании", "Смотрите в описании"


def send_telegram(token, chat_id, text, log_fn, api_url):
    base = api_url.rstrip("/")
    if not base.startswith("http://") and not base.startswith("https://"):
        base = "https://" + base
    url = f"{base}/bot{token}/sendMessage"

    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }

    endpoints = [
        url,
        f"https://tgproxy.yemzikk.in/bot{token}/sendMessage",
        f"https://api.telegram.org/bot{token}/sendMessage",
    ]
    for ep in endpoints:
        try:
            res = requests.post(ep, json=payload, timeout=12)
            if res.status_code == 200:
                return True
        except Exception:
            continue

    log_fn("[Telegram Ошибка] Не удалось доставить сообщение в чат.")
    return False


# ================= ПАРСЕР HEADHUNTER (ВЕБ-ДВИЖОК) =================


def get_hh_vacancies_web(search_url):
    try:
        resp = requests.get(search_url, headers=HEADERS, timeout=15)
        if resp.status_code != 200:
            return []
        match = re.search(
            r'<template[^>]*id="HH-Lux-InitialState"[^>]*>(.*?)</template>',
            resp.text,
            re.DOTALL,
        )
        if not match:
            return []
        raw_json = html.unescape(match.group(1))
        data = json.loads(raw_json)
        return data.get("vacancySearchResult", {}).get("vacancies", [])
    except Exception:
        return []


def check_hh(seen_ids, token, chat_id, api_url, log_fn):
    query = urllib.parse.quote(
        '"аналитик данных" OR "data analyst" OR "BI аналитик" OR "SQL разработчик" OR "инженер данных"'
    )
    main_urls = [
        f"https://hh.ru/search/vacancy?text={query}&search_field=name&area=2&experience=noExperience&experience=between1And3&search_period=1&order_by=publication_time",
        f"https://hh.ru/search/vacancy?text={query}&search_field=name&schedule=remote&experience=noExperience&experience=between1And3&search_period=1&order_by=publication_time",
    ]

    hh_main_found = 0
    for url in main_urls:
        if not is_running:
            return
        items = get_hh_vacancies_web(url)
        for vac in reversed(items):
            raw_id = vac.get("vacancyId") or vac.get("id")
            vac_id = f"hh_{raw_id}"
            if vac_id in seen_ids:
                continue

            title = vac.get("name", "")
            title_lower = title.lower()

            if any(b in title_lower for b in BANNED_ROLES):
                continue
            if any(w in title_lower for w in SENIOR_STOP_WORDS):
                continue
            if not any(role in title_lower for role in DATA_ROLES_WHITELIST):
                continue

            area_name = vac.get("area", {}).get("name", "")
            work_sched = (
                vac.get("workSchedule", {}).get("name", "")
                or vac.get("schedule", {}).get("name", "")
            )
            geo_ok, geo_label = is_valid_geo(area_name, work_sched)
            if not geo_ok:
                continue

            seen_ids.add(vac_id)
            save_seen_id(vac_id)
            hh_main_found += 1

            employer = (
                vac.get("company", {}).get("name")
                or vac.get("employer", {}).get("name")
                or "Не указан"
            )
            compensation = vac.get("compensation", {}).get(
                "formatted", "Не указана"
            )
            resp_txt, req_txt = get_hh_vacancy_details(raw_id)

            badge = "📊 <b>[HH.RU] Аналитик данных / BI / SQL</b>"
            is_intern = (
                ("стаж" in title_lower)
                or ("intern" in title_lower)
                or ("junior" in title_lower)
            )
            if is_intern:
                badge = (
                    "🎓 <b>[HH.RU СТАЖИРОВКА / JUNIOR] Аналитика / SQL / BI</b>"
                )

            log_fn(f"[HH.RU] {title} ({employer})")
            msg = (
                f"{badge}\n\n"
                f"<b>Должность:</b> {html.escape(title)}\n"
                f"<b>Компания:</b> {html.escape(employer)}\n"
                f"<b>Локация:</b> {geo_label}\n"
                f"<b>Зарплата:</b> {compensation}\n\n"
                f"📌 <b>Обязанности:</b>\n{resp_txt}\n\n"
                f"🎯 <b>Требования:</b>\n{req_txt}\n\n"
                f"🔗 <a href='https://hh.ru/vacancy/{raw_id}'>Открыть на hh.ru</a>"
            )
            send_telegram(token, chat_id, msg, log_fn, api_url)
            time.sleep(1.5)

    pt_query = urllib.parse.quote(
        'Excel OR "ввод данных" OR "разметка данных" OR "оператор ПК" OR таблицы OR нейросети OR ИИ OR модератор OR асессор'
    )
    pt_urls = [
        f"https://hh.ru/search/vacancy?text={pt_query}&schedule=remote&experience=noExperience&employment=part&search_period=1&order_by=publication_time",
        f"https://hh.ru/search/vacancy?text={pt_query}&schedule=remote&experience=noExperience&employment=project&search_period=1&order_by=publication_time",
    ]

    hh_pt_found = 0
    for url in pt_urls:
        if not is_running:
            return
        items = get_hh_vacancies_web(url)
        for vac in reversed(items):
            raw_id = vac.get("vacancyId") or vac.get("id")
            vac_id = f"hh_{raw_id}"
            if vac_id in seen_ids:
                continue

            title = vac.get("name", "")
            title_lower = title.lower()

            if any(bad in title_lower for bad in PART_TIME_BANNED):
                continue
            if not any(good in title_lower for good in PART_TIME_WHITELIST):
                continue

            emp_info = str(vac.get("employment", {})).lower()
            sched_info = (
                str(vac.get("schedule", {})).lower()
                + " "
                + str(vac.get("workSchedule", {})).lower()
            )
            if (
                "полная занятость" in emp_info
                or "full" in emp_info
                or "fullday" in sched_info
                or "полный день" in sched_info
            ):
                continue

            seen_ids.add(vac_id)
            save_seen_id(vac_id)
            hh_pt_found += 1

            employer = (
                vac.get("company", {}).get("name")
                or vac.get("employer", {}).get("name")
                or "Не указан"
            )
            compensation = vac.get("compensation", {}).get(
                "formatted", "По договоренности"
            )
            resp_txt, req_txt = get_hh_vacancy_details(raw_id)

            log_fn(f"[HH.RU Подработка] {title} ({employer})")
            msg = (
                f"☕ <b>[HH.RU: ПОДРАБОТКА] Данные / Таблицы / ИИ</b>\n\n"
                f"<b>Должность:</b> {html.escape(title)}\n"
                f"<b>Компания:</b> {html.escape(employer)}\n"
                f"<b>Оплата:</b> {compensation}\n"
                f"<b>Формат:</b> Удаленно (Частичная занятость)\n\n"
                f"📌 <b>Обязанности:</b>\n{resp_txt}\n\n"
                f"🎯 <b>Требования:</b>\n{req_txt}\n\n"
                f"🔗 <a href='https://hh.ru/vacancy/{raw_id}'>Открыть на hh.ru</a>"
            )
            send_telegram(token, chat_id, msg, log_fn, api_url)
            time.sleep(1.5)

    log_fn(f"[hh.ru] Проверено (новых: {hh_main_found + hh_pt_found})")


# ================= ПАРСЕР ХАБР КАРЬЕРА =================


def check_habr(seen_ids, token, chat_id, api_url, log_fn):
    if not is_running:
        return
    queries = ["Data+Analyst", "SQL", "BI"]
    found = 0
    for q in queries:
        rss_url = f"https://career.habr.com/vacancies/rss?q={q}"
        try:
            resp = requests.get(rss_url, headers=HEADERS, timeout=8)
            if resp.status_code != 200:
                continue
            root = ET.fromstring(resp.content)
            for item in reversed(root.findall(".//item")):
                link = item.findtext("link", "")
                vac_id = f"habr_{link.split('/')[-1]}"
                if vac_id in seen_ids:
                    continue

                title = item.findtext("title", "")
                title_lower = title.lower()

                if any(b in title_lower for b in BANNED_ROLES):
                    continue
                if any(w in title_lower for w in SENIOR_STOP_WORDS):
                    continue
                if not any(
                    role in title_lower for role in DATA_ROLES_WHITELIST
                ):
                    continue

                desc_raw = item.findtext("description", "")
                full_text = f"{title_lower} {desc_raw.lower()}"

                has_exp, _ = check_experience_rejection(full_text)
                if has_exp:
                    continue

                loc_ok, loc_reason = is_valid_geo(title, desc_raw)
                if not loc_ok:
                    continue

                seen_ids.add(vac_id)
                save_seen_id(vac_id)
                found += 1

                resp_txt, req_txt = parse_duties_and_requirements(desc_raw)
                log_fn(f"[Хабр Карьера] {title}")

                msg = (
                    f"🚀 <b>[ХАБР КАРЬЕРА] {html.escape(title)}</b>\n\n"
                    f"<b>Формат:</b> {loc_reason}\n\n"
                    f"📌 <b>Обязанности:</b>\n{resp_txt}\n\n"
                    f"🎯 <b>Требования:</b>\n{req_txt}\n\n"
                    f"🔗 <a href='{link}'>Открыть на Хабр Карьере</a>"
                )
                send_telegram(token, chat_id, msg, log_fn, api_url)
                time.sleep(1.5)
        except Exception:
            pass
    log_fn(f"[Хабр Карьера] Проверено (новых: {found})")


# ================= ПАРСЕР HIRIFY =================


def check_hirify(seen_ids, token, chat_id, api_url, log_fn):
    if not is_running:
        return
    queries = ["Data+Analyst", "SQL", "BI"]
    found = 0
    for q in queries:
        url = f"https://hirify.me/?search={q}"
        try:
            resp = requests.get(url, headers=HEADERS, timeout=8)
            if resp.status_code != 200:
                continue

            matches = re.findall(
                r'<a[^>]+href="(/jobs/(\d+)-([^"]+))"[^>]*>(.*?)</a>',
                resp.text,
                re.DOTALL,
            )
            for link, v_id, slug, inner in matches:
                if not is_running:
                    return
                vac_id = f"hirify_{v_id}"
                if vac_id in seen_ids:
                    continue

                clean = re.sub(r"<.*?>", " ", inner)
                clean_title = " ".join(clean.split())
                title = slug.replace("-", " ").title()
                t_lower = f"{clean_title} {title}".lower()

                if any(b in t_lower for b in BANNED_ROLES):
                    continue
                if any(s in t_lower for s in SENIOR_STOP_WORDS):
                    continue
                if not any(
                    role in t_lower for role in DATA_ROLES_WHITELIST
                ) and not any(k in t_lower for k in ENTRY_KEYWORDS):
                    continue

                full_link = f"https://hirify.me{link}"
                job_resp = requests.get(full_link, headers=HEADERS, timeout=5)
                if job_resp.status_code != 200:
                    continue

                full_job_text = job_resp.text.lower()
                loc_ok, loc_reason = is_valid_geo(clean_title, full_job_text)
                if not loc_ok:
                    continue

                has_exp, _ = check_experience_rejection(full_job_text)
                if has_exp:
                    continue

                seen_ids.add(vac_id)
                save_seen_id(vac_id)
                found += 1

                log_fn(f"[Hirify] {title} ({loc_reason})")
                resp_txt, req_txt = parse_duties_and_requirements(job_resp.text)

                msg = (
                    f"⚡ <b>[HIRIFY] {html.escape(title)}</b>\n\n"
                    f"<b>Локация/Формат:</b> {loc_reason}\n\n"
                    f"📌 <b>Обязанности:</b>\n{resp_txt}\n\n"
                    f"🎯 <b>Требования:</b>\n{req_txt}\n\n"
                    f"🔗 <a href='{full_link}'>Открыть вакансию на Hirify</a>"
                )
                send_telegram(token, chat_id, msg, log_fn, api_url)
                time.sleep(1.5)
        except Exception:
            pass
    log_fn(f"[Hirify] Проверено (новых: {found})")


# ================= ПАРСЕР TELEGRAM-КАНАЛОВ =================


TG_DATA_ROLE = re.compile(
    r"\b(?:data (?:analyst|analytics|engineer)|analytics engineer|"
    r"аналити(?:к\w*|ка) (?:по\s+)?данн\w*|(?:дата|bi)[ -]+аналитик\w*|аналитик\w* bi|"
    r"инженер\w* данн\w*|(?:bi|sql|dwh|etl)[ -]+(?:аналитик\w*|разработчик\w*|developer|engineer|analyst)|"
    r"(?:разработчик\w*|инженер\w*)[ -]+(?:sql|bi|dwh|etl|баз данн\w*))\b"
)
TG_OTHER_ROLE = re.compile(
    r"\b(?:(?:системн\w*|бизнес|продуктов\w*|финансов\w*)[ -]+аналитик\w*|"
    r"(?:system|business|product|financial) analyst|data scientist|"
    r"backend|front[ -]?end|full[ -]?stack|devops|qa|ux|ui|smm|дизайнер\w*|"
    r"тестировщик\w*|продаж\w*|маркетолог\w*|рекрутер\w*|бухгалтер\w*|"
    r"репетитор\w*|курьер\w*|копирайтер\w*|колл[ -]центр\w*)\b"
)
TG_ENTRY_GRADE = re.compile(
    r"\b(?:junior|intern(?:ship)?|trainee|джун\w*|стажер\w*|стажировк\w*|"
    r"младш\w*|начинающ\w*|начальн\w* уров\w*)\b"
)
TG_ENTRY_EXPERIENCE = re.compile(
    r"\b(?:без опыта|no experience|от\s+\d{1,2}\s+месяц\w*|"
    r"от\s+(?:1|одного)\s+года|до\s+(?:1\s+)?года|0\s*[-–—]\s*1\s+год\w*)\b"
)
TG_HIGH_GRADE = re.compile(
    r"\b(?:middle|mid-level|senior|lead|team[ -]?lead|principal|head|"
    r"м[ие]дд?л\w*|с[еи]ньор\w*|лид|ведущ\w*|старш\w*|руководител\w*)\b"
)
TG_REQUIRED_EXPERIENCE = re.compile(
    r"\b(?:опыт(?:а| работы)?\s*(?::\s*)?(?:(?:от|минимум|не менее)\s+)?|"
    r"(?:от|минимум|не менее|at least|minimum)\s+)"
    r"(?:[2-9]|\d{2,}|двух|трех|четырех|пяти)\s*(?:-?(?:х|ти)|\+)?\s*(?:лет|год\w*|years?)\b|"
    r"\b(?:[2-9]|\d{2,})(?:\s*\+|\s*[-–—]\s*\d+)\s*(?:лет|год\w*|years?)\b|"
    r"\b(?:[2-9]|\d{2,})\s+years?\s+(?:of\s+)?(?:professional\s+)?experience\b"
)
TG_VACANCY = re.compile(
    r"\b(?:ваканси\w*|отклик\w*|ищем|нанимаем|работодатель|компания\s*:|"
    r"обязанност\w*|требовани\w*|зарплат\w*|з/п|что нужно делать|задачи|"
    r"чем предстоит заниматься|присылай\w* резюме|apply|hiring|salary|requirements|responsibilities)\b"
)
TG_AD = re.compile(
    r"\b(?:подборка|дайджест|вакансии недели|вебинар\w*|буткемп\w*|"
    r"марафон\w*|мастер[ -]класс\w*|курс(?:ы|а|е|ом)?|интенсив\w*|"
    r"конференци\w*|хакатон\w*|партнерский пост|реклама|"
    r"ищу работу|ищу стажировку)\b"
)
TG_SPB = re.compile(
    r"\b(?:санкт[ -]петербург\w*|петербург\w*|спб|питер\w*|st\.?\s+petersburg)\b"
)
TG_REMOTE = re.compile(r"\b(?:удален(?:н\w*|к\w*)|дистанционн\w*|remote|anywhere)\b")
TG_NO_REMOTE = re.compile(
    r"\b(?:без удален\w*|не удален\w*|удален\w*\s+(?:нет|не (?:предусмотрен\w*|возможн\w*))|"
    r"no remote|remote\s+(?:unavailable|not available))\b"
)
TG_PART_TIME = re.compile(
    r"\b(?:подработк\w*|неполн\w*\s+(?:рабоч\w*\s+)?(?:день|недел\w*)|"
    r"частичн\w* занятост\w*|проектн\w*\s+(?:занятост\w*|работ\w*)|"
    r"part[ -]time|фриланс\w*|полставки|"
    r"(?:[1-9]|[12]\d|30)\s+час\w*\s+в\s+недел\w*)\b"
)
TG_NO_PART_TIME = re.compile(
    r"\b(?:только полн\w+\s+(?:занятост\w*|рабоч\w+\s+день)|"
    r"частичн\w* занятост\w*\s+не\s+(?:предусмотрен\w*|рассматрива\w*|возможн\w*))\b"
)
TG_PART_TIME_WORK = re.compile(
    r"\b(?:ввод\w* данн\w*|занос\w* данн\w*|размет\w*\s+(?:данн\w*|текст\w*|изображени\w*)|"
    r"оператор\w*\s+(?:пк|баз\w* данн\w*)|data (?:entry|labeling|annotation)|"
    r"разметчик\w*|асессор\w*|транскриб\w*|(?:ai|ии)[ -]+тренер\w*|"
    r"(?:заполня\w*|заполн\w*|вести|ведение|обновля\w*|обновлен\w*|обрабатыва\w*)"
    r"\s+(?:excel[ -]+)?(?:таблиц\w*|данн\w*)|(?:excel|google sheets)[ -]+(?:оператор|специалист))\b"
)
TG_ASSISTANT = re.compile(r"\b(?:оператор\w*|ассистент\w*|помощник\w*|подработк\w*)\b")
TG_SALES = re.compile(
    r"\b(?:холодн\w*\s+звонк\w*|обзвон\w*|телемаркет\w*|"
    r"активн\w*\s+продаж\w*|привлечени\w*\s+клиент\w*)\b"
)
TG_TAG = re.compile(r"(?<!\w)#[\w.]+")
TG_FOOTER = re.compile(r"(?im)^\s*(?:[—─━➖-][—─━➖\s-]{2,}|[^\w\n]*разместить вакансию)\s*$")
TG_ROUNDUP = re.compile(r"\b(?:подборка|дайджест|вакансии (?:недели|в\b))")
TG_BULLET = re.compile(r"(?m)^[ \t]*[-•][ \t]+")
TG_LOCATION_FIELD = re.compile(
    r"^\W*(?:город|локация|формат(?: работы| стажировки)?|место работы|location|work format)\s*:"
)
TG_GRADE_FIELD = re.compile(r"^\W*(?:грейд|уровень|grade|level)\s*:")
TG_OFFICE = re.compile(r"\b(?:офис\w*|гибрид\w*|office|hybrid|on[ -]site)\b")
TG_REMOTE_OFFER = re.compile(
    r"\b(?:можно\s+(?:работать\s+)?удален\w*|возможн\w*\s+удален\w*|"
    r"удален\w+\s+(?:формат|работа)|fully remote)\b"
)


def telegram_posts(page):
    blocks = re.split(
        r'<div\b[^>]*\bclass="[^"]*(?<![\w-])tgme_widget_message(?![\w-])[^"]*"'
        r'[^>]*\bdata-post="(\w+/\d+)"[^>]*>',
        page,
    )
    for post_id, block in zip(blocks[1::2], blocks[2::2]):
        match = re.search(
            r'class="[^"]*\btgme_widget_message_text\b[^"]*"[^>]*>(.*?)</div>',
            block,
            re.DOTALL,
        )
        if match:
            body = re.sub(r"<br\s*/?>", "\n", match.group(1), flags=re.IGNORECASE)
            yield post_id, html.unescape(re.sub(r"<[^>]*>", "", body))


def telegram_listings(text):
    text = TG_FOOTER.split(text, maxsplit=1)[0].strip()
    if not text:
        return
    header = text.splitlines()[0].lower().replace("ё", "е")
    if not TG_ROUNDUP.search(header):
        yield text
        return

    for section in re.split(r"\n\s*\n", text)[1:]:
        if "│" in section:
            continue
        context, *items = TG_BULLET.split(section)
        if not items:
            yield section
            continue

        context = context.strip().lower().replace("ё", "е")
        location = context if TG_SPB.search(context) or TG_REMOTE.search(context) else ""
        if not location and TG_REMOTE.search(header) and not TG_OFFICE.search(context):
            location = "Удалённо"
        level = f"{header} {context}"
        for item in items:
            if location:
                yield f"{item.strip()}\nФормат: {location}\nГрейд: {level}\nВакансия"


def telegram_vacancy_type(text):
    lines = [
        " ".join(line.lower().replace("ё", "е").split())
        for line in text.splitlines()
        if line.strip() and "│" not in line
    ]
    if not lines:
        return None

    # A generic vacancy label can precede the actual job title.
    title = next(
        (
            line for line in lines[:4]
            if not line.startswith("#")
            and not re.fullmatch(r"\W*(?:вакансия|стажировка|работа|подработка)\W*", line)
        ),
        lines[0],
    )
    title = title.replace("_", " ")
    if TG_AD.search(title) or TG_OTHER_ROLE.search(title):
        return None

    body = "\n".join(TG_TAG.sub(" ", line).replace("_", " ") for line in lines)
    if not TG_VACANCY.search(body) or TG_REQUIRED_EXPERIENCE.search(body):
        return None
    grade_lines = [line for line in lines if TG_GRADE_FIELD.match(line)]
    grade = "\n".join([title, *grade_lines])
    if TG_HIGH_GRADE.search(grade):
        return None

    locations = [line for line in lines if TG_LOCATION_FIELD.match(line)]
    if not locations:
        locations = [line for line in lines[:5] if not line.startswith("#")]
    location_text = "\n".join(locations)
    tags = " ".join(TG_TAG.findall("\n".join(lines))).replace("_", " ")
    remote = bool(
        TG_REMOTE.search(location_text)
        or TG_REMOTE_OFFER.search(body)
        or (TG_REMOTE.search(tags) and not TG_OFFICE.search(location_text))
    )
    remote = remote and not TG_NO_REMOTE.search(body)
    # Office-only openings are relevant in Saint Petersburg.
    spb = bool(TG_SPB.search(location_text))
    if not (remote or spb):
        return None

    generic_analyst = re.search(r"\b(?:аналитик\w*|analyst)\b", title) and re.search(
        r"\b(?:sql|power bi|datalens|tableau|qlik)\b", body
    )
    entry = TG_ENTRY_GRADE.search(grade) or TG_ENTRY_GRADE.search(tags) or TG_ENTRY_EXPERIENCE.search(body)
    if (TG_DATA_ROLE.search(title) or generic_analyst) and entry:
        return "data"

    relevant_tasks = TG_PART_TIME_WORK.search(title) or (
        TG_ASSISTANT.search(title) and TG_PART_TIME_WORK.search(body)
    )
    if (
        remote
        and TG_PART_TIME.search(body)
        and relevant_tasks
        and not (TG_SALES.search(body) or TG_NO_PART_TIME.search(body))
    ):
        return "part_time"
    return None


def check_tg(seen_ids, token, chat_id, api_url, log_fn):
    channels = get_channels()
    found = 0
    for channel in channels:
        if not is_running:
            return
        preview_url = f"https://t.me/s/{channel}"
        try:
            resp = requests.get(preview_url, headers=HEADERS, timeout=8)
            resp.raise_for_status()
        except requests.RequestException:
            log_fn(f"[TG @{channel}] Не удалось загрузить предпросмотр.")
            continue

        posts = list(telegram_posts(resp.text))
        if not posts:
            log_fn(f"[TG @{channel}] Нет доступных постов в предпросмотре.")
        for post_id, text in posts:
            if not is_running:
                return
            unique_id = f"tg_{post_id.replace('/', '_')}"
            if unique_id in seen_ids:
                continue

            matches = [
                (listing, vacancy_type)
                for listing in telegram_listings(text)
                if (vacancy_type := telegram_vacancy_type(listing))
            ]
            if not matches:
                continue

            badge = (
                "📢 <b>[TG-ВАКАНСИЯ] Аналитика данных / SQL / BI</b>"
                if any(vacancy_type == "data" for _, vacancy_type in matches)
                else "☕ <b>[TG-ПОДРАБОТКА] Данные / Таблицы / ИИ</b>"
            )
            post_link = f"https://t.me/{post_id}"
            snippets = [
                listing if len(listing) <= 600 else listing[:600] + "…"
                for listing, _ in matches[:3]
            ]
            snippet = "\n\n".join(snippets)

            log_fn(f"[TG @{channel}] Найдено совпадение!")
            msg = (
                f"{badge}\n"
                f"<i>Канал: @{channel}</i>\n\n"
                f"{html.escape(snippet)}\n\n"
                f"🔗 <a href='{post_link}'>Открыть пост в Telegram</a>"
            )
            if send_telegram(token, chat_id, msg, log_fn, api_url):
                save_seen_id(unique_id)
                seen_ids.add(unique_id)
                found += 1
            time.sleep(1.5)
    log_fn(f"[TG-Каналы] Источников: {len(channels)}, отправлено: {found}")


# ================= ФОНОВЫЙ ПОТОК =================


def bot_worker(token, chat_id, api_url, log_fn, on_stop_fn):
    global is_running
    log_fn("Бот запущен. Источники: hh.ru, Хабр, Hirify и Telegram.")
    seen = load_seen_ids()

    while is_running:
        try:
            log_fn("-> Сканирование новых предложений...")
            check_hh(seen, token, chat_id, api_url, log_fn)
            check_habr(seen, token, chat_id, api_url, log_fn)
            check_hirify(seen, token, chat_id, api_url, log_fn)
            check_tg(seen, token, chat_id, api_url, log_fn)

            next_time = time.strftime(
                "%H:%M:%S", time.localtime(time.time() + 7200)
            )
            log_fn(
                f"⏳ Круг завершен! Все 4 источника проверены. Сплю 2 часа (до {next_time})."
            )
        except Exception as e:
            log_fn(f"Ошибка в цикле: {e}")

        # Спим 2 часа с возможностью мгновенного выхода
        for _ in range(7200):
            if not is_running:
                break
            time.sleep(1)

    log_fn("Поиск полностью остановлен.")
    on_stop_fn()


# ================= ГРАФИЧЕСКИЙ ИНТЕРФЕЙС (TKINTER) =================


class JobHunterApp:

    def __init__(self, root):
        self.root = root
        self.root.title("Job Hunter AI — Data Analyst / BI / SQL & Подработка")
        self.root.geometry("820x600")
        self.root.minsize(740, 500)

        self.bg_color = "#0f172a"
        self.panel_bg = "#1e293b"
        self.text_color = "#f8fafc"
        self.accent_green = "#10b981"
        self.accent_red = "#ef4444"

        self.root.configure(bg=self.bg_color)
        config = load_config()

        # ШАПКА
        top_frame = tk.Frame(root, bg=self.panel_bg, padx=16, pady=12)
        top_frame.pack(fill="x", padx=16, pady=(16, 10))

        tk.Label(
            top_frame,
            text="Job Hunter AI",
            font=("Segoe UI", 16, "bold"),
            fg="#ffffff",
            bg=self.panel_bg,
        ).pack(side="left")
        tk.Label(
            top_frame,
            text="  •  Аналитик данных / BI / SQL & Подработка",
            font=("Segoe UI", 10),
            fg="#94a3b8",
            bg=self.panel_bg,
        ).pack(side="left", pady=(4, 0))

        self.status_label = tk.Label(
            top_frame,
            text="● Остановлен",
            font=("Segoe UI", 11, "bold"),
            fg=self.accent_red,
            bg=self.panel_bg,
        )
        self.status_label.pack(side="right")

        # ПАНЕЛЬ НАСТРОЕК (СТРОГО 3 ПОЛЯ, БЕЗ СОКСА)
        settings_frame = tk.LabelFrame(
            root,
            text=" Параметры подключения ",
            font=("Segoe UI", 10, "bold"),
            fg="#cbd5e1",
            bg=self.panel_bg,
            padx=14,
            pady=10,
        )
        settings_frame.pack(fill="x", padx=16, pady=6)

        tk.Label(
            settings_frame,
            text="Telegram Bot Token:",
            font=("Segoe UI", 9, "bold"),
            fg="#94a3b8",
            bg=self.panel_bg,
        ).grid(row=0, column=0, sticky="w", pady=4)
        self.token_entry = tk.Entry(
            settings_frame,
            bg="#0f172a",
            fg="#ffffff",
            insertbackground="white",
            font=("Consolas", 10),
            relief="flat",
        )
        self.token_entry.grid(row=0, column=1, sticky="ew", padx=10, pady=4)
        self.token_entry.insert(0, config.get("bot_token", ""))

        tk.Label(
            settings_frame,
            text="Telegram Chat ID:",
            font=("Segoe UI", 9, "bold"),
            fg="#94a3b8",
            bg=self.panel_bg,
        ).grid(row=1, column=0, sticky="w", pady=4)
        self.chat_id_entry = tk.Entry(
            settings_frame,
            bg="#0f172a",
            fg="#ffffff",
            insertbackground="white",
            font=("Consolas", 10),
            relief="flat",
        )
        self.chat_id_entry.grid(row=1, column=1, sticky="ew", padx=10, pady=4)
        self.chat_id_entry.insert(0, config.get("chat_id", ""))

        tk.Label(
            settings_frame,
            text="Cloudflare Worker URL:",
            font=("Segoe UI", 9, "bold"),
            fg="#94a3b8",
            bg=self.panel_bg,
        ).grid(row=2, column=0, sticky="w", pady=4)
        self.api_url_entry = tk.Entry(
            settings_frame,
            bg="#0f172a",
            fg="#ffffff",
            insertbackground="white",
            font=("Consolas", 10),
            relief="flat",
        )
        self.api_url_entry.grid(row=2, column=1, sticky="ew", padx=10, pady=4)
        self.api_url_entry.insert(0, config.get("api_url", ""))

        settings_frame.columnconfigure(1, weight=1)

        # ПАНЕЛЬ КНОПОК
        btn_frame = tk.Frame(root, bg=self.bg_color)
        btn_frame.pack(fill="x", padx=16, pady=8)

        self.start_btn = tk.Button(
            btn_frame,
            text="▶  Запустить поиск",
            font=("Segoe UI", 11, "bold"),
            bg=self.accent_green,
            fg="#ffffff",
            activebackground="#059669",
            activeforeground="#ffffff",
            padx=18,
            pady=8,
            relief="flat",
            cursor="hand2",
            command=self.start_bot,
        )
        self.start_btn.pack(side="left", padx=(0, 10))

        self.stop_btn = tk.Button(
            btn_frame,
            text="⏹  Остановить",
            font=("Segoe UI", 11, "bold"),
            bg="#334155",
            fg="#94a3b8",
            activebackground="#dc2626",
            activeforeground="#ffffff",
            padx=18,
            pady=8,
            relief="flat",
            state="disabled",
            command=self.stop_bot,
        )
        self.stop_btn.pack(side="left", padx=(0, 10))

        self.clear_btn = tk.Button(
            btn_frame,
            text="🗑  Сбросить историю",
            font=("Segoe UI", 10),
            bg=self.panel_bg,
            fg="#cbd5e1",
            activebackground="#334155",
            activeforeground="#ffffff",
            padx=14,
            pady=8,
            relief="flat",
            cursor="hand2",
            command=self.clear_history,
        )
        self.clear_btn.pack(side="right")

        # ТЕРМИНАЛ ЛОГОВ
        log_frame = tk.LabelFrame(
            root,
            text=" Журнал работы (hh.ru • Хабр • Hirify • Telegram) ",
            font=("Segoe UI", 9, "bold"),
            fg="#94a3b8",
            bg=self.panel_bg,
            padx=10,
            pady=8,
        )
        log_frame.pack(fill="both", expand=True, padx=16, pady=(4, 16))

        self.log_area = ScrolledText(
            log_frame,
            bg="#050811",
            fg="#cbd5e1",
            font=("Consolas", 10),
            relief="flat",
            insertbackground="white",
        )
        self.log_area.pack(fill="both", expand=True)

    def log(self, text):
        t_str = time.strftime("[%H:%M:%S] ")
        print(f"{t_str}{text}")
        self.root.after(
            0,
            lambda: (
                self.log_area.insert("end", t_str + text + "\n"),
                self.log_area.see("end"),
            ),
        )

    def start_bot(self):
        global is_running
        token = self.token_entry.get().strip()
        chat_id = self.chat_id_entry.get().strip()
        api_url = self.api_url_entry.get().strip()

        if not token or not chat_id:
            messagebox.showwarning(
                "Внимание!", "Пожалуйста, введите ваш Telegram Chat ID!"
            )
            return

        save_config(token, chat_id, api_url)
        is_running = True

        self.start_btn.config(state="disabled", bg="#334155", fg="#64748b")
        self.stop_btn.config(
            state="normal", bg=self.accent_red, fg="#ffffff", cursor="hand2"
        )
        self.status_label.config(
            text="● Активно ищет...", fg=self.accent_green
        )

        threading.Thread(
            target=bot_worker,
            args=(token, chat_id, api_url, self.log, self.on_bot_stopped),
            daemon=True,
        ).start()

    def stop_bot(self):
        global is_running
        is_running = False
        self.log("Останавливаю бота... пожалуйста, подождите.")
        self.status_label.config(text="● Остановка...", fg="#f59e0b")
        self.stop_btn.config(state="disabled")

    def on_bot_stopped(self):
        self.root.after(0, self._reset_ui)

    def _reset_ui(self):
        self.start_btn.config(
            state="normal", bg=self.accent_green, fg="#ffffff"
        )
        self.stop_btn.config(
            state="disabled", bg="#334155", fg="#94a3b8", cursor="default"
        )
        self.status_label.config(text="● Остановлен", fg=self.accent_red)

    def clear_history(self):
        if os.path.exists(SEEN_FILE):
            os.remove(SEEN_FILE)
            self.log("База вакансий очищена! Всё будет проверено заново.")
        else:
            self.log("База вакансий уже пуста.")


if __name__ == "__main__":
    root = tk.Tk()
    app = JobHunterApp(root)
    root.mainloop()
