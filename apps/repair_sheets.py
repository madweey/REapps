import re
from typing import Dict, Any
from apps.core.sheets import get_sheet_by_title

DEFAULT_SETTINGS = {
    "base_engineering": 22162.0,
    "base_finishing": 40931.0,
    "coefficients": {
        "state_bare_concrete": {"title": "Голый бетон", "value": 0.00, "base": "Инженерия"},
        "state_bare_blocks": {"title": "Голый бетон с пер. в 1 блок", "value": 0.05, "base": "Инженерия"},
        "state_wb_no_demo": {"title": "Вайтбокс (Без демонтажа)", "value": 0.00, "base": "Инженерия"},
        "state_wb_demo": {"title": "Вайтбокс (С демонтажем)", "value": 0.20, "base": "Инженерия"},
        "state_builder_finish": {"title": "Отделка от застройщика", "value": 0.25, "base": "Инженерия"},
        "state_secondary_demo": {"title": "Вторичка (Нужен демонтаж)", "value": 0.25, "base": "Инженерия"},
        "state_secondary_done": {"title": "Вторичка (Демонтаж выполнен)", "value": 0.05, "base": "Инженерия"},
        "ceil_high": {"title": "Потолки выше 3.0 м", "value": 0.10, "base": "Все"},
        "el_extended": {"title": "Пакет расширенной электрики", "value": 0.10, "base": "Инженерия"},
        "el_lines": {"title": "Подготовка линий под электрокарнизы / подсветку", "value": 0.05, "base": "Инженерия"},
        "el_low_current": {"title": "Вывод слаботочки / щит под роутер и умный дом", "value": 0.05, "base": "Инженерия"},
        "plumb_leak_protect": {"title": "Система защиты от протечек (Neptun / Аквасторож)", "value": 0.05, "base": "Инженерия"},
        "plumb_installation": {"title": "Монтаж инсталляции", "value": 0.05, "base": "Инженерия"},
        "floor_quartz": {"title": "Кварцвинил / кварцпаркет", "value": 0.05, "base": "Отделка"},
        "floor_eng_board": {"title": "Инженерная доска", "value": 0.10, "base": "Отделка"},
        "floor_parquet": {"title": "Паркет", "value": 0.15, "base": "Отделка"},
        "floor_granite_part": {"title": "Керамогранит (60х60 / 60х120) (Часть объекта)", "value": 0.05, "base": "Отделка"},
        "wall_wallpaper_paint": {"title": "Обои под покраску", "value": 0.05, "base": "Отделка"},
        "wall_paint": {"title": "Стена под покраску", "value": 0.15, "base": "Отделка"},
        "wall_decor": {"title": "Декоративная штукатурка", "value": 0.15, "base": "Отделка"},
        "wall_microcement": {"title": "Микроцемент", "value": 0.20, "base": "Отделка"},
        "ceil_shadow": {"title": "Натяжной (обычный) с теневым профилем", "value": 0.05, "base": "Отделка"},
        "ceil_tracks": {"title": "Натяжной с треками", "value": 0.05, "base": "Отделка"},
        "ceil_tracks_shadow": {"title": "Натяжной с треками и теневым профилем", "value": 0.10, "base": "Отделка"},
        "ceil_gkl": {"title": "ГКЛ", "value": 0.20, "base": "Отделка"},
        "tile_bath_60x60": {"title": "Керамогранит СУ (60х60)", "value": 0.00, "base": "Отделка"},
        "tile_bath_60x120": {"title": "Керамогранит СУ (60х120)", "value": 0.05, "base": "Отделка"},
        "tile_bath_120x120": {"title": "Керамогранит СУ (120х120)", "value": 0.10, "base": "Отделка"},
        "tile_bath_120x200": {"title": "Керамогранит СУ (120х200)", "value": 0.15, "base": "Отделка"},
        "door_hidden": {"title": "Скрытые двери", "value": 0.05, "base": "Отделка"},
        "door_regular": {"title": "Обычные двери", "value": 0.00, "base": "Отделка"},
        "plinth_hidden": {"title": "Скрытые плинтуса", "value": 0.05, "base": "Отделка"},
        "plinth_regular": {"title": "Обычные плинтуса", "value": 0.00, "base": "Отделка"},
        "moldings": {"title": "Молдинги", "value": 0.05, "base": "Отделка"},
        "sound_zips": {"title": "Шумоизоляция ЗИПС", "value": 0.10, "base": "Инженерия"},
        "sound_frame": {"title": "Шумоизоляция Каркасная", "value": 0.15, "base": "Инженерия"},
    }
}

_cache_repair_settings = None


def _clean_number(val: Any) -> float:
    if val is None:
        return 0.0
    s = str(val).strip().replace("\xa0", " ")
    for unit in ["р/м2", "руб/м2", "₽/м²", "р", "руб", "₽", "м2", "м²"]:
        if unit in s.lower():
            s = re.split(re.escape(unit), s, flags=re.IGNORECASE)[0]
            break

    cleaned = s.strip().replace(" ", "").replace(",", ".")
    match = re.search(r"(\d+(\.\d+)?)", cleaned)
    if match:
        try:
            return float(match.group(1))
        except ValueError:
            return 0.0
    return 0.0


def load_repair_settings(force_reload: bool = False) -> Dict[str, Any]:
    global _cache_repair_settings
    if _cache_repair_settings is not None and not force_reload:
        return _cache_repair_settings

    try:
        worksheet = get_sheet_by_title("Настройка_Ремонт")
        all_vals = worksheet.get_all_values()

        raw_b4 = all_vals[3][1] if len(all_vals) > 3 and len(all_vals[3]) > 1 else ""
        raw_b7 = all_vals[6][1] if len(all_vals) > 6 and len(all_vals[6]) > 1 else ""

        base_eng = _clean_number(raw_b4)
        base_fin = _clean_number(raw_b7)

        if base_eng <= 0:
            base_eng = DEFAULT_SETTINGS["base_engineering"]
        if base_fin <= 0:
            base_fin = DEFAULT_SETTINGS["base_finishing"]

        coeffs = {}
        for row in all_vals[1:]:
            if len(row) > 5 and row[3].strip():
                c_id = row[3].strip()
                title = row[4].strip() if len(row) > 4 and row[4].strip() else c_id
                val = _clean_number(row[5])
                base_type = row[6].strip() if len(row) > 6 and row[6].strip() else "Инженерия"
                coeffs[c_id] = {
                    "title": title,
                    "value": val,
                    "base": base_type
                }

        for k, v in DEFAULT_SETTINGS["coefficients"].items():
            if k not in coeffs:
                coeffs[k] = v

        _cache_repair_settings = {
            "base_engineering": base_eng,
            "base_finishing": base_fin,
            "coefficients": coeffs
        }
        return _cache_repair_settings
    except Exception as e:
        print(f"[Repair Sheets] Ошибка загрузки настроек ремонта: {e}")
        _cache_repair_settings = DEFAULT_SETTINGS
        return _cache_repair_settings