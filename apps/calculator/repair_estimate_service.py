import json
import math
import re
from datetime import datetime
import requests
from apps.core.sheets import RepairDataSync

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
        if ("нужен" in s or "демонтаж" in s) and "без" not in s and "выполнен" not in s:
            return 1.2
    if "вайтбокс" in s:
        if "без" in s: return 0.9
        if "частичн" in s: return 1.10
        if "с демонтаж" in s or "демонтаж" in s: return 1.15
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

def _distribute_stages(area: float, work_total: float, mat_total: float, stages_data: list, total_days: int) -> dict:
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

def calculate_engineering_stages(area: float, work_total: float, mat_total: float, state_name: str = "", tariff_name: str = "", config: dict = None) -> dict:
    total_days = calculate_eng_duration(area, state_name, tariff_name)
    stages = [dict(s) for s in config["eng_stages"]]
    s_lower = state_name.lower()
    
    is_wb_demo = ("вайтбокс" in s_lower and ("демонтаж" in s_lower or "частичн" in s_lower) and "без" not in s_lower)
    is_secondary_demo = (
        ("вторичка" in s_lower and ("нужен" in s_lower or "демонтаж" in s_lower) and "без" not in s_lower and "выполнен" not in s_lower)
        or ("застройщика" in s_lower)
    )

    if (is_wb_demo or is_secondary_demo) and len(stages) > 0:
        stages[0]["title"] = "1. Демонтажные и подготовительные работы"

        if is_wb_demo:
            # Изоляция для Вайтбокса (С полным или частичным демонтажем) относительно Вайтбокса без демонтажа
            val_demo = 0.10 if "частичн" in s_lower else 0.15
            val_nodemo = -0.10
            for c in config.get("coefficients", []):
                c_name = c["name"].lower()
                if "вайтбокс" in c_name:
                    if "частичн" in s_lower and "частичн" in c_name:
                        val_demo = c["value"]
                    elif "частичн" not in s_lower and "с демонтаж" in c_name and "частичн" not in c_name:
                        val_demo = c["value"]
                    elif "без" in c_name:
                        val_nodemo = c["value"]
            
            base_state_for_days = "Вайтбокс (Без демонтажа)"
        else:
            # Изоляция для Вторички с демонтажем / От застройщика относительно Голого бетона (0.0)
            val_demo = 0.20
            val_nodemo = 0.0
            for c in config.get("coefficients", []):
                c_name = c["name"].lower()
                if ("вторичка" in s_lower and "вторичка" in c_name and ("нужен" in c_name or "демонтаж" in c_name) and "без" not in c_name and "выполнен" not in c_name):
                    val_demo = c["value"]
                elif ("застройщика" in s_lower and "застройщика" in c_name):
                    val_demo = c["value"]
            
            base_state_for_days = "Голый бетон"

        premium_ratio = max(0.0, min(0.9, (val_demo - val_nodemo) / (1.0 + max(0.0, val_demo))))
        premium_work = work_total * premium_ratio
        premium_mat = mat_total * premium_ratio
        
        days_demo_k = get_k_state(state_name)
        days_nodemo_k = get_k_state(base_state_for_days)
        days_premium_ratio = max(0.0, min(0.9, (days_demo_k - days_nodemo_k) / days_demo_k)) if days_demo_k > 0 else 0.0
        premium_days = int(round(total_days * days_premium_ratio))
        
        res = _distribute_stages(area, work_total - premium_work, mat_total - premium_mat, stages, max(1, total_days - premium_days))
        
        res["stages"][0]["work_cost"] += premium_work
        res["stages"][0]["mat_cost"] += premium_mat
        res["stages"][0]["stage_total"] += (premium_work + premium_mat)
        res["stages"][0]["days"] += premium_days
        
        res["work_total"] = work_total
        res["mat_total"] = mat_total
        res["grand_total"] = work_total + mat_total
        res["total_days"] = total_days
        res["total_months"] = int(round(total_days / 22.0))
        return res

    return _distribute_stages(area, work_total, mat_total, stages, total_days)

