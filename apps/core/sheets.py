import json
import os
import sys

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
    global _CACHED_GEMINI_KEYS
    if _CACHED_GEMINI_KEYS and not force_refresh:
        return _CACHED_GEMINI_KEYS

    keys = []
    try:
        ws = get_sheet_by_title("Настройка")
        # Расширенный диапазон M11:M30 (до 20 ключей Gemini)
        vals = ws.get_values("M11:M30")
        for row in vals:
            if row and row[0]:
                k = row[0].strip()
                if k and k not in keys:
                    keys.append(k)
        if keys:
            _CACHED_GEMINI_KEYS = keys
            return _CACHED_GEMINI_KEYS
    except Exception as e:
        print(f"[Sheets] Ошибка чтения ключей Gemini: {e}")

    return _CACHED_GEMINI_KEYS or []


def get_gemini_api_key_from_sheet(force_refresh: bool = False) -> str:
    keys = get_gemini_api_keys_from_sheet(force_refresh)
    return keys[0] if keys else ""


# -------------------------------------------------------------------------
# ЯДРО СИНХРОНИЗАЦИИ БАЗЫ РЕМОНТА (КОМБИНИРОВАННЫЙ ПОДХОД)
# -------------------------------------------------------------------------

def _parse_float(val, default=0.0):
    if val is None or str(val).strip() == "": return default
    s = str(val).strip().replace(" ", "").replace("%", "").replace(",", ".")
    try: return float(s)
    except ValueError: return default

