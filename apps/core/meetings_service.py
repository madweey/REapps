from apps.core.sheets_client import get_main_spreadsheet


def get_meetings_worksheet():
    return get_main_spreadsheet().worksheet("Встречи")


def get_all_meetings() -> list[dict]:
    try:
        sheet = get_meetings_worksheet()
        values = sheet.get_all_values()
        if not values or len(values) < 2:
            return []

        meetings = []
        for idx, row in enumerate(values[1:], start=2):
            if not row or not any(row):
                continue
            item = {
                "row_idx": idx,
                "date": row[0].strip() if len(row) > 0 else "",
                "start": row[1].strip() if len(row) > 1 else "",
                "end": row[2].strip() if len(row) > 2 else "",
                "manager": row[3].strip() if len(row) > 3 else "",
                "client": row[4].strip() if len(row) > 4 else "",
                "deal_id": row[5].strip() if len(row) > 5 else "",
                "complex": row[6].strip() if len(row) > 6 else "",
                "area": row[7].strip() if len(row) > 7 else "",
                "deal_url": row[8].strip() if len(row) > 8 else "",
                "call_url": row[9].strip() if len(row) > 9 else "",
                "comment": row[10].strip() if len(row) > 10 else "",
                "hooks": row[11].strip() if len(row) > 11 else "",
                "feedback": row[12].strip() if len(row) > 12 else "",
                "meeting_url": row[13].strip() if len(row) > 13 else "",
                "transcription": row[14].strip() if len(row) > 14 else "",
                "gpt_summary": row[15].strip() if len(row) > 15 else "",
                "meeting_type": row[16].strip() if len(row) > 16 else "Онлайн встреча",
                "status": row[17].strip() if len(row) > 17 else "Ожидает подтверждения",
                "host_manager": row[18].strip() if len(row) > 18 else "",
                "created_by": row[19].strip() if len(row) > 19 else "",
            }
            if not item["status"]:
                item["status"] = "Ожидает подтверждения"
            if not item["meeting_type"]:
                item["meeting_type"] = "Онлайн встреча"
            meetings.append(item)
        return meetings
    except Exception as e:
        print(f"Ошибка загрузки встреч: {e}")
        return []


def get_meetings_data() -> list[dict]:
    return get_all_meetings()


def get_meetings_by_date(target_date: str) -> list[dict]:
    all_meetings = get_all_meetings()
    t_clean = target_date.strip()
    return [m for m in all_meetings if m.get("date", "").strip() == t_clean]


def save_new_meeting(payload: dict) -> bool:
    try:
        sheet = get_meetings_worksheet()
        row = [
            payload.get("date", ""),
            payload.get("start", ""),
            payload.get("end", ""),
            payload.get("manager", ""),
            payload.get("client", ""),
            payload.get("deal_id", ""),
            payload.get("complex", ""),
            payload.get("area", ""),
            payload.get("deal_url", ""),
            payload.get("call_url", ""),
            payload.get("comment", ""),
            payload.get("hooks", ""),
            payload.get("feedback", ""),
            payload.get("meeting_url", ""),
            payload.get("transcription", ""),
            payload.get("gpt_summary", ""),
            payload.get("meeting_type", "Онлайн встреча"),
            payload.get("status", "Ожидает подтверждения"),
            payload.get("host_manager", ""),
            payload.get("created_by", ""),
        ]
        sheet.append_row(row)
        return True
    except Exception as e:
        print(f"Ошибка сохранения встречи: {e}")
        return False


def update_meeting_status(row_idx: int, status: str) -> bool:
    try:
        sheet = get_meetings_worksheet()
        sheet.update_cell(row_idx, 18, status)
        return True
    except Exception as e:
        print(f"Ошибка обновления статуса встречи: {e}")
        return False


def complete_meeting(row_idx: int, feedback: str, recording_url: str) -> bool:
    try:
        sheet = get_meetings_worksheet()
        sheet.update_cell(row_idx, 18, "Встреча проведена")
        sheet.update_cell(row_idx, 13, feedback)
        sheet.update_cell(row_idx, 14, recording_url)
        return True
    except Exception as e:
        print(f"Ошибка завершения встречи: {e}")
        return False


def cancel_meeting(row_idx: int, reason: str) -> bool:
    try:
        sheet = get_meetings_worksheet()
        sheet.update_cell(row_idx, 18, "Отказ")
        old_comm = sheet.cell(row_idx, 11).value or ""
        new_comm = f"{old_comm} | Отказ: {reason}".strip(" |")
        sheet.update_cell(row_idx, 11, new_comm)
        return True
    except Exception as e:
        print(f"Ошибка отмены встречи: {e}")
        return False


def delete_meeting(row_idx: int) -> bool:
    try:
        sheet = get_meetings_worksheet()
        sheet.delete_rows(row_idx)
        return True
    except Exception as e:
        print(f"Ошибка удаления встречи: {e}")
        return False


def update_meeting_details(row_idx: int, updated_fields: dict) -> bool:
    try:
        sheet = get_meetings_worksheet()
        mapping = {
            "call_url": 10,
            "comment": 11,
            "hooks": 12,
            "meeting_type": 17,
            "host_manager": 19,
        }
        for k, col in mapping.items():
            if k in updated_fields:
                sheet.update_cell(row_idx, col, str(updated_fields[k]))
        return True
    except Exception as e:
        print(f"Ошибка сохранения изменений встречи: {e}")
        return False