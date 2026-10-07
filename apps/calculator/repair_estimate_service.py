import json
import math
import re
from datetime import datetime
import requests
from apps.core.sheets import RepairDataSync

# URL развернутого веб-приложения Google Apps Script
WEB_APP_URL = "https://script.google.com/macros/s/AKfycbxN7gEgP0ds1u5niMtdLLgTs6Qo20Hb2nrHcJi7tzKh-9LlaC3QSGKdnGGuxzU9z0htvw/exec"

def _parse_float(val, default=0.0) -> float:
    if val is None: return default
    s = str(val).strip().replace(" ", "").replace("%", "").replace(",", ".")
    try: return float(s)
    except ValueError: return default

def _format_money(val: float) -> str:
    rounded = int(round(val))
    return f"{rounded:,} ₽".replace(",", " ")

def load_base_rates_and_coefficients(sheet_name: str = "") -> dict:
    raw_data = RepairDataSync.get_data()
    coeffs_dict = {"engineering": {}, "finishing": {}, "all": {}}
    for c in raw_data.get("coefficients", []):
        c_type = str(c.get("type", "")).strip().lower()
        c_id = c.get("id")
        coef_data = {"name": c.get("name", ""), "value": c.get("value", 0.0)}
        if "инженерия" in c_type: coeffs_dict["engineering"][c_id] = coef_data
        elif "отделка" in c_type: coeffs_dict["finishing"][c_id] = coef_data
        elif "все" in c_type or "all" in c_type: coeffs_dict["all"][c_id] = coef_data
    rates = raw_data.get("base_rates", {})
    return {
        "base_rates": {"engineering": rates.get("engineering_work", 22162.0), "finishing": rates.get("finishing_work", 41405.0)},
        "coefficients": coeffs_dict
    }

def load_repair_estimate_settings() -> dict:
    return RepairDataSync.get_data()

def get_k_state(state_name: str) -> float:
    s = state_name.lower()
    if "застройщика" in s: return 1.2
    if "вторичка" in s:
        if "нужен" in s or "демонтаж" in s and "без" not in s and "выполнен" not in s: return 1.2
    if "вайтбокс" in s:
        if "без" in s: return 0.9
        if "с демонтаж" in s: return 1.15
    return 1.0

def calculate_eng_duration(area: float, state_name: str, tariff_name: str) -> int:
    if area <= 0: return 0
    if area < 40.0: k_area = 1.7
    elif area <= 60.0: k_area = 1.5
    else: k_area = 1.2
    k_state = get_k_state(state_name)
    t = tariff_name.lower()
    k_tariff = 1.1 if "комфорт" in t else (1.15 if "бизнес" in t else (1.2 if "люкс" in t else 1.0))
    return max(1, int(round(area * k_area * k_state * k_tariff)))

def calculate_fin_duration(area: float, state_name: str, tariff_name: str) -> int:
    if area <= 0: return 0
    if area < 40.0: k_area = 2.0
    elif area <= 60.0: k_area = 1.7
    else: k_area = 1.3
    k_state = get_k_state(state_name)
    t = tariff_name.lower()
    k_tariff = 1.2 if "комфорт" in t else (1.25 if "бизнес" in t else (1.3 if "люкс" in t else 1.0))
    return max(1, int(round(area * k_area * k_state * k_tariff)))

def _distribute_stages(area: float, work_total: float, material_rate: float, stages_data: list, total_days: int) -> dict:
    mat_total = area * material_rate
    grand_total = work_total + mat_total

    w_sum, m_sum, d_sum = sum(s["w_share"] for s in stages_data), sum(s["m_share"] for s in stages_data), sum(s["days"] for s in stages_data)
    if w_sum > 0:
        for s in stages_data: s["w_share"] /= w_sum
    if m_sum > 0:
        for s in stages_data: s["m_share"] /= m_sum

    allocated_days = [max(1, int(round(total_days * (s["days"] / d_sum)))) for s in stages_data] if d_sum > 0 else [max(1, int(round(total_days / len(stages_data)))) for _ in stages_data]
    diff_days = total_days - sum(allocated_days)
    if diff_days != 0 and allocated_days: allocated_days[allocated_days.index(max(allocated_days))] += diff_days

    calculated_stages = []
    for idx, s in enumerate(stages_data):
        c_work, c_mat = work_total * s["w_share"], mat_total * s["m_share"]
        calculated_stages.append({
            "num": s["num"], "title": s["title"], "days": allocated_days[idx], "work_cost": c_work,
            "mat_cost": c_mat, "stage_total": c_work + c_mat, "work_desc": s["w_desc"], "mat_desc": s["m_desc"],
        })

    return {
        "work_total": work_total, "mat_total": mat_total, "grand_total": grand_total,
        "total_days": total_days, "total_months": int(round(total_days / 22.0)), "stages": calculated_stages,
    }

