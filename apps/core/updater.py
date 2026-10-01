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
    """Извлекает числа из строки версии (v1.1.9 -> (1, 1, 9))."""
    nums = re.findall(r"\d+", ver_str)
    return tuple(map(int, nums)) if nums else (0, 0, 0)


def check_for_updates() -> dict | None:
    """
    Проверяет наличие нового релиза на GitHub.
    Использует официальный API с автоматическим резервным переходом на веб-парсинг.
    """
    print(f"[Updater] Проверка обновлений. Текущая версия: {CURRENT_VERSION}")
    remote_tag = None
    download_url = None
    body_text = ""

    # 1. Запрос к GitHub API
    try:
        resp = requests.get(API_LATEST_URL, headers=HEADERS, timeout=8)
        if resp.status_code == 200:
            data = resp.json()
            remote_tag = data.get("tag_name", "").strip()
            body_text = data.get("body", "")

            for asset in data.get("assets", []):
                if asset.get("name", "").lower() == "reapps.exe":
                    download_url = asset.get("browser_download_url")
                    break
    except Exception as e:
        print(f"[Updater] Ошибка API: {e}")

    # 2. Резервный запрос через веб-редирект
    if not remote_tag:
        try:
            web_url = f"https://github.com/{GITHUB_REPO}/releases/latest"
            web_headers = {"User-Agent": "Mozilla/5.0"}
            resp = requests.get(web_url, headers=web_headers, allow_redirects=True, timeout=8)
            if "/tag/" in resp.url:
                remote_tag = resp.url.split("/tag/")[-1].split('"')[0].split("#")[0].strip()
        except Exception as e:
            print(f"[Updater] Ошибка резервного запроса: {e}")

    if not remote_tag:
        print("[Updater] Не удалось определить версию на сервере.")
        return None

    current_v = parse_version(CURRENT_VERSION)
    remote_v = parse_version(remote_tag)

    if remote_v > current_v:
        if not download_url:
            download_url = f"https://github.com/{GITHUB_REPO}/releases/download/{remote_tag}/REapps.exe"

        return {
            "version": remote_tag,
            "name": f"REapps {remote_tag}",
            "body": body_text or "Доступно новое обновление на GitHub.",
            "download_url": download_url,
            "asset_name": "REapps.exe",
        }

    return None


def download_update_file(download_url: str, on_progress=None, on_success=None, on_error=None):
    """Скачивает бинарник обновления с валидацией целостности и сигнатуры PE."""
    def _worker():
        try:
            if not getattr(sys, "frozen", False):
                if on_error:
                    on_error("Автообновление доступно только в скомпилированной версии (.exe).")
                return

            temp_dir = tempfile.gettempdir()
            new_exe = os.path.join(temp_dir, "REapps_update.exe")

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
                raise Exception("Файл обновления загружен не полностью. Проверьте интернет-соединение.")

            # Валидация размера (бинарник PyInstaller не может быть меньше 20 МБ)
            if not os.path.exists(new_exe) or os.path.getsize(new_exe) < 20 * 1024 * 1024:
                raise Exception("Скачанный файл повреждён или не является полным бинарником.")

            # Валидация сигнатуры PE-файла Windows (первые 2 байта 'MZ')
            with open(new_exe, "rb") as f:
                magic_header = f.read(2)
                if magic_header != b"MZ":
                    raise Exception("Скачанный файл не является корректным исполняемым файлом Windows (.exe).")

            if on_success:
                on_success()

        except Exception as e:
            if on_error:
                on_error(str(e))

    threading.Thread(target=_worker, daemon=True).start()


