from apps.core.sheets_client import get_main_spreadsheet


def get_dp_tariffs_info() -> dict:
    default_info = {
        "online": {
            "target": "Клиентам у которых есть опыт ремонта, нужно быстро",
            "advantages": "Удобные онлайн-согласования в Zoom/Telegram, полный комплект чертежей",
        },
        "full": {
            "target": "Клиентам у которых первый ремонт или нет времени",
            "advantages": "Совместные выезды по магазинам, авторский надзор, максимальная экономия времени",
        },
    }

    try:
        ws = get_main_spreadsheet().worksheet("Настройка")
        rows = ws.get_all_values()
        for r in rows:
            if not r:
                continue
            row_id = r[0].strip().lower() if len(r) > 0 else ""
            if row_id == "online" and len(r) >= 8:
                default_info["online"]["target"] = r[6].strip() or default_info["online"]["target"]
                default_info["online"]["advantages"] = r[7].strip() or default_info["online"]["advantages"]
            elif row_id == "full" and len(r) >= 8:
                default_info["full"]["target"] = r[6].strip() or default_info["full"]["target"]
                default_info["full"]["advantages"] = r[7].strip() or default_info["full"]["advantages"]
    except Exception:
        pass

    return default_info