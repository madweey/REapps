import json
import re
import requests

WEB_APP_URL = "https://script.google.com/macros/s/AKfycbyApsDDassgk8TtCJXie1dH7v72S5At5X9VaxzXxSVpYvYJAWEjrbOfemdKBUrIbdmZrg/exec"


def generate_eng_estimate_pdf(sheets_mgr=None):
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json, text/plain, */*",
    })

    try:
        response = session.get(
            WEB_APP_URL,
            allow_redirects=True,
            timeout=80,
        )

        try:
            data = response.json()
        except json.JSONDecodeError:
            raw_text = response.text
            # Проверяем на ошибки авторизации
            if "accounts.google.com" in raw_text or "ServiceLogin" in raw_text:
                raise RuntimeError(
                    "Google заблокировал доступ: убедитесь, что в «Управление развертываниями» выбран доступ «Все» (Anyone)."
                )

            # Пытаемся извлечь читаемое сообщение ошибки из HTML-тега
            clean_error = re.findall(r"<title>(.*?)</title>", raw_text, re.IGNORECASE)
            err_title = clean_error[0] if clean_error else "Неизвестный ответ сервиса"
            raise RuntimeError(f"Google Apps Script вернул HTML: {err_title}")

        if data.get("status") == "success":
            return {
                "file_id": data["file_id"],
                "title": data["title"],
                "view_url": data["view_url"],
                "download_url": data["download_url"],
            }
        else:
            raise RuntimeError(data.get("message", "Неизвестная ошибка Google Apps Script"))

    except Exception as ex:
        raise RuntimeError(f"{ex}")