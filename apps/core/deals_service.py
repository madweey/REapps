import re
from apps.core.sheets_client import get_crm_spreadsheet, get_main_spreadsheet


def normalize_deal_url(url: str) -> str:
    if not url:
        return ""
    return str(url).strip()


def extract_deal_id_from_link(link: str) -> str:
    if not link:
        return ""
    clean = str(link).strip()
    match = re.search(r"detail/(\d+)", clean)
    if match:
        return match.group(1)
    match_leads = re.search(r"leads/detail/(\d+)", clean)
    if match_leads:
        return match_leads.group(1)
    parts = clean.rstrip("/").split("/")
    if parts and parts[-1].isdigit():
        return parts[-1]
    return clean


def find_deal_by_link(link: str) -> dict | None:
    """Точечный быстрый поиск сделки напрямую из оригинальной таблицы CRM (read-only)."""
    if not link:
        return None
    clean_link = str(link).strip().lower()
    deal_id = extract_deal_id_from_link(link)

    # 1. Поиск по оригинальной таблице CRM (лист 'Сделки', колонка AP = 42)
    try:
        crm_sh = get_crm_spreadsheet()
        sheet = crm_sh.worksheet("Сделки")
        ap_urls = sheet.col_values(42)
        found_row_idx = None

        for idx, cell_url in enumerate(ap_urls, start=1):
            if idx < 5:
                continue
            if not cell_url:
                continue
            u = str(cell_url).strip().lower()

            if clean_link and (clean_link in u or u in clean_link):
                found_row_idx = idx
                break
            if deal_id and deal_id in u:
                found_row_idx = idx
                break

        if found_row_idx:
            row = sheet.row_values(found_row_idx)

            def get_val(col_idx: int) -> str:
                return row[col_idx].strip() if len(row) > col_idx else ""

            r_id = get_val(14) or deal_id
            r_url = get_val(41) or link

            return {
                "manager": get_val(4),
                "client": get_val(7),
                "deal_id": str(r_id).strip(),
                "complex": get_val(16),
                "service_type": get_val(19),
                "area": get_val(21),
                "rooms": get_val(22),
                "pains": get_val(30),
                "condition": get_val(35),
                "keys": get_val(36),
                "deal_url": str(r_url).strip(),
                "hooks": get_val(84),
                "comment": get_val(85),
            }
    except Exception as e:
        print(f"Ошибка точечного чтения CRM: {e}")

    # 2. Резервный поиск по листу 'Встречи' в рабочей таблице
    try:
        main_sh = get_main_spreadsheet()
        sheet = main_sh.worksheet("Встречи")
        records = sheet.get_all_records()
        for r in records:
            r_id = str(r.get("ID") or r.get("ID сделки") or "").strip()
            r_url = str(r.get("Ссылка на сделку") or "").strip().lower()

            if (clean_link and clean_link in r_url) or (deal_id and deal_id in r_url) or (deal_id and deal_id == r_id):
                return {
                    "manager": str(r.get("Менеджер") or "").strip(),
                    "client": str(r.get("Клиент") or "").strip(),
                    "deal_id": str(r_id or deal_id).strip(),
                    "complex": str(r.get("ЖК") or "").strip(),
                    "service_type": "",
                    "area": str(r.get("Площадь") or "").strip(),
                    "rooms": "",
                    "pains": "",
                    "condition": "",
                    "keys": "",
                    "deal_url": str(r.get("Ссылка на сделку") or link).strip(),
                    "comment": str(r.get("Комментарий Пл") or "").strip(),
                    "hooks": str(r.get("Крючки") or "").strip(),
                }
    except Exception as e:
        print(f"Ошибка резервного поиска во 'Встречи': {e}")

    return None


def get_active_deals() -> list[dict]:
    try:
        sheet = get_main_spreadsheet().worksheet("Встречи")
        return sheet.get_all_records()
    except Exception:
        return []


def get_all_deals() -> list[dict]:
    return get_active_deals()