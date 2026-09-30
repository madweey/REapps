import os
import sys
import re
import json
import base64
import time
import shutil
import urllib.parse
import subprocess
import requests

from apps.core.vpn_manager import load_tunnel_states, OnDemandTunnel
from apps.core.sheets import get_split_vpn_keys, get_gemini_api_key_from_sheet

BASE_APPDATA = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "REapps")
TEMP_DIR = os.path.join(BASE_APPDATA, "temp_audio")
os.makedirs(TEMP_DIR, exist_ok=True)

MODEL_NAME = "gemini-3.6-flash"


def get_bundle_dir() -> str:
    """Возвращает базовую директорию сборки или проекта."""
    if getattr(sys, "frozen", False):
        return getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def get_binary_path(binary_name: str) -> str:
    """
    Глубокий поиск бинарника (ffmpeg.exe):
    1. _MEIPASS (при PyInstaller onefile)
    2. Рядом с .exe / в корне проекта
    3. В подпапках bin/, ffmpeg/, ffmpeg/bin/
    4. В LocalAppData / Roaming
    5. Системный PATH через shutil.which
    """
    exe_name = f"{binary_name}.exe" if sys.platform == "win32" and not binary_name.endswith(".exe") else binary_name

    candidate_dirs = []

    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        candidate_dirs.extend([
            meipass,
            os.path.join(meipass, "bin"),
            os.path.join(meipass, "ffmpeg"),
            os.path.join(meipass, "ffmpeg", "bin")
        ])

    if getattr(sys, "frozen", False):
        exe_dir = os.path.dirname(sys.executable)
        candidate_dirs.extend([
            exe_dir,
            os.path.join(exe_dir, "bin"),
            os.path.join(exe_dir, "ffmpeg"),
            os.path.join(exe_dir, "ffmpeg", "bin")
        ])

    root_dir = get_bundle_dir()
    candidate_dirs.extend([
        root_dir,
        os.path.join(root_dir, "bin"),
        os.path.join(root_dir, "ffmpeg"),
        os.path.join(root_dir, "ffmpeg", "bin")
    ])

    local_app_data = os.environ.get("LOCALAPPDATA", "")
    if local_app_data:
        candidate_dirs.extend([
            os.path.join(local_app_data, "REapps", "bin"),
            os.path.join(local_app_data, "Programs", "ffmpeg", "bin"),
            os.path.join(local_app_data, "Microsoft", "WinGet", "Links")
        ])

    for cdir in candidate_dirs:
        if cdir and os.path.isdir(cdir):
            target = os.path.join(cdir, exe_name)
            if os.path.exists(target):
                return os.path.abspath(target)

    # Проверка через системный PATH
    sys_path_find = shutil.which(binary_name) or shutil.which(exe_name)
    if sys_path_find:
        return sys_path_find

    return binary_name


def get_current_gemini_key() -> str:
    api_key = get_gemini_api_key_from_sheet()
    if not api_key:
        api_key = os.environ.get("GEMINI_API_KEY", "")
    return api_key.strip()


def get_gemini_url(model: str) -> str:
    key = get_current_gemini_key()
    return f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"


def get_yandex_disk_direct_download_url(public_url: str) -> str:
    api_url = "https://cloud-api.yandex.net/v1/disk/public/resources/download"
    encoded = urllib.parse.quote(public_url.strip(), safe="")
    resp = requests.get(f"{api_url}?public_key={encoded}", timeout=15)
    if resp.status_code == 200:
        return resp.json().get("href", "")
    raise Exception(f"Ошибка Яндекс.Диска ({resp.status_code}): {resp.text}")