def calculate_engineering_stages(area: float, work_total: float, state_name: str = "", tariff_name: str = "", config: dict = None) -> dict:
    total_days = calculate_eng_duration(area, state_name, tariff_name)
    stages = [dict(s) for s in config["eng_stages"]]
    s_lower = state_name.lower()
    if (("с демонтаж" in s_lower) or ("застройщика" in s_lower) or ("нужен демонтаж" in s_lower)) and len(stages) > 0:
        stages[0]["title"] = "1. Демонтажные и подготовительные работы"
    return _distribute_stages(area, work_total, config["base_rates"]["engineering_mat"], stages, total_days)

def calculate_finishing_stages(area: float, work_total: float, state_name: str = "", tariff_name: str = "", config: dict = None) -> dict:
    total_days = calculate_fin_duration(area, state_name, tariff_name)
    stages = [dict(s) for s in config["fin_stages"]]
    return _distribute_stages(area, work_total, config["base_rates"]["finishing_mat"], stages, total_days)

def generate_universal_estimate_presentation(project_data: dict) -> dict:
    cfg = load_repair_estimate_settings()
    folder_id = cfg["base_rates"]["folder_id"]

    repair_type = project_data.get("repair_type", "engineering")
    area = float(project_data.get("area", 0.0))
    eng_cost = float(project_data.get("eng_cost", 0.0))
    fin_cost = float(project_data.get("fin_cost", 0.0))
    furniture_cost = float(project_data.get("furniture_cost", 0.0))
    appliances_cost = float(project_data.get("appliances_cost", 0.0))
    
    address = str(project_data.get("address", "Объект")).strip()
    client_name = str(project_data.get("client_name", "Заказчик")).strip()
    state_name = str(project_data.get("state", "Голый бетон")).strip()
    
    eng_model = calculate_engineering_stages(area, eng_cost, state_name, "Комфорт", cfg)
    fin_model = calculate_finishing_stages(area, fin_cost, state_name, "Комфорт", cfg)

    today_str = datetime.now().strftime("%d.%m.%Y")
    replacements = {
        "{Адрес}": address, "{м2}": f"{area:g}", "{Имя}": client_name,
        "{Состояние}": state_name, "{сегодня}": today_str,
    }

    if repair_type == "engineering":
        template_id = cfg["base_rates"]["template_eng"]
        doc_title = f'RE Инженерный ремонт "{address}" | {area:g} м2'
        
        replacements.update({
            "{Цена ИР}": _format_money(eng_model["work_total"]),
            "{Цена МИР}": _format_money(eng_model["mat_total"]),
            "{Цена ИР+М}": _format_money(eng_model["grand_total"]),
            "{Цена ИРм2}": _format_money(eng_model['work_total'] / area) if area else "0 ₽",
            "{Цена МИРм2}": _format_money(eng_model['mat_total'] / area) if area else "0 ₽",
            "{Цена ИР+Мм2}": _format_money(eng_model['grand_total'] / area) if area else "0 ₽",
            "{СрокД ИР}": f"{eng_model['total_days']} раб. дней",
            "{СрокМ ИР}": f"~{eng_model['total_months']} месяцев",
        })
        for idx, st in enumerate(eng_model["stages"], start=1):
            replacements.update({
                f"{{{idx}ТипИ}}": st["title"], f"{{{idx}СрокИ}}": f"{st['days']} раб. дней", f"{{{idx}Сроки}}": f"{st['days']} раб. дней",
                f"{{{idx}СРИ}}": _format_money(st["work_cost"]), f"{{{idx}СЧМИ}}": _format_money(st["mat_cost"]),
                f"{{{idx}СЧЭИ}}": _format_money(st["stage_total"]), f"{{{idx}ОРИ}}": st["work_desc"], f"{{{idx}ЧМИ}}": st["mat_desc"],
            })

    elif repair_type == "finishing":
        template_id = cfg["base_rates"]["template_fin"]
        doc_title = f'RE Отделочные работы "{address}" | {area:g} м2'
        
        replacements.update({
            "{Цена ОР}": _format_money(fin_model["work_total"]),
            "{Цена МОР}": _format_money(fin_model["mat_total"]),
            "{Цена ОР+ОМ}": _format_money(fin_model["grand_total"]),
            "{Цена ОРм2}": _format_money(fin_model['work_total'] / area) if area else "0 ₽",
            "{Цена МОРм2}": _format_money(fin_model['mat_total'] / area) if area else "0 ₽",
            "{Цена ОР+ОМм2}": _format_money(fin_model['grand_total'] / area) if area else "0 ₽",
            "{СрокД ОР}": f"{fin_model['total_days']} раб. дней",
            "{СрокМ ОР}": f"~{fin_model['total_months']} месяцев",
        })
        for idx, st in enumerate(fin_model["stages"], start=1):
            replacements.update({
                f"{{{idx}ТипО}}": st["title"], f"{{{idx}СрокО}}": f"{st['days']} раб. дней",
                f"{{{idx}СРО}}": _format_money(st["work_cost"]), f"{{{idx}СЧМО}}": _format_money(st["mat_cost"]),
                f"{{{idx}СЧЭО}}": _format_money(st["stage_total"]), f"{{{idx}ОРО}}": st["work_desc"], f"{{{idx}ЧМО}}": st["mat_desc"],
            })

    else:
        template_id = cfg["base_rates"]["template_complex"]
        doc_title = f'RE Комплексный ремонт "{address}" | {area:g} м2'
        complex_total = eng_model["grand_total"] + fin_model["grand_total"] + furniture_cost + appliances_cost
        complex_days = eng_model['total_days'] + fin_model['total_days']
        
        replacements.update({
            "{Цена ИР}": _format_money(eng_model["work_total"]),
            "{Цена МИР}": _format_money(eng_model["mat_total"]),
            "{Цена ИР+М}": _format_money(eng_model["grand_total"]),
            "{Цена ИРм2}": _format_money(eng_model['work_total'] / area) if area else "0 ₽",
            "{Цена МИРм2}": _format_money(eng_model['mat_total'] / area) if area else "0 ₽",
            "{Цена ИР+Мм2}": _format_money(eng_model['grand_total'] / area) if area else "0 ₽",
            "{СрокД ИР}": f"{eng_model['total_days']} раб. дней",
            "{СрокМ ИР}": f"~{eng_model['total_months']} месяцев",
            
            "{Цена ОР}": _format_money(fin_model["work_total"]),
            "{Цена МОР}": _format_money(fin_model["mat_total"]),
            "{Цена ОР+ОМ}": _format_money(fin_model["grand_total"]),
            "{Цена ОРм2}": _format_money(fin_model['work_total'] / area) if area else "0 ₽",
            "{Цена МОРм2}": _format_money(fin_model['mat_total'] / area) if area else "0 ₽",
            "{Цена ОР+ОМм2}": _format_money(fin_model['grand_total'] / area) if area else "0 ₽",
            "{СрокД ОР}": f"{fin_model['total_days']} раб. дней",
            "{СрокМ ОР}": f"~{fin_model['total_months']} месяцев",

            "{Цена КР}": _format_money(eng_model["work_total"] + fin_model["work_total"]),
            "{Цена МКР}": _format_money(eng_model["mat_total"] + fin_model["mat_total"]),
            "{Цена КР+М}": _format_money(complex_total),
            "{Цена КР+Мм2}": _format_money(complex_total / area) if area else "0 ₽",
            "{Полнбюдж КР+М}": _format_money(complex_total),
            "{Полнбюдж КР+Мм2}": _format_money(complex_total / area) if area else "0 ₽",
            
            "{СрокД КР}": f"{complex_days} раб. дней",
            "{СрокМ КР}": f"~{int(round(complex_days / 22.0))} месяцев",
            
            "{Меб КР}": _format_money(furniture_cost),
            "{Тех КР}": _format_money(appliances_cost),
        })
        
        for idx, st in enumerate(eng_model["stages"], start=1):
            replacements.update({
                f"{{{idx}ТипИ}}": st["title"], f"{{{idx}СрокИ}}": f"{st['days']} раб. дней", f"{{{idx}Сроки}}": f"{st['days']} раб. дней",
                f"{{{idx}СРИ}}": _format_money(st["work_cost"]), f"{{{idx}СЧМИ}}": _format_money(st["mat_cost"]),
                f"{{{idx}СЧЭИ}}": _format_money(st["stage_total"]), f"{{{idx}ОРИ}}": st["work_desc"], f"{{{idx}ЧМИ}}": st["mat_desc"],
            })
        for idx, st in enumerate(fin_model["stages"], start=1):
            replacements.update({
                f"{{{idx}ТипО}}": st["title"], f"{{{idx}СрокО}}": f"{st['days']} раб. дней",
                f"{{{idx}СРО}}": _format_money(st["work_cost"]), f"{{{idx}СЧМО}}": _format_money(st["mat_cost"]),
                f"{{{idx}СЧЭО}}": _format_money(st["stage_total"]), f"{{{idx}ОРО}}": st["work_desc"], f"{{{idx}ЧМО}}": st["mat_desc"],
            })

    payload = {
        "template_id": template_id, "folder_id": folder_id,
        "title": doc_title, "fileName": doc_title, "name": doc_title, "doc_title": doc_title,
        "address": address, "area": f"{area:g}", "client_name": client_name, "replacements": replacements
    }

    headers = {"Content-Type": "text/plain;charset=utf-8"}
    raw_data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    response = requests.post(WEB_APP_URL, data=raw_data, headers=headers, timeout=120, allow_redirects=True)
    text_resp = response.text.strip()
    
    try: res_data = json.loads(text_resp)
    except Exception: raise RuntimeError(f"Ответ сервера не JSON: {text_resp[:200]}")
    if res_data.get("status") != "ok": raise RuntimeError(f"Ошибка скрипта: {res_data.get('message')}")

    return {
        "presentation_id": res_data.get("presentation_id"), "title": doc_title,
        "edit_url": res_data.get("presentation_url"), "pdf_url": res_data.get("pdf_url"),
    }