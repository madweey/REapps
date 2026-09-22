from datetime import datetime
from apps.core.sheets_client import get_main_spreadsheet

# ==========================================
# ПРОМТЫ (лист 'Промты')
# ==========================================

def get_prompts_worksheet():
    return get_main_spreadsheet().worksheet("Промты")


def get_all_prompts() -> list[dict]:
    try:
        ws = get_prompts_worksheet()
        values = ws.get_all_values()
        if not values or len(values) < 2:
            return []

        prompts = []
        for idx, row in enumerate(values[1:], start=2):
            if not row or not any(row):
                continue
            title = row[0].strip() if len(row) > 0 else ""
            category = row[1].strip() if len(row) > 1 else "Встречи"
            prompt_text = row[2].strip() if len(row) > 2 else ""
            created_at = row[3].strip() if len(row) > 3 else datetime.now().strftime("%d.%m.%Y")

            if title and prompt_text:
                prompts.append({
                    "row_idx": idx,
                    "title": title,
                    "category": category,
                    "prompt_text": prompt_text,
                    "created_at": created_at,
                })
        return prompts
    except Exception as e:
        print(f"Ошибка чтения промтов: {e}")
        return []


def get_prompts_dict() -> dict[str, str]:
    items = get_all_prompts()
    return {p["title"]: p["prompt_text"] for p in items}


def add_prompt(title: str, category: str = "Встречи", prompt_text: str = "") -> bool:
    try:
        # Поддержка вызова add_prompt(title, prompt_text)
        if prompt_text == "" and category != "Встречи":
            prompt_text = category
            category = "Встречи"

        ws = get_prompts_worksheet()
        now_str = datetime.now().strftime("%d.%m.%Y")
        ws.append_row([title.strip(), category.strip(), prompt_text.strip(), now_str])
        return True
    except Exception as e:
        print(f"Ошибка сохранения промта: {e}")
        return False


def delete_prompt(row_idx: int) -> bool:
    try:
        ws = get_prompts_worksheet()
        ws.delete_rows(row_idx)
        return True
    except Exception as e:
        print(f"Ошибка удаления промта: {e}")
        return False


def update_prompt(row_idx: int, title: str, category: str, prompt_text: str = "") -> bool:
    try:
        if prompt_text == "":
            prompt_text = category
            category = "Встречи"
        ws = get_prompts_worksheet()
        ws.update(range_name=f"A{row_idx}:C{row_idx}", values=[[title.strip(), category.strip(), prompt_text.strip()]])
        return True
    except Exception as e:
        print(f"Ошибка обновления промта: {e}")
        return False


# ==========================================
# РАЗБОРЫ (лист 'Разборы')
# ==========================================

def get_analyses_worksheet():
    sh = get_main_spreadsheet()
    try:
        return sh.worksheet("Разборы")
    except Exception:
        return sh.worksheet("Анализ звонков")


def save_analysis(payload: dict) -> bool:
    try:
        ws = get_analyses_worksheet()
        now_str = datetime.now().strftime("%d.%m.%Y %H:%M")
        row = [
            now_str,
            payload.get("author", ""),
            payload.get("comm_type", ""),
            payload.get("client_deal", ""),
            payload.get("source_url", ""),
            payload.get("prompt_title", ""),
            payload.get("summary", ""),
            str(payload.get("transcription", ""))[:15000],
            str(payload.get("full_ai_report", ""))[:15000],
        ]
        ws.append_row(row)
        return True
    except Exception as e:
        print(f"Ошибка сохранения разбора: {e}")
        return False


def get_all_analyses() -> list[dict]:
    try:
        ws = get_analyses_worksheet()
        values = ws.get_all_values()
        if not values or len(values) < 2:
            return []

        analyses = []
        for idx, row in enumerate(values[1:], start=2):
            if not row or not any(row):
                continue
            analyses.append({
                "row_idx": idx,
                "date": row[0].strip() if len(row) > 0 else "",
                "author": row[1].strip() if len(row) > 1 else "",
                "comm_type": row[2].strip() if len(row) > 2 else "",
                "client_deal": row[3].strip() if len(row) > 3 else "",
                "source_url": row[4].strip() if len(row) > 4 else "",
                "prompt_title": row[5].strip() if len(row) > 5 else "",
                "summary": row[6].strip() if len(row) > 6 else "",
                "transcription": row[7].strip() if len(row) > 7 else "",
                "full_ai_report": row[8].strip() if len(row) > 8 else (row[7].strip() if len(row) > 7 else ""),
            })
        return analyses
    except Exception as e:
        print(f"Ошибка чтения разборов: {e}")
        return []


# ==========================================
# VPN ТУННЕЛИ (лист 'Настройка', ячейки M3:M8)
# ==========================================

def get_split_vpn_keys() -> tuple[list[str], list[str]]:
    try:
        ws = get_main_spreadsheet().worksheet("Настройка")
        vals = ws.get("M3:M8")
        raw_list = [row[0].strip() if row and len(row) > 0 else "" for row in vals]
        while len(raw_list) < 6:
            raw_list.append("")

        ru_keys = [k for k in raw_list[0:3] if k]
        foreign_keys = [k for k in raw_list[3:6] if k]
        return ru_keys, foreign_keys
    except Exception as e:
        print(f"Ошибка чтения ключей туннелей M3:M8: {e}")
        return [], []


def save_split_vpn_keys(ru_keys: list[str], foreign_keys: list[str]) -> bool:
    try:
        ws = get_main_spreadsheet().worksheet("Настройка")
        m_rows = []
        for i in range(3):
            m_rows.append([ru_keys[i] if i < len(ru_keys) else ""])
        for i in range(3):
            m_rows.append([foreign_keys[i] if i < len(foreign_keys) else ""])

        ws.update(range_name="M3:M8", values=m_rows)
        return True
    except Exception as e:
        print(f"Ошибка сохранения ключей в M3:M8: {e}")
        return False