def download_file_stream(url: str, target_filename: str, progress_callback=None) -> str:
    actual_url = url
    if "disk.yandex." in url or "yadi.sk" in url:
        actual_url = get_yandex_disk_direct_download_url(url)

    target_path = os.path.join(TEMP_DIR, target_filename)
    is_megapbx = "megapbx.ru" in actual_url
    enable_ru, _ = load_tunnel_states()
    ru_keys, _ = get_split_vpn_keys()

    candidates = []
    if is_megapbx and enable_ru and ru_keys:
        candidates = ru_keys.copy()
    else:
        candidates = [None]

    last_error = None
    for key_or_none in candidates:
        try:
            if key_or_none:
                if progress_callback:
                    progress_callback("Подключение через туннель РФ (МегаФон)...")
                with OnDemandTunnel(key_or_none, local_http_port=20810) as proxy_url:
                    proxies = {"http": proxy_url, "https": proxy_url}
                    with requests.get(actual_url, stream=True, timeout=30, proxies=proxies) as r:
                        r.raise_for_status()
                        total_size = int(r.headers.get("content-length", 0))
                        downloaded = 0
                        with open(target_path, "wb") as f:
                            for chunk in r.iter_content(chunk_size=1024 * 1024):
                                if chunk:
                                    f.write(chunk)
                                    downloaded += len(chunk)
                                    if progress_callback and total_size > 0:
                                        progress_callback(downloaded / total_size)
                    return target_path
            else:
                if progress_callback:
                    progress_callback("Скачивание медиафайла...")
                with requests.get(actual_url, stream=True, timeout=45) as r:
                    r.raise_for_status()
                    total_size = int(r.headers.get("content-length", 0))
                    downloaded = 0
                    with open(target_path, "wb") as f:
                        for chunk in r.iter_content(chunk_size=1024 * 1024):
                            if chunk:
                                f.write(chunk)
                                downloaded += len(chunk)
                                if progress_callback and total_size > 0:
                                    progress_callback(downloaded / total_size)
                return target_path
        except Exception as e:
            last_error = e
            continue

    raise Exception(f"Не удалось скачать файл: {last_error}")


def extract_audio_with_ffmpeg(input_path: str, progress_callback=None) -> str:
    output_filename = os.path.splitext(os.path.basename(input_path))[0] + "_compressed.mp3"
    output_path = os.path.join(TEMP_DIR, output_filename)

    if progress_callback:
        progress_callback("Сжатие звука через ffmpeg...")

    ffmpeg_bin = get_binary_path("ffmpeg")

    cmd = [
        ffmpeg_bin, "-y", "-i", input_path,
        "-vn", "-acodec", "libmp3lame",
        "-ac", "1", "-ar", "16000", "-b:a", "32k",
        output_path
    ]

    creationflags = 0x08000000 if sys.platform == "win32" else 0  # CREATE_NO_WINDOW
    try:
        subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True, creationflags=creationflags)
        return output_path
    except Exception as ex:
        if input_path.lower().endswith((".mp3", ".wav", ".m4a", ".aac", ".ogg")):
            return input_path
        raise Exception(f"Ошибка обработки ffmpeg: {ex}. Убедитесь, что ffmpeg.exe лежит рядом с программой или в папке bin/")


def extract_audio_to_folder(source_type: str, source_val: str, output_folder: str, custom_name: str = "", progress_callback=None) -> str:
    """
    Извлекает чистое аудио (MP3 192k) из видео (файла или ссылки) в указанную пользователем папку.
    """
    if not os.path.exists(output_folder):
        os.makedirs(output_folder, exist_ok=True)

    local_input = ""
    is_temp = False

    try:
        if source_type == "url":
            if progress_callback:
                progress_callback("Скачивание видео по ссылке...")
            temp_name = f"download_{int(time.time())}.dat"
            local_input = download_file_stream(source_val, temp_name, progress_callback)
            is_temp = True
            base_title = custom_name.strip() or f"audio_{int(time.time())}"
        else:
            local_input = source_val
            base_title = custom_name.strip() or os.path.splitext(os.path.basename(source_val))[0]

        safe_title = re.sub(r'[\\/*?:"<>|]', "", base_title).strip() or "extracted_audio"
        out_file_path = os.path.join(output_folder, f"{safe_title}.mp3")

        counter = 1
        while os.path.exists(out_file_path):
            out_file_path = os.path.join(output_folder, f"{safe_title}_{counter}.mp3")
            counter += 1

        if progress_callback:
            progress_callback("Извлечение аудиодорожки (MP3)...")

        ffmpeg_bin = get_binary_path("ffmpeg")
        cmd = [
            ffmpeg_bin, "-y", "-i", local_input,
            "-vn", "-acodec", "libmp3lame",
            "-q:a", "2",
            out_file_path
        ]

        creationflags = 0x08000000 if sys.platform == "win32" else 0
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=creationflags)
        if proc.returncode != 0:
            err_text = proc.stderr.decode("utf-8", errors="ignore")
            raise RuntimeError(f"FFmpeg ошибка: {err_text[:200]}")

        return out_file_path

    finally:
        if is_temp and local_input and os.path.exists(local_input):
            try:
                os.remove(local_input)
            except Exception:
                pass


