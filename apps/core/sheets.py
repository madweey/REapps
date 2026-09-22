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
    update_prompt,
    save_analysis,
    get_all_analyses,
    get_split_vpn_keys,
    save_split_vpn_keys,
)
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


def get_sheet_by_title(title: str):
    return get_main_spreadsheet().worksheet(title)


__all__ = [
    "get_main_spreadsheet",
    "get_crm_spreadsheet",
    "get_spreadsheet",
    "get_spreadsheet_instance",
    "get_sheets_client",
    "get_sheet_by_title",
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