def apply_update_and_restart():
    """
    Применяет обновление методом атомарного переименования:
    1. Ждёт выгрузки исходного процесса.
    2. Переименовывает REapps.exe в REapps.old (в Windows это разрешено всегда).
    3. Перемещает REapps_update.exe на место REapps.exe.
    4. Запускает чистый REapps.exe.
    5. Удаляет .old файл и сам скрипт.
    """
    try:
        current_exe = os.path.abspath(sys.executable)
        current_dir = os.path.dirname(current_exe)
        old_exe = os.path.join(current_dir, "REapps.old")
        temp_dir = tempfile.gettempdir()
        new_exe = os.path.join(temp_dir, "REapps_update.exe")
        vbs_script = os.path.join(temp_dir, "reapps_atomic_updater.vbs")

        vbs_current_exe = current_exe.replace('"', '""')
        vbs_old_exe = old_exe.replace('"', '""')
        vbs_new_exe = new_exe.replace('"', '""')
        vbs_current_dir = current_dir.replace('"', '""')

        vbs_content = f'''Dim fso, shell
Set fso = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")

' Даём 2 секунды на гарантированное завершение процесса и очистку дескрипторов
WScript.Sleep 2000

' 1. Удаляем предыдущий .old, если остался
On Error Resume Next
If fso.FileExists("{vbs_old_exe}") Then
    fso.DeleteFile "{vbs_old_exe}", True
End If
Err.Clear
On Error GoTo 0

' 2. Атомарное переименование текущего exe в .old (до 10 попыток)
Dim renamed, i
renamed = False

For i = 1 To 10
    On Error Resume Next
    If fso.FileExists("{vbs_current_exe}") Then
        fso.MoveFile "{vbs_current_exe}", "{vbs_old_exe}"
        If Err.Number = 0 Then
            renamed = True
            Err.Clear
            Exit For
        End If
        Err.Clear
    End If
    On Error GoTo 0
    WScript.Sleep 500
Next

' 3. Перемещение нового файла на место основного exe
Dim installed
installed = False

If renamed And fso.FileExists("{vbs_new_exe}") Then
    For i = 1 To 10
        On Error Resume Next
        fso.CopyFile "{vbs_new_exe}", "{vbs_current_exe}", True
        If Err.Number = 0 Then
            installed = True
            Err.Clear
            Exit For
        End If
        Err.Clear
        WScript.Sleep 500
    Next
End If

' 4. Очистка временного загруженного файла
On Error Resume Next
If fso.FileExists("{vbs_new_exe}") Then
    fso.DeleteFile "{vbs_new_exe}", True
End If
Err.Clear
On Error GoTo 0

' 5. Запуск обновленного приложения
If installed Then
    shell.CurrentDirectory = "{vbs_current_dir}"
    shell.Run """{vbs_current_exe}""", 1, False
    
    ' Даем приложению запуститься и удаляем .old
    WScript.Sleep 1500
    On Error Resume Next
    If fso.FileExists("{vbs_old_exe}") Then
        fso.DeleteFile "{vbs_old_exe}", True
    End If
    Err.Clear
    On Error GoTo 0
Else
    ' Если произошёл сбой установки, откатываем старый файл назад
    On Error Resume Next
    If fso.FileExists("{vbs_old_exe}") And Not fso.FileExists("{vbs_current_exe}") Then
        fso.MoveFile "{vbs_old_exe}", "{vbs_current_exe}"
        shell.CurrentDirectory = "{vbs_current_dir}"
        shell.Run """{vbs_current_exe}""", 1, False
    End If
    Err.Clear
    On Error GoTo 0
End If

' 6. Удаление скрипта апдейтера
On Error Resume Next
fso.DeleteFile WScript.ScriptFullName, True
'''
        with open(vbs_script, "w", encoding="cp1251", errors="ignore") as f:
            f.write(vbs_content)

        # Полностью скрытый фоновый запуск через системный wscript.exe
        DETACHED_PROCESS = 0x00000008
        CREATE_NO_WINDOW = 0x08000000

        subprocess.Popen(
            ["wscript.exe", vbs_script],
            creationflags=DETACHED_PROCESS | CREATE_NO_WINDOW,
            close_fds=True,
            shell=False
        )

        os._exit(0)
    except Exception as e:
        print(f"[Updater] Ошибка применения обновления: {e}")
        os._exit(1)