import json
import time
from datetime import datetime
import requests
from apps.core.sheets import RepairDataSync

WEB_APP_URL = "https://script.google.com/macros/s/AKfycbxN7gEgP0ds1u5niMtdLLgTs6Qo20Hb2nrHcJi7tzKh-9LlaC3QSGKdnGGuxzU9z0htvw/exec"

def _format_money(val: float) -> str:
    return f"{int(round(val)):,} ₽".replace(",", " ")

def get_k_state(state_name: str) -> float:
    s = state_name.lower()
    if "застройщика" in s: return 1.2
    if "вторичка" in s:
        if ("нужен" in s or "демонтаж" in s) and "без" not in s and "выполнен" not in s: return 1.2
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
    return max(1, int(round(area * k_area * get_k_state(state_name) * (1.1 if "комфорт" in tariff_name.lower() else 1.0))))

def calculate_fin_duration(area: float, state_name: str, tariff_name: str) -> int:
    if area <= 0: return 0
    if area < 40.0: k_area = 2.0
    elif area <= 60.0: k_area = 1.7
    else: k_area = 1.3
    return max(1, int(round(area * k_area * get_k_state(state_name) * (1.2 if "комфорт" in tariff_name.lower() else 1.0))))

def _distribute_stages(work_total: float, mat_total: float, stages_data: list, total_days: int) -> dict:
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

    return {"work_total": work_total, "mat_total": mat_total, "grand_total": work_total + mat_total, "total_days": total_days, "total_months": int(round(total_days / 22.0)), "stages": calculated_stages}

