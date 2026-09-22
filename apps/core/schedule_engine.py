from datetime import datetime, timedelta

DEFAULT_SLOTS = [
    "11:00",
    "12:00",
    "13:00",
    "14:00",
    "15:00",
    "16:00",
    "17:00",
    "18:00",
    "19:00",
    "20:00",
]

MEETING_DURATION_MINUTES = 60
BREAK_DURATION_MINUTES = 15


def parse_time_str(time_str: str) -> datetime:
    return datetime.strptime(time_str.strip(), "%H:%M")


def calculate_end_time(start_str: str, duration_minutes: int = MEETING_DURATION_MINUTES) -> str:
    start_dt = parse_time_str(start_str)
    end_dt = start_dt + timedelta(minutes=duration_minutes)
    return end_dt.strftime("%H:%M")


def evaluate_slot_status(slot_time_str: str, existing_meetings: list[dict], target_date_str: str | None = None) -> dict:
    """
    Проверяет доступность слота с учётом занятости и текущего времени суток.
    """
    # 1. Проверка на прошедшее время для сегодняшнего дня
    if target_date_str:
        try:
            target_date = datetime.strptime(target_date_str.strip(), "%d.%m.%Y").date()
            now = datetime.now()
            today_date = now.date()

            if target_date < today_date:
                return {
                    "status": "BUSY",
                    "reason": "Дата уже прошла",
                    "color": "#9E9E9E",
                }
            elif target_date == today_date:
                slot_time = parse_time_str(slot_time_str).time()
                current_time = now.time()
                if slot_time <= current_time:
                    return {
                        "status": "BUSY",
                        "reason": "Время уже прошло",
                        "color": "#9E9E9E",
                    }
        except Exception:
            pass

    # 2. Проверка пересечения с существующими встречами ведущего
    slot_start = parse_time_str(slot_time_str)
    slot_end = slot_start + timedelta(minutes=MEETING_DURATION_MINUTES)

    for m in existing_meetings:
        m_status = m.get("status", "").strip()
        if m_status == "Отказ":
            continue

        start_raw = m.get("start", "").strip()
        end_raw = m.get("end", "").strip()

        if not start_raw:
            continue

        m_start = parse_time_str(start_raw)
        m_end = parse_time_str(end_raw) if end_raw else (m_start + timedelta(minutes=MEETING_DURATION_MINUTES))

        # Полное пересечение со встречей
        if not (slot_end <= m_start or slot_start >= m_end):
            client = m.get("client", "Клиент")
            return {
                "status": "BUSY",
                "reason": f"Занято: встреча с {client} ({start_raw}-{end_raw})",
                "color": "#9E9E9E",
            }

        # Проверка 15-минутного буфера перерыва
        break_start = m_end
        break_end = m_end + timedelta(minutes=BREAK_DURATION_MINUTES)
        if not (slot_end <= break_start or slot_start >= break_end):
            return {
                "status": "BUFFER",
                "reason": f"Перерыв 15 мин после встречи в {start_raw}",
                "color": "#FFC107",
            }

    return {
        "status": "FREE",
        "reason": "Свободно для записи",
        "color": "#4CAF50",
    }


def get_day_schedule_grid(existing_meetings: list[dict], target_date_str: str | None = None) -> list[dict]:
    grid = []
    for t in DEFAULT_SLOTS:
        res = evaluate_slot_status(t, existing_meetings, target_date_str)
        grid.append({
            "time": t,
            "status": res["status"],
            "reason": res["reason"],
            "color": res["color"],
        })
    return grid