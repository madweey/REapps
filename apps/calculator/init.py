from apps.core.sheets import get_sheets_client


def get_dp_settings() -> dict:
    """
    Считывает актуальные тарифы и шкалу сроков с листа 'Настройка'.
    Тариф online -> ДП (онлайн разработка)
    Тариф full   -> ОДП (с сопровождением / оффлайн)
    """
    default_settings = {
        "tariffs": {
            "online": {"name": "Онлайн разработка", "price_m2": 4950},
            "full": {"name": "С сопровождением", "price_m2": 7450},
            "tech": {"name": "Технический проект", "price_m2": 3050},
        },
        "deadlines": [],
    }

    try:
        sh = get_sheets_client()
        ws = sh.worksheet("Настройка")
        rows = ws.get_all_values()

        # 1. Читаем тарифы (строки со 2 по 5)
        tariffs = {}
        for r in rows[2:6]:
            if len(r) >= 3 and r[0].strip():
                t_id = r[0].strip()
                t_name = r[1].strip()
                try:
                    price = float(str(r[2]).replace(" ", "").replace("₽", "").replace(",", "."))
                except ValueError:
                    price = 0.0
                tariffs[t_id] = {"name": t_name, "price_m2": price}

        if tariffs:
            default_settings["tariffs"] = tariffs

        # 2. Читаем шкалу сроков (начиная со строки 9, индекс 8)
        deadlines = []
        for r in rows[8:]:
            if len(r) >= 5 and r[0].strip():
                t_id = r[0].strip()
                try:
                    min_m2 = float(str(r[1]).replace(",", "."))
                    max_m2 = float(str(r[2]).replace(",", "."))
                    days_text = str(r[3]).strip()
                    days_num = int(float(str(r[4]).replace(",", ".")))
                    deadlines.append({
                        "tariff_id": t_id,
                        "min_m2": min_m2,
                        "max_m2": max_m2,
                        "days_text": days_text,
                        "days_num": days_num,
                    })
                except (ValueError, IndexError):
                    continue

        if deadlines:
            default_settings["deadlines"] = deadlines

    except Exception as e:
        print(f"Предупреждение: Не удалось прочитать лист 'Настройка' ({e}), используются стандартные ставки.")

    return default_settings


def get_deadline_for_area(deadlines: list, tariff_id: str, area: float) -> str:
    """Находит срок в рабочих днях по шкале площади."""
    for item in deadlines:
        if item["tariff_id"] == tariff_id:
            if item["min_m2"] <= area <= item["max_m2"]:
                return item["days_text"]
    # Резервные значения, если площадь выходит за пределы шкалы
    if tariff_id == "online":
        return "130 рабочих дней" if area > 120 else "50 рабочих дней"
    elif tariff_id == "full":
        return "130 рабочих дней" if area > 120 else "50 рабочих дней"
    return "30 рабочих дней"


def calculate_dp(area: float, discount_val: float = 0.0, discount_type: str = "fixed") -> dict:
    """
    Рассчитывает параметры для двух тарифов:
    ДП (online) и ОДП (full).
    """
    settings = get_dp_settings()
    tariffs = settings["tariffs"]
    deadlines = settings["deadlines"]

    # Цены за м2
    price_dp_m2 = tariffs.get("online", {}).get("price_m2", 4950.0)
    price_odp_m2 = tariffs.get("full", {}).get("price_m2", 7450.0)

    # Базовые стоимости
    cost_dp_base = area * price_dp_m2
    cost_odp_base = area * price_odp_m2

    # Учет скидки
    if discount_type == "percent":
        discount_dp = cost_dp_base * (discount_val / 100.0)
        discount_odp = cost_odp_base * (discount_val / 100.0)
    else:
        discount_dp = discount_val
        discount_odp = discount_val

    cost_dp_total = max(0.0, cost_dp_base - discount_dp)
    cost_odp_total = max(0.0, cost_odp_base - discount_odp)

    # Итоговая цена за м2 с учетом скидки
    effective_dp_m2 = round(cost_dp_total / area, 2) if area > 0 else price_dp_m2
    effective_odp_m2 = round(cost_odp_total / area, 2) if area > 0 else price_odp_m2

    # Сроки разработки
    deadline_dp = get_deadline_for_area(deadlines, "online", area)
    deadline_odp = get_deadline_for_area(deadlines, "full", area)

    return {
        "area": area,
        "dp": {
            "tariff_name": "Онлайн разработка",
            "price_m2": round(effective_dp_m2),
            "base_price_m2": round(price_dp_m2),
            "total_cost": round(cost_dp_total),
            "deadline": deadline_dp,
        },
        "odp": {
            "tariff_name": "С сопровождением (Оффлайн)",
            "price_m2": round(effective_odp_m2),
            "base_price_m2": round(price_odp_m2),
            "total_cost": round(cost_odp_total),
            "deadline": deadline_odp,
        },
    }