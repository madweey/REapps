import os
import sys
import tempfile
import subprocess
import threading
import requests

CURRENT_VERSION = "1.0.0"
GITHUB_REPO = "madweey/REapps"
API_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"


def parse_version(ver_str: str) -> tuple:
    """Очищает строку версии (v1.0.2 -> (1, 0, 2))."""
    clean = ver_str.strip().lstrip("vV")
    parts = []
    for p in clean.split("."):
        try:
            parts.append(int(p))
        except ValueError:
            parts.append(0)
    return tuple(parts)


def check_for_updates() -> dict | None:
    """
    Проверяет наличие новой версии на GitHub Releases.
    Возвращает dict с данными релиза или None, если обновление не требуется.
    """
    try:
        resp = requests.get(API_URL, timeout=5)
        if resp.status_code != 200:
            return None

        data = resp.json()
        remote_tag = data.get("tag_name", "")
        if not remote_tag:
            return None

        current_v = parse_version(CURRENT_VERSION)
        remote_v = parse_version(remote_tag)

        if remote_v > current_v:
            # Ищем исполняемый файл .exe в ассетах релиза
            exe_asset = None
            for asset in data.get("assets", []):
                name = asset.get("name", "").lower()
                if name.endswith(".exe"):
                    exe_asset = asset
                    break

            return {
                "version": remote_tag,
                "name": data.get("name", remote_tag),
                "body": data.get("body", ""),
                "download_url": exe_asset.get("browser_download_url") if exe_asset else None,
                "asset_name": exe_asset.get("name") if exe_asset else None,
            }
    except Exception as e:
        print(f"Ошибка проверки обновлений: {e}")

    return None


def download_and_install_update(download_url: str, on_progress=None, on_error=None):
    """
    Скачивает новый бинарник и запускает процесс самообновления.
    Работает как для скомпилированного .exe, так и сигнализирует при запуске из исходников.
    """
    def _worker():
        try:
            if not getattr(sys, "frozen", False):
                if on_error:
                    on_error("Автообновление работает только в скомпилированной версии (.exe).")
                return

            current_exe = os.path.abspath(sys.executable)
            temp_dir = tempfile.gettempdir()
            new_exe = os.path.join(temp_dir, "REapps_new.exe")

            # Скачивание файла
            resp = requests.get(download_url, stream=True, timeout=30)
            resp.raise_for_status()
            total_len = int(resp.headers.get("content-length", 0))

            downloaded = 0
            with open(new_exe, "wb") as f:
                for chunk in resp.iter_content(chunk_size=65536):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total_len > 0 and on_progress:
                            on_progress(downloaded / total_len)

            # Генерация bat-скрипта для замены занятого файла Windows
            bat_path = os.path.join(temp_dir, "reapps_updater.bat")
            pid = os.getpid()

            bat_script = f"""@echo off
chcp 65001 > nul
:wait_loop
tasklist /fi "PID eq {pid}" | find ":" > nul
if errorlevel 1 (
    timeout /t 1 /nobreak > nul
    goto wait_loop
)

copy /y "{new_exe}" "{current_exe}" > nul
del /f /q "{new_exe}" > nul
start "" "{current_exe}"
del /f /q "%~f0" > nul
"""
            with open(bat_path, "w", encoding="cp866", errors="ignore") as f:
                f.write(bat_script)

            # Запуск скрипта обновления в отдельном процессе и завершение текущего приложения
            subprocess.Popen(
                ["cmd.exe", "/c", bat_path],
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
            )
            os._exit(0)

        except Exception as e:
            if on_error:
                on_error(str(e))

    threading.Thread(target=_worker, daemon=True).start()