import os
import json
from apps.core.sheets_client import get_main_spreadsheet


def get_session_file_path() -> str:
    """Возвращает постоянный путь к файлу сессии в папке AppData пользователя."""
    app_data = os.environ.get("APPDATA") or os.path.expanduser("~")
    base_dir = os.path.join(app_data, "REapps")
    os.makedirs(base_dir, exist_ok=True)
    return os.path.join(base_dir, "session.json")


def get_access_worksheet():
    return get_main_spreadsheet().worksheet("Доступы")


def get_all_users() -> list[dict]:
    try:
        ws = get_access_worksheet()
        values = ws.get_all_values()
        if not values or len(values) < 2:
            return []

        users = []
        for idx, row in enumerate(values[1:], start=2):
            if not row or not any(row):
                continue

            def is_checked(col_idx):
                if len(row) > col_idx:
                    v = row[col_idx].strip().upper()
                    return v in ("TRUE", "1", "ДА", "YES", "+")
                return False

            name = row[0].strip() if len(row) > 0 else ""
            if name:
                users.append({
                    "row_idx": idx,
                    "name": name,
                    "password": row[1].strip() if len(row) > 1 else "",
                    "role": row[2].strip() if len(row) > 2 else "Сотрудник",
                    "can_meetings": is_checked(3),
                    "can_transcription": is_checked(4),
                    "can_calculator": is_checked(5),
                    "can_reports": is_checked(6),
                    "can_access_settings": is_checked(7),
                })
        return users
    except Exception as e:
        print(f"Ошибка загрузки пользователей: {e}")
        return []


def get_all_accounts() -> list[dict]:
    """Алиас для meetings_view и access_view."""
    return get_all_users()


def get_users_list() -> list[dict]:
    return get_all_users()


def add_new_user(name: str, password: str, role: str = "Сотрудник", permissions: dict = None) -> bool:
    try:
        ws = get_access_worksheet()
        perms = permissions or {}
        row = [
            name.strip(),
            password.strip(),
            role.strip(),
            "TRUE" if perms.get("can_meetings", True) else "FALSE",
            "TRUE" if perms.get("can_transcription", False) else "FALSE",
            "TRUE" if perms.get("can_calculator", False) else "FALSE",
            "TRUE" if perms.get("can_reports", False) else "FALSE",
            "TRUE" if perms.get("can_access_settings", False) else "FALSE",
        ]
        ws.append_row(row)
        return True
    except Exception as e:
        print(f"Ошибка добавления пользователя: {e}")
        return False


def add_user(user_data: dict) -> bool:
    return add_new_user(
        name=user_data.get("name", ""),
        password=user_data.get("password", ""),
        role=user_data.get("role", "Сотрудник"),
        permissions=user_data
    )


def update_user_permissions(row_idx: int, permissions: dict) -> bool:
    try:
        ws = get_access_worksheet()
        if "role" in permissions:
            ws.update_cell(row_idx, 3, permissions.get("role", "Сотрудник"))
        ws.update_cell(row_idx, 4, "TRUE" if permissions.get("can_meetings") else "FALSE")
        ws.update_cell(row_idx, 5, "TRUE" if permissions.get("can_transcription") else "FALSE")
        ws.update_cell(row_idx, 6, "TRUE" if permissions.get("can_calculator") else "FALSE")
        ws.update_cell(row_idx, 7, "TRUE" if permissions.get("can_reports") else "FALSE")
        ws.update_cell(row_idx, 8, "TRUE" if permissions.get("can_access_settings") else "FALSE")
        return True
    except Exception as e:
        print(f"Ошибка обновления прав пользователя: {e}")
        return False


def update_user_access(row_index: int, permissions: dict) -> bool:
    return update_user_permissions(row_index, permissions)


def delete_user(row_idx: int) -> bool:
    try:
        ws = get_access_worksheet()
        ws.delete_rows(row_idx)
        return True
    except Exception as e:
        print(f"Ошибка удаления пользователя: {e}")
        return False


def authenticate(login_name: str, login_pass: str):
    users = get_all_users()
    for u in users:
        if u.get("name", "").strip().lower() == login_name.strip().lower():
            if u.get("password", "").strip() == login_pass.strip():
                return u
    return None


def save_session(name: str, password: str):
    try:
        data = {"name": name.strip(), "password": password.strip()}
        session_file = get_session_file_path()
        with open(session_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[Auth] Ошибка сохранения сессии: {e}")


def load_session():
    session_file = get_session_file_path()
    if not os.path.exists(session_file):
        return None
    try:
        with open(session_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict) and data.get("name") and data.get("password"):
            return data
    except Exception as e:
        print(f"[Auth] Ошибка загрузки сессии: {e}")
    return None


def clear_session():
    session_file = get_session_file_path()
    if os.path.exists(session_file):
        try:
            os.remove(session_file)
        except Exception:
            pass