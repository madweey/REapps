import os
import sys
import json
import ctypes
import threading
import flet as ft

from apps.core.auth import authenticate, load_session, save_session, clear_session
from apps.meetings.meetings_view import MeetingsController
from apps.admin.access_view import AccessView
from apps.admin.links_view import LinksView
from apps.transcription.single_analysis_view import SingleAnalysisView
from apps.transcription.batch_analysis_view import BatchAnalysisView
from apps.transcription.prompts_view import PromptsView
from apps.calculator.dp_view import DPView
from apps.core.sheets import get_split_vpn_keys, save_split_vpn_keys
from apps.core.vpn_manager import load_tunnel_states, save_tunnel_states, ping_key
from apps.core.updater import check_for_updates, download_and_install_update, CURRENT_VERSION

# ==========================================
# WINDOWS APP ID И ЗАЩИТА ОТ ДУБЛИКАТОВ (SINGLE INSTANCE)
# ==========================================
MUTEX_HANDLE = None

def setup_windows_environment():
    """Задает AppUserModelID для отображения корректной иконки в панели задач Windows."""
    if sys.platform == "win32":
        try:
            myappid = "redesignburo.reapps.assistant.1.0"
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
        except Exception:
            pass

def ensure_single_instance() -> bool:
    """
    Проверяет, запущена ли уже копия программы через глобальный мьютекс Windows.
    Если запущена — активирует существующее окно и возвращает False.
    """
    global MUTEX_HANDLE
    if sys.platform != "win32":
        return True

    try:
        kernel32 = ctypes.windll.kernel32
        user32 = ctypes.windll.user32
        mutex_name = "Global\\REapps_SingleInstance_Mutex_REdesign"
        MUTEX_HANDLE = kernel32.CreateMutexW(None, False, mutex_name)
        last_error = kernel32.GetLastError()

        if last_error == 183:
            window_title = f"REapps v{CURRENT_VERSION} - Внутренняя система"
            hwnd = user32.FindWindowW(None, window_title)
            if not hwnd:
                hwnd = user32.FindWindowW(None, None)
            if hwnd:
                user32.ShowWindow(hwnd, 9)  # SW_RESTORE
                user32.SetForegroundWindow(hwnd)
            return False
        return True
    except Exception:
        return True


def build_brand_logo_widget(size: int = 84) -> ft.Control:
    """Отрисовывает логотип RE DESIGN BURO (Вариант 1) строго через нативные компоненты."""
    re_font_size = int(size * 0.40)
    sub_font_size = max(8, int(size * 0.10))
    radius = int(size * 0.22)

    return ft.Container(
        width=size,
        height=size,
        bgcolor="#16181B",
        border_radius=radius,
        alignment=ft.alignment.center,
        content=ft.Column(
            controls=[
                ft.Text(
                    "RE",
                    size=re_font_size,
                    weight=ft.FontWeight.W_900,
                    color="#FFFFFF",
                    text_align=ft.TextAlign.CENTER,
                ),
                ft.Text(
                    "DESIGN BURO",
                    size=sub_font_size,
                    weight=ft.FontWeight.BOLD,
                    color="#94A3B8",
                    text_align=ft.TextAlign.CENTER,
                ),
            ],
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=1,
            tight=True,
        ),
    )


