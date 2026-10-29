def get_reject_reason(row: dict) -> str:
    """Возвращает причину отказа (если есть)"""
    return str(row.get("Причина отказа", "")).strip()

def is_rejected(row: dict) -> bool:
    """Сделка считается отказом, если поле причины не пустое"""
    return bool(get_reject_reason(row))

def filter_rejected(row: dict, included_reasons: list) -> bool:
    """Подходит ли отказ под фильтр выбранных причин"""
    if not is_rejected(row):
        return False
    reason = get_reject_reason(row)
    if included_reasons and reason not in included_reasons:
        return False
    return True