class RepairDataSync:
    LOCAL_FILE = "repair_db.json"

    @classmethod
    def get_local_path(cls):
        if getattr(sys, 'frozen', False):
            base = os.path.dirname(sys.executable)
        else:
            base = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        return os.path.join(base, cls.LOCAL_FILE)

    @classmethod
    def save_local_only(cls, data):
        with open(cls.get_local_path(), "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    @classmethod
    def pull_from_cloud(cls):
        sh = get_main_spreadsheet()
        ws = sh.worksheet("Настройка_Ремонт")
        all_vals = ws.get_all_values()
        
        # Подгружаем текущие локальные данные, чтобы не потерять настройки, если в таблице пусто
        existing_rates = {}
        local_path = cls.get_local_path()
        if os.path.exists(local_path):
            try:
                with open(local_path, "r", encoding="utf-8") as f:
                    existing_rates = json.load(f).get("base_rates", {})
            except Exception:
                pass

        data = {
            "base_rates": {
                "engineering_work": existing_rates.get("engineering_work", 25254.0),
                "finishing_work": existing_rates.get("finishing_work", 33024.0),
                "engineering_mat": existing_rates.get("engineering_mat", 29475.0),
                "finishing_mat": existing_rates.get("finishing_mat", 26500.0),
                "eng_mat_pct": existing_rates.get("eng_mat_pct", 85.0),
                "fin_mat_pct": existing_rates.get("fin_mat_pct", 120.0),
                "furn_market": existing_rates.get("furn_market", 20.0),
                "furn_aggr": existing_rates.get("furn_aggr", 25.0),
                "furn_custom": existing_rates.get("furn_custom", 35.0),
                "app_base": existing_rates.get("app_base", 10.0),
                "app_mid": existing_rates.get("app_mid", 15.0),
                "app_prem": existing_rates.get("app_prem", 25.0),
                "template_eng": existing_rates.get("template_eng", "1oakVh-dtwWQGDCXSNQZc_Zs9tOjJtMoG5zZSKIAcabQ"),
                "template_fin": existing_rates.get("template_fin", "17-2u5SqSYQBjSoR72X4qhlFAAdwhMz2dhVB1dmK3CFQ"),
                "template_complex": existing_rates.get("template_complex", "1-0bwSourv-vwEeKupk0oReYUazj-L_-Q6l5PKWw0nkc"),
                "template_whitebox": existing_rates.get("template_whitebox", ""),
                "folder_id": existing_rates.get("folder_id", "1kLOMyKkU9YLx5PfqUHUDfDhNR3x6xGhq"),
                "custom_templates": []
            },
            "coefficients": [],
            "eng_stages": [],
            "fin_stages": []
        }
        
        last_num = 0
        current_stages = data["eng_stages"]

        for r_idx in range(1, len(all_vals)):
            row = all_vals[r_idx]
            
            # Базовые ставки, проценты и Шаблоны (Столбцы A-B)
            if r_idx < 60 and len(row) > 1:
                raw_name = str(row[0]).strip()
                n = raw_name.lower()
                v = str(row[1]).strip()
                if raw_name:
                    if "инж. рем" in n: data["base_rates"]["engineering_work"] = _parse_float(v, 25254.0)
                    elif "отдел. раб" in n: data["base_rates"]["finishing_work"] = _parse_float(v, 33024.0)
                    elif "материал инж (%)" in n or "инженерия (материалы %)" in n: data["base_rates"]["eng_mat_pct"] = _parse_float(v, 85.0)
                    elif "материал отдел (%)" in n or "отделка (материалы %)" in n: data["base_rates"]["fin_mat_pct"] = _parse_float(v, 120.0)
                    elif "материал инж" in n: data["base_rates"]["engineering_mat"] = _parse_float(v, 29475.0)
                    elif "материал отдел" in n: data["base_rates"]["finishing_mat"] = _parse_float(v, 26500.0)
                    elif "мебель: маркетплейс" in n: data["base_rates"]["furn_market"] = _parse_float(v, 20.0)
                    elif "мебель: агрегаторы" in n: data["base_rates"]["furn_aggr"] = _parse_float(v, 25.0)
                    elif "мебель: индив" in n: data["base_rates"]["furn_custom"] = _parse_float(v, 35.0)
                    elif "техника: базовая" in n: data["base_rates"]["app_base"] = _parse_float(v, 10.0)
                    elif "техника: средняя" in n: data["base_rates"]["app_mid"] = _parse_float(v, 15.0)
                    elif "техника: премиум" in n: data["base_rates"]["app_prem"] = _parse_float(v, 25.0)
                    elif "шаблон инж" in n: data["base_rates"]["template_eng"] = v
                    elif "шаблон отдел" in n: data["base_rates"]["template_fin"] = v
                    elif "шаблон компл" in n: data["base_rates"]["template_complex"] = v
                    elif "шаблон вайтбокс" in n: data["base_rates"]["template_whitebox"] = v
                    elif "папка" in n: data["base_rates"]["folder_id"] = v
                    elif n.startswith("шаблон"):
                        data["base_rates"]["custom_templates"].append({"name": raw_name, "id": v})

            # Коэффициенты (Столбцы D-G)
            if len(row) > 6:
                c_id = str(row[3]).strip()
                c_name = str(row[4]).strip()
                c_val = _parse_float(row[5], 0.0)
                c_type = str(row[6]).strip()
                if c_id:
                    data["coefficients"].append({
                        "id": c_id, "name": c_name, "value": c_val, "type": c_type
                    })

            # Этапы ремонта (Столбцы L-R)
            if len(row) > 17:
                s_title = str(row[12]).strip()
                if s_title:
                    s_num_str = str(row[11]).strip()
                    s_num = int(_parse_float(s_num_str, last_num + 1))
                    if s_num <= last_num and len(data["eng_stages"]) > 0:
                        current_stages = data["fin_stages"]
                    last_num = s_num
                    
                    s_ws = _parse_float(row[13], 0.0)
                    s_ms = _parse_float(row[14], 0.0)
                    s_days = _parse_float(row[15], 10)
                    s_wd = str(row[16]).strip()
                    s_md = str(row[17]).strip()
                    
                    current_stages.append({
                        "num": s_num, "title": s_title, "w_share": s_ws,
                        "m_share": s_ms, "days": s_days, "w_desc": s_wd, "m_desc": s_md
                    })
        
        cls.save_local_only(data)
        return data

    @classmethod
    def get_data(cls):
        path = cls.get_local_path()
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    d = json.load(f)
                    if "custom_templates" not in d.get("base_rates", {}):
                        d.setdefault("base_rates", {})["custom_templates"] = []
                    return d
            except Exception:
                pass
        return cls.pull_from_cloud()

    @classmethod
    def save_and_push(cls, data):
        # 1. Сохраняем локально для мгновенной работы
        cls.save_local_only(data)
            
        # 2. Выгружаем батчем в Google Sheets
        sh = get_main_spreadsheet()
        ws = sh.worksheet("Настройка_Ремонт")
        br = data.get("base_rates", {})
        
        rates_arr = [
            ["Инж. рем за м2", br.get("engineering_work", 25254.0)],
            ["Отдел. раб за м2", br.get("finishing_work", 33024.0)],
            ["Материал инженерия", br.get("engineering_mat", 29475.0)],
            ["Материал отделка", br.get("finishing_mat", 26500.0)],
            ["Материал инж (%)", br.get("eng_mat_pct", 85.0)],
            ["Материал отдел (%)", br.get("fin_mat_pct", 120.0)],
            ["Мебель: Маркетплейс (%)", br.get("furn_market", 20.0)],
            ["Мебель: Агрегаторы (%)", br.get("furn_aggr", 25.0)],
            ["Мебель: Индив. изготовление (%)", br.get("furn_custom", 35.0)],
            ["Техника: Базовая (%)", br.get("app_base", 10.0)],
            ["Техника: Средняя (%)", br.get("app_mid", 15.0)],
            ["Техника: Премиум (%)", br.get("app_prem", 25.0)],
            ["Шаблон Инженерия", br.get("template_eng", "")],
            ["Шаблон Отделка", br.get("template_fin", "")],
            ["Шаблон Комплекс", br.get("template_complex", "")],
            ["Шаблон Вайтбокс", br.get("template_whitebox", "")],
            ["Папка сохранения", br.get("folder_id", "")],
        ]

        # Добавляем все пользовательские поля шаблонов
        for ct in br.get("custom_templates", []):
            t_name = str(ct.get("name", "")).strip()
            t_id = str(ct.get("id", "")).strip()
            if t_name:
                if not t_name.lower().startswith("шаблон"):
                    t_name = f"Шаблон: {t_name}"
                rates_arr.append([t_name, t_id])
        
        coeffs_arr = []
        for c in data.get("coefficients", []):
            coeffs_arr.append([c["id"], c["name"], c["value"], c["type"]])
        
        stages_arr = []
        for s in data.get("eng_stages", []):
            stages_arr.append([s["num"], s["title"], s["w_share"], s["m_share"], s["days"], s["w_desc"], s["m_desc"]])
        for s in data.get("fin_stages", []):
            stages_arr.append([s["num"], s["title"], s["w_share"], s["m_share"], s["days"], s["w_desc"], s["m_desc"]])

        # Очищаем старые диапазоны и записываем новые без смещения ячеек
        ws.batch_clear(["A2:B60", "D2:G500", "L2:R500"])
        if rates_arr: ws.update("A2", rates_arr)
        if coeffs_arr: ws.update("D2", coeffs_arr)
        if stages_arr: ws.update("L2", stages_arr)
        
        return True


__all__ = [
    "get_main_spreadsheet",
    "get_crm_spreadsheet",
    "get_spreadsheet",
    "get_spreadsheet_instance",
    "get_sheets_client",
    "get_sheet_by_title",
    "get_gemini_api_key_from_sheet",
    "get_gemini_api_keys_from_sheet",
    "RepairDataSync",
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