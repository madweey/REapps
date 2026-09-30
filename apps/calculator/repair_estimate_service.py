import json
import math
import re
from datetime import datetime
import requests
from apps.core.sheets_client import get_main_spreadsheet


# URL развернутого веб-приложения Google Apps Script
WEB_APP_URL = "https://script.google.com/macros/s/AKfycbxN7gEgP0ds1u5niMtdLLgTs6Qo20Hb2nrHcJi7tzKh-9LlaC3QSGKdnGGuxzU9z0htvw/exec"


def _parse_float(val, default=0.0) -> float:
    if val is None:
        return default
    s = str(val).strip().replace(" ", "").replace("%", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return default


def _format_money(val: float) -> str:
    rounded = int(round(val))
    return f"{rounded:,} ₽".replace(",", " ")


def calculate_dynamic_duration_days(area: float, state_name: str = "", tariff_name: str = "") -> int:
    """
    Расчёт итогового срока инженерного ремонта в рабочих днях по формуле:
    B4 * K_area * K_state * K_tariff
    """
    if area <= 0:
        return 0

    # 1. Коэффициент по площади (B4)
    if area < 40.0:
        k_area = 1.7
    elif area <= 60.0:
        k_area = 1.5
    else:
        k_area = 1.2

    # 2. Коэффициент состояния объекта (B5)
    s_lower = str(state_name).lower()
    if "вайтбокс (с демонтаж" in s_lower or ("вайтбокс" in s_lower and "демонтаж" in s_lower and "без" not in s_lower):
        k_state = 1.15
    elif "вайтбокс" in s_lower and "без демонтажа" in s_lower:
        k_state = 0.9
    elif "отделка от застройщика" in s_lower:
        k_state = 1.2
    elif "вторичка" in s_lower:
        k_state = 1.2
    else:
        # Голый бетон / новостройка без демонтажа
        k_state = 1.0

    # 3. Коэффициент тарифа (B11)
    t_lower = str(tariff_name).lower()
    if "комфорт" in t_lower:
        k_tariff = 1.1
    elif "бизнес" in t_lower:
        k_tariff = 1.15
    elif "люкс" in t_lower:
        k_tariff = 1.2
    else:
        k_tariff = 1.0

    total_days = round(area * k_area * k_state * k_tariff)
    return max(1, int(total_days))


def load_repair_estimate_settings() -> dict:
    """
    Загружает параметры этапов инженерного ремонта из листа 'Настройка_Ремонт'
    (диапазон L:R для этапов 1-7, ячейки L11:M13 для настроек шаблона и материалов).
    """
    default_template_id = "1oakVh-dtwWQGDCXSNQZc_Zs9tOjJtMoG5zZSKIAcabQ"
    default_folder_id = "1kLOMyKkU9YLx5PfqUHUDfDhNR3x6xGhq"
    default_material_rate = 29475.0

    template_id = default_template_id
    folder_id = default_folder_id
    material_rate = default_material_rate

    try:
        sh = get_main_spreadsheet()
        ws = sh.worksheet("Настройка_Ремонт")
        all_vals = ws.get_all_values()
    except Exception as e:
        print(f"[RepairEstimateService] Ошибка загрузки листа 'Настройка_Ремонт': {e}")
        all_vals = []

    # Чтение настроек (L11:M13)
    for row in all_vals[10:16]:
        if len(row) > 12:
            key_name = str(row[11]).strip().lower()
            val_col = str(row[12]).strip()
            if "материал" in key_name:
                material_rate = _parse_float(val_col, default_material_rate)
            elif "шаблон" in key_name and val_col:
                template_id = val_col
            elif "папк" in key_name and val_col:
                folder_id = val_col

    # 7 этапов (строки 2-8, колонки L:R -> индексы 11:18)
    stages = []
    for r_idx in range(1, 8):
        if r_idx < len(all_vals) and len(all_vals[r_idx]) > 17:
            row = all_vals[r_idx]
            num = int(_parse_float(row[11], r_idx))
            title = str(row[12]).strip() or f"Этап {num}"
            work_share = _parse_float(row[13], 0.0)
            mat_share = _parse_float(row[14], 0.0)
            days = int(_parse_float(row[15], 10))
            work_desc = str(row[16]).strip()
            mat_desc = str(row[17]).strip()

            stages.append({
                "num": num,
                "title": title,
                "work_share": work_share,
                "mat_share": mat_share,
                "days": days,
                "work_desc": work_desc,
                "mat_desc": mat_desc,
            })
        else:
            stages.append({
                "num": r_idx,
                "title": f"Этап {r_idx}",
                "work_share": 0.14,
                "mat_share": 0.14,
                "days": 14,
                "work_desc": "",
                "mat_desc": "",
            })

    return {
        "template_id": template_id,
        "folder_id": folder_id,
        "material_rate": material_rate,
        "stages": stages,
    }


def calculate_engineering_stages(area: float,
                                 work_total: float,
                                 has_demolition: bool = False,
                                 state_name: str = "",
                                 tariff_name: str = "",
                                 material_rate: float = 29475.0,
                                 custom_stages: list = None) -> dict:
    """
    Рассчитывает полную модель:
    - Общий срок по формуле калькулятора
    - Пропорциональное распределение дней по этапам (11%, 10%, 10%, 16%, 21%, 16%, 16%)
    - Доли работ и материалов по 7 этапам
    """
    if custom_stages:
        stages_data = [dict(s) for s in custom_stages]
    else:
        cfg = load_repair_estimate_settings()
        stages_data = [dict(s) for s in cfg["stages"]]
        material_rate = cfg.get("material_rate", material_rate)

    mat_total = area * material_rate
    grand_total = work_total + mat_total

    # Итоговый динамический срок в рабочих днях
    total_days = calculate_dynamic_duration_days(area, state_name=state_name, tariff_name=tariff_name)

    # Доли сроков по 7 этапам: 11%, 10%, 10%, 16%, 21%, 16%, 16%
    if has_demolition:
        days_shares = [0.11, 0.10, 0.10, 0.16, 0.21, 0.16, 0.16]
        stages_data[0]["title"] = "1. Демонтажные и подготовительные работы"
        stages_data[0]["work_share"] = 0.12
        if "Демонтаж" not in stages_data[0]["work_desc"]:
            stages_data[0]["work_desc"] = (
                "Комплексный демонтаж перегородок, стяжки и старых сетей. "
                + stages_data[0]["work_desc"]
            ).strip()

        base_rem_sum = sum(s["work_share"] for s in stages_data[1:])
        scale = 0.88 / base_rem_sum if base_rem_sum > 0 else 1.0
        for s in stages_data[1:]:
            s["work_share"] = s["work_share"] * scale
    else:
        # Без демонтажа подготовительный этап занимает меньше времени (3%), остальное перераспределяется
        days_shares = [0.03, 0.11, 0.11, 0.18, 0.23, 0.17, 0.17]
        stages_data[0]["title"] = "1. Подготовительные работы"
        stages_data[0]["work_share"] = 0.03

        base_rem_sum = sum(s["work_share"] for s in stages_data[1:])
        scale = 0.97 / base_rem_sum if base_rem_sum > 0 else 1.0
        for s in stages_data[1:]:
            s["work_share"] = s["work_share"] * scale

    # Нормирование долей материалов
    mat_sum = sum(s["mat_share"] for s in stages_data)
    if mat_sum > 0 and abs(mat_sum - 1.0) > 0.01:
        for s in stages_data:
            s["mat_share"] = s["mat_share"] / mat_sum

    # Расчёт дней для каждого этапа
    allocated_days = []
    for share in days_shares:
        d = max(1, int(round(total_days * share)))
        allocated_days.append(d)

    # Коррекция округления, чтобы сумма дней строго равнялась total_days
    diff_days = total_days - sum(allocated_days)
    if diff_days != 0 and len(allocated_days) > 4:
        # Корректируем самый длительный этап (водоснабжение - индекс 4)
        allocated_days[4] += diff_days

    calculated_stages = []
    for idx, s in enumerate(stages_data):
        stage_work = work_total * s["work_share"]
        stage_mat = mat_total * s["mat_share"]
        stage_total = stage_work + stage_mat
        stage_days = allocated_days[idx] if idx < len(allocated_days) else s.get("days", 10)

        calculated_stages.append({
            "num": s["num"],
            "title": s["title"],
            "days": stage_days,
            "work_cost": stage_work,
            "mat_cost": stage_mat,
            "stage_total": stage_total,
            "work_desc": s.get("work_desc", ""),
            "mat_desc": s.get("mat_desc", ""),
        })

    months_approx = round(total_days / 22.0, 1)

    return {
        "area": area,
        "work_total": work_total,
        "work_per_m2": work_total / area if area > 0 else 0.0,
        "mat_total": mat_total,
        "mat_per_m2": mat_total / area if area > 0 else 0.0,
        "grand_total": grand_total,
        "grand_per_m2": grand_total / area if area > 0 else 0.0,
        "total_days": total_days,
        "total_months": months_approx,
        "stages": calculated_stages,
    }


def generate_engineering_estimate_presentation(project_data: dict) -> dict:
    """
    Формирует пакет тегов и отправляет запрос в Google Apps Script Web App.
    """
    cfg = load_repair_estimate_settings()
    template_id = cfg["template_id"]
    folder_id = cfg["folder_id"]

    area = float(project_data.get("area", 0.0))
    work_cost = float(project_data.get("work_cost", 0.0))
    has_demolition = bool(project_data.get("has_demolition", False))
    address = str(project_data.get("address", "Объект")).strip()
    client_name = str(project_data.get("client_name", "Заказчик")).strip()
    state_name = str(project_data.get("state", "Голый бетон")).strip()
    tariff_name = str(project_data.get("tariff", "Комфорт")).strip()

    model = calculate_engineering_stages(
        area=area,
        work_total=work_cost,
        has_demolition=has_demolition,
        state_name=state_name,
        tariff_name=tariff_name,
        material_rate=cfg["material_rate"],
        custom_stages=cfg["stages"]
    )

    today_str = datetime.now().strftime("%d.%m.%Y")

    replacements = {
        "{Адрес}": address,
        "{м2}": f"{area:g}",
        "{Имя}": client_name,
        "{Состояние}": state_name,
        "{сегодня}": today_str,

        # Сводные показатели
        "{Цена ИР+М}": _format_money(model["grand_total"]),
        "{Цена ИР+Мм2}": f"{_format_money(model['grand_per_m2'])} за м²",
        "{Цена ИР}": _format_money(model["work_total"]),
        "{Цена ИРм2}": f"{_format_money(model['work_per_m2'])} за м²",
        "{Цена МИР}": _format_money(model["mat_total"]),
        "{Цена МИРм2}": f"{_format_money(model['mat_per_m2'])} за м²",
        "{СрокД ИР}": f"{model['total_days']} раб. дней",
        "{СрокМ ИР}": f"~{model['total_months']} месяцев",
    }

    # Плейсхолдеры 7 этапов
    for idx, st in enumerate(model["stages"], start=1):
        replacements[f"{{{idx}ТипИ}}"] = st["title"]
        replacements[f"{{{idx}СрокИ}}"] = f"{st['days']} раб. дней"
        replacements[f"{{{idx}Сроки}}"] = f"{st['days']} раб. дней"
        replacements[f"{{{idx}СРИ}}"] = _format_money(st["work_cost"])
        replacements[f"{{{idx}СЧМИ}}"] = _format_money(st["mat_cost"])
        replacements[f"{{{idx}СЧЭИ}}"] = _format_money(st["stage_total"])
        replacements[f"{{{idx}ОРИ}}"] = st["work_desc"]
        replacements[f"{{{idx}ЧМИ}}"] = st["mat_desc"]

    payload = {
        "template_id": template_id,
        "folder_id": folder_id,
        "address": address,
        "area": f"{area:g}",
        "client_name": client_name,
        "replacements": replacements
    }

    headers = {"Content-Type": "text/plain;charset=utf-8"}
    raw_data = json.dumps(payload, ensure_ascii=False).encode("utf-8")

    response = requests.post(WEB_APP_URL, data=raw_data, headers=headers, timeout=120, allow_redirects=True)

    text_resp = response.text.strip()
    try:
        res_data = json.loads(text_resp)
    except Exception:
        raise RuntimeError(f"Ответ сервера не в формате JSON (HTTP {response.status_code}): {text_resp[:200]}")

    if res_data.get("status") != "ok":
        err_msg = res_data.get("message", "Неизвестная ошибка скрипта Google Apps Script")
        raise RuntimeError(f"Ошибка Google Apps Script: {err_msg}")

    return {
        "presentation_id": res_data.get("presentation_id"),
        "title": res_data.get("title", f'RE Расчёт на инженерный ремонт "{address}" | {area:g} м2'),
        "edit_url": res_data.get("presentation_url"),
        "pdf_url": res_data.get("pdf_url"),
        "model": model,
    }