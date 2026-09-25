import re
from apps.core.sheets_client import get_main_spreadsheet

_CACHED_REPAIR_SETTINGS = None


def transliterate_to_id(category_prefix: str, title: str) -> str:
    """Генерирует slug/ID ключа без необходимости придумывать его вручную."""
    ru_map = {
        'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'e',
        'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm',
        'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
        'ф': 'f', 'х': 'h', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'sch',
        'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya', ' ': '_'
    }
    cleaned = title.lower().strip()
    result = []
    for ch in cleaned:
        if ch in ru_map:
            result.append(ru_map[ch])
        elif ch.isalnum() or ch == '_':
            result.append(ch)
    slug = "".join(result)
    slug = re.sub(r'_+', '_', slug).strip('_')
    
    prefix = category_prefix.strip('_')
    if prefix:
        return f"{prefix}_{slug[:25]}"
    return slug[:30] or "custom_item"


def parse_float_safe(val) -> float:
    """Безопасный парсинг чисел и коэффициентов."""
    if val is None:
        return 0.0
    s = str(val).strip()
    s = s.replace("\u00a0", "").replace("\u202f", "").replace(" ", "")
    s = s.replace("₽", "").replace("%", "")

    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    else:
        s = s.replace(",", ".")

    s = re.sub(r"[^\d.-]", "", s)
    try:
        return float(s)
    except ValueError:
        return 0.0


def parse_rate_safe(raw_val, default_val: float) -> float:
    """Специальный парсинг базовой ставки за м² с защитой от лишнего ноля из копеек."""
    parsed = parse_float_safe(raw_val)
    if parsed <= 0:
        return default_val

    # Если число пришло в виде 221622 (копейка 2 склеилась с числом без запятой)
    # или ставка превышает 120 000 руб/м², уменьшаем порядок числа
    while parsed > 120000.0:
        parsed /= 10.0

    return round(parsed, 2)


def load_repair_settings(force_reload: bool = False) -> dict:
    """Загружает базовые тарифы и весь список работ/коэффициентов с листа Настройка_Ремонт."""
    global _CACHED_REPAIR_SETTINGS
    if _CACHED_REPAIR_SETTINGS and not force_reload:
        return _CACHED_REPAIR_SETTINGS

    settings = {
        "base_engineering": 22162.0,
        "base_finishing": 40931.0,
        "coefficients": {},
        "raw_items": [],
    }

    try:
        sh = get_main_spreadsheet()
        ws = sh.worksheet("Настройка_Ремонт")
        all_vals = ws.get_all_values()

        # 1. Чтение базовых ставок из столбца B
        if len(all_vals) >= 4 and len(all_vals[3]) >= 2:
            raw_b4 = all_vals[3][1]
            settings["base_engineering"] = parse_rate_safe(raw_b4, 22162.0)

        if len(all_vals) >= 7 and len(all_vals[6]) >= 2:
            raw_b7 = all_vals[6][1]
            settings["base_finishing"] = parse_rate_safe(raw_b7, 40931.0)

        # 2. Чтение справочника работ и коэффициентов D:G (начиная со 2-й строки)
        for r_idx, row in enumerate(all_vals[1:], start=2):
            if len(row) < 7:
                continue

            key_id = row[3].strip()
            title = row[4].strip()
            raw_coeff = parse_float_safe(row[5])
            coeff_val = raw_coeff / 100.0 if raw_coeff > 1.0 else raw_coeff
            base_type = row[6].strip() or "Отделка"

            if not key_id and not title:
                continue

            category = "other"
            if key_id.startswith("floor_"):
                category = "floor"
            elif key_id.startswith("wall_"):
                category = "wall"
            elif key_id.startswith("ceil_"):
                category = "ceil"
            elif key_id.startswith("tile_") or "санузел" in title.lower() or "керамогранит" in title.lower():
                category = "tile"
            elif key_id.startswith("door_"):
                category = "door"
            elif key_id.startswith("plinth_"):
                category = "plinth"
            elif key_id.startswith("el_") or key_id.startswith("plumb_"):
                category = "eng"
            elif key_id.startswith("sound_"):
                category = "sound"
            elif key_id.startswith("state_"):
                category = "state"

            item_data = {
                "row_idx": r_idx,
                "id": key_id,
                "title": title,
                "value": coeff_val,
                "base": base_type,
                "category": category,
            }

            settings["coefficients"][key_id] = item_data
            settings["raw_items"].append(item_data)

        _CACHED_REPAIR_SETTINGS = settings
    except Exception as e:
        print(f"[RepairSheets] Ошибка чтения настроек: {e}")

    return _CACHED_REPAIR_SETTINGS or settings


def add_repair_work(category: str, title: str, coeff_pct: float, base_type: str = "Отделка") -> bool:
    """Генерирует Key ID и добавляет новую работу в диапазон D:G листа Настройка_Ремонт."""
    try:
        sh = get_main_spreadsheet()
        ws = sh.worksheet("Настройка_Ремонт")
        all_vals = ws.get_all_values()

        target_row = len(all_vals) + 1
        for i, row in enumerate(all_vals):
            if i >= 1 and (len(row) < 4 or not row[3].strip()):
                target_row = i + 1
                break

        key_id = transliterate_to_id(category, title)
        coeff_val = coeff_pct / 100.0 if coeff_pct > 1.0 else coeff_pct

        ws.update_cell(target_row, 4, key_id)
        ws.update_cell(target_row, 5, title.strip())
        ws.update_cell(target_row, 6, str(coeff_val).replace(".", ","))
        ws.update_cell(target_row, 7, base_type.strip())

        load_repair_settings(force_reload=True)
        return True
    except Exception as e:
        print(f"[RepairSheets] Ошибка добавления работы: {e}")
        return False


def delete_repair_work(row_idx: int) -> bool:
    """Очищает данные работы в строке диапазона D:G."""
    try:
        sh = get_main_spreadsheet()
        ws = sh.worksheet("Настройка_Ремонт")
        ws.update(f"D{row_idx}:G{row_idx}", [["", "", "", ""]])
        load_repair_settings(force_reload=True)
        return True
    except Exception as e:
        print(f"[RepairSheets] Ошибка удаления работы: {e}")
        return False