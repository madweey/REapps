import json
import re
import datetime
import requests
from apps.core.sheets import get_sheets_client

SCRIPT_URL = "https://script.google.com/macros/s/AKfycbxQZ6pYW9JRUKsFJv70MUEyKOHcJ2iiQEhVI6NKOqaMM-zubsxZIyDYv3oXX6RrSlFP/exec"
TARGET_FOLDER_ID = "1SJvStDf7UyTKfrNnLYrutRRQv4n_ODn8"


def extract_file_id_from_url(url: str) -> str | None:
    match = re.search(r"/d/([a-zA-Z0-9_-]+)", str(url))
    if match:
        return match.group(1)
    return None


def get_kp_template_id_from_links() -> str:
    fallback_id = "1dEj43-yatgANpNoyLgMry1DZ1PgO41cRjdxt2P1jtEk"
    try:
        sh = get_sheets_client()
        ws = sh.worksheet("Ссылки")
        rows = ws.get_all_values()
        if len(rows) > 1:
            for r in rows[1:]:
                if not r:
                    continue
                row_str = " ".join(r).lower()
                if "кп дп" in row_str or "кп дизайн" in row_str:
                    for cell in r:
                        fid = extract_file_id_from_url(cell)
                        if fid:
                            return fid
    except Exception as e:
        print(f"Ошибка чтения шаблона из листа 'Ссылки': {e}")
    return fallback_id


def format_money(val) -> str:
    """Форматирует число с разделителем тысяч: '315 562 руб.' (для таблицы)."""
    try:
        n = int(round(float(val)))
        return f"{n:,}".replace(",", " ") + " руб."
    except Exception:
        return str(val)


def format_number_only(val) -> str:
    """Форматирует строго число с пробелами: '315 562' (без приписок валют)."""
    try:
        n = int(round(float(val)))
        return f"{n:,}".replace(",", " ")
    except Exception:
        return str(val)


def format_area(val) -> str:
    """Форматирует площадь без лишних нулей и без приписки 'м²'."""
    try:
        fl = float(val)
        return str(int(fl)) if fl.is_integer() else f"{fl:.1f}"
    except Exception:
        return str(val)


def extract_digits_only(val) -> str:
    """Извлекает только цифры срока (например, из '68 рабочих дней' делает '68')."""
    s = str(val).strip()
    digits = re.findall(r"\d+", s)
    return digits[0] if digits else s


def generate_kp_presentation(calc_data: dict, client_name: str, address: str, promo_text: str, user_name: str = "Менеджер") -> dict:
    template_id = get_kp_template_id_from_links()
    clean_client = client_name.strip() or "Клиент"
    clean_promo = promo_text.strip()
    area_str = format_area(calc_data.get("area", 0))

    dp_price_m2_formatted = format_number_only(calc_data["dp"]["price_m2"])
    odp_price_m2_formatted = format_number_only(calc_data["odp"]["price_m2"])

    formula_dp_m2 = f"{dp_price_m2_formatted} ₽/м² x {area_str} м²"
    formula_odp_m2 = f"{odp_price_m2_formatted} ₽/м² x {area_str} м²"

    replacements = {
        "{Имя}": clean_client,
        "{Адрес}": address.strip() or "Не указан",
        "{м2}": area_str,
        "{Стоимость ДП}": format_number_only(calc_data["dp"]["total_cost"]),
        "{Стоимость ДП м2}": formula_dp_m2,
        "{СрокПДП}": extract_digits_only(calc_data["dp"]["deadline"]),
        "{Стоимость ОДП}": format_number_only(calc_data["odp"]["total_cost"]),
        "{Стоимость ОДП м2}": formula_odp_m2,
        "{СрокПОДП}": extract_digits_only(calc_data["odp"]["deadline"]),
        "{АкцияД}": clean_promo,
    }

    payload = {
        "template_id": template_id,
        "folder_id": TARGET_FOLDER_ID,
        "client_name": clean_client,
        "address": address.strip() or "Не указан",
        "promo_text": clean_promo,
        "replacements": replacements,
    }

    headers = {
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
    }

    session = requests.Session()
    session.trust_env = False  # Игнорировать системные переменные прокси, чтобы исключить помехи со стороны Windows

    try:
        resp = session.post(
            SCRIPT_URL,
            data=json.dumps(payload),
            headers=headers,
            timeout=120,
            allow_redirects=True,
        )
    except Exception as ex:
        raise RuntimeError(f"Ошибка соединения с Google Apps Script: {ex}")

    if resp.status_code != 200:
        raise RuntimeError(f"Apps Script вернул ошибку {resp.status_code}: {resp.text[:300]}")

    try:
        result = resp.json()
    except Exception:
        result = json.loads(resp.text)

    if result.get("status") != "ok":
        error_msg = result.get("message", "Неизвестная ошибка Apps Script")
        raise RuntimeError(f"Apps Script Error: {error_msg}")

    pres_link = result["presentation_url"]
    pdf_link = result["pdf_url"]

    # Запись в лист 'КП' строго по колонкам A-N:
    # A: Дата | B: Кто составил | C: Заказчик | D: ЖК Мод | E: м2 | F: Акция |
    # G: стоимостьм2 онл | H: Стоимость онл | I: срок | J: стоимостьм2 офф |
    # K: Стоимость офф | L: срок оффлайн | M: Преза | N: Преза пдф
    try:
        sh = get_sheets_client()
        ws = sh.worksheet("КП")
        now_str = datetime.datetime.now().strftime("%d.%m.%Y %H:%M")
        new_kp_row = [
            now_str,
            user_name,
            clean_client,
            address.strip(),
            area_str,
            clean_promo or "Без акции",
            format_money(calc_data["odp"]["price_m2"]),
            format_money(calc_data["odp"]["total_cost"]),
            str(calc_data["odp"]["deadline"]),
            format_money(calc_data["dp"]["price_m2"]),
            format_money(calc_data["dp"]["total_cost"]),
            str(calc_data["dp"]["deadline"]),
            pres_link,
            pdf_link,
        ]
        ws.append_row(new_kp_row)
    except Exception as e:
        print(f"Ошибка сохранения записи в лист 'КП': {e}")

    return {
        "presentation_id": result.get("presentation_id", ""),
        "presentation_url": pres_link,
        "pdf_url": pdf_link,
    }