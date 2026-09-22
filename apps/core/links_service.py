from datetime import datetime
from apps.core.sheets_client import get_main_spreadsheet


def get_links_worksheet():
    return get_main_spreadsheet().worksheet("Ссылки")


def get_all_template_links() -> list[dict]:
    try:
        ws = get_links_worksheet()
        values = ws.get_all_values()
        if not values or len(values) < 2:
            return []

        links = []
        for idx, row in enumerate(values[1:], start=2):
            if not row or not any(row):
                continue
            cat = row[0].strip() if len(row) > 0 else "КП"
            title = row[1].strip() if len(row) > 1 else ""
            url = row[2].strip() if len(row) > 2 else ""
            desc = row[3].strip() if len(row) > 3 else ""
            c_at = row[4].strip() if len(row) > 4 else ""

            if title or url:
                links.append({
                    "row_idx": idx,
                    "category": cat,
                    "title": title,
                    "url": url,
                    "desc": desc,
                    "created_at": c_at,
                })
        return links
    except Exception as e:
        print(f"Ошибка чтения ссылок: {e}")
        return []


def add_template_link(category: str, title: str = "", url: str = "", desc: str = "") -> bool:
    try:
        # Поддержка сигнатуры add_template_link(title, url, category)
        if url == "" and desc == "" and title.startswith("http"):
            url = title
            title = category
            category = "КП"

        ws = get_links_worksheet()
        now_str = datetime.now().strftime("%d.%m.%Y")
        ws.append_row([category.strip(), title.strip(), url.strip(), desc.strip(), now_str])
        return True
    except Exception as e:
        print(f"Ошибка добавления ссылки: {e}")
        return False


def delete_template_link(row_idx: int) -> bool:
    try:
        ws = get_links_worksheet()
        ws.delete_rows(row_idx)
        return True
    except Exception as e:
        print(f"Ошибка удаления ссылки: {e}")
        return False