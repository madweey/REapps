import os
import sys
import json
import time
import urllib.parse
import subprocess
import requests

BASE_APPDATA = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "REapps")
TEMP_DIR = os.path.join(BASE_APPDATA, "temp_audio")
STATE_FILE = os.path.join(TEMP_DIR, "tunnel_state.json")
os.makedirs(TEMP_DIR, exist_ok=True)


def get_xray_path() -> str:
    """Возвращает путь к xray.exe."""
    if getattr(sys, "frozen", False):
        base_dir = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    else:
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    exe_path = os.path.join(base_dir, "xray.exe")
    if os.path.exists(exe_path):
        return exe_path
    local_path = os.path.join(os.path.dirname(sys.executable), "xray.exe")
    if os.path.exists(local_path):
        return local_path
    return "xray.exe"


def load_tunnel_states() -> tuple[bool, bool]:
    try:
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                d = json.load(f)
                return d.get("enable_ru", False), d.get("enable_foreign", False)
    except Exception:
        pass
    return False, False


def save_tunnel_states(enable_ru: bool, enable_foreign: bool):
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump({"enable_ru": enable_ru, "enable_foreign": enable_foreign}, f)
    except Exception:
        pass


def parse_vless_url(vless_url: str) -> dict | None:
    try:
        raw = vless_url.strip()
        if not raw.startswith("vless://"):
            return None
        parsed = urllib.parse.urlparse(raw)
        uuid = parsed.username
        host = parsed.hostname
        port = parsed.port or 443
        query = urllib.parse.parse_qs(parsed.query)

        security = query.get("security", ["none"])[0]
        flow = query.get("flow", [""])[0]
        sni = query.get("sni", [""])[0]
        pbk = query.get("pbk", [""])[0]
        sid = query.get("sid", [""])[0]
        fp = query.get("fp", ["chrome"])[0]
        net_type = query.get("type", ["tcp"])[0]

        return {
            "uuid": uuid,
            "host": host,
            "port": port,
            "security": security,
            "flow": flow,
            "sni": sni,
            "pbk": pbk,
            "sid": sid,
            "fp": fp,
            "type": net_type,
        }
    except Exception:
        return None


def generate_xray_config(parsed_key: dict, local_http_port: int, local_socks_port: int) -> dict:
    """Генерирует надежный JSON-конфиг для Xray с DNS 1.1.1.1 и 8.8.8.8."""
    outbound = {
        "protocol": "vless",
        "settings": {
            "vnext": [
                {
                    "address": parsed_key["host"],
                    "port": parsed_key["port"],
                    "users": [
                        {
                            "id": parsed_key["uuid"],
                            "encryption": "none",
                            "flow": parsed_key["flow"] if parsed_key["security"] == "reality" else ""
                        }
                    ]
                }
            ]
        },
        "streamSettings": {
            "network": parsed_key["type"],
            "security": parsed_key["security"]
        }
    }

    if parsed_key["security"] == "reality":
        outbound["streamSettings"]["realitySettings"] = {
            "show": False,
            "fingerprint": parsed_key["fp"] or "chrome",
            "serverName": parsed_key["sni"],
            "publicKey": parsed_key["pbk"],
            "shortId": parsed_key["sid"],
            "spiderX": ""
        }
    elif parsed_key["security"] == "tls":
        outbound["streamSettings"]["tlsSettings"] = {
            "serverName": parsed_key["sni"],
            "fingerprint": parsed_key["fp"] or "chrome"
        }

    config = {
        "log": {"loglevel": "none"},
        "dns": {
            "servers": ["1.1.1.1", "8.8.8.8", "localhost"]
        },
        "inbounds": [
            {
                "listen": "127.0.0.1",
                "port": local_http_port,
                "protocol": "http",
                "settings": {"timeout": 60}
            },
            {
                "listen": "127.0.0.1",
                "port": local_socks_port,
                "protocol": "socks",
                "settings": {"auth": "noauth", "udp": True}
            }
        ],
        "outbounds": [
            outbound,
            {"protocol": "freedom", "tag": "direct"}
        ]
    }
    return config


class OnDemandTunnel:
    """
    Контекстный менеджер. Запускает xray.exe ТОЛЬКО на время сетевого запроса
    и принудительно убивает процесс при выходе.
    """
    def __init__(self, key_str: str, local_http_port: int = 20808):
        self.key_str = key_str.strip()
        self.local_http_port = local_http_port
        self.local_socks_port = local_http_port + 1
        self.process = None
        self.is_native_proxy = self.key_str.startswith("http://") or self.key_str.startswith("socks5://")

    def __enter__(self):
        if not self.key_str:
            return None

        if self.is_native_proxy:
            return self.key_str

        parsed = parse_vless_url(self.key_str)
        if not parsed:
            raise Exception("Некорректный формат ключа vless://")

        xray_exe = get_xray_path()
        if not os.path.exists(xray_exe):
            raise Exception(f"Файл ядра {xray_exe} не найден рядом с программой!")

        config = generate_xray_config(parsed, self.local_http_port, self.local_socks_port)
        cfg_path = os.path.join(TEMP_DIR, f"xray_cfg_{self.local_http_port}.json")
        with open(cfg_path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)

        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = subprocess.SW_HIDE

        self.process = subprocess.Popen(
            [xray_exe, "run", "-c", cfg_path],
            startupinfo=startupinfo,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

        time.sleep(1.0)  # Даем ядру полностью подняться
        if self.process.poll() is not None:
            raise Exception("Ядро xray.exe завершилось с ошибкой при старте.")

        return f"http://127.0.0.1:{self.local_http_port}"

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.process:
            try:
                self.process.terminate()
                self.process.kill()
            except Exception:
                pass
            self.process = None


def ping_key(key_str: str) -> bool:
    """Проверяет пинг ключа прямо до Google API."""
    if not key_str or not key_str.strip():
        return False
    k = key_str.strip()
    try:
        with OnDemandTunnel(k, local_http_port=20890) as proxy_url:
            p_dict = {"http": proxy_url, "https": proxy_url} if proxy_url else None
            r = requests.get("https://generativelanguage.googleapis.com", proxies=p_dict, timeout=6)
            return r.status_code in [200, 400, 403, 404]
    except Exception:
        return False