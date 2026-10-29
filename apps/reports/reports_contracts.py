from datetime import datetime

def parse_money(val: str) -> float:
    s = str(val).strip().replace(" ", "").replace("₽", "").replace(",", ".")
    try: return float(s)
    except: return 0.0

def parse_date(val: str):
    s = str(val).strip()
    if not s: return None
    try: return datetime.strptime(s.split(" ")[0], "%d.%m.%Y")
    except: return None

def is_in_period(d, start_dt, end_dt):
    if not d: return False
    if not start_dt or not end_dt: return True
    return start_dt.replace(hour=0, minute=0, second=0) <= d <= end_dt.replace(hour=23, minute=59, second=59)

def evaluate_contract(row: dict, mode: str, types: dict, start_dt, end_dt, in_creation_period: bool):
    """
    Возвращает (is_signed, budget_sum) на основе выбранного режима и галочек
    """
    dp_signed = types["dp"] and str(row.get("Договор ДП подписан", "")).strip().lower() == "да"
    r1_signed = types["rem1"] and str(row.get("Договор 1 подписан", "")).strip().lower() == "да"
    r2_signed = types["rem2"] and str(row.get("Договор 2 подписан", "")).strip().lower() == "да"

    budget = 0.0
    is_valid = False

    if mode == "by_creation":
        # Заявка/договор (по дате создания лида)
        if not in_creation_period:
            return False, 0.0
            
        if dp_signed or r1_signed or r2_signed:
            is_valid = True
            if dp_signed: budget += parse_money(row.get("Стоимость по договору ДП", "0"))
            if r1_signed: budget += parse_money(row.get("Стоимость по договору 1", "0"))
            if r2_signed: budget += parse_money(row.get("Стоимость по договору 2", "0"))
            
    else:
        # Общие договора (строго по датам подписания из AG, AH, AO)
        d_dp = parse_date(row.get("Дата подписания ДП", ""))
        d_r1 = parse_date(row.get("Дата подписания Ремонта", ""))
        d_r2 = parse_date(row.get("Дата подписания Отделки", ""))
        
        ok_dp = dp_signed and is_in_period(d_dp, start_dt, end_dt)
        ok_r1 = r1_signed and is_in_period(d_r1, start_dt, end_dt)
        ok_r2 = r2_signed and is_in_period(d_r2, start_dt, end_dt)
        
        if ok_dp or ok_r1 or ok_r2:
            is_valid = True
            if ok_dp: budget += parse_money(row.get("Стоимость по договору ДП", "0"))
            if ok_r1: budget += parse_money(row.get("Стоимость по договору 1", "0"))
            if ok_r2: budget += parse_money(row.get("Стоимость по договору 2", "0"))

    return is_valid, budget