def generate_whitebox_estimate_presentation(project_data: dict) -> dict:
    cfg = RepairDataSync.get_data()
    folder_id = cfg.get("base_rates", {}).get("folder_id", "")
    template_id = cfg.get("base_rates", {}).get("template_whitebox", cfg.get("base_rates", {}).get("template_complex", ""))
    
    area = float(project_data.get("area", 0.0))
    eng_cost = float(project_data.get("eng_cost", 0.0)) 
    fin_cost = float(project_data.get("fin_cost", 0.0))
    eng_mat_cost = float(project_data.get("eng_mat_cost", 0.0)) 
    fin_mat_cost = float(project_data.get("fin_mat_cost", 0.0))
    
    address = str(project_data.get("address", "Объект")).strip()
    client_name = str(project_data.get("client_name", "Заказчик")).strip()
    state_name = str(project_data.get("state", "Голый бетон")).strip()
    s_lower = state_name.lower()
    doc_title = f'RE Сравнение Вайтбокс "{address}" | {area:g} м2'

    val_demo = 0.10 if "частичн" in s_lower else 0.15
    val_nodemo = -0.10
    for c in cfg.get("coefficients", []):
        c_name = c["name"].lower()
        if "вайтбокс" in c_name:
            if "частичн" in s_lower and "частичн" in c_name:
                val_demo = c["value"]
            elif "частичн" not in s_lower and "с демонтаж" in c_name and "частичн" not in c_name:
                val_demo = c["value"]
            elif "без" in c_name:
                val_nodemo = c["value"]

    days_100_wb = max(1, calculate_eng_duration(area, "Вайтбокс (Без демонтажа)", "Комфорт"))
    days_60_wb = max(1, int(round(days_100_wb * 0.6)))
    
    stages_B = [dict(s) for s in cfg.get("eng_stages", [])]
    eng_model_B = _distribute_stages(eng_cost, eng_mat_cost, stages_B, days_60_wb)

    eng_work_100_demo = eng_cost / 0.6 if eng_cost > 0 else 0
    eng_mat_100_demo = eng_mat_cost / 0.6 if eng_mat_cost > 0 else 0
    days_100_demo = max(1, calculate_eng_duration(area, state_name, "Комфорт"))
    
    stages_A = [dict(s) for s in cfg.get("eng_stages", [])]
    if len(stages_A) > 0:
        stages_A[0]["title"] = "1. Демонтажные и подготовительные работы"
        
    premium_ratio = max(0.0, min(0.9, (val_demo - val_nodemo) / (1.0 + max(0.0, val_demo))))
    premium_work = eng_work_100_demo * premium_ratio
    premium_mat = eng_mat_100_demo * premium_ratio
    
    days_demo_k = get_k_state(state_name) 
    days_nodemo_k = get_k_state("Вайтбокс (Без демонтажа)") 
    days_premium_ratio = max(0.0, min(0.9, (days_demo_k - days_nodemo_k) / days_demo_k))
    premium_days = int(round(days_100_demo * days_premium_ratio))
    
    eng_model_A = _distribute_stages(eng_work_100_demo - premium_work, eng_mat_100_demo - premium_mat, stages_A, max(1, days_100_demo - premium_days))
    
    eng_model_A["stages"][0]["work_cost"] += premium_work
    eng_model_A["stages"][0]["mat_cost"] += premium_mat
    eng_model_A["stages"][0]["stage_total"] += (premium_work + premium_mat)
    eng_model_A["stages"][0]["days"] += premium_days
    eng_model_A["work_total"] = eng_work_100_demo
    eng_model_A["mat_total"] = eng_mat_100_demo
    eng_model_A["grand_total"] = eng_work_100_demo + eng_mat_100_demo
    eng_model_A["total_days"] = days_100_demo
    
    fin_days = calculate_fin_duration(area, state_name, "Комфорт")
    fin_model = _distribute_stages(fin_cost, fin_mat_cost, [dict(s) for s in cfg.get("fin_stages", [])], fin_days)

    total_A = eng_model_A["grand_total"] + fin_model["grand_total"]
    total_B = eng_model_B["grand_total"] + fin_model["grand_total"]
    
    complex_days_A = eng_model_A['total_days'] + fin_model['total_days']
    complex_days_B = eng_model_B['total_days'] + fin_model['total_days']

    replacements = {
        "{Адрес}": address, "{м2}": f"{area:g}", "{Имя}": client_name, "{Состояние}": state_name, "{сегодня}": datetime.now().strftime("%d.%m.%Y"),
        
        "{Разница ИР}": _format_money(eng_model_A["work_total"] - eng_model_B["work_total"]),
        "{Разница МИР}": _format_money(eng_model_A["mat_total"] - eng_model_B["mat_total"]),
        "{Разница}": _format_money(total_A - total_B),
        "{Разница м2}": _format_money((total_A - total_B) / area) if area else "0 ₽",
        "{Разница срок}": f"{complex_days_A - complex_days_B} раб. дней",
        "{Разница СрокИ}": f"{eng_model_A['total_days'] - eng_model_B['total_days']} раб. дней",
        "{Разница СрокО}": "0 раб. дней",
        "{Разница %}": f"{int(round(((total_A - total_B) / total_A) * 100)) if total_A > 0 else 0}%",

        "{Цена ИР Д}": _format_money(eng_model_A["work_total"]),
        "{Цена МИР Д}": _format_money(eng_model_A["mat_total"]),
        "{Цена ИР+М Д}": _format_money(eng_model_A["grand_total"]),
        "{СрокД ИР Д}": f"{eng_model_A['total_days']} раб. дней",
        "{ИТОГО Д}": _format_money(total_A),
        "{ИТОГО Дм2}": _format_money(total_A / area) if area else "0 ₽",
        "{Срок Д}": f"{complex_days_A} раб. дней",

        "{Цена ИР Б}": _format_money(eng_model_B["work_total"]),
        "{Цена МИР Б}": _format_money(eng_model_B["mat_total"]),
        "{Цена ИР+М Б}": _format_money(eng_model_B["grand_total"]),
        "{СрокД ИР Б}": f"{eng_model_B['total_days']} раб. дней",
        "{ИТОГО Б}": _format_money(total_B),
        "{ИТОГО Бм2}": _format_money(total_B / area) if area else "0 ₽",
        "{Срок Б}": f"{complex_days_B} раб. дней",

        "{Цена ИР+М}": _format_money(eng_model_A["grand_total"]),
        "{Цена КР+М}": _format_money(total_A),
        "{Цена КР+Мм2}": _format_money(total_A / area) if area else "0 ₽",
        "{Цена КРм2}": _format_money(total_A / area) if area else "0 ₽",
        "{СрокД КР}": f"{complex_days_A} раб. дней",
        "{СрокМ КР}": f"~{int(round(complex_days_A / 22.0))} месяцев",

        "{Цена ОР}": _format_money(fin_model["work_total"]),
        "{Цена МОР}": _format_money(fin_model["mat_total"]),
        "{Цена ОР+ОМ}": _format_money(fin_model["grand_total"]),
        "{СрокД ОР}": f"{fin_model['total_days']} раб. дней",
        "{СрокД ОР Д}": f"{fin_model['total_days']} раб. дней",
        "{СрокД ОР Б}": f"{fin_model['total_days']} раб. дней",
        "{СрокМ ОР}": f"~{fin_model['total_months']} месяцев",
    }

    for idx, st in enumerate(eng_model_A["stages"], start=1):
        replacements.update({f"{{{idx}СрокИ Д}}": f"{st['days']} раб. дней", f"{{{idx}СРИ Д}}": _format_money(st["work_cost"]), f"{{{idx}СЧМИ Д}}": _format_money(st["mat_cost"]), f"{{{idx}СЧЭИ Д}}": _format_money(st["stage_total"])})
    for idx, st in enumerate(eng_model_B["stages"], start=1):
        replacements.update({f"{{{idx}СрокИ Б}}": f"{st['days']} раб. дней", f"{{{idx}СРИ Б}}": _format_money(st["work_cost"]), f"{{{idx}СЧМИ Б}}": _format_money(st["mat_cost"]), f"{{{idx}СЧЭИ Б}}": _format_money(st["stage_total"])})
    for idx, st in enumerate(fin_model["stages"], start=1):
        replacements.update({f"{{{idx}СрокО Д}}": f"{st['days']} раб. дней", f"{{{idx}СрокО Б}}": f"{st['days']} раб. дней", f"{{{idx}СРО}}": _format_money(st["work_cost"]), f"{{{idx}СЧМО}}": _format_money(st["mat_cost"]), f"{{{idx}СЧЭО}}": _format_money(st["stage_total"])})

    payload = {"template_id": template_id, "folder_id": folder_id, "title": doc_title, "fileName": doc_title, "name": doc_title, "doc_title": doc_title, "address": address, "area": f"{area:g}", "client_name": client_name, "replacements": replacements}
    
    max_retries = 3
    text_resp = ""
    for attempt in range(max_retries):
        try:
            response = requests.post(WEB_APP_URL, data=json.dumps(payload, ensure_ascii=False).encode("utf-8"), headers={"Content-Type": "text/plain;charset=utf-8"}, timeout=120, allow_redirects=True)
            text_resp = response.text.strip()
            break
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(2)
            else:
                raise RuntimeError(f"Ошибка сети (сброс соединения) после {max_retries} попыток: {e}")

    res_data = json.loads(text_resp)
    if res_data.get("status") != "ok": raise RuntimeError(f"Ошибка скрипта: {res_data.get('message')}")

    return {"presentation_id": res_data.get("presentation_id"), "title": doc_title, "edit_url": res_data.get("presentation_url"), "pdf_url": res_data.get("pdf_url")}