def calculate_finishing_stages(area: float, work_total: float, mat_total: float, state_name: str = "", tariff_name: str = "", config: dict = None) -> dict:
    total_days = calculate_fin_duration(area, state_name, tariff_name)
    stages = [dict(s) for s in config["fin_stages"]]
    return _distribute_stages(area, work_total, mat_total, stages, total_days)

def generate_universal_estimate_presentation(project_data: dict) -> dict:
    cfg = load_repair_estimate_settings()
    folder_id = cfg["base_rates"]["folder_id"]

    repair_type = project_data.get("repair_type", "engineering")
    area = float(project_data.get("area", 0.0))
    eng_cost = float(project_data.get("eng_cost", 0.0))
    fin_cost = float(project_data.get("fin_cost", 0.0))
    eng_mat_cost = float(project_data.get("eng_mat_cost", 0.0))
    fin_mat_cost = float(project_data.get("fin_mat_cost", 0.0))
    furniture_cost = float(project_data.get("furniture_cost", 0.0))
    appliances_cost = float(project_data.get("appliances_cost", 0.0))
    
    address = str(project_data.get("address", "Объект")).strip()
    client_name = str(project_data.get("client_name", "Заказчик")).strip()
    state_name = str(project_data.get("state", "Голый бетон")).strip()
    
    eng_model = calculate_engineering_stages(area, eng_cost, eng_mat_cost, state_name, "Комфорт", cfg)
    fin_model = calculate_finishing_stages(area, fin_cost, fin_mat_cost, state_name, "Комфорт", cfg)

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
        
        repair_total = eng_model["grand_total"] + fin_model["grand_total"]
        full_budget_total = repair_total + furniture_cost + appliances_cost
        complex_days = eng_model['total_days'] + fin_model['total_days']
        
        replacements.update({
            # Инженерия
            "{Цена ИР}": _format_money(eng_model["work_total"]),
            "{Цена МИР}": _format_money(eng_model["mat_total"]),
            "{Цена ИР+М}": _format_money(eng_model["grand_total"]),
            "{Цена ИРм2}": _format_money(eng_model['work_total'] / area) if area else "0 ₽",
            "{Цена МИРм2}": _format_money(eng_model['mat_total'] / area) if area else "0 ₽",
            "{Цена ИР+Мм2}": _format_money(eng_model['grand_total'] / area) if area else "0 ₽",
            "{СрокД ИР}": f"{eng_model['total_days']} раб. дней",
            "{СрокМ ИР}": f"~{eng_model['total_months']} месяцев",
            
            # Отделка
            "{Цена ОР}": _format_money(fin_model["work_total"]),
            "{Цена МОР}": _format_money(fin_model["mat_total"]),
            "{Цена ОР+ОМ}": _format_money(fin_model["grand_total"]),
            "{Цена ОРм2}": _format_money(fin_model['work_total'] / area) if area else "0 ₽",
            "{Цена МОРм2}": _format_money(fin_model['mat_total'] / area) if area else "0 ₽",
            "{Цена ОР+ОМм2}": _format_money(fin_model['grand_total'] / area) if area else "0 ₽",
            "{СрокД ОР}": f"{fin_model['total_days']} раб. дней",
            "{СрокМ ОР}": f"~{fin_model['total_months']} месяцев",

            # Комплекс
            "{Цена КР}": _format_money(eng_model["work_total"] + fin_model["work_total"]),
            "{Цена МКР}": _format_money(eng_model["mat_total"] + fin_model["mat_total"]),
            "{Цена КР+М}": _format_money(repair_total),
            "{Цена КР+Мм2}": _format_money(repair_total / area) if area else "0 ₽",
            "{Полнбюдж КР+М}": _format_money(full_budget_total),
            "{Полнбюдж КР+Мм2}": _format_money(full_budget_total / area) if area else "0 ₽",
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