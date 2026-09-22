from datetime import datetime
from apps.core.sheets_client import get_main_spreadsheet


def get_meetings_data() -> list[dict]:
    """Извлекает все встречи из листа 'Встречи'."""
    try:
        sh = get_main_spreadsheet()
        ws = sh.worksheet("Встречи")
        rows = ws.get_all_values()
        if len(rows) <= 1:
            return []

        meetings = []
        for idx, r in enumerate(rows[1:], start=2):
            if not any(r):
                continue
            item = {
                "row_idx": idx,
                "date": r[0] if len(r) > 0 else "",
                "start": r[1] if len(r) > 1 else "",
                "end": r[2] if len(r) > 2 else "",
                "manager": r[3] if len(r) > 3 else "",
                "client": r[4] if len(r) > 4 else "",
                "deal_id": r[5] if len(r) > 5 else "",
                "complex": r[6] if len(r) > 6 else "",
                "area": r[7] if len(r) > 7 else "",
                "deal_url": r[8] if len(r) > 8 else "",
                "call_url": r[9] if len(r) > 9 else "",
                "comment": r[10] if len(r) > 10 else "",
                "hooks": r[11] if len(r) > 11 else "",
                "feedback": r[12] if len(r) > 12 else "",
                "meeting_url": r[13] if len(r) > 13 else "",
                "transcription": r[14] if len(r) > 14 else "",
                "gpt_summary": r[15] if len(r) > 15 else "",
                "meeting_type": r[16] if len(r) > 16 else "Онлайн встреча",
                "status": r[17] if len(r) > 17 else "Ожидает подтверждения",
                "host_manager": r[18] if len(r) > 18 else "",
                "created_by": r[19] if len(r) > 19 else "",
            }
            meetings.append(item)
        return meetings
    except Exception as e:
        print(f"Ошибка при чтении встреч: {e}")
        return []


# Псевдоним для поддержки обоих вариантов вызова
get_all_meetings = get_meetings_data


def get_meetings_by_date(target_date_str: str) -> list[dict]:
    """Возвращает список встреч на указанную дату."""
    all_m = get_meetings_data()
    return [m for m in all_m if m.get("date", "").strip() == target_date_str.strip()]


def save_new_meeting(data: dict) -> bool:
    """Добавляет новую строку встречи в таблицу."""
    sh = get_main_spreadsheet()
    ws = sh.worksheet("Встречи")
    row_values = [
        data.get("date", ""),
        data.get("start", ""),
        data.get("end", ""),
        data.get("manager", ""),
        data.get("client", ""),
        data.get("deal_id", ""),
        data.get("complex", ""),
        data.get("area", ""),
        data.get("deal_url", ""),
        data.get("call_url", ""),
        data.get("comment", ""),
        data.get("hooks", ""),
        data.get("feedback", ""),
        data.get("meeting_url", ""),
        data.get("transcription", ""),
        data.get("gpt_summary", ""),
        data.get("meeting_type", "Онлайн встреча"),
        data.get("status", "Ожидает подтверждения"),
        data.get("host_manager", ""),
        data.get("created_by", ""),
    ]
    ws.append_row(row_values)
    return True


def update_meeting_status(row_idx: int, status: str) -> bool:
    """Обновляет статус встречи."""
    sh = get_main_spreadsheet()
    ws = sh.worksheet("Встречи")
    ws.update_cell(row_idx, 18, status)
    return True


def update_meeting_details(row_idx: int, details: dict) -> bool:
    """Обновляет данные встречи при её редактировании."""
    sh = get_main_spreadsheet()
    ws = sh.worksheet("Встречи")
    if "call_url" in details:
        ws.update_cell(row_idx, 10, details["call_url"])
    if "comment" in details:
        ws.update_cell(row_idx, 11, details["comment"])
    if "hooks" in details:
        ws.update_cell(row_idx, 12, details["hooks"])
    if "meeting_type" in details:
        ws.update_cell(row_idx, 17, details["meeting_type"])
    if "host_manager" in details:
        ws.update_cell(row_idx, 19, details["host_manager"])
    return True


def complete_meeting(row_idx: int, feedback: str, meeting_url: str) -> bool:
    """Фиксирует итоги и переводит встречу в статус 'Встреча проведена'."""
    sh = get_main_spreadsheet()
    ws = sh.worksheet("Встречи")
    ws.update_cell(row_idx, 13, feedback)
    ws.update_cell(row_idx, 14, meeting_url)
    ws.update_cell(row_idx, 18, "Встреча проведена")
    return True


def cancel_meeting(row_idx: int, reason: str) -> bool:
    """Отменяет встречу и записывает причину отмены."""
    sh = get_main_spreadsheet()
    ws = sh.worksheet("Встречи")
    current_comment = ws.cell(row_idx, 11).value or ""
    new_comment = f"{current_comment} [Причина отмены: {reason}]".strip()
    ws.update_cell(row_idx, 11, new_comment)
    ws.update_cell(row_idx, 18, "Отказ")
    return True


def delete_meeting(row_idx: int) -> bool:
    """Удаляет строку встречи из таблицы."""
    sh = get_main_spreadsheet()
    ws = sh.worksheet("Встречи")
    ws.delete_rows(row_idx)
    return True