def build_in_development_view(module_name: str) -> ft.Control:
    return ft.Container(
        alignment=ft.alignment.center,
        expand=True,
        content=ft.Column(
            controls=[
                ft.Icon(ft.icons.CONSTRUCTION, size=64, color="#1976D2"),
                ft.Text(module_name, size=24, weight=ft.FontWeight.BOLD, color="#263238"),
                ft.Text("Раздел находится в разработке", size=14, color="#78909C"),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            alignment=ft.MainAxisAlignment.CENTER,
            tight=True,
            spacing=10,
        ),
    )


def main(page: ft.Page):
    page.title = f"REapps v{CURRENT_VERSION} - Внутренняя система"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.padding = 0

    icon_relative_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app_icon.ico")
    if os.path.exists(icon_relative_path):
        page.window.icon = icon_relative_path

    page.locale_configuration = ft.LocaleConfiguration(
        supported_locales=[ft.Locale("ru", "RU")],
        current_locale=ft.Locale("ru", "RU"),
    )

    current_user = {"data": None}
    active_nav_key = {"val": "meetings_book"}
    content_area = ft.Container(expand=True)
    update_checked = {"done": False}

    controllers_cache = {
        "meetings": None,
        "access": None,
        "links": None,
        "transcription_single": None,
        "transcription_batch": None,
        "transcription_prompts": None,
        "calc_dp": None,
    }

    login_name_input = ft.TextField(label="Имя сотрудника (Логин)", width=320, autofocus=True, height=48)
    login_pass_input = ft.TextField(label="Пароль", password=True, can_reveal_password=True, width=320, height=48)
    remember_checkbox = ft.Checkbox(label="Оставаться в системе", value=True)
    login_error_text = ft.Text("", size=12, color="#D32F2F", weight=ft.FontWeight.W_500)
    login_btn = ft.ElevatedButton(
        "Войти в систему",
        icon=ft.icons.LOGIN,
        bgcolor="#1976D2",
        color="#FFFFFF",
        width=320,
        height=45,
    )

    splash_status = ft.Text("Подключение к Google Таблицам...", size=13, color="#616161")

    # ==========================================
    # ДИАЛОГ АВТООБНОВЛЕНИЯ
    # ==========================================
    def prompt_update_dialog(update_info: dict):
        prog_bar = ft.ProgressBar(width=420, value=0, visible=False, color="#1976D2")
        status_lbl = ft.Text("", size=11, color="#616161")
        has_exe = bool(update_info.get("download_url"))

        btn_update = ft.ElevatedButton(
            "Обновить сейчас" if has_exe else "Перейти к релизу",
            bgcolor="#1976D2",
            color="#FFFFFF",
        )
        btn_cancel = ft.TextButton("Напомнить позже")

        def close_dlg(e=None):
            dlg.open = False
            page.update()

        def do_update(e):
            download_url = update_info.get("download_url")
            if not download_url:
                page.launch_url(f"https://github.com/madweey/REapps/releases/tag/{update_info.get('version')}")
                close_dlg()
                return

            btn_update.disabled = True
            btn_cancel.disabled = True
            prog_bar.visible = True
            status_lbl.value = "Скачивание обновления..."
            status_lbl.color = "#1976D2"
            page.update()

            def on_progress(pct: float):
                prog_bar.value = pct
                status_lbl.value = f"Загрузка: {int(pct * 100)}%"
                page.update()

            def on_err(err_msg: str):
                btn_update.disabled = False
                btn_cancel.disabled = False
                prog_bar.visible = False
                status_lbl.value = f"Ошибка: {err_msg}"
                status_lbl.color = "#D32F2F"
                page.update()

            def run_update_thread():
                download_and_install_update(
                    download_url=download_url,
                    on_progress=on_progress,
                    on_error=on_err,
                )

            threading.Thread(target=run_update_thread, daemon=True).start()

        btn_update.on_click = do_update
        btn_cancel.on_click = close_dlg

        body_notes = update_info.get("body", "").strip() or "Улучшения стабильности и новые функции."

        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Row([
                ft.Icon(ft.icons.SYSTEM_UPDATE_ROUNDED, color="#1976D2", size=24),
                ft.Text(f"Доступно обновление {update_info.get('version')}", size=16, weight=ft.FontWeight.BOLD),
            ]),
            content=ft.Container(
                width=450,
                content=ft.Column(
                    controls=[
                        ft.Text(f"Текущая версия: v{CURRENT_VERSION}  ->  Новая: {update_info.get('version')}", size=12, color="#424242"),
                        ft.Container(height=4),
                        ft.Text("Что нового:", size=12, weight=ft.FontWeight.BOLD),
                        ft.Container(
                            bgcolor="#F4F6F8",
                            padding=10,
                            border_radius=6,
                            content=ft.Text(body_notes, size=11, color="#37474F"),
                            height=120,
                        ),
                        prog_bar,
                        status_lbl,
                    ],
                    spacing=8,
                    tight=True,
                ),
            ),
            actions=[btn_cancel, btn_update],
        )

        if dlg not in page.overlay:
            page.overlay.append(dlg)
        dlg.open = True
        page.update()

    def start_background_update_check():
        if update_checked["done"]:
            return
        update_checked["done"] = True

        def _worker():
            info = check_for_updates()
            if info:
                try:
                    if hasattr(page, "run_thread"):
                        page.run_thread(prompt_update_dialog, info)
                    elif hasattr(page, "loop") and page.loop and page.loop.is_running():
                        page.loop.call_soon_threadsafe(prompt_update_dialog, info)
                    else:
                        prompt_update_dialog(info)
                except Exception as ex:
                    prompt_update_dialog(info)

        threading.Thread(target=_worker, daemon=True).start()

    def render_splash_screen():
        page.clean()
        page.add(
            ft.Container(
                content=ft.Column(
                    controls=[
                        build_brand_logo_widget(size=88),
                        ft.Container(height=12),
                        ft.Text("REapps", size=26, weight=ft.FontWeight.BOLD, color="#0D47A1"),
                        ft.Container(height=8),
                        ft.ProgressRing(width=34, height=34, stroke_width=3, color="#1976D2"),
                        ft.Container(height=10),
                        splash_status,
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    alignment=ft.MainAxisAlignment.CENTER,
                    tight=True,
                ),
                alignment=ft.alignment.center,
                expand=True,
                bgcolor="#F8FAFC",
            )
        )
        page.update()

    def handle_login(e):
        name = login_name_input.value.strip()
        pwd = login_pass_input.value.strip()
        if not name or not pwd:
            login_error_text.value = "Введите имя и пароль!"
            page.update()
            return
        login_btn.disabled = True
        login_error_text.value = "Проверка..."
        login_error_text.color = "#1976D2"
        page.update()

        user = authenticate(name, pwd)
        login_btn.disabled = False
        if not user:
            login_error_text.value = "Неверное имя или пароль!"
            login_error_text.color = "#D32F2F"
            page.update()
            return

        if remember_checkbox.value:
            save_session(name, pwd)
        else:
            clear_session()
        current_user["data"] = user
        render_main_layout()
        start_background_update_check()

    login_btn.on_click = handle_login
    login_pass_input.on_submit = handle_login

    def render_login_screen(initial_error: str = ""):
        page.clean()
        login_name_input.value = ""
        login_pass_input.value = ""
        login_error_text.value = initial_error
        page.add(
            ft.Container(
                content=ft.Card(
                    elevation=4,
                    content=ft.Container(
                        padding=35,
                        content=ft.Column(
                            controls=[
                                build_brand_logo_widget(size=72),
                                ft.Container(height=6),
                                ft.Text("Вход в REapps", size=22, weight=ft.FontWeight.BOLD),
                                ft.Text("Введите учетные данные для доступа", size=12, color="#757575"),
                                ft.Container(height=10),
                                login_name_input,
                                login_pass_input,
                                remember_checkbox,
                                login_error_text,
                                ft.Container(height=5),
                                login_btn,
                            ],
                            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                            tight=True,
                            spacing=10,
                        ),
                    ),
                ),
                alignment=ft.alignment.center,
                expand=True,
                bgcolor="#F8FAFC",
            )
        )
        page.update()

    def handle_logout(e=None):
        clear_session()
        current_user["data"] = None
        for k in controllers_cache:
            controllers_cache[k] = None
        render_login_screen()

    def open_vpn_dialog(e=None):
        en_ru, en_for = load_tunnel_states()
        ru_keys, foreign_keys = get_split_vpn_keys()

        ru_statuses = {}
        for_statuses = {}

        new_ru_input = ft.TextField(hint_text="Ключ РФ (vless://...)", expand=True, dense=True, text_size=11)
        new_for_input = ft.TextField(hint_text="Ключ Зарубеж (vless://...)", expand=True, dense=True, text_size=11)

        ru_col = ft.Column(spacing=4)
        for_col = ft.Column(spacing=4)

        def build_key_item(k_text: str, is_ru: bool):
            st_dict = ru_statuses if is_ru else for_statuses
            st = st_dict.get(k_text)
            if st is True:
                s_icon = ft.Icon(ft.icons.CHECK_CIRCLE, color="#388E3C", size=16)
            elif st is False:
                s_icon = ft.Icon(ft.icons.CANCEL, color="#D32F2F", size=16)
            else:
                s_icon = ft.Icon(ft.icons.HELP_OUTLINE, color="#9E9E9E", size=16)

            def remove_me(ev):
                target_list = ru_keys if is_ru else foreign_keys
                if k_text in target_list:
                    target_list.remove(k_text)
                    save_split_vpn_keys(ru_keys, foreign_keys)
                    refresh_dialog_lists()
                    render_sidebar()
                    page.update()

            def ping_me(ev):
                s_icon.name = ft.icons.HOURGLASS_EMPTY
                page.update()
                st_dict[k_text] = ping_key(k_text)
                refresh_dialog_lists()
                page.update()

            return ft.Container(
                bgcolor="#FFFFFF",
                border=ft.border.all(1, "#E0E0E0"),
                border_radius=6,
                padding=ft.padding.symmetric(horizontal=8, vertical=4),
                content=ft.Row(
                    controls=[
                        s_icon,
                        ft.Text(k_text[:38] + "...", size=11, expand=True, tooltip=k_text),
                        ft.IconButton(ft.icons.REFRESH, icon_size=16, tooltip="Проверить", on_click=ping_me),
                        ft.IconButton(ft.icons.DELETE_OUTLINE, icon_size=16, icon_color="#E57373", tooltip="Удалить", on_click=remove_me),
                    ],
                    spacing=4,
                ),
            )

        def refresh_dialog_lists():
            ru_col.controls = [build_key_item(k, True) for k in ru_keys]
            if not ru_keys:
                ru_col.controls.append(ft.Text("Нет ключей РФ (M3:M5)", size=11, color="#757575"))

            for_col.controls = [build_key_item(k, False) for k in foreign_keys]
            if not foreign_keys:
                for_col.controls.append(ft.Text("Нет ключей Зарубеж (M6:M8)", size=11, color="#757575"))

        def on_ru_switch(ev):
            nonlocal en_ru
            en_ru = ev.control.value
            save_tunnel_states(en_ru, en_for)
            render_sidebar()
            page.update()

        def on_for_switch(ev):
            nonlocal en_for
            en_for = ev.control.value
            save_tunnel_states(en_ru, en_for)
            render_sidebar()
            page.update()

        def add_ru_key(ev):
            v = new_ru_input.value.strip()
            if not v or len(ru_keys) >= 3:
                return
            ru_keys.append(v)
            save_split_vpn_keys(ru_keys, foreign_keys)
            new_ru_input.value = ""
            refresh_dialog_lists()
            render_sidebar()
            page.update()

        def add_for_key(ev):
            v = new_for_input.value.strip()
            if not v or len(foreign_keys) >= 3:
                return
            foreign_keys.append(v)
            save_split_vpn_keys(ru_keys, foreign_keys)
            new_for_input.value = ""
            refresh_dialog_lists()
            render_sidebar()
            page.update()

        refresh_dialog_lists()

        dlg = ft.AlertDialog(
            title=ft.Row([ft.Icon(ft.icons.TUNE, color="#1976D2"), ft.Text("Управление туннелями VPN", size=16, weight=ft.FontWeight.BOLD)]),
            content=ft.Container(
                width=480,
                content=ft.Column(
                    controls=[
                        ft.Text("Включается строго по требованию в момент разбора:", size=11, color="#757575"),
                        ft.Container(
                            bgcolor="#F4F8FA",
                            padding=10,
                            border_radius=8,
                            content=ft.Column(
                                controls=[
                                    ft.Row(
                                        [
                                            ft.Icon(ft.icons.PHONE_IN_TALK, color="#1565C0", size=18),
                                            ft.Text("🇷🇺 Туннель РФ (для МегаФон)", size=12, weight=ft.FontWeight.BOLD, expand=True),
                                            ft.Switch(value=en_ru, on_change=on_ru_switch),
                                        ],
                                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN
                                    ),
                                    ft.Text("Нужен в Ереване для скачивания записей. В РФ выключить.", size=10, color="#757575"),
                                    ru_col,
                                    ft.Row([new_ru_input, ft.IconButton(ft.icons.ADD_CIRCLE, icon_color="#1976D2", on_click=add_ru_key)], spacing=4),
                                ],
                                spacing=6,
                            )
                        ),
                        ft.Container(
                            bgcolor="#F6F7F9",
                            padding=10,
                            border_radius=8,
                            content=ft.Column(
                                controls=[
                                    ft.Row(
                                        [
                                            ft.Icon(ft.icons.AUTO_AWESOME, color="#6A1B9A", size=18),
                                            ft.Text("🌐 Туннель Зарубеж (для Gemini ИИ)", size=12, weight=ft.FontWeight.BOLD, expand=True),
                                            ft.Switch(value=en_for, on_change=on_for_switch),
                                        ],
                                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN
                                    ),
                                    ft.Text("Нужен в РФ для разборов через ИИ. В Ереване выключить.", size=10, color="#757575"),
                                    for_col,
                                    ft.Row([new_for_input, ft.IconButton(ft.icons.ADD_CIRCLE, icon_color="#8E24AA", on_click=add_for_key)], spacing=4),
                                ],
                                spacing=6,
                            )
                        ),
                    ],
                    spacing=12,
                    tight=True,
                )
            ),
            actions=[ft.TextButton("Закрыть", on_click=lambda ev: (setattr(dlg, "open", False), page.update()))],
        )
        if dlg not in page.overlay:
            page.overlay.append(dlg)
        dlg.open = True
        page.update()

    sidebar_container = ft.Container(
        width=240,
        bgcolor="#F8FAFC",
        padding=ft.padding.symmetric(horizontal=8, vertical=12),
    )

    def render_sidebar():
        user = current_user["data"]
        menu_items = []

        def make_nav_item(title: str, icon: str, key: str, is_subitem: bool = False, badge: str | None = None):
            is_active = (active_nav_key["val"] == key)

            default_bg = "#EBF3FC" if is_active else ft.colors.TRANSPARENT
            hover_bg = "#E1ECF9" if is_active else "#F1F5F9"
            icon_color = "#1565C0" if is_active else "#64748B"
            text_color = "#0D47A1" if is_active else "#334155"
            text_weight = ft.FontWeight.BOLD if is_active else ft.FontWeight.W_500

            indicator = ft.Container(
                width=3,
                height=18,
                border_radius=2,
                bgcolor="#1976D2" if is_active else ft.colors.TRANSPARENT,
            )

            label_row_controls = [
                indicator,
                ft.Icon(icon, size=16, color=icon_color),
                ft.Text(title, size=13, weight=text_weight, color=text_color, expand=True),
            ]

            if badge:
                label_row_controls.append(
                    ft.Container(
                        content=ft.Text(badge, size=9, color="#64748B", weight=ft.FontWeight.W_600),
                        bgcolor="#E2E8F0",
                        padding=ft.padding.symmetric(horizontal=5, vertical=2),
                        border_radius=4,
                    )
                )

            item_container = ft.Container(
                content=ft.Row(label_row_controls, spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                padding=ft.padding.only(left=10 if is_subitem else 6, top=7, bottom=7, right=8),
                border_radius=6,
                bgcolor=default_bg,
                on_click=lambda e, k=key: load_module_by_key(k),
            )

            def on_item_hover(e):
                item_container.bgcolor = hover_bg if e.data == "true" else default_bg
                item_container.update()

            item_container.on_hover = on_item_hover
            return item_container

        if user.get("can_meetings"):
            menu_items.append(
                ft.ExpansionTile(
                    leading=ft.Icon(ft.icons.CALENDAR_MONTH, color="#64748B", size=18),
                    title=ft.Text("Встречи", size=13, weight=ft.FontWeight.W_600, color="#1E293B"),
                    controls=[
                        make_nav_item("Назначение встречи", ft.icons.ADD_TASK, "meetings_book", True),
                        make_nav_item("Расписание встреч", ft.icons.VIEW_TIMELINE, "meetings_schedule", True),
                        make_nav_item("Реестр встреч", ft.icons.LIST_ALT, "meetings_registry", True),
                    ],
                    initially_expanded=active_nav_key["val"].startswith("meetings_"),
                )
            )

        if user.get("can_transcription"):
            menu_items.append(
                ft.ExpansionTile(
                    leading=ft.Icon(ft.icons.MIC, color="#64748B", size=18),
                    title=ft.Text("Транскрибация", size=13, weight=ft.FontWeight.W_600, color="#1E293B"),
                    controls=[
                        make_nav_item("Разбор звонка / встречи", ft.icons.RECORD_VOICE_OVER, "transcription_single", True),
                        make_nav_item("Анализ разборов (пакетный)", ft.icons.ANALYTICS_OUTLINED, "transcription_batch", True),
                        make_nav_item("Промты", ft.icons.PSYCHOLOGY, "transcription_prompts", True),
                    ],
                    initially_expanded=active_nav_key["val"].startswith("transcription_"),
                )
            )

        if user.get("can_calculator"):
            menu_items.append(
                ft.ExpansionTile(
                    leading=ft.Icon(ft.icons.CALCULATE, color="#64748B", size=18),
                    title=ft.Text("Калькулятор", size=13, weight=ft.FontWeight.W_600, color="#1E293B"),
                    controls=[
                        make_nav_item("Калькулятор ДП", ft.icons.DRAW_OUTLINED, "calculator_dp", True),
                        make_nav_item("Калькулятор ремонта", ft.icons.HOME_REPAIR_SERVICE_OUTLINED, "calculator_repair", True, badge="в разработке"),
                        make_nav_item("Смета", ft.icons.REQUEST_QUOTE_OUTLINED, "estimate", True, badge="в разработке"),
                    ],
                    initially_expanded=active_nav_key["val"].startswith("calculator_") or active_nav_key["val"] == "estimate",
                )
            )

        if user.get("can_reports"):
            menu_items.append(make_nav_item("Отчеты", ft.icons.INSERT_CHART_OUTLINED, "reports", False, badge="в разработке"))

        if user.get("can_access_settings"):
            menu_items.append(
                ft.ExpansionTile(
                    leading=ft.Icon(ft.icons.SETTINGS, color="#64748B", size=18),
                    title=ft.Text("Настройки", size=13, weight=ft.FontWeight.W_600, color="#1E293B"),
                    controls=[
                        make_nav_item("Доступы", ft.icons.ADMIN_PANEL_SETTINGS_OUTLINED, "access", True),
                        make_nav_item("Ссылки", ft.icons.LINK, "links", True),
                    ],
                    initially_expanded=active_nav_key["val"] in ("access", "links"),
                )
            )

        en_ru, en_for = load_tunnel_states()
        status_parts = []
        if en_ru:
            status_parts.append("РФ")
        if en_for:
            status_parts.append("Зарубеж")
        status_text = f"Активен: {', '.join(status_parts)}" if status_parts else "Выключен (Прямой)"
        badge_color = "#2E7D32" if status_parts else "#616161"
        badge_bg = "#E8F5E9" if status_parts else "#ECEFF1"

        vpn_widget = ft.Container(
            padding=ft.padding.symmetric(horizontal=10, vertical=8),
            border_radius=8,
            bgcolor=badge_bg,
            border=ft.border.all(1, "#81C784" if status_parts else "#B0BEC5"),
            content=ft.Row(
                controls=[
                    ft.Icon(ft.icons.SECURITY if status_parts else ft.icons.SHIELD_OUTLINED, size=18, color=badge_color),
                    ft.Column(
                        controls=[
                            ft.Text("Шлюз (VPN)", size=11, weight=ft.FontWeight.BOLD, color="#212121"),
                            ft.Text(status_text, size=10, color=badge_color),
                        ],
                        spacing=1,
                        expand=True,
                    ),
                    ft.Icon(ft.icons.TUNE, size=16, color="#616161"),
                ],
                spacing=8,
            ),
            on_click=open_vpn_dialog,
        )

        user_card = ft.Container(
            padding=10,
            border_radius=8,
            bgcolor="#FFFFFF",
            content=ft.Row(
                controls=[
                    ft.Icon(ft.icons.ACCOUNT_CIRCLE, size=32, color="#1976D2"),
                    ft.Column(
                        controls=[
                            ft.Text(user["name"], size=12, weight=ft.FontWeight.BOLD),
                            ft.Text(user["role"], size=10, color="#757575"),
                        ],
                        spacing=1,
                        expand=True,
                    ),
                    ft.IconButton(ft.icons.LOGOUT, icon_size=18, icon_color="#E57373", on_click=handle_logout),
                ],
                spacing=8,
            ),
        )

        sidebar_container.content = ft.Column(
            controls=[
                ft.Container(
                    content=ft.Row([
                        build_brand_logo_widget(size=30),
                        ft.Text("REapps", size=17, weight=ft.FontWeight.BOLD),
                        ft.Container(
                            bgcolor="#E3F2FD",
                            padding=ft.padding.symmetric(horizontal=6, vertical=2),
                            border_radius=4,
                            content=ft.Text(f"v{CURRENT_VERSION}", size=9, color="#1976D2", weight=ft.FontWeight.BOLD)
                        ),
                    ], spacing=8),
                    padding=ft.padding.only(left=8, bottom=8, top=4),
                ),
                ft.Divider(height=1),
                ft.Column(controls=menu_items, spacing=2, expand=True, scroll=ft.ScrollMode.AUTO),
                ft.Divider(height=1),
                vpn_widget,
                user_card,
            ],
            spacing=6,
            expand=True,
        )

    def load_module_by_key(key: str):
        active_nav_key["val"] = key
        user = current_user["data"]

        if key.startswith("meetings_"):
            if not controllers_cache["meetings"]:
                controllers_cache["meetings"] = MeetingsController(page, user)
            content_area.content = controllers_cache["meetings"].get_view(key)
        elif key == "transcription_single":
            if not controllers_cache["transcription_single"]:
                controllers_cache["transcription_single"] = SingleAnalysisView(page, user)
            content_area.content = controllers_cache["transcription_single"]
        elif key == "transcription_batch":
            if not controllers_cache["transcription_batch"]:
                controllers_cache["transcription_batch"] = BatchAnalysisView(page)
            content_area.content = controllers_cache["transcription_batch"]
        elif key == "transcription_prompts":
            if not controllers_cache["transcription_prompts"]:
                controllers_cache["transcription_prompts"] = PromptsView(page)
            content_area.content = controllers_cache["transcription_prompts"]
        elif key == "calculator_dp":
            if not controllers_cache["calc_dp"]:
                controllers_cache["calc_dp"] = DPView(page, user)
            content_area.content = controllers_cache["calc_dp"]
        elif key == "calculator_repair":
            content_area.content = build_in_development_view("Калькулятор ремонта")
        elif key == "estimate":
            content_area.content = build_in_development_view("Смета")
        elif key == "reports":
            content_area.content = build_in_development_view("Отчеты")
        elif key == "access":
            if not controllers_cache["access"]:
                controllers_cache["access"] = AccessView(page, user)
            content_area.content = controllers_cache["access"]
        elif key == "links":
            if not controllers_cache["links"]:
                controllers_cache["links"] = LinksView(page)
            content_area.content = controllers_cache["links"]

        render_sidebar()
        page.update()

    def render_main_layout():
        page.clean()
        user = current_user["data"]
        render_sidebar()
        if user.get("can_meetings"):
            load_module_by_key("meetings_book")
        elif user.get("can_transcription"):
            load_module_by_key("transcription_single")

        page.add(
            ft.Row(
                controls=[
                    sidebar_container,
                    ft.VerticalDivider(width=1),
                    content_area,
                ],
                expand=True,
                spacing=0,
            )
        )
        page.update()

    render_splash_screen()

    def init_app_background():
        try:
            saved_sess = load_session()
            if saved_sess:
                splash_status.value = f"Авторизация: {saved_sess.get('name', '')}..."
                page.update()
                valid_user = authenticate(saved_sess["name"], saved_sess["password"])
                if valid_user:
                    current_user["data"] = valid_user
                    splash_status.value = "Загрузка модулей..."
                    page.update()
                    render_main_layout()
                    start_background_update_check()
                    return
            render_login_screen()
        except Exception as err:
            render_login_screen(initial_error=f"Сбой загрузки: {err}")

    threading.Timer(0.15, init_app_background).start()


if __name__ == "__main__":
    setup_windows_environment()
    if not ensure_single_instance():
        sys.exit(0)
    ft.app(target=main)