def _post_gemini_request(payload: dict, progress_callback=None, step_label: str = "") -> dict:
    url = get_gemini_url(MODEL_NAME)
    headers = {"Content-Type": "application/json"}

    _, enable_foreign = load_tunnel_states()
    _, foreign_keys = get_split_vpn_keys()

    candidates = []
    if enable_foreign and foreign_keys:
        candidates = foreign_keys.copy()
    candidates.append(None)

    last_resp = None
    last_err = None

    for key_or_none in candidates:
        for attempt in range(3):
            try:
                if key_or_none:
                    if progress_callback:
                        progress_callback(f"{step_label} через туннель (попытка {attempt + 1})...")
                    with OnDemandTunnel(key_or_none, local_http_port=20820) as proxy_url:
                        proxies = {"http": proxy_url, "https": proxy_url}
                        resp = requests.post(url, headers=headers, json=payload, timeout=160, proxies=proxies)
                else:
                    if progress_callback:
                        progress_callback(f"{step_label} напрямую (попытка {attempt + 1})...")
                    resp = requests.post(url, headers=headers, json=payload, timeout=160)

                if resp.status_code == 200:
                    last_resp = resp
                    break

                if resp.status_code == 503:
                    last_resp = resp
                    last_err = resp.text
                    time.sleep(3)
                    continue

                if resp.status_code == 400 and "User location is not supported" in resp.text:
                    last_err = resp.text
                    break

                last_resp = resp
                last_err = resp.text
                break
            except Exception as ex:
                last_err = str(ex)
                break

        if last_resp and last_resp.status_code == 200:
            break

    if not last_resp or last_resp.status_code != 200:
        err_detail = last_resp.text if last_resp else str(last_err)
        raise Exception(f"Ошибка Gemini API: {err_detail}")

    return last_resp.json()


