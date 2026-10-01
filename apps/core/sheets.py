# Единый фасад обратной совместимости
from apps.core.sheets_client import (
    get_main_spreadsheet,
    get_crm_spreadsheet,
    get_main_spreadsheet as get_spreadsheet,
    get_main_spreadsheet as get_spreadsheet_instance,
    get_main_spreadsheet as get_sheets_client,
)
from apps.core.deals_service import (
    find_deal_by_link,
    normalize_deal_url,
    get_active_deals,
    get_all_deals,
)
from apps.core.meetings_service import (
    get_all_meetings,
    get_meetings_data,
    get_meetings_by_date,
    save_new_meeting,
    update_meeting_status,
    complete_meeting,
    cancel_meeting,
    delete_meeting,
    update_meeting_details,
)
from apps.core.links_service import (
    get_all_template_links,
    add_template_link,
    delete_template_link,
)
from apps.core.misc_service import (
    get_all_prompts,
    get_prompts_dict,
    add_prompt,
    delete_prompt,
    save_analysis,
    get_all_analyses,
    get_split_vpn_keys,
    save_split_vpn_keys,
)

# Безопасный импорт / определение update_prompt
try:
    from apps.core.misc_service import update_prompt as _imported_update_prompt
    update_prompt = _imported_update_prompt
except ImportError:
    def update_prompt(row_idx: int, title: str, category: str, prompt_text: str) -> bool:
        """Обновляет название, категорию и текст промта в листе 'Промты'."""
        try:
            sh = get_main_spreadsheet()
            ws = sh.worksheet("Промты")
            ws.update_cell(row_idx, 2, title.strip())
            ws.update_cell(row_idx, 3, category.strip())
            ws.update_cell(row_idx, 4, prompt_text.strip())
            return True
        except Exception as e:
            print(f"[Sheets] Ошибка обновления промта в строке {row_idx}: {e}")
            raise e

from apps.core.calculator_service import get_dp_tariffs_info
from apps.core.auth import (
    get_all_users,
    get_all_accounts,
    get_users_list,
    add_new_user,
    add_user,
    update_user_permissions,
    update_user_access,
    delete_user,
    authenticate,
    save_session,
    load_session,
    clear_session,
)

_CACHED_GEMINI_KEYS: list[str] = []


def get_sheet_by_title(title: str):
    return get_main_spreadsheet().worksheet(title)


def get_gemini_api_keys_from_sheet(force_refresh: bool = False) -> list[str]:
    """Загружает пул API-ключей Gemini из листа 'Настройка' (диапазон M11:M13)."""
    global _CACHED_GEMINI_KEYS
    if _CACHED_GEMINI_KEYS and not force_refresh:
        return _CACHED_GEMINI_KEYS

    keys = []
    try:
        ws = get_sheet_by_title("Настройка")
        vals = ws.get_values("M11:M13")
        for row in vals:
            if row and row[0]:
                k = row[0].strip()
                if k and k not in keys:
                    keys.append(k)
        if keys:
            _CACHED_GEMINI_KEYS = keys
            return _CACHED_GEMINI_KEYS
    except Exception as e:
        print(f"[Sheets] Ошибка чтения ключей Gemini из M11:M13: {e}")

    return _CACHED_GEMINI_KEYS or []


def get_gemini_api_key_from_sheet(force_refresh: bool = False) -> str:
    """Для обратной совместимости: возвращает первый доступный ключ."""
    keys = get_gemini_api_keys_from_sheet(force_refresh)
    return keys[0] if keys else ""


__all__ = [
    "get_main_spreadsheet",
    "get_crm_spreadsheet",
    "get_spreadsheet",
    "get_spreadsheet_instance",
    "get_sheets_client",
    "get_sheet_by_title",
    "get_gemini_api_key_from_sheet",
    "get_gemini_api_keys_from_sheet",
    "find_deal_by_link",
    "normalize_deal_url",
    "get_active_deals",
    "get_all_deals",
    "get_all_meetings",
    "get_meetings_data",
    "get_meetings_by_date",
    "save_new_meeting",
    "update_meeting_status",
    "complete_meeting",
    "cancel_meeting",
    "delete_meeting",
    "update_meeting_details",
    "get_all_template_links",
    "add_template_link",
    "delete_template_link",
    "get_all_prompts",
    "get_prompts_dict",
    "add_prompt",
    "delete_prompt",
    "update_prompt",
    "save_analysis",
    "get_all_analyses",
    "get_split_vpn_keys",
    "save_split_vpn_keys",
    "get_dp_tariffs_info",
    "get_all_users",
    "get_all_accounts",
    "get_users_list",
    "add_new_user",
    "add_user",
    "update_user_permissions",
    "update_user_access",
    "delete_user",
    "authenticate",
    "save_session",
    "load_session",
    "clear_session",
]