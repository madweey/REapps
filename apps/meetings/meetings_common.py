import os
import threading
from datetime import datetime
import flet as ft
from apps.core.sheets import (
    find_deal_by_link,
    update_meeting_status,
    update_meeting_details,
    complete_meeting,
    cancel_meeting,
    delete_meeting,
    get_all_prompts,
    get_sheets_client,
)
from apps.core.schedule_engine import calculate_end_time
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


class MeetingsModalManager:
    """Управляет модальными окнами, плеером и действиями над встречами."""

    def __init__(self, page: ft.Page, account_names: list[str], on_data_changed_callback):
        self.page = page
        self.account_names = account_names
        self.on_data_changed = on_data_changed_callback

        self.audio_state = {
            "player": None,
            "is_playing": False,
            "duration_ms": 0,
            "position_ms": 0,
            "rate": 1.0,
        }
        self.action_context = {"meeting": None}
        self._is_deleting = False

        self._build_modals()

    def _build_modals(self):
        # 1. Диалог успешного бронирования
        self.booked_success_content = ft.Column(spacing=8, tight=True)
        self.booked_success_dialog = ft.AlertDialog(
            title=ft.Row([
                ft.Icon(ft.icons.CHECK_CIRCLE_ROUNDED, color="#15803D", size=24),
                ft.Text("Встреча забронирована!", size=16, weight=ft.FontWeight.BOLD),
            ], spacing=8),
            content=ft.Container(content=self.booked_success_content, width=480),
            actions=[
                ft.ElevatedButton(
                    "Отлично",
                    bgcolor="#0C66E4",
                    color=ft.colors.WHITE,
                    on_click=lambda e: setattr(self.booked_success_dialog, "open", False) or self.page.update(),
                )
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )

        # 2. DatePicker редактирования
        self.edit_date_picker = ft.DatePicker(
            on_change=self._on_edit_date_picked,
            first_date=datetime(2025, 1, 1),
            last_date=datetime(2030, 12, 31),
            confirm_text="Выбрать",
            cancel_text="Отмена",
            help_text="Изменить дату встречи",
        )

        # 3. Диалог завершения встречи
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
                ft.ElevatedButton("Сохранить", icon=ft.icons.CHECK_ROUNDED, bgcolor="#2E7D32", color=ft.colors.WHITE, on_click=self._on_confirm_complete),
            ],
        )

        # 4. Диалог отмены встречи
        self.cancel_reason_input = ft.TextField(label="Причина отмены встречи", multiline=True, min_lines=3, border_radius=12, text_size=13)
        self.cancel_dialog = ft.AlertDialog(
            title=ft.Row([ft.Icon(ft.icons.CANCEL_OUTLINED, color="#D32F2F"), ft.Text("Отмена встречи", size=16, weight=ft.FontWeight.BOLD)]),
            content=ft.Container(content=self.cancel_reason_input, width=500),
            actions=[
                ft.TextButton("Назад", on_click=lambda e: setattr(self.cancel_dialog, "open", False) or self.page.update()),
                ft.ElevatedButton("Подтвердить отмену", icon=ft.icons.CLOSE_ROUNDED, bgcolor="#D32F2F", color=ft.colors.WHITE, on_click=self._on_confirm_cancel),
            ],
        )

        # 5. Диалог удаления
        self.delete_confirm_text = ft.Text("", size=13)
        self.btn_delete_confirm = ft.ElevatedButton("Удалить", icon=ft.icons.DELETE_FOREVER_ROUNDED, bgcolor="#D32F2F", color=ft.colors.WHITE, on_click=self._on_confirm_delete)
        self.btn_delete_cancel = ft.TextButton("Отмена", on_click=lambda e: setattr(self.delete_dialog, "open", False) or self.page.update())
        self.delete_dialog = ft.AlertDialog(
            title=ft.Row([ft.Icon(ft.icons.DELETE_OUTLINE_ROUNDED, color="#D32F2F"), ft.Text("Удаление встречи", size=16, weight=ft.FontWeight.BOLD)]),
            content=ft.Container(content=self.delete_confirm_text, width=450),
            actions=[self.btn_delete_cancel, self.btn_delete_confirm],
        )

        # 6. Диалог редактирования
        self.edit_date_input = ft.TextField(
            label="Дата встречи",
            hint_text="ДД.ММ.ГГГГ",
            text_size=13,
            label_style=ft.TextStyle(size=12, color="#64748B"),
            width=175,
            border_radius=12,
            suffix=ft.IconButton(
                icon=ft.icons.CALENDAR_TODAY_OUTLINED,
                icon_size=18,
                tooltip="Выбрать дату",
                on_click=lambda e: self.edit_date_picker.pick_date(),
            ),
        )
        self.edit_time_input = ft.TextField(
            label="Время встречи (напр. 13:00)",
            hint_text="13:00",
            text_size=13,
            label_style=ft.TextStyle(size=12, color="#64748B"),
            expand=True,
            border_radius=12,
        )
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
            expand=True,
        )
        self.edit_type_dropdown = ft.Dropdown(
            label="Тип встречи",
            options=[ft.dropdown.Option("Онлайн встреча"), ft.dropdown.Option("Звонок")],
            border_radius=12,
            text_size=13,
            expand=True,
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
                        ft.Row([self.edit_date_input, self.edit_time_input], spacing=10),
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
                ft.ElevatedButton("Сохранить изменения", icon=ft.icons.SAVE_ROUNDED, bgcolor="#0C66E4", color=ft.colors.WHITE, on_click=self._on_save_edited_meeting),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )

        # 7. Диалог деталей встречи
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

        # 8. Диалог ИИ-анализа
        self.meeting_ai_prompt_dd = ft.Dropdown(label="Шаблон промта", width=480, height=48, border_radius=12, text_size=13)
        self.meeting_ai_custom_input = ft.TextField(
            label="Инструкция для ИИ", multiline=True, min_lines=2, max_lines=5, border_radius=12, text_size=13,
            hint_text="Отредактируйте или введите свой запрос к ИИ...",
        )
        self.meeting_ai_status = ft.Text("", size=12, color="#0C66E4")
        self.meeting_ai_progress = ft.ProgressBar(visible=False, color="#0C66E4")
        self.meeting_ai_result = ft.TextField(label="Итоги анализа ИИ", multiline=True, min_lines=8, max_lines=14, border_radius=12, text_size=13, read_only=True)

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
                ft.ElevatedButton("Запустить анализ", icon=ft.icons.AUTO_AWESOME_ROUNDED, bgcolor="#0C66E4", color=ft.colors.WHITE, on_click=self._run_meeting_ai_analysis),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )

        for d in (
            self.booked_success_dialog, self.edit_date_picker, self.complete_dialog,
            self.cancel_dialog, self.delete_dialog, self.detail_dialog,
            self.meeting_ai_dialog, self.edit_dialog
        ):
            if d not in self.page.overlay:
                self.page.overlay.append(d)

    def _on_edit_date_picked(self, e):
        if self.edit_date_picker.value:
            self.edit_date_input.value = self.edit_date_picker.value.strftime("%d.%m.%Y")
            self.page.update()

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
                src=url, autoplay=True, playback_rate=self.audio_state["rate"],
                on_loaded=self._on_audio_loaded, on_position_changed=self._on_audio_position_changed,
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

    def _on_audio_loaded(self, e):
        try:
            dur = self.audio_state["player"].get_duration() if hasattr(self.audio_state["player"], "get_duration") else int(e.data)
            if dur:
                self.audio_state["duration_ms"] = int(dur)
                self.time_label.value = f"{format_ms(self.audio_state['position_ms'])} / {format_ms(self.audio_state['duration_ms'])}"
                self.page.update()
        except Exception:
            pass

    def _on_audio_position_changed(self, e):
        if not self.audio_state["player"]:
            return
        try:
            pos = int(e.data)
            self.audio_state["position_ms"] = pos
            self.time_label.value = f"{format_ms(pos)} / {format_ms(self.audio_state['duration_ms'])}"
            self.page.update()
        except Exception:
            pass

    def _on_confirm_complete(self, e):
        meeting = self.action_context.get("meeting")
        if meeting and meeting.get("row_idx"):
            fb_val = self.complete_feedback_input.value.strip()
            rec_val = self.complete_recording_input.value.strip()
            complete_meeting(meeting["row_idx"], fb_val, rec_val)
            meeting["feedback"] = fb_val
            meeting["meeting_url"] = rec_val
            meeting["status"] = "Встреча проведена"

            self.complete_dialog.open = False
            self.on_data_changed()
            if self.detail_dialog.open:
                self.open_meeting_details(meeting)
            self.page.update()

    def _on_confirm_cancel(self, e):
        meeting = self.action_context.get("meeting")
        if meeting and meeting.get("row_idx"):
            cancel_meeting(meeting["row_idx"], self.cancel_reason_input.value.strip())
            self.cancel_dialog.open = False
            self.on_data_changed()
            self.page.update()

    def _on_confirm_delete(self, e):
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
            self.on_data_changed()
        finally:
            self._is_deleting = False
            self.page.update()

    def open_edit_dialog(self, item: dict):
        self.action_context["editing_meeting"] = item
        self.edit_date_input.value = item.get("date", "")
        self.edit_time_input.value = item.get("start", "")
        self.edit_call_url_input.value = item.get("call_url", "")
        self.edit_host_dropdown.value = item.get("host_manager") or (self.account_names[0] if self.account_names else "")
        self.edit_type_dropdown.value = item.get("meeting_type") or "Онлайн встреча"
        self.edit_hooks_input.value = item.get("hooks", "")
        self.edit_comment_input.value = item.get("comment", "")
        self.edit_status_text.value = ""

        self.edit_dialog.open = True
        self.page.update()

    def _on_save_edited_meeting(self, e):
        item = self.action_context.get("editing_meeting")
        if not item or not item.get("row_idx"):
            return

        row_idx = item["row_idx"]
        new_date = self.edit_date_input.value.strip()
        new_start = self.edit_time_input.value.strip()
        new_end = calculate_end_time(new_start) if new_start else item.get("end", "")

        updated_data = {
            "date": new_date,
            "start": new_start,
            "end": new_end,
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
            self.on_data_changed()
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

    def _run_meeting_ai_analysis(self, e):
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

    def refresh_meeting_crm_data(self, item: dict, sync_btn: ft.OutlinedButton):
        """Фоновое принудительное обновление данных из CRM."""
        deal_url = (item.get("deal_url") or item.get("Ссылка на сделку") or "").strip()
        deal_id = (item.get("deal_id") or item.get("ID") or item.get("ID сделки") or "").strip()
        search_query = deal_url or deal_id

        if not search_query:
            self.audio_status_text.value = "В карточке отсутствует ссылка или ID сделки!"
            self.audio_status_text.color = "#DC2626"
            self.page.update()
            return

        sync_btn.disabled = True
        self.audio_status_text.value = "⏳ Запрос актуальных данных из CRM..."
        self.audio_status_text.color = "#0C66E4"
        self.page.update()

        def _worker():
            try:
                crm_deal = find_deal_by_link(search_query, force_refresh=True)
                if not crm_deal:
                    self.audio_status_text.value = "Сделка не найдена в таблице выгрузки CRM!"
                    self.audio_status_text.color = "#DC2626"
                else:
                    updated_fields = {
                        "complex": crm_deal.get("complex", "") or item.get("complex", "") or item.get("ЖК", ""),
                        "area": crm_deal.get("area", "") or item.get("area", "") or item.get("Площадь", ""),
                        "client": crm_deal.get("client", "") or item.get("client", "") or item.get("Клиент", ""),
                        "manager": crm_deal.get("manager", "") or item.get("manager", "") or item.get("Менеджер", ""),
                        "deal_id": crm_deal.get("deal_id", "") or item.get("deal_id", "") or item.get("ID", ""),
                        "hooks": crm_deal.get("hooks", "") or item.get("hooks", "") or item.get("Крючки", ""),
                        "comment": crm_deal.get("comment", "") or item.get("comment", "") or item.get("Комментарий", ""),
                        "deal_url": crm_deal.get("deal_url", "") or deal_url,
                        "rooms": crm_deal.get("rooms", "") or item.get("rooms", "") or item.get("Комнат", ""),
                        "condition": crm_deal.get("condition", "") or item.get("condition", "") or item.get("Состояние", ""),
                        "keys": crm_deal.get("keys", "") or item.get("keys", "") or item.get("Ключи", ""),
                        "service_type": crm_deal.get("service_type", "") or item.get("service_type", "") or item.get("Тип услуги", ""),
                        "pains": crm_deal.get("pains", "") or item.get("pains", "") or item.get("Боли", ""),
                    }

                    row_idx = item.get("row_idx")
                    if row_idx:
                        update_meeting_details(row_idx, updated_fields)

                    item.update(updated_fields)
                    item["ЖК"] = updated_fields["complex"]
                    item["Площадь"] = updated_fields["area"]
                    item["Клиент"] = updated_fields["client"]
                    item["Менеджер"] = updated_fields["manager"]

                    self.open_meeting_details(item)
                    self.audio_status_text.value = "Данные сделки успешно обновлены из CRM!"
                    self.audio_status_text.color = "#2E7D32"
                    self.on_data_changed()
            except Exception as err:
                self.audio_status_text.value = f"Ошибка обновления: {err}"
                self.audio_status_text.color = "#DC2626"
            finally:
                sync_btn.disabled = False
                self.page.update()

        threading.Thread(target=_worker, daemon=True).start()

    def open_meeting_details(self, item: dict):
        """Открывает детальное окно мгновенно без сетевых задержек."""
        self.cleanup_audio_player()
        deal_url = item.get("deal_url") or item.get("Ссылка на сделку") or ""
        call_url = (item.get("call_url") or item.get("Ссылка на звонок") or "").strip()

        deal_id = item.get("deal_id") or item.get("ID") or item.get("ID сделки") or ""
        complex_name = item.get("complex") or item.get("ЖК") or ""
        area_val = item.get("area") or item.get("Площадь") or ""
        client_name = item.get("client") or item.get("Клиент") or ""
        crm_manager = item.get("manager") or item.get("Менеджер") or "Не назначен"
        host_mgr = item.get("host_manager") or item.get("Кто проведет") or "Не назначен"
        creator_name = item.get("created_by") or item.get("Кто записал") or "Не указан"
        meeting_status = item.get("status") or item.get("Статус") or ""

        rooms = item.get("rooms") or item.get("Комнат") or ""
        condition = item.get("condition") or item.get("Состояние") or ""
        keys = item.get("keys") or item.get("Ключи") or ""
        service_type = item.get("service_type") or item.get("Тип услуги") or ""
        pains = item.get("pains") or item.get("Боли") or ""
        hooks = item.get("hooks") or item.get("Крючки") or ""
        comment_val = item.get("comment") or item.get("Комментарий") or ""
        feedback_val = item.get("feedback") or item.get("Результат") or ""
        meeting_url = item.get("meeting_url") or item.get("Ссылка на онлайн встречу") or ""

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

        sync_crm_btn = ft.OutlinedButton(
            "Обновить из CRM",
            icon=ft.icons.SYNC_ROUNDED,
            tooltip="Принудительно подтянуть ЖК, площадь и клиента из CRM",
        )
        sync_crm_btn.on_click = lambda e, it=item, btn=sync_crm_btn: self.refresh_meeting_crm_data(it, btn)

        def copy_transfer(e):
            rooms_str = f"{rooms} ком" if rooms else ""
            id_complex_str = f"{deal_id} {complex_name}".strip()
            area_str = f"{area_val} м²" if area_val else ""
            tmpl = (
                f"{client_name}\n{id_complex_str}\n{area_str} {rooms_str}".strip() + "\n"
                f"Состояние: {condition}\nКлючи: {keys}\nТип услуги: {service_type}\n"
                f"Тип встречи: {item.get('meeting_type', 'Онлайн встреча')}\nДата встречи/звонка: {item.get('date', '')}\n"
                f"Время: {item.get('start', '')}\nВедущий встречи: {host_mgr}\n"
                f"Записал(а): {creator_name}\nОтветственный CRM: {crm_manager}\n"
                f"Крючки: {hooks}\nБоли клиента: {pains}\nКомментарии КЦ: {comment_val}\nСсылка CRM: {deal_url}"
            )
            self.page.set_clipboard(tmpl)
            self.audio_status_text.value = "Форма для передачи скопирована!"
            self.audio_status_text.color = "#2E7D32"
            self.page.update()

        def copy_result(e):
            rooms_str = f"{rooms} ком" if rooms else ""
            id_complex_str = f"{deal_id} {complex_name}".strip()
            area_str = f"{area_val} м²" if area_val else ""
            rec_line = f"Ссылка на онлайн встречу: {meeting_url}\n" if meeting_url else ""
            tmpl = (
                f"{client_name}\n{id_complex_str}\n{area_str} {rooms_str}".strip() + "\n"
                f"Состояние: {condition}\nКлючи: {keys}\nТип услуги: {service_type}\n"
                f"Тип встречи: {item.get('meeting_type', 'Онлайн встреча')}\nДата встречи/звонка: {item.get('date', '')}\n"
                f"Время: {item.get('start', '')}\nВедущий: {host_mgr}\n"
                f"Записал(а): {creator_name}\nСтатус: {meeting_status}\n"
                f"ОС / Результат: {feedback_val}\n{rec_line}Ссылка CRM: {deal_url}"
            )
            self.page.set_clipboard(tmpl)
            self.audio_status_text.value = "Форма с результатом скопирована!"
            self.audio_status_text.color = "#2E7D32"
            self.page.update()

        feedback_block = ft.Text(f"📋 ОС / Результат: {feedback_val}", weight=ft.FontWeight.W_500, color="#0C66E4") if feedback_val else ft.Container()
        recording_block = ft.ElevatedButton("Запись встречи", icon=ft.icons.CLOUD_DOWNLOAD_ROUNDED, on_click=lambda e, u=meeting_url: self.page.launch_url(u)) if meeting_url else ft.Container()

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

        area_display = f"({area_val} м²)" if area_val else ""
        jk_display = f"🏢 ЖК: {complex_name} {area_display}".strip()

        self.detail_content.controls = [
            ft.Row([ft.Text(f"🕒 {item.get('start', '')} - {item.get('end', '')}", size=18, weight=ft.FontWeight.BOLD), ft.Text(f"Статус: {meeting_status}", size=14, weight=ft.FontWeight.BOLD, color="#0C66E4")], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            ft.Divider(),
            ft.Text(f"👤 Клиент: {client_name}", weight=ft.FontWeight.BOLD),
            ft.Text(f"🎯 Кто проведет встречу: {host_mgr}", weight=ft.FontWeight.W_600, color="#0C66E4"),
            ft.Text(f"✍️ Кто записал: {creator_name} | 👨‍💼 Менеджер CRM: {crm_manager}"),
            ft.Text(jk_display if complex_name or area_val else "🏢 ЖК: не указан"),
            ft.Text(f"🚪 Комнат: {rooms} | Состояние: {condition} | Ключи: {keys}" if rooms or condition or keys else ""),
            ft.Text(f"🎯 Крючки: {hooks}", italic=True) if hooks else ft.Container(),
            ft.Text(f"⚡ Боли: {pains}", italic=True) if pains else ft.Container(),
            ft.Text(f"💬 Комментарий: {comment_val}") if comment_val else ft.Container(),
            feedback_block, recording_block, summary_block,
            ft.Divider(), audio_section,
            ft.Row(
                controls=[crm_btn, ai_analysis_btn, edit_detail_btn, sync_crm_btn],
                spacing=10, wrap=True, vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            ft.Row(
                controls=[
                    ft.OutlinedButton("Форма для передачи", icon=ft.icons.COPY_ALL_ROUNDED, on_click=copy_transfer),
                    ft.OutlinedButton("Форма после встречи", icon=ft.icons.FACT_CHECK_OUTLINED, on_click=copy_result),
                ],
                spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        ]
        self.detail_dialog.open = True
        self.page.update()

    def render_meeting_card(self, item: dict, is_registry: bool = False) -> ft.Control:
        deal_link = item.get("deal_url") or item.get("Ссылка на сделку") or ""
        meeting_type = item.get("meeting_type") or item.get("Тип встречи") or "Онлайн встреча"
        status = item.get("status") or item.get("Статус") or "Ожидает подтверждения"
        row_idx = item.get("row_idx")
        host_m = item.get("host_manager") or item.get("Кто проведет") or "Не назначен"
        created_b = item.get("created_by") or item.get("Кто записал") or "Не указан"
        crm_m = item.get("manager") or item.get("Менеджер") or "Не назначен"

        complex_val = item.get("complex") or item.get("ЖК") or ""
        area_val = item.get("area") or item.get("Площадь") or ""
        area_str = f"({area_val} м²)" if area_val else ""
        jk_str = f"🏢 {complex_val} {area_str}".strip() if (complex_val or area_val) else ""

        is_online = "онлайн" in meeting_type.lower()
        type_badge = ft.Container(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.icons.VIDEO_CAMERA_FRONT_OUTLINED if is_online else ft.icons.CALL_OUTLINED, size=13, color="#0C66E4" if is_online else "#B45309"),
                    ft.Text(meeting_type, size=11, weight=ft.FontWeight.BOLD, color="#0C66E4" if is_online else "#78350F"),
                ],
                spacing=4, tight=True, vertical_alignment=ft.CrossAxisAlignment.CENTER,
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
                self.on_data_changed()

        def handle_open_complete(e, it=item):
            self.action_context["meeting"] = it
            self.complete_feedback_input.value = it.get("feedback") or it.get("Результат") or ""
            self.complete_recording_input.value = it.get("meeting_url") or it.get("Ссылка на онлайн встречу") or ""
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
            client_name = it.get("client") or it.get("Клиент") or "без имени"
            meeting_date = it.get("date") or it.get("Дата") or ""
            meeting_time = it.get("start") or it.get("Время начала") or ""
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

        card_body = ft.Column(
            controls=[
                card_progress_bar,
                ft.Row(
                    controls=[
                        ft.Row([ft.Text(f"🕒 {item.get('start', '')} - {item.get('end', '')}", size=15, weight=ft.FontWeight.BOLD), type_badge], spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                        ft.Text(f"📅 {item.get('date', '')} | {jk_str}" if jk_str else f"📅 {item.get('date', '')}", weight=ft.FontWeight.W_500, color="#334155"),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                ft.Text(f"Клиент: {item.get('client') or item.get('Клиент') or ''} | Менеджер CRM: {crm_m}", size=13),
                ft.Row(
                    controls=[
                        ft.Container(content=ft.Row([ft.Icon(ft.icons.PERSON_ROUNDED, size=14, color="#0C66E4"), ft.Text(f"Проведет: {host_m}", size=12, weight=ft.FontWeight.BOLD, color="#0C66E4")], spacing=4, vertical_alignment=ft.CrossAxisAlignment.CENTER), bgcolor="#E9F2FF", padding=ft.padding.symmetric(horizontal=10, vertical=4), border_radius=10),
                        ft.Container(content=ft.Row([ft.Icon(ft.icons.CREATE_ROUNDED, size=14, color="#64748B"), ft.Text(f"Записал(а): {created_b}", size=12, color="#475569")], spacing=4, vertical_alignment=ft.CrossAxisAlignment.CENTER), bgcolor="#F1F5F9", padding=ft.padding.symmetric(horizontal=10, vertical=4), border_radius=10),
                    ],
                    spacing=8,
                ),
                ft.Text(f"Крючки: {item.get('hooks') or item.get('Крючки')}", size=12, italic=True, color="#475569") if (item.get('hooks') or item.get('Крючки')) else ft.Container(),
                ft.Text(f"Комментарий: {item.get('comment') or item.get('Комментарий')}", size=12, color="#64748B") if (item.get('comment') or item.get('Комментарий')) else ft.Container(),
                ft.Row(
                    controls=[
                        crm_btn,
                        ft.Row(controls=status_controls, spacing=8, wrap=True, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                        ft.Row(
                            controls=[
                                ft.TextButton("Подробнее и звонок", icon=ft.icons.INFO_OUTLINE_ROUNDED, on_click=lambda e, it=item: self.open_meeting_details(it)),
                                ft.IconButton(icon=ft.icons.EDIT_NOTE_ROUNDED, tooltip="Редактировать", icon_color="#0C66E4", on_click=lambda e, it=item: self.open_edit_dialog(it)),
                                ft.IconButton(icon=ft.icons.DELETE_OUTLINE_ROUNDED, tooltip="Удалить", icon_color="#EF4444", on_click=lambda e, it=item, p=card_progress_bar: handle_open_delete(e, it, p)),
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