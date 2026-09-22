import os
import flet as ft
from datetime import datetime, timedelta
from apps.core.sheets import (
    find_deal_by_link,
    get_meetings_by_date,
    get_all_meetings,
    save_new_meeting,
    normalize_deal_url,
    update_meeting_status,
    update_meeting_details,
    complete_meeting,
    cancel_meeting,
    delete_meeting,
    get_all_prompts,
    get_sheets_client,
)
from apps.core.auth import get_all_accounts
from apps.core.schedule_engine import evaluate_slot_status, get_day_schedule_grid, calculate_end_time
from apps.core.ai_engine import download_file_stream, extract_audio_with_ffmpeg, analyze_audio_with_gemini


def format_ms(ms: int) -> str:
    if not ms or ms < 0:
        return "00:00"
    total_seconds = int(ms // 1000)
    minutes = total_seconds // 60
    seconds = total_seconds % 60
    return f"{minutes:02d}:{seconds:02d}"


def parse_date_safely(d_str: str):
    try:
        return datetime.strptime(d_str.strip(), "%d.%m.%Y").date()
    except Exception:
        return None


def build_oneui_badge(num: str) -> ft.Container:
    """Круглый индикатор шага в мягкой стилистике One UI."""
    return ft.Container(
        content=ft.Text(
            num,
            size=12,
            weight=ft.FontWeight.W_700,
            color="#FFFFFF",
            text_align=ft.TextAlign.CENTER,
        ),
        width=24,
        height=24,
        bgcolor="#0C66E4",
        border_radius=12,
        alignment=ft.alignment.center,
    )


class MeetingsController:
    def __init__(self, page: ft.Page, current_user: dict | None = None):
        self.page = page
        self.current_user = current_user
        self.current_username = (current_user.get("name") if current_user else "Не указан").strip()

        self.deal_cache = {
            "manager": "",
            "client": "",
            "deal_id": "",
            "complex": "",
            "service_type": "",
            "area": "",
            "rooms": "",
            "pains": "",
            "condition": "",
            "keys": "",
            "deal_url": "",
            "comment": "",
            "hooks": "",
        }

        self.deal_verified = False

        self.selected_time = {"start": "", "end": "", "reason": ""}
        self.audio_state = {
            "player": None,
            "is_playing": False,
            "duration_ms": 0,
            "position_ms": 0,
            "rate": 1.0,
        }
        self.action_context = {"meeting": None}
        self.registry_mode = {"all_time": False}

        self._is_loading_schedule = False
        self._is_loading_registry = False
        self._is_deleting = False
        self._is_refreshing_slots = False

        try:
            accs = get_all_accounts()
            self.account_names = sorted(list(set(a["name"] for a in accs if a.get("name"))))
        except Exception:
            self.account_names = [self.current_username] if self.current_username else []

        self._build_ui_elements()
        self._build_modals()
        self.refresh_slots()

    def _build_ui_elements(self):
        # 1. Сделка amoCRM
        self.deal_url_input = ft.TextField(
            label="Ссылка на сделку или ID (amoCRM)",
            hint_text="Вставьте URL или номер сделки amoCRM...",
            text_size=13,
            label_style=ft.TextStyle(size=12, color="#64748B"),
            expand=True,
            height=48,
            filled=True,
            fill_color="#F1F5F9",
            border=ft.InputBorder.NONE,
            border_radius=14,
            prefix_icon=ft.icons.LINK_ROUNDED,
            on_change=self.on_deal_input_changed,
        )

        self.info_card_content = ft.Column(
            controls=[ft.Text("Данные сделки не загружены", italic=True, color="#94A3B8", size=12)],
            spacing=4,
        )
        self.info_card = ft.Container(
            content=self.info_card_content,
            padding=16,
            border_radius=16,
            bgcolor="#F8FAFC",
            border=ft.border.all(1, "#E2E8F0"),
            visible=False,
        )

        # 2. Параметры даты и участников (Шаг 2) — единые шрифты и стиль One UI
        self.date_input = ft.TextField(
            label="Дата встречи",
            hint_text="ДД.ММ.ГГГГ",
            value=datetime.today().strftime("%d.%m.%Y"),
            text_size=13,
            label_style=ft.TextStyle(size=12, color="#64748B"),
            width=175,
            height=48,
            filled=True,
            fill_color="#F1F5F9",
            border=ft.InputBorder.NONE,
            border_radius=14,
            suffix=ft.IconButton(
                icon=ft.icons.CALENDAR_TODAY_OUTLINED,
                icon_size=18,
                tooltip="Выбрать дату",
                on_click=lambda e: self.book_date_picker.pick_date(),
            ),
        )

        self.meeting_type_dropdown = ft.Dropdown(
            label="Тип встречи",
            value="Онлайн встреча",
            text_size=13,
            label_style=ft.TextStyle(size=12, color="#64748B"),
            width=220,
            height=48,
            filled=True,
            fill_color="#F1F5F9",
            border=ft.InputBorder.NONE,
            border_radius=14,
            options=[
                ft.dropdown.Option("Онлайн встреча"),
                ft.dropdown.Option("Звонок"),
            ],
        )

        def on_host_changed(e):
            self.selected_time = {"start": "", "end": "", "reason": ""}
            self.slot_info_badge.visible = False
            self.refresh_slots()

        self.host_manager_dropdown = ft.Dropdown(
            label="Кто проведет встречу",
            value=self.current_username if self.current_username in self.account_names else (self.account_names[0] if self.account_names else ""),
            text_size=13,
            label_style=ft.TextStyle(size=12, color="#64748B"),
            expand=True,
            height=48,
            filled=True,
            fill_color="#F1F5F9",
            border=ft.InputBorder.NONE,
            border_radius=14,
            options=[ft.dropdown.Option(name) for name in self.account_names],
            on_change=on_host_changed,
        )

        self.created_by_badge = ft.Container(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.icons.PERSON_OUTLINE_ROUNDED, size=14, color="#64748B"),
                    ft.Text(f"Автор записи: {self.current_username}", size=11, weight=ft.FontWeight.W_600, color="#64748B"),
                ],
                spacing=5,
                tight=True,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.padding.symmetric(horizontal=12, vertical=6),
            bgcolor="#F1F5F9",
            border_radius=12,
        )

        self.slots_row = ft.Row(wrap=True, spacing=8)
        self.slot_info_icon = ft.Icon(ft.icons.ACCESS_TIME_ROUNDED, size=16, color="#0C66E4")
        self.slot_info_text = ft.Text("", size=12, weight=ft.FontWeight.W_600, color="#0C66E4")
        self.slot_info_badge = ft.Container(
            content=ft.Row(
                controls=[self.slot_info_icon, self.slot_info_text],
                spacing=6,
                tight=True,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.padding.symmetric(horizontal=14, vertical=0),
            height=42,
            bgcolor="#E9F2FF",
            border_radius=14,
            alignment=ft.alignment.center,
            visible=False,
        )

        self.custom_time_input = ft.TextField(
            label="Своё время",
            hint_text="11:30",
            text_size=13,
            label_style=ft.TextStyle(size=11, color="#64748B"),
            width=140,
            height=42,
            filled=True,
            fill_color="#F1F5F9",
            border=ft.InputBorder.NONE,
            border_radius=14,
            content_padding=ft.padding.symmetric(horizontal=14, vertical=4),
        )

        self.call_url_input = ft.TextField(
            label="Ссылка на запись звонка (mp3)",
            hint_text="https://vats.../record.mp3",
            text_size=13,
            label_style=ft.TextStyle(size=12, color="#64748B"),
            height=48,
            filled=True,
            fill_color="#F1F5F9",
            border=ft.InputBorder.NONE,
            border_radius=14,
            prefix_icon=ft.icons.AUDIO_FILE_OUTLINED,
        )
        self.save_status_text = ft.Text("", size=13, weight=ft.FontWeight.W_500)

        self.btn_book_meeting = ft.ElevatedButton(
            "Забронировать встречу",
            icon=ft.icons.ADD_TASK_ROUNDED,
            bgcolor="#0C66E4",
            color=ft.colors.WHITE,
            height=46,
            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=14)),
            disabled=True,
            on_click=self.on_save_meeting,
        )

        self.btn_tg_form = ft.OutlinedButton(
            "Форма для передачи",
            icon=ft.icons.COPY_ALL_ROUNDED,
            height=46,
            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=14)),
            disabled=True,
            on_click=self.show_tg_form,
        )

        # 3. Расписание
        self.sched_date_from_input = ft.TextField(
            label="С даты", hint_text="ДД.ММ.ГГГГ",
            value=datetime.today().strftime("%d.%m.%Y"),
            text_size=13, label_style=ft.TextStyle(size=12, color="#64748B"),
            width=145, height=48,
            filled=True, fill_color="#F1F5F9",
            border=ft.InputBorder.NONE, border_radius=14,
        )
        self.sched_date_to_input = ft.TextField(
            label="По дату", hint_text="ДД.ММ.ГГГГ",
            value=(datetime.today() + timedelta(days=7)).strftime("%d.%m.%Y"),
            text_size=13, label_style=ft.TextStyle(size=12, color="#64748B"),
            width=145, height=48,
            filled=True, fill_color="#F1F5F9",
            border=ft.InputBorder.NONE, border_radius=14,
        )
        self.sched_host_filter = ft.Dropdown(
            label="Кто проведет", value="Все ведущие",
            text_size=13, label_style=ft.TextStyle(size=12, color="#64748B"),
            width=200, height=48,
            filled=True, fill_color="#F1F5F9",
            border=ft.InputBorder.NONE, border_radius=14,
            options=[ft.dropdown.Option("Все ведущие")] + [ft.dropdown.Option(n) for n in self.account_names],
        )
        self.sched_creator_filter = ft.Dropdown(
            label="Кто записал", value="Все авторы",
            text_size=13, label_style=ft.TextStyle(size=12, color="#64748B"),
            width=200, height=48,
            filled=True, fill_color="#F1F5F9",
            border=ft.InputBorder.NONE, border_radius=14,
            options=[ft.dropdown.Option("Все авторы")] + [ft.dropdown.Option(n) for n in self.account_names],
        )
        self.schedule_list = ft.Column(spacing=12, scroll=ft.ScrollMode.AUTO)

        # 4. Реестр
        self.reg_date_from_input = ft.TextField(
            label="С даты", hint_text="ДД.ММ.ГГГГ",
            value=datetime.today().strftime("%d.%m.%Y"),
            text_size=13, label_style=ft.TextStyle(size=12, color="#64748B"),
            width=145, height=48,
            filled=True, fill_color="#F1F5F9",
            border=ft.InputBorder.NONE, border_radius=14,
        )
        self.reg_date_to_input = ft.TextField(
            label="По дату", hint_text="ДД.ММ.ГГГГ",
            value=(datetime.today() + timedelta(days=7)).strftime("%d.%m.%Y"),
            text_size=13, label_style=ft.TextStyle(size=12, color="#64748B"),
            width=145, height=48,
            filled=True, fill_color="#F1F5F9",
            border=ft.InputBorder.NONE, border_radius=14,
        )
        self.reg_status_filter = ft.Dropdown(
            label="Статус встречи", value="Все статусы",
            text_size=13, label_style=ft.TextStyle(size=12, color="#64748B"),
            width=230, height=48,
            filled=True, fill_color="#F1F5F9",
            border=ft.InputBorder.NONE, border_radius=14,
            options=[
                ft.dropdown.Option("Все статусы"),
                ft.dropdown.Option("Ожидает подтверждения"),
                ft.dropdown.Option("Подтверждена"),
                ft.dropdown.Option("Встреча проведена"),
                ft.dropdown.Option("Отказ"),
            ],
        )
        self.reg_host_filter = ft.Dropdown(
            label="Кто проведет", value="Все ведущие",
            text_size=13, label_style=ft.TextStyle(size=12, color="#64748B"),
            width=200, height=48,
            filled=True, fill_color="#F1F5F9",
            border=ft.InputBorder.NONE, border_radius=14,
            options=[ft.dropdown.Option("Все ведущие")] + [ft.dropdown.Option(n) for n in self.account_names],
        )
        self.reg_creator_filter = ft.Dropdown(
            label="Кто записал", value="Все авторы",
            text_size=13, label_style=ft.TextStyle(size=12, color="#64748B"),
            width=200, height=48,
            filled=True, fill_color="#F1F5F9",
            border=ft.InputBorder.NONE, border_radius=14,
            options=[ft.dropdown.Option("Все авторы")] + [ft.dropdown.Option(n) for n in self.account_names],
        )
        self.registry_list = ft.Column(spacing=12, scroll=ft.ScrollMode.AUTO)

    def _build_modals(self):
        self.tg_text_field = ft.TextField(multiline=True, min_lines=15, max_lines=19, read_only=True, border_radius=12, text_size=13)
        self.tg_dialog = ft.AlertDialog(
            title=ft.Row([ft.Icon(ft.icons.COPY_ALL_ROUNDED, color="#0C66E4"), ft.Text("Форма для передачи", size=16, weight=ft.FontWeight.BOLD)]),
            content=ft.Container(content=self.tg_text_field, width=500),
            actions=[
                ft.TextButton("Закрыть", on_click=lambda e: setattr(self.tg_dialog, "open", False) or self.page.update()),
                ft.ElevatedButton("Скопировать в буфер", icon=ft.icons.CONTENT_COPY_ROUNDED, bgcolor="#0C66E4", color=ft.colors.WHITE, on_click=self.copy_tg_form_to_clipboard),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )

        self.book_date_picker = ft.DatePicker(
            on_change=self.on_book_date_picked,
            first_date=datetime(2025, 1, 1), last_date=datetime(2030, 12, 31),
            confirm_text="Выбрать", cancel_text="Отмена", help_text="Выберите дату встречи",
        )
        self.sched_date_picker_from = ft.DatePicker(
            on_change=lambda e: setattr(self.sched_date_from_input, "value", self.sched_date_picker_from.value.strftime("%d.%m.%Y")) or self.page.update(),
            first_date=datetime(2025, 1, 1), last_date=datetime(2030, 12, 31),
            confirm_text="Выбрать", cancel_text="Отмена", help_text="С даты",
        )
        self.sched_date_picker_to = ft.DatePicker(
            on_change=lambda e: setattr(self.sched_date_to_input, "value", self.sched_date_picker_to.value.strftime("%d.%m.%Y")) or self.page.update(),
            first_date=datetime(2025, 1, 1), last_date=datetime(2030, 12, 31),
            confirm_text="Выбрать", cancel_text="Отмена", help_text="По дату",
        )
        self.reg_date_picker_from = ft.DatePicker(
            on_change=lambda e: setattr(self.reg_date_from_input, "value", self.reg_date_picker_from.value.strftime("%d.%m.%Y")) or self.page.update(),
            first_date=datetime(2025, 1, 1), last_date=datetime(2030, 12, 31),
            confirm_text="Выбрать", cancel_text="Отмена", help_text="С даты",
        )
        self.reg_date_picker_to = ft.DatePicker(
            on_change=lambda e: setattr(self.reg_date_to_input, "value", self.reg_date_picker_to.value.strftime("%d.%m.%Y")) or self.page.update(),
            first_date=datetime(2025, 1, 1), last_date=datetime(2030, 12, 31),
            confirm_text="Выбрать", cancel_text="Отмена", help_text="По дату",
        )

        self.complete_feedback_input = ft.TextField(label="Результат встречи", multiline=True, min_lines=3, border_radius=12, text_size=13)
        self.complete_recording_input = ft.TextField(
            label="Ссылка на онлайн встречу (Яндекс.Диск)",
            hint_text="https://disk.yandex.ru/...",
            border_radius=12,
            text_size=13,
        )
        self.complete_dialog = ft.AlertDialog(
            title=ft.Row([ft.Icon(ft.icons.TASK_ALT_ROUNDED, color="#2E7D32"), ft.Text("Итоги встречи", size=16, weight=ft.FontWeight.BOLD)]),
            content=ft.Container(
                content=ft.Column([self.complete_feedback_input, self.complete_recording_input], spacing=10, tight=True),
                width=500,
            ),
            actions=[
                ft.TextButton("Отмена", on_click=lambda e: setattr(self.complete_dialog, "open", False) or self.page.update()),
                ft.ElevatedButton("Сохранить", icon=ft.icons.CHECK_ROUNDED, bgcolor="#2E7D32", color=ft.colors.WHITE, on_click=self.on_confirm_complete),
            ],
        )

        self.cancel_reason_input = ft.TextField(label="Причина отмены встречи", multiline=True, min_lines=3, border_radius=12, text_size=13)
        self.cancel_dialog = ft.AlertDialog(
            title=ft.Row([ft.Icon(ft.icons.CANCEL_OUTLINED, color="#D32F2F"), ft.Text("Отмена встречи", size=16, weight=ft.FontWeight.BOLD)]),
            content=ft.Container(content=self.cancel_reason_input, width=500),
            actions=[
                ft.TextButton("Назад", on_click=lambda e: setattr(self.cancel_dialog, "open", False) or self.page.update()),
                ft.ElevatedButton("Подтвердить отмену", icon=ft.icons.CLOSE_ROUNDED, bgcolor="#D32F2F", color=ft.colors.WHITE, on_click=self.on_confirm_cancel),
            ],
        )

        self.delete_confirm_text = ft.Text("", size=13)
        self.btn_delete_confirm = ft.ElevatedButton("Удалить", icon=ft.icons.DELETE_FOREVER_ROUNDED, bgcolor="#D32F2F", color=ft.colors.WHITE)
        self.btn_delete_cancel = ft.TextButton("Отмена")
        self.delete_dialog = ft.AlertDialog(
            title=ft.Row([ft.Icon(ft.icons.DELETE_OUTLINE_ROUNDED, color="#D32F2F"), ft.Text("Удаление встречи", size=16, weight=ft.FontWeight.BOLD)]),
            content=ft.Container(content=self.delete_confirm_text, width=450),
            actions=[
                self.btn_delete_cancel,
                self.btn_delete_confirm,
            ],
        )

        self.btn_delete_cancel.on_click = lambda e: setattr(self.delete_dialog, "open", False) or self.page.update()
        self.btn_delete_confirm.on_click = self.on_confirm_delete

        self.edit_call_url_input = ft.TextField(
            label="Ссылка на звонок (mp3)",
            hint_text="https://vats.../record.mp3 или Яндекс.Диск",
            border_radius=12,
            text_size=13,
        )
        self.edit_host_dropdown = ft.Dropdown(
            label="Кто проведет встречу",
            options=[ft.dropdown.Option(name) for name in self.account_names],
            border_radius=12,
            text_size=13,
        )
        self.edit_type_dropdown = ft.Dropdown(
            label="Тип встречи",
            options=[
                ft.dropdown.Option("Онлайн встреча"),
                ft.dropdown.Option("Звонок"),
            ],
            border_radius=12,
            text_size=13,
        )
        self.edit_hooks_input = ft.TextField(label="Крючки", multiline=True, min_lines=2, max_lines=3, border_radius=12, text_size=13)
        self.edit_comment_input = ft.TextField(label="Комментарий", multiline=True, min_lines=2, max_lines=3, border_radius=12, text_size=13)
        self.edit_status_text = ft.Text("", size=12, weight=ft.FontWeight.W_500)

        self.edit_dialog = ft.AlertDialog(
            title=ft.Row([ft.Icon(ft.icons.EDIT_NOTE_ROUNDED, color="#0C66E4"), ft.Text("Редактирование встречи", size=16, weight=ft.FontWeight.BOLD)], spacing=8),
            content=ft.Container(
                content=ft.Column(
                    controls=[
                        self.edit_call_url_input,
                        ft.Row([self.edit_host_dropdown, self.edit_type_dropdown], spacing=10),
                        self.edit_hooks_input,
                        self.edit_comment_input,
                        self.edit_status_text,
                    ],
                    spacing=10,
                    tight=True,
                ),
                width=520,
            ),
            actions=[
                ft.TextButton("Отмена", on_click=lambda e: setattr(self.edit_dialog, "open", False) or self.page.update()),
                ft.ElevatedButton("Сохранить изменения", icon=ft.icons.SAVE_ROUNDED, bgcolor="#0C66E4", color=ft.colors.WHITE, on_click=self.on_save_edited_meeting),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )

        self.detail_content = ft.Column(spacing=10, scroll=ft.ScrollMode.AUTO)
        self.audio_status_text = ft.Text("Готов к воспроизведению", size=12, color="#64748B")
        self.time_label = ft.Text("00:00 / 00:00", size=12, weight=ft.FontWeight.BOLD)
        self.play_pause_btn = ft.ElevatedButton("Слушать", icon=ft.icons.PLAY_ARROW_ROUNDED, bgcolor="#0C66E4", color=ft.colors.WHITE)

        speed_rates = [1.0, 1.25, 1.5, 2.0]
        self.speed_buttons_row = ft.Row(
            controls=[
                ft.TextButton(
                    f"{r}x", data=r,
                    on_click=lambda e, val=r: self.set_playback_rate(val),
                    style=ft.ButtonStyle(color="#0C66E4" if r == 1.0 else ft.colors.BLACK),
                )
                for r in speed_rates
            ],
            spacing=4,
        )

        self.detail_dialog = ft.AlertDialog(
            title=ft.Row([ft.Icon(ft.icons.INFO_OUTLINE_ROUNDED, color="#0C66E4"), ft.Text("Информация о встрече", size=16, weight=ft.FontWeight.BOLD)]),
            content=ft.Container(content=self.detail_content, width=620, height=540),
            actions=[ft.TextButton("Закрыть", on_click=lambda e: self.close_detail_dialog())],
        )

        self.meeting_ai_prompt_dd = ft.Dropdown(label="Шаблон промта", width=480, height=48, border_radius=12, text_size=13)
        self.meeting_ai_custom_input = ft.TextField(
            label="Инструкция для ИИ",
            multiline=True,
            min_lines=2,
            max_lines=5,
            border_radius=12,
            text_size=13,
            hint_text="Отредактируйте или введите свой запрос к ИИ...",
        )
        self.meeting_ai_status = ft.Text("", size=12, color="#0C66E4")
        self.meeting_ai_progress = ft.ProgressBar(visible=False, color="#0C66E4")
        self.meeting_ai_result = ft.TextField(
            label="Итоги анализа ИИ",
            multiline=True,
            min_lines=8,
            max_lines=14,
            border_radius=12,
            text_size=13,
            read_only=True,
        )

        self.meeting_ai_dialog = ft.AlertDialog(
            title=ft.Row([ft.Icon(ft.icons.AUTO_AWESOME_ROUNDED, color="#0C66E4"), ft.Text("ИИ-анализ звонка / встречи", size=16, weight=ft.FontWeight.BOLD)]),
            content=ft.Container(
                content=ft.Column(
                    controls=[
                        self.meeting_ai_prompt_dd,
                        self.meeting_ai_custom_input,
                        self.meeting_ai_progress,
                        self.meeting_ai_status,
                        self.meeting_ai_result,
                    ],
                    spacing=10,
                    scroll=ft.ScrollMode.AUTO,
                ),
                width=550,
                height=480,
            ),
            actions=[
                ft.TextButton("Закрыть", on_click=lambda e: setattr(self.meeting_ai_dialog, "open", False) or self.page.update()),
                ft.ElevatedButton("Запустить анализ", icon=ft.icons.AUTO_AWESOME_ROUNDED, bgcolor="#0C66E4", color=ft.colors.WHITE, on_click=self.run_meeting_ai_analysis),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )

        for d in (
            self.tg_dialog, self.book_date_picker, self.sched_date_picker_from,
            self.sched_date_picker_to, self.reg_date_picker_from, self.reg_date_picker_to,
            self.complete_dialog, self.cancel_dialog, self.delete_dialog, self.detail_dialog,
            self.meeting_ai_dialog, self.edit_dialog
        ):
            if d not in self.page.overlay:
                self.page.overlay.append(d)

    def cleanup_audio_player(self):
        if self.audio_state["player"]:
            try:
                self.audio_state["player"].pause()
            except Exception:
                pass
            if self.audio_state["player"] in self.page.overlay:
                self.page.overlay.remove(self.audio_state["player"])
            self.audio_state["player"] = None
        self.audio_state["is_playing"] = False
        self.audio_state["duration_ms"] = 0
        self.audio_state["position_ms"] = 0
        self.play_pause_btn.text = "Слушать"
        self.play_pause_btn.icon = ft.icons.PLAY_ARROW_ROUNDED
        self.time_label.value = "00:00 / 00:00"

    def close_detail_dialog(self):
        self.cleanup_audio_player()
        self.detail_dialog.open = False
        self.page.update()

    def set_playback_rate(self, rate: float):
        self.audio_state["rate"] = rate
        if self.audio_state["player"]:
            try:
                self.audio_state["player"].playback_rate = rate
                self.audio_state["player"].update()
            except Exception:
                pass
        for btn in self.speed_buttons_row.controls:
            btn.weight = ft.FontWeight.BOLD if btn.data == rate else ft.FontWeight.NORMAL
            btn.style = ft.ButtonStyle(color="#0C66E4" if btn.data == rate else ft.colors.BLACK)
        self.page.update()

    def toggle_play_pause(self, url: str):
        if not self.audio_state["player"]:
            player = ft.Audio(
                src=url, autoplay=True,
                playback_rate=self.audio_state["rate"],
                on_loaded=self.on_audio_loaded,
                on_position_changed=self.on_audio_position_changed,
            )
            self.audio_state["player"] = player
            self.audio_state["is_playing"] = True
            self.page.overlay.append(player)
            self.play_pause_btn.text = "Пауза"
            self.play_pause_btn.icon = ft.icons.PAUSE_ROUNDED
            self.audio_status_text.value = "▶ Воспроизведение записи..."
            self.audio_status_text.color = "#2E7D32"
            self.page.update()
            return

        if self.audio_state["is_playing"]:
            self.audio_state["player"].pause()
            self.audio_state["is_playing"] = False
            self.play_pause_btn.text = "Продолжить"
            self.play_pause_btn.icon = ft.icons.PLAY_ARROW_ROUNDED
            self.audio_status_text.value = "⏸ Пауза"
            self.audio_status_text.color = "#D97706"
        else:
            try:
                self.audio_state["player"].resume()
            except AttributeError:
                self.audio_state["player"].play()
            self.audio_state["is_playing"] = True
            self.play_pause_btn.text = "Пауза"
            self.play_pause_btn.icon = ft.icons.PAUSE_ROUNDED
            self.audio_status_text.value = "▶ Воспроизведение записи..."
            self.audio_status_text.color = "#2E7D32"
        self.page.update()

    def on_audio_loaded(self, e):
        try:
            dur = self.audio_state["player"].get_duration() if hasattr(self.audio_state["player"], "get_duration") else int(e.data)
            if dur:
                self.audio_state["duration_ms"] = int(dur)
                self.time_label.value = f"{format_ms(self.audio_state['position_ms'])} / {format_ms(self.audio_state['duration_ms'])}"
                self.page.update()
        except Exception:
            pass

    def on_audio_position_changed(self, e):
        if not self.audio_state["player"]:
            return
        try:
            pos = int(e.data)
            self.audio_state["position_ms"] = pos
            self.time_label.value = f"{format_ms(pos)} / {format_ms(self.audio_state['duration_ms'])}"
            self.page.update()
        except Exception:
            pass

    def on_book_date_picked(self, e):
        if self.book_date_picker.value:
            self.date_input.value = self.book_date_picker.value.strftime("%d.%m.%Y")
            self.selected_time = {"start": "", "end": "", "reason": ""}
            self.slot_info_badge.visible = False
            self.refresh_slots()

    def get_host_filtered_meetings(self, target_date: str) -> list[dict]:
        try:
            existing = get_meetings_by_date(target_date)
        except Exception:
            existing = []

        current_host = (self.host_manager_dropdown.value or "").strip().lower()
        filtered = []
        for m in existing:
            if m.get("status", "").strip() == "Отказ":
                continue
            m_host = (m.get("host_manager") or "").strip().lower()
            if current_host and m_host == current_host:
                filtered.append(m)
        return filtered

    def refresh_slots(self):
        if self._is_refreshing_slots:
            return
        self._is_refreshing_slots = True

        try:
            target_date = self.date_input.value.strip()
            host_meetings = self.get_host_filtered_meetings(target_date)
            grid = get_day_schedule_grid(host_meetings, target_date)

            new_buttons = []
            for item in grid:
                time_val = item["time"]
                status_val = item["status"]
                reason_val = item["reason"]

                is_selected = (self.selected_time["start"] == time_val and self.selected_time["start"] != "")

                if is_selected:
                    bg_color = "#0C66E4"
                    txt_color = "#FFFFFF"
                    border_color = "#0C66E4"
                    icon_control = ft.icons.CHECK_ROUNDED
                elif status_val == "BUSY":
                    bg_color = "#F1F5F9"
                    txt_color = "#94A3B8"
                    border_color = "#E2E8F0"
                    icon_control = None
                else:
                    bg_color = "#FFFFFF"
                    txt_color = "#0F172A"
                    border_color = "#CBD5E1"
                    icon_control = None

                btn = ft.Container(
                    content=ft.Row(
                        controls=[
                            ft.Icon(icon_control, size=14, color=txt_color) if icon_control else ft.Container(),
                            ft.Text(time_val, size=13, weight=ft.FontWeight.W_600, color=txt_color),
                        ],
                        spacing=4,
                        alignment=ft.MainAxisAlignment.CENTER,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        tight=True,
                    ),
                    padding=ft.padding.symmetric(horizontal=14, vertical=9),
                    border_radius=12,
                    bgcolor=bg_color,
                    border=ft.border.all(1, border_color),
                    on_click=None if status_val == "BUSY" else (lambda e, t=time_val, r=reason_val: self.set_slot(t, r)),
                )
                new_buttons.append(btn)

            self.slots_row.controls = new_buttons
            self.page.update()
        finally:
            self._is_refreshing_slots = False

    def set_slot(self, time_str: str, reason: str):
        self.selected_time["start"] = time_str
        self.selected_time["end"] = calculate_end_time(time_str)
        self.selected_time["reason"] = reason

        self.slot_info_text.value = f"Выбрано: {self.selected_time['start']} - {self.selected_time['end']} ({reason})"
        self.slot_info_badge.visible = True
        self.refresh_slots()

    def check_custom_time(self, e):
        val = self.custom_time_input.value.strip()
        if not val:
            return
        target_date = self.date_input.value.strip()
        try:
            host_meetings = self.get_host_filtered_meetings(target_date)
            res = evaluate_slot_status(val, host_meetings, target_date)
            if res["status"] == "BUSY":
                self.slot_info_text.value = f"Время {val} недоступно: {res['reason']}"
                self.slot_info_text.color = "#C62828"
                self.slot_info_badge.bgcolor = "#FFEBEE"
                self.slot_info_icon.color = "#C62828"
                self.slot_info_badge.visible = True
                self.page.update()
            else:
                self.set_slot(val, res["reason"])
        except Exception as err:
            self.slot_info_text.value = f"Ошибка формата: {err}"
            self.slot_info_text.color = "#C62828"
            self.slot_info_badge.bgcolor = "#FFEBEE"
            self.slot_info_icon.color = "#C62828"
            self.slot_info_badge.visible = True
            self.page.update()

    def on_deal_input_changed(self, e):
        if self.deal_verified:
            self.deal_verified = False
            self.btn_book_meeting.disabled = True
            self.btn_tg_form.disabled = True
            self.info_card.visible = False
            self.save_status_text.value = "Ссылка изменена. Нажмите «Найти сделку» для проверки."
            self.save_status_text.color = "#D97706"
            self.page.update()

    def on_find_deal(self, e):
        url = self.deal_url_input.value.strip()
        if not url:
            self.save_status_text.value = "Введите ссылку или номер сделки amoCRM!"
            self.save_status_text.color = "#DC2626"
            self.page.update()
            return

        self.deal_url_input.disabled = True
        self.save_status_text.value = "Поиск сделки..."
        self.save_status_text.color = "#0C66E4"
        self.page.update()

        try:
            data = find_deal_by_link(url)
            if data:
                self.deal_cache.update(data)
                self.deal_verified = True
                self.btn_book_meeting.disabled = False
                self.btn_tg_form.disabled = False

                self.info_card_content.controls = [
                    ft.Text(f"Клиент: {data['client']} | ID: {data['deal_id']} | ЖК: {data['complex']}", weight=ft.FontWeight.BOLD, size=13),
                    ft.Text(f"Менеджер amoCRM: {data['manager']}", weight=ft.FontWeight.W_500, color="#0C66E4", size=12),
                    ft.Text(f"Площадь: {data['area']} м² | Комнат: {data['rooms']} | Услуга: {data['service_type']}", size=12),
                    ft.Text(f"Состояние: {data['condition']} | Ключи: {data['keys']}", size=12),
                    ft.Text(f"Боли: {data['pains']}", size=11, italic=True, color="#475569") if data.get("pains") else ft.Container(),
                    ft.Text(f"Крючки: {data['hooks']}", size=11, italic=True, color="#475569") if data.get("hooks") else ft.Container(),
                    ft.Text(f"Комментарий: {data['comment']}", size=11, color="#64748B") if data.get("comment") else ft.Container(),
                ]
                self.info_card.visible = True
                self.save_status_text.value = "Сделка успешно найдена и подтверждена!"
                self.save_status_text.color = "#2E7D32"
            else:
                self.deal_verified = False
                self.btn_book_meeting.disabled = True
                self.btn_tg_form.disabled = True
                self.info_card_content.controls = [ft.Text("Сделка не найдена в таблице", color="#DC2626", size=12)]
                self.info_card.visible = True
                self.save_status_text.value = "Сделка не найдена!"
                self.save_status_text.color = "#DC2626"
        except Exception as err:
            self.deal_verified = False
            self.btn_book_meeting.disabled = True
            self.btn_tg_form.disabled = True
            self.info_card_content.controls = [ft.Text(f"Ошибка загрузки: {err}", color="#DC2626", size=12)]
            self.info_card.visible = True
            self.save_status_text.value = f"Ошибка: {err}"
            self.save_status_text.color = "#DC2626"
        finally:
            self.deal_url_input.disabled = False
            self.page.update()

    def show_tg_form(self, e):
        if not self.deal_verified:
            self.save_status_text.value = "Сначала подтвердите сделку (кнопка «Найти сделку»)!"
            self.save_status_text.color = "#DC2626"
            self.page.update()
            return

        if not self.selected_time["start"]:
            self.save_status_text.value = "Сначала выберите время встречи!"
            self.save_status_text.color = "#DC2626"
            self.page.update()
            return

        rooms_val = self.deal_cache.get("rooms", "").strip()
        rooms_str = f"{rooms_val} ком" if rooms_val else ""
        id_complex_str = f"{self.deal_cache.get('deal_id', '')} {self.deal_cache.get('complex', '')}".strip()
        area_val = self.deal_cache.get("area", "").strip()
        area_str = f"{area_val} м²" if area_val else ""
        area_rooms_str = f"{area_str} {rooms_str}".strip()
        crm_url = normalize_deal_url(self.deal_cache.get("deal_url") or self.deal_url_input.value.strip())

        template = (
            f"{self.deal_cache.get('client', '')}\n"
            f"{id_complex_str}\n"
            f"{area_rooms_str}\n"
            f"Состояние: {self.deal_cache.get('condition', '')}\n"
            f"Ключи: {self.deal_cache.get('keys', '')}\n"
            f"Тип услуги: {self.deal_cache.get('service_type', '')}\n"
            f"Тип встречи: {self.meeting_type_dropdown.value}\n"
            f"Дата встречи/звонка: {self.date_input.value.strip()}\n"
            f"Время: {self.selected_time['start']}\n"
            f"Ведущий встречи: {self.host_manager_dropdown.value}\n"
            f"Записал(а): {self.current_username}\n"
            f"Ответственный CRM: {self.deal_cache.get('manager', '')}\n"
            f"Крючки: {self.deal_cache.get('hooks', '')}\n"
            f"Боли клиента: {self.deal_cache.get('pains', '')}\n"
            f"Комментарии КЦ: {self.deal_cache.get('comment', '')}\n"
            f"Ссылка CRM: {crm_url}"
        )
        self.tg_text_field.value = template
        self.tg_dialog.open = True
        self.page.update()

    def copy_tg_form_to_clipboard(self, e):
        self.page.set_clipboard(self.tg_text_field.value)
        self.save_status_text.value = "Текст скопирован в буфер обмена!"
        self.save_status_text.color = "#2E7D32"
        self.tg_dialog.open = False
        self.page.update()

    def clear_form(self, e=None):
        self.deal_url_input.value = ""
        self.call_url_input.value = ""
        self.custom_time_input.value = ""
        self.info_card.visible = False
        self.save_status_text.value = ""
        self.deal_verified = False
        self.btn_book_meeting.disabled = True
        self.btn_tg_form.disabled = True

        for k in self.deal_cache:
            self.deal_cache[k] = ""
        self.selected_time = {"start": "", "end": "", "reason": ""}
        self.slot_info_badge.visible = False
        self.refresh_slots()

    def on_save_meeting(self, e):
        if not self.deal_verified:
            self.save_status_text.value = "Сначала подтвердите сделку (кнопка «Найти сделку»)!"
            self.save_status_text.color = "#DC2626"
            self.page.update()
            return

        if not self.selected_time["start"]:
            self.save_status_text.value = "Выберите время встречи!"
            self.save_status_text.color = "#DC2626"
            self.page.update()
            return

        payload = {
            "date": self.date_input.value.strip(),
            "start": self.selected_time["start"],
            "end": self.selected_time["end"],
            "manager": self.deal_cache.get("manager", ""),
            "client": self.deal_cache.get("client", ""),
            "deal_id": self.deal_cache.get("deal_id", ""),
            "complex": self.deal_cache.get("complex", ""),
            "area": self.deal_cache.get("area", ""),
            "deal_url": self.deal_cache.get("deal_url") or self.deal_url_input.value.strip(),
            "call_url": self.call_url_input.value.strip(),
            "comment": self.deal_cache.get("comment", ""),
            "hooks": self.deal_cache.get("hooks", ""),
            "feedback": "",
            "meeting_url": "",
            "transcription": "",
            "gpt_summary": "",
            "meeting_type": self.meeting_type_dropdown.value,
            "status": "Ожидает подтверждения",
            "host_manager": self.host_manager_dropdown.value or "",
            "created_by": self.current_username,
        }

        self.save_status_text.value = "Сохранение в Google Таблицу..."
        self.save_status_text.color = "#0C66E4"
        self.page.update()

        try:
            save_new_meeting(payload)
            self.save_status_text.value = f"Встреча на {payload['date']} в {payload['start']} успешно записана!"
            self.save_status_text.color = "#2E7D32"
            self.selected_time = {"start": "", "end": "", "reason": ""}
            self.slot_info_badge.visible = False
            self.refresh_slots()
        except Exception as err:
            self.save_status_text.value = f"Ошибка записи: {err}"
            self.save_status_text.color = "#DC2626"
        self.page.update()

    def render_meeting_card(self, item: dict, is_registry: bool = False) -> ft.Control:
        deal_link = item.get("deal_url", "")
        meeting_type = item.get("meeting_type", "Онлайн встреча")
        status = item.get("status", "Ожидает подтверждения")
        row_idx = item.get("row_idx")
        host_m = item.get("host_manager") or "Не назначен"
        created_b = item.get("created_by") or "Не указан"
        crm_m = item.get("manager") or "Не назначен"

        is_online = "онлайн" in meeting_type.lower()
        type_badge = ft.Container(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.icons.VIDEO_CAMERA_FRONT_OUTLINED if is_online else ft.icons.CALL_OUTLINED, size=13, color="#0C66E4" if is_online else "#B45309"),
                    ft.Text(meeting_type, size=11, weight=ft.FontWeight.BOLD, color="#0C66E4" if is_online else "#78350F"),
                ],
                spacing=4, tight=True,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.padding.symmetric(horizontal=10, vertical=5),
            border_radius=10,
            bgcolor="#E9F2FF" if is_online else "#FEF3C7",
        )

        card_progress_bar = ft.ProgressBar(height=2, color="#D32F2F", bgcolor="#FFCDD2", visible=False)
        status_controls = []

        def handle_confirm(e, idx=row_idx):
            if idx:
                update_meeting_status(idx, "Подтверждена")
                self.load_schedule_list()
                self.load_registry_list()

        def handle_open_complete(e, it=item):
            self.action_context["meeting"] = it
            self.complete_feedback_input.value = it.get("feedback", "")
            self.complete_recording_input.value = it.get("meeting_url", "")
            self.complete_dialog.open = True
            self.page.update()

        def handle_open_cancel(e, it=item):
            self.action_context["meeting"] = it
            self.cancel_reason_input.value = ""
            self.cancel_dialog.open = True
            self.page.update()

        def handle_open_delete(e, it=item, prog=card_progress_bar):
            if self._is_deleting:
                return
            self.action_context["meeting"] = it
            self.action_context["card_progress"] = prog
            client_name = it.get("client") or "без имени"
            meeting_date = it.get("date") or ""
            meeting_time = it.get("start") or ""
            self.delete_confirm_text.value = f"Удалить встречу клиента '{client_name}' на {meeting_date} ({meeting_time})?"
            self.btn_delete_confirm.disabled = False
            self.btn_delete_confirm.text = "Удалить"
            self.delete_dialog.open = True
            self.page.update()

        if status == "Ожидает подтверждения":
            status_controls.append(
                ft.ElevatedButton(
                    "Подтвердить встречу",
                    icon=ft.icons.CHECK_CIRCLE_OUTLINE_ROUNDED,
                    bgcolor="#0C66E4",
                    color=ft.colors.WHITE,
                    style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=12)),
                    on_click=handle_confirm,
                )
            )
        elif status == "Подтверждена":
            status_controls.extend([
                ft.Container(
                    content=ft.Row([ft.Icon(ft.icons.CHECK_ROUNDED, size=14, color="#15803D"), ft.Text("Встреча подтверждена", size=12, weight=ft.FontWeight.BOLD, color="#166534")], spacing=4, tight=True, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                    padding=ft.padding.symmetric(horizontal=10, vertical=5),
                    bgcolor="#F0FDF4", border_radius=10,
                ),
                ft.ElevatedButton(
                    "Встреча проведена",
                    icon=ft.icons.DONE_ALL_ROUNDED,
                    bgcolor="#2E7D32",
                    color=ft.colors.WHITE,
                    style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=12)),
                    on_click=handle_open_complete,
                ),
                ft.OutlinedButton(
                    "Отменена",
                    icon=ft.icons.CLOSE_ROUNDED,
                    style=ft.ButtonStyle(color="#DC2626", shape=ft.RoundedRectangleBorder(radius=12)),
                    on_click=handle_open_cancel,
                ),
            ])
        elif status == "Встреча проведена":
            status_controls.append(
                ft.Container(content=ft.Text("Встреча проведена", size=12, weight=ft.FontWeight.BOLD, color="#166534"), padding=ft.padding.symmetric(horizontal=10, vertical=5), bgcolor="#DCFCE7", border_radius=10)
            )
        elif status == "Отказ":
            status_controls.append(
                ft.Container(content=ft.Text("Отказ", size=12, weight=ft.FontWeight.BOLD, color="#991B1B"), padding=ft.padding.symmetric(horizontal=10, vertical=5), bgcolor="#FEE2E2", border_radius=10)
            )

        crm_btn = ft.Container()
        if deal_link:
            crm_btn = ft.TextButton("Открыть сделку в CRM", icon=ft.icons.OPEN_IN_NEW_ROUNDED, on_click=lambda e, u=deal_link: self.page.launch_url(u))

        edit_btn = ft.IconButton(
            icon=ft.icons.EDIT_NOTE_ROUNDED,
            tooltip="Редактировать встречу / звонок",
            icon_color="#0C66E4",
            on_click=lambda e, it=item: self.open_edit_dialog(it),
        )

        delete_btn = ft.IconButton(
            icon=ft.icons.DELETE_OUTLINE_ROUNDED,
            tooltip="Удалить встречу",
            icon_color="#EF4444",
            on_click=lambda e, it=item, p=card_progress_bar: handle_open_delete(e, it, p),
        )

        card_body = ft.Column(
            controls=[
                card_progress_bar,
                ft.Row(
                    controls=[
                        ft.Row([ft.Text(f"🕒 {item['start']} - {item['end']}", size=15, weight=ft.FontWeight.BOLD), type_badge], spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                        ft.Text(f"📅 {item['date']} | 🏢 {item['complex']} ({item['area']} м²)", weight=ft.FontWeight.W_500, color="#334155"),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                ft.Text(f"Клиент: {item['client']} | Менеджер CRM: {crm_m}", size=13),
                ft.Row(
                    controls=[
                        ft.Container(content=ft.Row([ft.Icon(ft.icons.PERSON_ROUNDED, size=14, color="#0C66E4"), ft.Text(f"Проведет: {host_m}", size=12, weight=ft.FontWeight.BOLD, color="#0C66E4")], spacing=4, vertical_alignment=ft.CrossAxisAlignment.CENTER), bgcolor="#E9F2FF", padding=ft.padding.symmetric(horizontal=10, vertical=4), border_radius=10),
                        ft.Container(content=ft.Row([ft.Icon(ft.icons.CREATE_ROUNDED, size=14, color="#64748B"), ft.Text(f"Записал(а): {created_b}", size=12, color="#475569")], spacing=4, vertical_alignment=ft.CrossAxisAlignment.CENTER), bgcolor="#F1F5F9", padding=ft.padding.symmetric(horizontal=10, vertical=4), border_radius=10),
                    ],
                    spacing=8,
                ),
                ft.Text(f"Крючки: {item['hooks']}", size=12, italic=True, color="#475569") if item.get("hooks") else ft.Container(),
                ft.Text(f"Комментарий: {item['comment']}", size=12, color="#64748B") if item.get("comment") else ft.Container(),
                ft.Row(
                    controls=[
                        crm_btn,
                        ft.Row(controls=status_controls, spacing=8, wrap=True, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                        ft.Row(
                            controls=[
                                ft.TextButton("Подробнее и звонок", icon=ft.icons.INFO_OUTLINE_ROUNDED, on_click=lambda e, it=item: self.open_meeting_details(it)),
                                edit_btn,
                                delete_btn,
                            ],
                            spacing=2,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN, wrap=True,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
            ],
            spacing=8,
        )

        return ft.Container(
            border_radius=18,
            bgcolor=ft.colors.WHITE,
            border=ft.border.all(1, "#E2E8F0"),
            padding=16,
            content=card_body,
        )

    def on_confirm_complete(self, e):
        meeting = self.action_context.get("meeting")
        if meeting and meeting.get("row_idx"):
            fb_val = self.complete_feedback_input.value.strip()
            rec_val = self.complete_recording_input.value.strip()
            complete_meeting(meeting["row_idx"], fb_val, rec_val)
            meeting["feedback"] = fb_val
            meeting["meeting_url"] = rec_val
            meeting["status"] = "Встреча проведена"

            self.complete_dialog.open = False
            self.load_schedule_list()
            self.load_registry_list()
            self.refresh_slots()

            if self.detail_dialog.open:
                self.open_meeting_details(meeting)

            self.page.update()

    def on_confirm_cancel(self, e):
        meeting = self.action_context.get("meeting")
        if meeting and meeting.get("row_idx"):
            cancel_meeting(meeting["row_idx"], self.cancel_reason_input.value.strip())
            self.cancel_dialog.open = False
            self.load_schedule_list()
            self.load_registry_list()
            self.refresh_slots()
            self.page.update()

    def on_confirm_delete(self, e):
        if self._is_deleting:
            return
        self._is_deleting = True

        meeting = self.action_context.get("meeting")
        prog_bar = self.action_context.get("card_progress")

        self.btn_delete_confirm.disabled = True
        self.btn_delete_confirm.text = "Удаление..."
        if prog_bar:
            prog_bar.visible = True
        self.page.update()

        try:
            if meeting and meeting.get("row_idx"):
                delete_meeting(meeting["row_idx"])
            self.delete_dialog.open = False
            self.load_schedule_list()
            self.load_registry_list()
            self.refresh_slots()
        finally:
            self._is_deleting = False
            self.page.update()

    def open_edit_dialog(self, item: dict):
        self.action_context["editing_meeting"] = item
        self.edit_call_url_input.value = item.get("call_url", "")
        self.edit_host_dropdown.value = item.get("host_manager") or (self.account_names[0] if self.account_names else "")
        self.edit_type_dropdown.value = item.get("meeting_type") or "Онлайн встреча"
        self.edit_hooks_input.value = item.get("hooks", "")
        self.edit_comment_input.value = item.get("comment", "")
        self.edit_status_text.value = ""

        self.edit_dialog.open = True
        self.page.update()

    def on_save_edited_meeting(self, e):
        item = self.action_context.get("editing_meeting")
        if not item or not item.get("row_idx"):
            return

        row_idx = item["row_idx"]
        updated_data = {
            "call_url": self.edit_call_url_input.value.strip(),
            "host_manager": self.edit_host_dropdown.value or "",
            "meeting_type": self.edit_type_dropdown.value or "Онлайн встреча",
            "hooks": self.edit_hooks_input.value.strip(),
            "comment": self.edit_comment_input.value.strip(),
        }

        self.edit_status_text.value = "Сохранение в таблицу..."
        self.edit_status_text.color = "#0C66E4"
        self.page.update()

        try:
            update_meeting_details(row_idx, updated_data)
            item.update(updated_data)

            self.edit_dialog.open = False
            self.load_schedule_list()
            self.load_registry_list()

            if self.detail_dialog.open:
                self.open_meeting_details(item)

            self.page.update()
        except Exception as err:
            self.edit_status_text.value = f"Ошибка сохранения: {err}"
            self.edit_status_text.color = "#DC2626"
            self.page.update()

    def open_meeting_ai_modal(self, item: dict):
        self.action_context["ai_meeting"] = item
        self.meeting_ai_status.value = ""
        self.meeting_ai_result.value = item.get("gpt_summary", "")

        try:
            prompts = get_all_prompts()
            self.meeting_ai_prompt_dd.options = [ft.dropdown.Option(p["title"]) for p in prompts]
            if prompts:
                self.meeting_ai_prompt_dd.value = prompts[0]["title"]
                self.meeting_ai_custom_input.value = prompts[0]["prompt_text"]

            def on_p_change(e):
                for p in prompts:
                    if p["title"] == self.meeting_ai_prompt_dd.value:
                        self.meeting_ai_custom_input.value = p["prompt_text"]
                        self.page.update()
                        break
            self.meeting_ai_prompt_dd.on_change = on_p_change
        except Exception:
            pass

        self.meeting_ai_dialog.open = True
        self.page.update()

    def run_meeting_ai_analysis(self, e):
        meeting = self.action_context.get("ai_meeting")
        if not meeting:
            return

        audio_url = meeting.get("call_url", "").strip() or meeting.get("meeting_url", "").strip()
        if not audio_url:
            self.meeting_ai_status.value = "В карточке нет ссылки на звонок (mp3) или встречу!"
            self.meeting_ai_status.color = "#DC2626"
            self.page.update()
            return

        prompt_text = self.meeting_ai_custom_input.value.strip()
        self.meeting_ai_progress.visible = True
        self.meeting_ai_status.value = "Скачивание и обработка аудио..."
        self.meeting_ai_status.color = "#0C66E4"
        self.page.update()

        try:
            local_filename = f"m_{int(datetime.now().timestamp())}.dat"
            raw_path = download_file_stream(audio_url, local_filename)
            comp_path = extract_audio_with_ffmpeg(raw_path)

            self.meeting_ai_status.value = "Анализ в Gemini..."
            self.page.update()

            ai_res = analyze_audio_with_gemini(comp_path, prompt_text)
            self.meeting_ai_result.value = ai_res["full_report"]

            row_idx = meeting.get("row_idx")
            if row_idx:
                sh = get_sheets_client()
                ws = sh.worksheet("Встречи")
                ws.update_cell(row_idx, 15, ai_res["transcription"][:4000])
                ws.update_cell(row_idx, 16, ai_res["summary"])
                meeting["transcription"] = ai_res["transcription"]
                meeting["gpt_summary"] = ai_res["summary"]

            self.meeting_ai_status.value = "Анализ успешно сохранён в карточку и таблицу!"
            self.meeting_ai_status.color = "#2E7D32"

            for p in (raw_path, comp_path):
                if p and os.path.exists(p) and p != raw_path:
                    try:
                        os.remove(p)
                    except Exception:
                        pass
        except Exception as err:
            self.meeting_ai_status.value = f"Ошибка: {err}"
            self.meeting_ai_status.color = "#DC2626"
        finally:
            self.meeting_ai_progress.visible = False
            self.page.update()

    def open_meeting_details(self, item: dict):
        self.cleanup_audio_player()
        deal_url = item.get("deal_url", "")
        call_url = item.get("call_url", "").strip()

        full_deal = None
        if deal_url:
            try:
                full_deal = find_deal_by_link(deal_url)
            except Exception:
                pass

        deal_id = item.get("deal_id") or (full_deal.get("deal_id", "") if full_deal else "")
        rooms = full_deal.get("rooms", "") if full_deal else ""
        condition = full_deal.get("condition", "") if full_deal else ""
        keys = full_deal.get("keys", "") if full_deal else ""
        service_type = full_deal.get("service_type", "") if full_deal else ""
        pains = full_deal.get("pains", "") if full_deal else ""

        audio_section = ft.Container()
        if call_url:
            self.play_pause_btn.on_click = lambda e, u=call_url: self.toggle_play_pause(u)
            audio_section = ft.Container(
                bgcolor="#F8FAFC", border_radius=14, padding=14,
                content=ft.Column(
                    controls=[
                        ft.Row([ft.Icon(ft.icons.RECORD_VOICE_OVER_ROUNDED, color="#0C66E4"), ft.Text("Запись звонка:", weight=ft.FontWeight.BOLD), ft.Container(expand=True), self.time_label], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                        ft.Row([self.play_pause_btn, ft.OutlinedButton("Стоп", icon=ft.icons.STOP_ROUNDED, on_click=lambda e: self.cleanup_audio_player() or self.page.update()), ft.VerticalDivider(width=1), ft.Text("Скорость:", size=12), self.speed_buttons_row], spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                        self.audio_status_text,
                    ],
                    spacing=8,
                ),
            )

        crm_btn = ft.Container()
        if deal_url:
            crm_btn = ft.ElevatedButton("Открыть сделку в CRM", icon=ft.icons.OPEN_IN_NEW_ROUNDED, on_click=lambda e, u=deal_url: self.page.launch_url(u))

        ai_analysis_btn = ft.ElevatedButton(
            "✨ ИИ-анализ звонка",
            icon=ft.icons.AUTO_AWESOME_ROUNDED,
            bgcolor="#0C66E4",
            color=ft.colors.WHITE,
            on_click=lambda e, it=item: self.open_meeting_ai_modal(it),
        )

        edit_detail_btn = ft.OutlinedButton(
            "Редактировать встречу",
            icon=ft.icons.EDIT_NOTE_ROUNDED,
            on_click=lambda e, it=item: self.open_edit_dialog(it),
        )

        def copy_transfer(e):
            rooms_str = f"{rooms} ком" if rooms else ""
            id_complex_str = f"{deal_id} {item.get('complex', '')}".strip()
            area_str = f"{item.get('area', '')} м²" if item.get('area') else ""
            tmpl = (
                f"{item.get('client', '')}\n{id_complex_str}\n{area_str} {rooms_str}".strip() + "\n"
                f"Состояние: {condition}\nКлючи: {keys}\nТип услуги: {service_type}\n"
                f"Тип встречи: {item.get('meeting_type', 'Онлайн встреча')}\nДата встречи/звонка: {item.get('date', '')}\n"
                f"Время: {item.get('start', '')}\nВедущий встречи: {item.get('host_manager', '')}\n"
                f"Записал(а): {item.get('created_by', '')}\nОтветственный CRM: {item.get('manager', '')}\n"
                f"Крючки: {item.get('hooks', '')}\nБоли клиента: {pains}\nКомментарии КЦ: {item.get('comment', '')}\nСсылка CRM: {deal_url}"
            )
            self.page.set_clipboard(tmpl)
            self.audio_status_text.value = "Форма для передачи скопирована!"
            self.audio_status_text.color = "#2E7D32"
            self.page.update()

        def copy_result(e):
            rooms_str = f"{rooms} ком" if rooms else ""
            id_complex_str = f"{deal_id} {item.get('complex', '')}".strip()
            area_str = f"{item.get('area', '')} м²" if item.get('area') else ""
            rec_val = item.get("meeting_url", "").strip()
            rec_line = f"Ссылка на онлайн встречу: {rec_val}\n" if rec_val else ""
            tmpl = (
                f"{item.get('client', '')}\n{id_complex_str}\n{area_str} {rooms_str}".strip() + "\n"
                f"Состояние: {condition}\nКлючи: {keys}\nТип услуги: {service_type}\n"
                f"Тип встречи: {item.get('meeting_type', 'Онлайн встреча')}\nДата встречи/звонка: {item.get('date', '')}\n"
                f"Время: {item.get('start', '')}\nВедущий: {item.get('host_manager', '')}\n"
                f"Записал(а): {item.get('created_by', '')}\nСтатус: {item.get('status', '')}\n"
                f"ОС / Результат: {item.get('feedback', '')}\n{rec_line}Ссылка CRM: {deal_url}"
            )
            self.page.set_clipboard(tmpl)
            self.audio_status_text.value = "Форма с результатом скопирована!"
            self.audio_status_text.color = "#2E7D32"
            self.page.update()

        feedback_block = ft.Text(f"📋 ОС / Результат: {item['feedback']}", weight=ft.FontWeight.W_500, color="#0C66E4") if item.get("feedback") else ft.Container()
        recording_block = ft.ElevatedButton("Запись встречи", icon=ft.icons.CLOUD_DOWNLOAD_ROUNDED, on_click=lambda e, u=item["meeting_url"]: self.page.launch_url(u)) if item.get("meeting_url") else ft.Container()

        summary_block = ft.Container()
        if item.get("gpt_summary"):
            summary_block = ft.Container(
                content=ft.Column([
                    ft.Text("🤖 Итог ИИ-анализа:", weight=ft.FontWeight.BOLD, color="#0C66E4"),
                    ft.Text(item["gpt_summary"], size=12, italic=True),
                ], spacing=4),
                bgcolor="#E9F2FF",
                padding=12,
                border_radius=12,
            )

        self.detail_content.controls = [
            ft.Row([ft.Text(f"🕒 {item.get('start', '')} - {item.get('end', '')}", size=18, weight=ft.FontWeight.BOLD), ft.Text(f"Статус: {item.get('status', '')}", size=14, weight=ft.FontWeight.BOLD, color="#0C66E4")], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            ft.Divider(),
            ft.Text(f"👤 Клиент: {item.get('client', '')}", weight=ft.FontWeight.BOLD),
            ft.Text(f"🎯 Кто проведет встречу: {item.get('host_manager', 'Не назначен')}", weight=ft.FontWeight.W_600, color="#0C66E4"),
            ft.Text(f"✍️ Кто записал: {item.get('created_by', 'Не указан')} | 👨‍💼 Менеджер CRM: {item.get('manager', 'Не назначен')}"),
            ft.Text(f"🏢 ЖК: {item.get('complex', '')} ({item.get('area', '')} м²)"),
            ft.Text(f"🚪 Комнат: {rooms} | Состояние: {condition} | Ключи: {keys}" if rooms or condition or keys else ""),
            ft.Text(f"🎯 Крючки: {item.get('hooks', '')}", italic=True) if item.get("hooks") else ft.Container(),
            ft.Text(f"⚡ Боли: {pains}", italic=True) if pains else ft.Container(),
            ft.Text(f"💬 Комментарий: {item.get('comment', '')}") if item.get("comment") else ft.Container(),
            feedback_block, recording_block, summary_block,
            ft.Divider(), audio_section,
            ft.Row(
                controls=[
                    crm_btn,
                    ai_analysis_btn,
                    edit_detail_btn,
                ],
                spacing=10,
                wrap=True,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            ft.Row(
                controls=[
                    ft.OutlinedButton("Форма для передачи", icon=ft.icons.COPY_ALL_ROUNDED, on_click=copy_transfer),
                    ft.OutlinedButton("Форма после встречи", icon=ft.icons.FACT_CHECK_OUTLINED, on_click=copy_result),
                ],
                spacing=10,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        ]
        self.detail_dialog.open = True
        self.page.update()

    def load_schedule_list(self, e=None):
        if self._is_loading_schedule:
            return
        self._is_loading_schedule = True

        self.schedule_list.controls.clear()
        self.schedule_list.controls.append(
            ft.Row([ft.ProgressRing(width=20, height=20, stroke_width=2), ft.Text("Загрузка расписания...", size=13, color="#64748B")], spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER)
        )
        self.page.update()

        try:
            all_items = get_all_meetings()
            d_from = parse_date_safely(self.sched_date_from_input.value)
            d_to = parse_date_safely(self.sched_date_to_input.value)
            h_filter = self.sched_host_filter.value
            c_filter = self.sched_creator_filter.value

            filtered = [
                it for it in all_items
                if (not d_from or (parse_date_safely(it.get("date", "")) and parse_date_safely(it.get("date", "")) >= d_from))
                and (not d_to or (parse_date_safely(it.get("date", "")) and parse_date_safely(it.get("date", "")) <= d_to))
                and (h_filter == "Все ведущие" or it.get("host_manager") == h_filter)
                and (c_filter == "Все авторы" or it.get("created_by") == c_filter)
            ]

            self.schedule_list.controls.clear()
            if not filtered:
                self.schedule_list.controls.append(ft.Text("На выбранный период встреч не найдено", italic=True, color="#64748B"))
            else:
                filtered.sort(key=lambda x: (parse_date_safely(x.get("date", "")) or datetime.max.date(), x.get("start", "00:00")))
                for item in filtered:
                    self.schedule_list.controls.append(self.render_meeting_card(item, is_registry=False))
        except Exception as err:
            self.schedule_list.controls.clear()
            self.schedule_list.controls.append(ft.Text(f"Ошибка чтения: {err}", color="#DC2626"))
        finally:
            self._is_loading_schedule = False
            self.page.update()

    def load_registry_list(self, e=None):
        if self._is_loading_registry:
            return
        self._is_loading_registry = True

        self.registry_list.controls.clear()
        self.registry_list.controls.append(
            ft.Row([ft.ProgressRing(width=20, height=20, stroke_width=2), ft.Text("Загрузка реестра...", size=13, color="#64748B")], spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER)
        )
        self.page.update()

        try:
            all_items = get_all_meetings()
            status_filter = self.reg_status_filter.value
            h_filter = self.reg_host_filter.value
            c_filter = self.reg_creator_filter.value
            d_from = parse_date_safely(self.reg_date_from_input.value)
            d_to = parse_date_safely(self.reg_date_to_input.value)

            filtered = []
            for item in all_items:
                if status_filter != "Все статусы" and item.get("status") != status_filter:
                    continue
                if h_filter != "Все ведущие" and item.get("host_manager") != h_filter:
                    continue
                if c_filter != "Все авторы" and item.get("created_by") != c_filter:
                    continue
                if not self.registry_mode["all_time"]:
                    item_date = parse_date_safely(item.get("date", ""))
                    if not item_date:
                        continue
                    if d_from and item_date < d_from:
                        continue
                    if d_to and item_date > d_to:
                        continue
                filtered.append(item)

            self.registry_list.controls.clear()
            if not filtered:
                self.registry_list.controls.append(ft.Text("По заданным фильтрам встреч не найдено", italic=True, color="#64748B"))
            else:
                filtered.sort(key=lambda x: (parse_date_safely(x.get("date", "")) or datetime.min.date(), x.get("start", "00:00")), reverse=True)
                for item in filtered:
                    self.registry_list.controls.append(self.render_meeting_card(item, is_registry=True))
        except Exception as err:
            self.registry_list.controls.clear()
            self.registry_list.controls.append(ft.Text(f"Ошибка фильтрации: {err}", color="#DC2626"))
        finally:
            self._is_loading_registry = False
            self.page.update()

    def get_view(self, subview_key: str) -> ft.Control:
        if subview_key == "meetings_book":
            # Шаг 1: amoCRM
            step1_card = ft.Container(
                bgcolor=ft.colors.WHITE,
                border_radius=20,
                padding=20,
                border=ft.border.all(1, "#E2E8F0"),
                content=ft.Column(
                    controls=[
                        ft.Row(
                            controls=[
                                ft.Row([
                                    build_oneui_badge("1"),
                                    ft.Text("Сделка amoCRM", size=15, weight=ft.FontWeight.W_700, color="#1E293B"),
                                ], spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                            ],
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                        ft.Row(
                            controls=[
                                self.deal_url_input,
                                ft.ElevatedButton(
                                    "Найти сделку",
                                    icon=ft.icons.SAVED_SEARCH_ROUNDED,
                                    bgcolor="#0C66E4",
                                    color=ft.colors.WHITE,
                                    height=48,
                                    style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=14)),
                                    on_click=self.on_find_deal,
                                ),
                                ft.OutlinedButton(
                                    "Сбросить",
                                    icon=ft.icons.RESTART_ALT_ROUNDED,
                                    height=48,
                                    style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=14)),
                                    on_click=self.clear_form,
                                ),
                            ],
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                        self.info_card,
                    ],
                    spacing=14,
                ),
            )

            # Шаг 2: Время и ведущий
            step2_card = ft.Container(
                bgcolor=ft.colors.WHITE,
                border_radius=20,
                padding=20,
                border=ft.border.all(1, "#E2E8F0"),
                content=ft.Column(
                    controls=[
                        ft.Row(
                            controls=[
                                ft.Row([
                                    build_oneui_badge("2"),
                                    ft.Text("Параметры и доступные слоты", size=15, weight=ft.FontWeight.W_700, color="#1E293B"),
                                ], spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                                self.created_by_badge,
                            ],
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                        ft.Row(
                            controls=[
                                self.date_input,
                                self.meeting_type_dropdown,
                                self.host_manager_dropdown,
                            ],
                            spacing=12,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                        ft.Container(height=2),
                        ft.Row(
                            controls=[
                                ft.Text("Сетка времени на выбранную дату:", size=13, weight=ft.FontWeight.W_600, color="#475569"),
                                ft.IconButton(
                                    icon=ft.icons.SYNC_ROUNDED,
                                    icon_size=18,
                                    tooltip="Обновить слоты",
                                    icon_color="#0C66E4",
                                    on_click=lambda e: self.refresh_slots(),
                                ),
                            ],
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                        self.slots_row,
                        ft.Row(
                            controls=[
                                self.custom_time_input,
                                ft.OutlinedButton(
                                    "Задать время",
                                    height=42,
                                    style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=14)),
                                    on_click=self.check_custom_time,
                                ),
                                self.slot_info_badge,
                            ],
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            spacing=10,
                        ),
                    ],
                    spacing=14,
                ),
            )

            # Шаг 3: Аудиозапись и действие
            step3_card = ft.Container(
                bgcolor=ft.colors.WHITE,
                border_radius=20,
                padding=20,
                border=ft.border.all(1, "#E2E8F0"),
                content=ft.Column(
                    controls=[
                        ft.Row([
                            build_oneui_badge("3"),
                            ft.Text("Завершение бронирования", size=15, weight=ft.FontWeight.W_700, color="#1E293B"),
                        ], spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                        self.call_url_input,
                        ft.Row(
                            controls=[
                                self.btn_book_meeting,
                                self.btn_tg_form,
                            ],
                            spacing=12,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                        self.save_status_text,
                    ],
                    spacing=14,
                ),
            )

            return ft.Container(
                padding=24,
                content=ft.Column(
                    controls=[
                        ft.Text("Назначение встречи", size=24, weight=ft.FontWeight.BOLD, color="#0F172A"),
                        ft.Text("Пошаговый выбор сделки amoCRM, ведущего и бронирование слота", size=13, color="#64748B"),
                        ft.Container(height=4),
                        step1_card,
                        step2_card,
                        step3_card,
                    ],
                    spacing=16,
                    scroll=ft.ScrollMode.AUTO,
                ),
                expand=True,
            )

        elif subview_key == "meetings_schedule":
            self.load_schedule_list()
            return ft.Container(
                padding=24,
                content=ft.Column(
                    controls=[
                        ft.Text("Расписание встреч", size=24, weight=ft.FontWeight.BOLD, color="#0F172A"),
                        ft.Text("Просмотр запланированных встреч за произвольный период", size=13, color="#64748B"),
                        ft.Container(height=4),
                        ft.Container(
                            bgcolor=ft.colors.WHITE,
                            border_radius=20,
                            padding=16,
                            border=ft.border.all(1, "#E2E8F0"),
                            content=ft.Row(
                                controls=[
                                    self.sched_date_from_input,
                                    ft.IconButton(icon=ft.icons.CALENDAR_TODAY_OUTLINED, icon_size=18, tooltip="С даты", on_click=lambda e: self.sched_date_picker_from.pick_date()),
                                    self.sched_date_to_input,
                                    ft.IconButton(icon=ft.icons.CALENDAR_TODAY_OUTLINED, icon_size=18, tooltip="По дату", on_click=lambda e: self.sched_date_picker_to.pick_date()),
                                    self.sched_host_filter,
                                    self.sched_creator_filter,
                                    ft.ElevatedButton(
                                        "Показать",
                                        icon=ft.icons.SYNC_ROUNDED,
                                        bgcolor="#0C66E4",
                                        color=ft.colors.WHITE,
                                        height=48,
                                        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=14)),
                                        on_click=self.load_schedule_list,
                                    ),
                                    ft.OutlinedButton(
                                        "Сегодня",
                                        height=48,
                                        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=14)),
                                        on_click=lambda e: setattr(self.sched_date_from_input, "value", datetime.today().strftime("%d.%m.%Y")) or setattr(self.sched_date_to_input, "value", datetime.today().strftime("%d.%m.%Y")) or self.load_schedule_list(),
                                    ),
                                    ft.OutlinedButton(
                                        "На неделю",
                                        height=48,
                                        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=14)),
                                        on_click=lambda e: setattr(self.sched_date_from_input, "value", datetime.today().strftime("%d.%m.%Y")) or setattr(self.sched_date_to_input, "value", (datetime.today() + timedelta(days=7)).strftime("%d.%m.%Y")) or self.load_schedule_list(),
                                    ),
                                ],
                                wrap=True, vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=10,
                            ),
                        ),
                        self.schedule_list,
                    ],
                    spacing=16, scroll=ft.ScrollMode.AUTO,
                ),
                expand=True,
            )

        elif subview_key == "meetings_registry":
            self.load_registry_list()
            return ft.Container(
                padding=24,
                content=ft.Column(
                    controls=[
                        ft.Text("Реестр встреч", size=24, weight=ft.FontWeight.BOLD, color="#0F172A"),
                        ft.Text("Полная база и фильтрация всех проведённых и отменённых встреч", size=13, color="#64748B"),
                        ft.Container(height=4),
                        ft.Container(
                            bgcolor=ft.colors.WHITE,
                            border_radius=20,
                            padding=16,
                            border=ft.border.all(1, "#E2E8F0"),
                            content=ft.Row(
                                controls=[
                                    self.reg_date_from_input,
                                    ft.IconButton(icon=ft.icons.CALENDAR_TODAY_OUTLINED, icon_size=18, tooltip="С даты", on_click=lambda e: self.reg_date_picker_from.pick_date()),
                                    self.reg_date_to_input,
                                    ft.IconButton(icon=ft.icons.CALENDAR_TODAY_OUTLINED, icon_size=18, tooltip="По дату", on_click=lambda e: self.reg_date_picker_to.pick_date()),
                                    self.reg_status_filter,
                                    self.reg_host_filter,
                                    self.reg_creator_filter,
                                    ft.ElevatedButton(
                                        "Фильтр",
                                        icon=ft.icons.FILTER_ALT_OUTLINED,
                                        bgcolor="#0C66E4",
                                        color=ft.colors.WHITE,
                                        height=48,
                                        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=14)),
                                        on_click=lambda e: setattr(self.registry_mode, "all_time", False) or self.load_registry_list(),
                                    ),
                                    ft.OutlinedButton(
                                        "Все встречи",
                                        icon=ft.icons.ALL_INCLUSIVE_ROUNDED,
                                        height=48,
                                        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=14)),
                                        on_click=lambda e: setattr(self.registry_mode, "all_time", True) or self.load_registry_list(),
                                    ),
                                ],
                                wrap=True, vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=10,
                            ),
                        ),
                        self.registry_list,
                    ],
                    spacing=16, scroll=ft.ScrollMode.AUTO,
                ),
                expand=True,
            )

        return ft.Container()