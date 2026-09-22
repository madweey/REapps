import os
import re
import json
import base64
import time
import urllib.parse
import subprocess
import requests

from apps.core.vpn_manager import load_tunnel_states, OnDemandTunnel
from apps.core.sheets import get_split_vpn_keys

BASE_APPDATA = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "REapps")
TEMP_DIR = os.path.join(BASE_APPDATA, "temp_audio")
os.makedirs(TEMP_DIR, exist_ok=True)

GEMINI_API_KEY = "AQ.Ab8RN6J7pqoYY0dOJqEaQ0zINqdmZVXLB1gof1iWG6mNt98zQw"
MODEL_NAME = "gemini-3.6-flash"


def configure_gemini(api_key: str | None = None) -> bool:
    return True


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

    cmd = [
        "ffmpeg", "-y", "-i", input_path,
        "-vn", "-acodec", "libmp3lame",
        "-ac", "1", "-ar", "16000", "-b:a", "32k",
        output_path
    ]

    try:
        subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        return output_path
    except Exception:
        if input_path.lower().endswith((".mp3", ".wav", ".m4a", ".aac")):
            return input_path
        raise Exception("Ошибка обработки ffmpeg. Проверьте наличие ffmpeg.exe.")


def analyze_audio_with_gemini(audio_path: str, prompt_text: str, progress_callback=None) -> dict:
    if progress_callback:
        progress_callback("Чтение и кодирование звука...")

    with open(audio_path, "rb") as f:
        audio_bytes = f.read()

    audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")

    full_instruction = (
        f"{prompt_text}\n\n"
        "СТРОГО СОБЛЮДАЙ ФОРМАТ ВЫВОДА! Раздели весь ответ на три блока с точными маркерами:\n\n"
        "---ТРАНСКРИПЦИЯ---\n"
        "(Полная дословная транскрипция разговора по ролям с таймкодами)\n\n"
        "---ОТЧЕТ ИИ---\n"
        "(Структурированный разбор разговора согласно инструкции выше)\n\n"
        "---КРАТКОЕ САММАРИ---\n"
        "(2-3 емких ключевых предложения с итогом разговора для CRM)"
    )

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL_NAME}:generateContent?key={GEMINI_API_KEY}"
    headers = {"Content-Type": "application/json"}
    payload = {
        "contents": [
            {
                "parts": [
                    {"text": full_instruction},
                    {
                        "inline_data": {
                            "mime_type": "audio/mp3",
                            "data": audio_b64,
                        }
                    }
                ]
            }
        ]
    }

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
                        msg = "Отправка в Gemini через туннель..." if attempt == 0 else f"Повтор {attempt + 1}/3..."
                        progress_callback(msg)
                    with OnDemandTunnel(key_or_none, local_http_port=20820) as proxy_url:
                        proxies = {"http": proxy_url, "https": proxy_url}
                        resp = requests.post(url, headers=headers, json=payload, timeout=120, proxies=proxies)
                else:
                    if progress_callback:
                        msg = "Отправка в Gemini напрямую..." if attempt == 0 else f"Повтор {attempt + 1}/3..."
                        progress_callback(msg)
                    resp = requests.post(url, headers=headers, json=payload, timeout=120)

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

    resp_data = last_resp.json()
    result_text = resp_data["candidates"][0]["content"]["parts"][0]["text"]

    transcription = ""
    full_report = ""
    summary = ""

    if "---ТРАНСКРИПЦИЯ---" in result_text and "---ОТЧЕТ ИИ---" in result_text:
        parts_after_tr = result_text.split("---ТРАНСКРИПЦИЯ---", 1)[1]
        tr_part, rest = parts_after_tr.split("---ОТЧЕТ ИИ---", 1)
        transcription = tr_part.strip()

        if "---КРАТКОЕ САММАРИ---" in rest:
            rep_part, sum_part = rest.split("---КРАТКОЕ САММАРИ---", 1)
            full_report = rep_part.strip()
            summary = sum_part.strip()
        else:
            full_report = rest.strip()
            summary = full_report[:250] + "..."
    elif "---КРАТКОЕ САММАРИ---" in result_text:
        rep_part, sum_part = result_text.split("---КРАТКОЕ САММАРИ---", 1)
        full_report = rep_part.strip()
        summary = sum_part.strip()
        transcription = full_report
    else:
        full_report = result_text.strip()
        transcription = full_report
        summary = full_report[:250] + "..."

    return {
        "transcription": transcription,
        "full_report": full_report,
        "summary": summary,
    }


def analyze_batch_summaries_with_gemini(summaries: list[dict], meta_prompt: str) -> str:
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

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL_NAME}:generateContent?key={GEMINI_API_KEY}"
    headers = {"Content-Type": "application/json"}
    payload = {"contents": [{"parts": [{"text": instruction}]}]}

    _, enable_foreign = load_tunnel_states()
    _, foreign_keys = get_split_vpn_keys()

    candidates = foreign_keys.copy() if (enable_foreign and foreign_keys) else []
    candidates.append(None)

    last_resp = None
    last_err = None

    for key_or_none in candidates:
        for attempt in range(3):
            try:
                if key_or_none:
                    with OnDemandTunnel(key_or_none, local_http_port=20820) as proxy_url:
                        proxies = {"http": proxy_url, "https": proxy_url}
                        resp = requests.post(url, headers=headers, json=payload, timeout=60, proxies=proxies)
                else:
                    resp = requests.post(url, headers=headers, json=payload, timeout=60)

                if resp.status_code == 200:
                    last_resp = resp
                    break

                if resp.status_code == 503:
                    last_resp = resp
                    last_err = resp.text
                    time.sleep(3)
                    continue

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

    return last_resp.json()["candidates"][0]["content"]["parts"][0]["text"]