import re
import time
from apps.core.sheets_client import get_crm_spreadsheet, get_main_spreadsheet

# Кэш результатов поиска в памяти на время сессии (URL/ID -> (timestamp, data))
_DEALS_SEARCH_CACHE: dict[str, tuple[float, dict]] = {}
CACHE_TTL_SECONDS = 90


def normalize_deal_url(url: str) -> str:
    if not url:
        return ""
    clean = str(url).strip()
    match = re.search(r"https?://[^\s]+amocrm\.ru/leads/detail/\d+", clean)
    if match:
        return match.group(0)
    return clean


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
    clean_digits = re.sub(r"\D", "", clean)
    if len(clean_digits) >= 5:
        return clean_digits
    return ""


def find_deal_by_link(link: str, force_refresh: bool = False) -> dict | None:
    """Быстрый поиск сделки с кэшированием и точечным поиском ячейки."""
    if not link:
        return None

    raw_link = str(link).strip()
    deal_id = extract_deal_id_from_link(raw_link)
    cache_key = deal_id if deal_id else raw_link.lower()

    # 1. Проверяем кэш в памяти
    if not force_refresh and cache_key in _DEALS_SEARCH_CACHE:
        cached_time, cached_data = _DEALS_SEARCH_CACHE[cache_key]
        if time.time() - cached_time < CACHE_TTL_SECONDS:
            return cached_data

    # 2. Быстрый точечный поиск в CRM-таблице через sheet.find()
    try:
        crm_sh = get_crm_spreadsheet()
        sheet = crm_sh.worksheet("Сделки")

        found_cell = None
        # Ищем ячейку напрямую через API Google (ищет за 1 секунду)
        if deal_id:
            try:
                found_cell = sheet.find(deal_id)
            except Exception:
                found_cell = None

        if not found_cell:
            try:
                found_cell = sheet.find(raw_link)
            except Exception:
                found_cell = None

        if found_cell:
            row = sheet.row_values(found_cell.row)

            def get_val(col_idx: int) -> str:
                return row[col_idx].strip() if len(row) > col_idx else ""

            r_id = get_val(14) or deal_id
            r_url = get_val(41) or get_val(49) or raw_link

            res = {
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
                "hooks": get_val(84) if len(row) > 84 else "",
                "comment": get_val(85) if len(row) > 85 else "",
            }

            _DEALS_SEARCH_CACHE[cache_key] = (time.time(), res)
            if deal_id:
                _DEALS_SEARCH_CACHE[deal_id] = (time.time(), res)
            return res

    except Exception as e:
        print(f"[DealsService] Ошибка точечного поиска в CRM: {e}")

    # 3. Резервный поиск по листу 'Встречи' в рабочей таблице
    try:
        main_sh = get_main_spreadsheet()
        sheet = main_sh.worksheet("Встречи")
        records = sheet.get_all_records()
        clean_link_lower = raw_link.lower()

        for r in records:
            r_id = str(r.get("ID") or r.get("ID сделки") or "").strip()
            r_url = str(r.get("Ссылка на сделку") or r.get("deal_url") or "").strip().lower()

            if (deal_id and deal_id == r_id) or (deal_id and deal_id in r_url) or (clean_link_lower and clean_link_lower in r_url):
                res = {
                    "manager": str(r.get("Менеджер") or r.get("manager") or "").strip(),
                    "client": str(r.get("Клиент") or r.get("client") or "").strip(),
                    "deal_id": str(r_id or deal_id).strip(),
                    "complex": str(r.get("ЖК") or r.get("complex") or "").strip(),
                    "service_type": str(r.get("Тип услуги") or r.get("service_type") or "").strip(),
                    "area": str(r.get("Площадь") or r.get("area") or "").strip(),
                    "rooms": str(r.get("Комнат") or r.get("rooms") or "").strip(),
                    "pains": str(r.get("Боли") or r.get("pains") or "").strip(),
                    "condition": str(r.get("Состояние") or r.get("condition") or "").strip(),
                    "keys": str(r.get("Ключи") or r.get("keys") or "").strip(),
                    "deal_url": str(r.get("Ссылка на сделку") or r.get("deal_url") or raw_link).strip(),
                    "comment": str(r.get("Комментарий") or r.get("comment") or "").strip(),
                    "hooks": str(r.get("Крючки") or r.get("hooks") or "").strip(),
                }
                _DEALS_SEARCH_CACHE[cache_key] = (time.time(), res)
                return res
    except Exception as e:
        print(f"[DealsService] Ошибка резервного поиска: {e}")

    return None


def get_active_deals() -> list[dict]:
    try:
        sheet = get_main_spreadsheet().worksheet("Встречи")
        return sheet.get_all_records()
    except Exception:
        return []


def get_all_deals() -> list[dict]:
    return get_active_deals()