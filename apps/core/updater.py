import os
import sys
import tempfile
import subprocess
import threading
import requests

CURRENT_VERSION = "1.0.8"
GITHUB_REPO = "madweey/REapps"
RELEASE_URL = f"https://github.com/{GITHUB_REPO}/releases/latest"


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
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        }
        resp = requests.get(RELEASE_URL, headers=headers, allow_redirects=False, timeout=5)
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
    Скачивает новый бинарник и запускает процесс самообновления
    с принудительным завершением старых процессов приложения.
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

            resp = requests.get(download_url, stream=True, timeout=60)
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
$pid_to_wait = {pid}
$attempts = 0

# Ожидание выхода основного процесса
while ((Get-Process -Id $pid_to_wait -ErrorAction SilentlyContinue) -and ($attempts -lt 15)) {{
    Start-Sleep -Milliseconds 300
    $attempts++
}}

# Принудительное уничтожение процессов REapps и движка Flet
taskkill /F /PID $pid_to_wait /T 2>$null
taskkill /F /IM REapps.exe /T 2>$null
taskkill /F /IM flet.exe /T 2>$null
Start-Sleep -Milliseconds 600

$copySuccess = $false
for ($i = 0; $i -lt 15; $i++) {{
    try {{
        Copy-Item -Path '{new_exe}' -Destination '{current_exe}' -Force -ErrorAction Stop
        $copySuccess = $true
        break
    }} catch {{
        Start-Sleep -Milliseconds 600
    }}
}}

if ($copySuccess) {{
    Remove-Item -Path '{new_exe}' -Force -ErrorAction SilentlyContinue
    Start-Process -FilePath '{current_exe}'
}}

Remove-Item -Path $MyInvocation.MyCommand.Path -Force -ErrorAction SilentlyContinue
"""
            with open(ps_script, "w", encoding="utf-8-sig") as f:
                f.write(ps_content)

            vbs_launcher = os.path.join(temp_dir, "reapps_elevate.vbs")
            vbs_content = f'''Set UAC = CreateObject("Shell.Application")
UAC.ShellExecute "powershell.exe", "-ExecutionPolicy Bypass -WindowStyle Hidden -File ""{ps_script}""", "", "runas", 0
'''
            with open(vbs_launcher, "w", encoding="ansi") as f:
                f.write(vbs_content)

            subprocess.Popen(["wscript.exe", vbs_launcher], shell=True)
            os._exit(0)

        except Exception as e:
            if on_error:
                on_error(str(e))

    threading.Thread(target=_worker, daemon=True).start()