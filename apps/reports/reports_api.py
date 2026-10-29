from datetime import datetime
import gspread
from apps.core.sheets import get_crm_spreadsheet, get_main_spreadsheet

DEALS_SPREADSHEET_ID = "1Y6k-xfn4_pN7_hqnrQGQJps3Cb4FEN-o7y-XqmHr5aQ"

def fetch_deals_data_full():
    """Скачивает и подготавливает данные из таблицы (Только чтение)"""
    try:
        sh = get_crm_spreadsheet()
        sheet = sh.worksheet("Сделки")
    except Exception:
        main_sh = get_main_spreadsheet()
        client = gspread.authorize(main_sh.client.auth)
        sh = client.open_by_key(DEALS_SPREADSHEET_ID)
        sheet = sh.worksheet("Сделки")
    
    all_values = sheet.get_all_values()
    if not all_values or len(all_values) < 2:
        return [], []
        
    headers = all_values[0]
    data_rows = []
    
    for row in all_values[1:]:
        row_dict = {}
        for i, h in enumerate(headers):
            row_dict[h.strip()] = row[i] if i < len(row) else ""
            
        date_str = row_dict.get("Дата создания", "").split(" ")[0]
        try:
            row_dict["_date_obj"] = datetime.strptime(date_str, "%d.%m.%Y")
        except:
            row_dict["_date_obj"] = None
            
        data_rows.append(row_dict)
        
    return headers, data_rows