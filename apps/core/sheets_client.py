import os
import sys
import gspread
from google.oauth2.service_account import Credentials

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

MAIN_SPREADSHEET_ID = "1mDQYuw8hFfgPuuhAebhciiSJAv_owhGKo-tuEN5j9uE"
CRM_SPREADSHEET_ID = "1Y6k-xfn4_pN7_hqnrQGQJps3Cb4FEN-o7y-XqmHr5aQ"

_CACHED_CLIENT = None
_CACHED_MAIN_SPREADSHEET = None
_CACHED_CRM_SPREADSHEET = None


def get_base_path() -> str:
    if getattr(sys, "frozen", False):
        return getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def get_credentials():
    base_path = get_base_path()
    key_path = os.path.join(base_path, "google_key.json")
    if not os.path.exists(key_path):
        local_key = os.path.join(os.path.dirname(sys.executable), "google_key.json")
        if os.path.exists(local_key):
            key_path = local_key
        else:
            raise FileNotFoundError(f"Файл ключа не найден по пути: {key_path}")

    return Credentials.from_service_account_file(key_path, scopes=SCOPES)


def get_raw_gspread_client():
    global _CACHED_CLIENT
    if _CACHED_CLIENT is None:
        creds = get_credentials()
        _CACHED_CLIENT = gspread.authorize(creds)
    return _CACHED_CLIENT


def get_main_spreadsheet():
    """Подключение к основной рабочей таблице REapps."""
    global _CACHED_MAIN_SPREADSHEET
    if _CACHED_MAIN_SPREADSHEET is not None:
        return _CACHED_MAIN_SPREADSHEET

    gc = get_raw_gspread_client()
    try:
        _CACHED_MAIN_SPREADSHEET = gc.open_by_key(MAIN_SPREADSHEET_ID)
        return _CACHED_MAIN_SPREADSHEET
    except Exception:
        _CACHED_MAIN_SPREADSHEET = gc.open("REapps")
        return _CACHED_MAIN_SPREADSHEET


def get_crm_spreadsheet():
    """Подключение к оригинальной таблице CRM со сделками (только чтение)."""
    global _CACHED_CRM_SPREADSHEET
    if _CACHED_CRM_SPREADSHEET is not None:
        return _CACHED_CRM_SPREADSHEET

    gc = get_raw_gspread_client()
    _CACHED_CRM_SPREADSHEET = gc.open_by_key(CRM_SPREADSHEET_ID)
    return _CACHED_CRM_SPREADSHEET