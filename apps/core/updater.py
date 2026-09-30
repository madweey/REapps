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
    """Извлекает только числа из любой строки версии (v.1.1.9 -> (1, 1, 9))."""
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

    # 1. Прямой запрос к GitHub API
    try:
        print(f"[Updater] Запрос к API: {API_LATEST_URL}")
        resp = requests.get(API_LATEST_URL, headers=HEADERS, timeout=8)
        print(f"[Updater] Статус ответа API: {resp.status_code}")

        if resp.status_code == 200:
            data = resp.json()
            remote_tag = data.get("tag_name", "").strip()
            body_text = data.get("body", "")

            for asset in data.get("assets", []):
                if asset.get("name", "").lower() == "reapps.exe":
                    download_url = asset.get("browser_download_url")
                    break
        else:
            print("[Updater] API недоступен (лимит запросов или приватный доступ).")
    except Exception as e:
        print(f"[Updater] Ошибка API запроса: {e}")

    # 2. Резервный запрос через веб-редирект
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
    """Скачивает бинарник обновления во временный каталог с проверкой целостности."""
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
    Создаёт тихий автономный скрипт VBScript (wscript), который выполняется в фоне
    без единого консольного окна, дожидается закрытия программы, аккуратно заменяет
    файл и запускает обновлённое приложение.
    """
    try:
        current_exe = os.path.abspath(sys.executable)
        current_dir = os.path.dirname(current_exe)
        temp_dir = tempfile.gettempdir()
        new_exe = os.path.join(temp_dir, "REapps_new.exe")
        vbs_script = os.path.join(temp_dir, "reapps_updater.vbs")

        # Двойные кавычки для корректной подстановки путей внутри VBS
        vbs_current_exe = current_exe.replace('"', '""')
        vbs_new_exe = new_exe.replace('"', '""')
        vbs_current_dir = current_dir.replace('"', '""')

        vbs_content = f'''Dim fso, shell
Set fso = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")

' Пауза 2.5 секунды: за это время приложение полностью закрывается,
' а PyInstaller спокойно выгружает свои библиотеки и удаляет папку MEI
WScript.Sleep 2500

' Попытка замены файла (до 15 попыток с интервалом в полсекунды)
Dim replaced, i
replaced = False

For i = 1 To 15
    On Error Resume Next
    If fso.FileExists("{vbs_new_exe}") Then
        fso.CopyFile "{vbs_new_exe}", "{vbs_current_exe}", True
        If Err.Number = 0 Then
            replaced = True
            Err.Clear
            Exit For
        End If
        Err.Clear
    End If
    On Error GoTo 0
    WScript.Sleep 500
Next

' Удаляем временный скачанный файл
On Error Resume Next
If fso.FileExists("{vbs_new_exe}") Then
    fso.DeleteFile "{vbs_new_exe}", True
End If
Err.Clear
On Error GoTo 0

' Запускаем обновленное приложение
If replaced Then
    shell.CurrentDirectory = "{vbs_current_dir}"
    shell.Run """{vbs_current_exe}""", 1, False
End If

' Удаляем сам VBScript скрипт
On Error Resume Next
fso.DeleteFile WScript.ScriptFullName, True
'''
        with open(vbs_script, "w", encoding="cp1251", errors="ignore") as f:
            f.write(vbs_content)

        # wscript.exe выполняет скрипты GUI без открытия черных окон
        DETACHED_PROCESS = 0x00000008
        CREATE_NO_WINDOW = 0x08000000

        subprocess.Popen(
            ["wscript.exe", vbs_script],
            creationflags=DETACHED_PROCESS | CREATE_NO_WINDOW,
            close_fds=True,
            shell=False
        )

        # Принудительный быстрый выход на уровне ОС (окно Flet к этому моменту уже закрыто)
        os._exit(0)
    except Exception as e:
        print(f"[Updater] Сбой перезапуска: {e}")
        os._exit(1)