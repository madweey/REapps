import os
import sys
import tempfile
import subprocess
import threading
import requests
import re

CURRENT_VERSION = "1.1.9"
GITHUB_REPO = "madweey/REapps"
API_LATEST_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"

HEADERS = {
    "User-Agent": "REapps-Updater-Client",
    "Accept": "application/vnd.github.v3+json",
}


def parse_version(ver_str: str) -> tuple:
    """Извлекает только числа из любой строки версии (v.1.1.8 -> (1, 1, 8))."""
    nums = re.findall(r"\d+", ver_str)
    return tuple(map(int, nums)) if nums else (0, 0, 0)


def check_for_updates() -> dict | None:
    """
    Проверяет наличие нового релиза через официальный GitHub API.
    В случае сетевых ограничений (403) делает запасной запрос через веб-редирект.
    """
    print(f"[Updater] Проверка обновлений. Локальная версия: {CURRENT_VERSION}")
    remote_tag = None
    download_url = None
    body_text = ""

    # Способ 1: Прямой запрос к GitHub API
    try:
        print(f"[Updater] Запрос к API: {API_LATEST_URL}")
        resp = requests.get(API_LATEST_URL, headers=HEADERS, timeout=8)
        print(f"[Updater] Статус ответа API: {resp.status_code}")

        if resp.status_code == 200:
            data = resp.json()
            remote_tag = data.get("tag_name", "").strip()
            body_text = data.get("body", "")

            # Поиск прямой ссылки на REapps.exe в assets
            for asset in data.get("assets", []):
                if asset.get("name", "").lower() == "reapps.exe":
                    download_url = asset.get("browser_download_url")
                    break
        else:
            print("[Updater] API недоступен (лимит запросов или приватный доступ).")
    except Exception as e:
        print(f"[Updater] Ошибка API запроса: {e}")

    # Способ 2 (Резервный): Определение тега через веб-редирект
    if not remote_tag:
        try:
            web_url = f"https://github.com/{GITHUB_REPO}/releases/latest"
            print(f"[Updater] Запуск резервного парсинга веб-страницы: {web_url}")
            web_headers = {"User-Agent": "Mozilla/5.0"}
            resp = requests.get(web_url, headers=web_headers, allow_redirects=True, timeout=8)
            print(f"[Updater] Резервный статус: {resp.status_code}, Итоговый URL: {resp.url}")

            if "/tag/" in resp.url:
                remote_tag = resp.url.split("/tag/")[-1].split('"')[0].split("#")[0].strip()
        except Exception as e:
            print(f"[Updater] Ошибка резервного запроса: {e}")

    if not remote_tag:
        print("[Updater] ОШИБКА: Не удалось определить версию на сервере GitHub.")
        return None

    print(f"[Updater] Найден релиз на GitHub: {remote_tag}")

    current_v = parse_version(CURRENT_VERSION)
    remote_v = parse_version(remote_tag)

    print(f"[Updater] Сравнение версий: Локальная {current_v} | GitHub {remote_v}")

    if remote_v > current_v:
        print("[Updater] Найдена новая версия! Готовим данные для обновления.")
        if not download_url:
            download_url = f"https://github.com/{GITHUB_REPO}/releases/download/{remote_tag}/REapps.exe"

        return {
            "version": remote_tag,
            "name": f"REapps {remote_tag}",
            "body": body_text or "Доступно новое обновление на GitHub.",
            "download_url": download_url,
            "asset_name": "REapps.exe",
        }

    print("[Updater] Обновление не требуется. Установлена актуальная версия.")
    return None


def download_update_file(download_url: str, on_progress=None, on_success=None, on_error=None):
    """Скачивает бинарник обновления во временный каталог с проверкой размера."""
    def _worker():
        try:
            if not getattr(sys, "frozen", False):
                if on_error:
                    on_error("Автообновление доступно только в скомпилированной версии (.exe).")
                return

            temp_dir = tempfile.gettempdir()
            new_exe = os.path.join(temp_dir, "REapps_new.exe")

            if os.path.exists(new_exe):
                try:
                    os.remove(new_exe)
                except Exception:
                    pass

            download_headers = {"User-Agent": "Mozilla/5.0"}
            resp = requests.get(download_url, headers=download_headers, stream=True, timeout=300)
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

            if total_len > 0 and downloaded < total_len:
                raise Exception("Файл обновления скачан не полностью. Проверьте соединение с интернетом.")

            if os.path.exists(new_exe) and os.path.getsize(new_exe) < 10 * 1024 * 1024:
                raise Exception("Скачанный файл поврежден или имеет недопустимо малый размер.")

            if on_success:
                on_success()

        except Exception as e:
            if on_error:
                on_error(str(e))

    threading.Thread(target=_worker, daemon=True).start()


def apply_update_and_restart():
    """
    Заменяет текущий .exe новым через PowerShell и перезапускает программу
    с корректным ожиданием освобождения файловых блокировок и DLL.
    """
    try:
        current_exe = os.path.abspath(sys.executable)
        current_dir = os.path.dirname(current_exe)
        current_exe_name = os.path.basename(current_exe)
        temp_dir = tempfile.gettempdir()
        new_exe = os.path.join(temp_dir, "REapps_new.exe")
        log_file = os.path.join(temp_dir, "reapps_update.log")
        ps_script = os.path.join(temp_dir, "reapps_updater.ps1")
        pid = os.getpid()

        ps_content = f"""
$ErrorActionPreference = "Continue"
$log = "{log_file}"

function Log($msg) {{
    $time = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    "[$time] $msg" | Out-File -FilePath $log -Append -Encoding utf8
}}

Log "Запуск процедуры обновления. Текущий PID: {pid}"
Log "Целевой путь: '{current_exe}'"

# Ожидание завершения исходного процесса
$attempts = 0
while ((Get-Process -Id {pid} -ErrorAction SilentlyContinue) -and ($attempts -lt 40)) {{
    Start-Sleep -Milliseconds 250
    $attempts++
}}

taskkill /F /PID {pid} /T 2>$null
taskkill /F /IM "{current_exe_name}" /T 2>$null
taskkill /F /IM "REapps.exe" /T 2>$null

# Пауза для полной выгрузки DLL из памяти и снятия файловых блокировок Windows
Start-Sleep -Seconds 3

$copySuccess = $false
for ($i = 0; $i -lt 40; $i++) {{
    try {{
        Copy-Item -Path '{new_exe}' -Destination '{current_exe}' -Force -ErrorAction Stop
        $copySuccess = $true
        Log "Файл успешно скопирован на попытке $i"
        break
    }} catch {{
        Log "Попытка замены $i: $_"
        Start-Sleep -Milliseconds 600
    }}
}}

if ($copySuccess) {{
    Remove-Item -Path '{new_exe}' -Force -ErrorAction SilentlyContinue
    
    # Дополнительная пауза перед запуском для корректной распаковки PyInstaller
    Start-Sleep -Seconds 2
    
    Set-Location -Path '{current_dir}'
    Start-Process -FilePath '{current_exe}' -WorkingDirectory '{current_dir}'
    Log "Приложение успешно перезапущено."
}} else {{
    Log "Критический сбой: не удалось скопировать обновленный файл."
}}

Start-Sleep -Seconds 2
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
        print(f"[Updater] Сбой перезапуска: {e}")
        os._exit(1)