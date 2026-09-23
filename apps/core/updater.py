import os
import sys
import tempfile
import subprocess
import threading
import requests

CURRENT_VERSION = "1.1.2"
GITHUB_REPO = "madweey/REapps"
RELEASE_URL = f"https://github.com/{GITHUB_REPO}/releases/latest"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/octet-stream",
}


def parse_version(ver_str: str) -> tuple:
    """Очищает строку версии (v1.0.8 -> (1, 0, 8))."""
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
    Проверяет наличие новой версии на GitHub через прямой редирект веб-страницы.
    Не использует REST API, благодаря чему не подвержен ограничениям rate limit (ошибка 403).
    """
    try:
        resp = requests.get(RELEASE_URL, headers=HEADERS, allow_redirects=False, timeout=10)
        print(f"[Updater DEBUG] URL: {RELEASE_URL}")
        print(f"[Updater DEBUG] Status code: {resp.status_code}")

        remote_tag = None
        if resp.status_code in (301, 302):
            location = resp.headers.get("Location", "")
            if "/tag/" in location:
                remote_tag = location.split("/tag/")[-1].strip()
        elif resp.status_code == 200:
            final_url = resp.url
            if "/tag/" in final_url:
                remote_tag = final_url.split("/tag/")[-1].strip()

        print(f"[Updater DEBUG] Remote tag: '{remote_tag}'")
        if not remote_tag:
            return None

        current_v = parse_version(CURRENT_VERSION)
        remote_v = parse_version(remote_tag)
        print(f"[Updater DEBUG] Сравнение версий: локальная {current_v} vs удаленная {remote_v}")

        if remote_v > current_v:
            download_url = f"https://github.com/{GITHUB_REPO}/releases/download/{remote_tag}/REapps.exe"
            return {
                "version": remote_tag,
                "name": f"REapps {remote_tag}",
                "body": "Доступно новое обновление на GitHub.",
                "download_url": download_url,
                "asset_name": "REapps.exe",
            }
        else:
            print("[Updater DEBUG] Версия актуальна. Обновление не требуется.")
    except Exception as e:
        print(f"[Updater DEBUG] Ошибка проверки обновлений: {e}")

    return None


def download_and_install_update(download_url: str, on_progress=None, on_error=None):
    """
    Скачивает новый бинарник с User-Agent и запускает надежный процесс
    самообновления через PowerShell с полным логированием.
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
            log_file = os.path.join(temp_dir, "reapps_update.log")

            # Скачивание файла с браузерным заголовком во избежание блокировки 403
            resp = requests.get(download_url, headers=HEADERS, stream=True, timeout=120)
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

            pid = os.getpid()
            ps_script = os.path.join(temp_dir, "reapps_updater.ps1")

            ps_content = f"""
$ErrorActionPreference = "Continue"
$log = "{log_file}"

function Log($msg) {{
    $time = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    "[$time] $msg" | Out-File -FilePath $log -Append -Encoding utf8
}}

Log "Начало процесса обновления. PID приложения: {pid}"

# Ожидание выхода основного процесса
$attempts = 0
while ((Get-Process -Id {pid} -ErrorAction SilentlyContinue) -and ($attempts -lt 25)) {{
    Start-Sleep -Milliseconds 300
    $attempts++
}}

Log "Завершение фоновых процессов Flet и приложения..."
taskkill /F /PID {pid} /T 2>$null
taskkill /F /IM REapps.exe /T 2>$null
taskkill /F /IM flet.exe /T 2>$null
Start-Sleep -Milliseconds 1000

Log "Копирование нового файла: '{new_exe}' -> '{current_exe}'"
$copySuccess = $false
for ($i = 0; $i -lt 25; $i++) {{
    try {{
        Copy-Item -Path '{new_exe}' -Destination '{current_exe}' -Force -ErrorAction Stop
        $copySuccess = $true
        Log "Файл успешно заменен на попытке $i"
        break
    }} catch {{
        Log "Попытка $i не удалась (файл занят): $_"
        Start-Sleep -Milliseconds 500
    }}
}}

if ($copySuccess) {{
    Log "Удаление временного файла и запуск обновленной версии..."
    Remove-Item -Path '{new_exe}' -Force -ErrorAction SilentlyContinue
    Start-Process -FilePath '{current_exe}'
    Log "Обновление завершено успешно!"
}} else {{
    Log "ОШИБКА: Не удалось перезаписать файл приложения."
}}

Start-Sleep -Seconds 1
Remove-Item -Path $MyInvocation.MyCommand.Path -Force -ErrorAction SilentlyContinue
"""
            with open(ps_script, "w", encoding="utf-8-sig") as f:
                f.write(ps_content)

            cmd = f'powershell.exe -ExecutionPolicy Bypass -WindowStyle Hidden -File "{ps_script}"'
            subprocess.Popen(
                cmd,
                shell=True,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
            )

            os._exit(0)

        except Exception as e:
            if on_error:
                on_error(str(e))

    threading.Thread(target=_worker, daemon=True).start()