from apps.reports.reports_rejects import is_rejected, get_reject_reason

def parse_area(val: str) -> float:
    s = str(val).strip().replace(" ", "").replace(",", ".")
    try: return float(s)
    except: return 0.0

def is_target_lead(row: dict, excluded_reasons: list) -> bool:
    """Лид считается НЕцелевым, если это отказ по одной из исключенных причин"""
    if is_rejected(row):
        reason = get_reject_reason(row)
        if reason in excluded_reasons:
            return False
    return True