def analyze_audio_with_gemini(audio_path: str, prompt_text: str, progress_callback=None) -> dict:
    """
    Двухэтапная обработка записи любой длины:
    1. Гарантированный аналитический разбор РОПа и Саммари (не обрезается лимитом).
    2. Дословная транскрипция с таймкодами.
    """
    key = get_current_gemini_key()
    if not key:
        raise Exception("Не найден API-ключ Gemini в листе 'Настройка' (ячейка M11/M12)!")

    if progress_callback:
        progress_callback("Подготовка аудио к анализу...")

    ext = os.path.splitext(audio_path)[1].lower()
    mime_type_map = {
        ".mp3": "audio/mp3",
        ".wav": "audio/wav",
        ".m4a": "audio/m4a",
        ".aac": "audio/aac",
        ".ogg": "audio/ogg",
        ".flac": "audio/flac"
    }
    mime_type = mime_type_map.get(ext, "audio/mp3")

    with open(audio_path, "rb") as f:
        audio_bytes = f.read()

    audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")

    # ЭТАП 1: Анализ РОПа и Краткое Саммари (Приоритет №1)
    prompt_stage1 = (
        f"{prompt_text}\n\n"
        "ВАЖНО! Сформируй ответ строго по двум блокам с указанными заголовками:\n\n"
        "---КРАТКОЕ САММАРИ---\n"
        "(2-3 емких ключевых предложения с сутью и итогом разговора для CRM)\n\n"
        "---ОТЧЕТ ИИ---\n"
        "(Полный структурированный разбор разговора согласно инструкции выше: боли, возражения, договоренности)"
    )

    payload_analysis = {
        "contents": [
            {
                "parts": [
                    {"text": prompt_stage1},
                    {"inline_data": {"mime_type": mime_type, "data": audio_b64}}
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": 8192
        }
    }

    resp_analysis = _post_gemini_request(payload_analysis, progress_callback, "AI-анализ разговора")
    text_analysis = resp_analysis["candidates"][0]["content"]["parts"][0]["text"]

    summary = ""
    full_report = ""

    # Извлечение Саммари и Отчета с защитой регулярными выражениями
    sum_match = re.search(r"---КРАТКОЕ САММАРИ---(.*?)(?=---ОТЧЕТ ИИ---|$)", text_analysis, re.DOTALL | re.IGNORECASE)
    rep_match = re.search(r"---ОТЧЕТ ИИ---(.*)", text_analysis, re.DOTALL | re.IGNORECASE)

    if sum_match:
        summary = sum_match.group(1).strip()
    if rep_match:
        full_report = rep_match.group(1).strip()

    if not full_report:
        full_report = text_analysis.strip()
    if not summary:
        summary = full_report[:250] + "..."

    # ЭТАП 2: Дословная транскрипция с таймкодами
    prompt_stage2 = (
        "Сделай подробную дословную транскрипцию всего разговора на русском языке с таймкодами и разделением по ролям (например: 00:00 М1: ..., 00:05 М2: ...).\n"
        "СТРОГО начни вывод сразу со строки:\n"
        "---ТРАНСКРИПЦИЯ---"
    )

    payload_transcription = {
        "contents": [
            {
                "parts": [
                    {"text": prompt_stage2},
                    {"inline_data": {"mime_type": mime_type, "data": audio_b64}}
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.1,
            "maxOutputTokens": 8192
        }
    }

    try:
        resp_transcription = _post_gemini_request(payload_transcription, progress_callback, "Стенограмма аудио")
        text_transcription = resp_transcription["candidates"][0]["content"]["parts"][0]["text"]
        tr_match = re.search(r"---ТРАНСКРИПЦИЯ---(.*)", text_transcription, re.DOTALL | re.IGNORECASE)
        transcription = tr_match.group(1).strip() if tr_match else text_transcription.strip()
    except Exception as e:
        transcription = f"Стенограмма не была сформирована: {e}"

    return {
        "transcription": transcription,
        "full_report": full_report,
        "summary": summary,
    }


def analyze_batch_summaries_with_gemini(summaries: list[dict], meta_prompt: str) -> str:
    key = get_current_gemini_key()
    if not key:
        raise Exception("Не найден API-ключ Gemini в листе 'Настройка' (ячейка M11/M12)!")

    context_lines = []
    for idx, s in enumerate(summaries, start=1):
        context_lines.append(
            f"Встреча #{idx} ({s.get('date', '')} | {s.get('comm_type', '')} | {s.get('client_deal', '')}):\n"
            f"{s.get('full_ai_report') or s.get('summary')}\n"
            "----------------------------------------"
        )
    joined_context = "\n".join(context_lines)

    instruction = (
        f"Ты опытный РОП. Ниже приведены разборы {len(summaries)} встреч:\n\n"
        f"{joined_context}\n\n"
        f"Задача / Инструкция:\n{meta_prompt}\n\n"
        "Сформируй четкий аналитический отчет."
    )

    payload = {
        "contents": [{"parts": [{"text": instruction}]}],
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": 8192
        }
    }

    res_json = _post_gemini_request(payload, None, "Пакетный анализ встреч")
    return res_json["candidates"][0]["content"]["parts"][0]["text"]