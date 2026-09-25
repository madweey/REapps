from datetime import datetime
import flet as ft
from apps.core.sheets import (
    find_deal_by_link,
    save_new_meeting,
    get_meetings_by_date,
    normalize_deal_url,
)
from apps.core.schedule_engine import evaluate_slot_status, get_day_schedule_grid, calculate_end_time
from apps.meetings.meetings_common import build_oneui_badge, MeetingsModalManager


class MeetingsBookView:
    def __init__(self, page: ft.Page, current_username: str, account_names: list[str], modal_mgr: MeetingsModalManager):
        self.page = page
        self.current_username = current_username
        self.account_names = account_names
        self.modal_mgr = modal_mgr

        self.deal_cache = {
            "manager": "", "client": "", "deal_id": "", "complex": "",
            "service_type": "", "area": "", "rooms": "", "pains": "",
            "condition": "", "keys": "", "deal_url": "", "comment": "", "hooks": "",
        }
        self.deal_verified = False
        self.selected_time = {"start": "", "end": "", "reason": ""}
        self._is_refreshing_slots = False

        self._build_controls()
        self.refresh_slots()

    def _build_controls(self):
        # Шаг 1
        self.deal_url_input = ft.TextField(
            label="Ссылка на сделку или ID (amoCRM)",
            hint_text="Вставьте URL или номер сделки amoCRM...",
            text_size=13, label_style=ft.TextStyle(size=12, color="#64748B"),
            expand=True, height=48, filled=True, fill_color="#F1F5F9",
            border=ft.InputBorder.NONE, border_radius=14,
            prefix_icon=ft.icons.LINK_ROUNDED, on_change=self.on_deal_input_changed,
        )

        self.info_card_content = ft.Column(
            controls=[ft.Text("Данные сделки не загружены", italic=True, color="#94A3B8", size=12)],
            spacing=4,
        )
        self.info_card = ft.Container(
            content=self.info_card_content,
            padding=16, border_radius=16, bgcolor="#F8FAFC",
            border=ft.border.all(1, "#E2E8F0"), visible=False,
        )

        # Шаг 2
        self.book_date_picker = ft.DatePicker(
            on_change=self.on_book_date_picked,
            first_date=datetime(2025, 1, 1), last_date=datetime(2030, 12, 31),
            confirm_text="Выбрать", cancel_text="Отмена", help_text="Выберите дату встречи",
        )
        if self.book_date_picker not in self.page.overlay:
            self.page.overlay.append(self.book_date_picker)

        self.date_input = ft.TextField(
            label="Дата встречи", hint_text="ДД.ММ.ГГГГ",
            value=datetime.today().strftime("%d.%m.%Y"),
            text_size=13, label_style=ft.TextStyle(size=12, color="#64748B"),
            width=175, height=48, filled=True, fill_color="#F1F5F9",
            border=ft.InputBorder.NONE, border_radius=14,
            suffix=ft.IconButton(
                icon=ft.icons.CALENDAR_TODAY_OUTLINED,
                icon_size=18, tooltip="Выбрать дату",
                on_click=lambda e: self.book_date_picker.pick_date(),
            ),
        )

        self.meeting_type_dropdown = ft.Dropdown(
            label="Тип встречи", value="Онлайн встреча",
            text_size=13, label_style=ft.TextStyle(size=12, color="#64748B"),
            width=220, height=48, filled=True, fill_color="#F1F5F9",
            border=ft.InputBorder.NONE, border_radius=14,
            options=[ft.dropdown.Option("Онлайн встреча"), ft.dropdown.Option("Звонок")],
        )

        def on_host_changed(e):
            self.selected_time = {"start": "", "end": "", "reason": ""}
            self.slot_info_badge.visible = False
            self.refresh_slots()

        self.host_manager_dropdown = ft.Dropdown(
            label="Кто проведет встречу",
            value=self.current_username if self.current_username in self.account_names else (self.account_names[0] if self.account_names else ""),
            text_size=13, label_style=ft.TextStyle(size=12, color="#64748B"),
            expand=True, height=48, filled=True, fill_color="#F1F5F9",
            border=ft.InputBorder.NONE, border_radius=14,
            options=[ft.dropdown.Option(name) for name in self.account_names],
            on_change=on_host_changed,
        )

        self.created_by_badge = ft.Container(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.icons.PERSON_OUTLINE_ROUNDED, size=14, color="#64748B"),
                    ft.Text(f"Автор записи: {self.current_username}", size=11, weight=ft.FontWeight.W_600, color="#64748B"),
                ],
                spacing=5, tight=True, vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.padding.symmetric(horizontal=12, vertical=6),
            bgcolor="#F1F5F9", border_radius=12,
        )

        self.slots_row = ft.Row(wrap=True, spacing=8)
        self.slot_info_icon = ft.Icon(ft.icons.ACCESS_TIME_ROUNDED, size=16, color="#0C66E4")
        self.slot_info_text = ft.Text("", size=12, weight=ft.FontWeight.W_600, color="#0C66E4")
        self.slot_info_badge = ft.Container(
            content=ft.Row([self.slot_info_icon, self.slot_info_text], spacing=6, tight=True, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            padding=ft.padding.symmetric(horizontal=14, vertical=0), height=42, bgcolor="#E9F2FF",
            border_radius=14, alignment=ft.alignment.center, visible=False,
        )

        self.custom_time_input = ft.TextField(
            label="Своё время", hint_text="11:30", text_size=13, label_style=ft.TextStyle(size=11, color="#64748B"),
            width=140, height=42, filled=True, fill_color="#F1F5F9", border=ft.InputBorder.NONE,
            border_radius=14, content_padding=ft.padding.symmetric(horizontal=14, vertical=4),
        )

        # Шаг 3
        self.call_url_input = ft.TextField(
            label="Ссылка на запись звонка (mp3)", hint_text="https://vats.../record.mp3",
            text_size=13, label_style=ft.TextStyle(size=12, color="#64748B"),
            height=48, filled=True, fill_color="#F1F5F9", border=ft.InputBorder.NONE,
            border_radius=14, prefix_icon=ft.icons.AUDIO_FILE_OUTLINED,
        )
        self.save_status_text = ft.Text("", size=13, weight=ft.FontWeight.W_500)

        self.btn_book_meeting = ft.ElevatedButton(
            "Забронировать встречу", icon=ft.icons.ADD_TASK_ROUNDED, bgcolor="#0C66E4", color=ft.colors.WHITE,
            height=46, style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=14)),
            disabled=True, on_click=self.on_save_meeting,
        )

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
                    bg_color, txt_color, border_color, icon_control = "#0C66E4", "#FFFFFF", "#0C66E4", ft.icons.CHECK_ROUNDED
                elif status_val == "BUSY":
                    bg_color, txt_color, border_color, icon_control = "#F1F5F9", "#94A3B8", "#E2E8F0", None
                else:
                    bg_color, txt_color, border_color, icon_control = "#FFFFFF", "#0F172A", "#CBD5E1", None

                btn = ft.Container(
                    content=ft.Row(
                        controls=[
                            ft.Icon(icon_control, size=14, color=txt_color) if icon_control else ft.Container(),
                            ft.Text(time_val, size=13, weight=ft.FontWeight.W_600, color=txt_color),
                        ],
                        spacing=4, alignment=ft.MainAxisAlignment.CENTER, vertical_alignment=ft.CrossAxisAlignment.CENTER, tight=True,
                    ),
                    padding=ft.padding.symmetric(horizontal=14, vertical=9), border_radius=12,
                    bgcolor=bg_color, border=ft.border.all(1, border_color),
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
                self.info_card_content.controls = [ft.Text("Сделка не найдена в таблице", color="#DC2626", size=12)]
                self.info_card.visible = True
                self.save_status_text.value = "Сделка не найдена!"
                self.save_status_text.color = "#DC2626"
        except Exception as err:
            self.deal_verified = False
            self.btn_book_meeting.disabled = True
            self.info_card_content.controls = [ft.Text(f"Ошибка загрузки: {err}", color="#DC2626", size=12)]
            self.info_card.visible = True
            self.save_status_text.value = f"Ошибка: {err}"
            self.save_status_text.color = "#DC2626"
        finally:
            self.deal_url_input.disabled = False
            self.page.update()

    def build_transfer_text(self) -> str:
        rooms_val = self.deal_cache.get("rooms", "").strip()
        rooms_str = f"{rooms_val} ком" if rooms_val else ""
        id_complex_str = f"{self.deal_cache.get('deal_id', '')} {self.deal_cache.get('complex', '')}".strip()
        area_val = self.deal_cache.get("area", "").strip()
        area_str = f"{area_val} м²" if area_val else ""
        area_rooms_str = f"{area_str} {rooms_str}".strip()
        crm_url = normalize_deal_url(self.deal_cache.get("deal_url") or self.deal_url_input.value.strip())

        return (
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

    def clear_form(self, e=None):
        self.deal_url_input.value = ""
        self.call_url_input.value = ""
        self.custom_time_input.value = ""
        self.info_card.visible = False
        self.save_status_text.value = ""
        self.deal_verified = False
        self.btn_book_meeting.disabled = True

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
            "feedback": "", "meeting_url": "", "transcription": "", "gpt_summary": "",
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
            transfer_text = self.build_transfer_text()
            self.page.set_clipboard(transfer_text)

            self.modal_mgr.booked_success_content.controls = [
                ft.Text("Форма для передачи скопирована в буфер обмена!", size=13, weight=ft.FontWeight.W_600, color="#15803D"),
                ft.Container(
                    content=ft.Text(transfer_text, size=11, color="#334155", selectable=True),
                    bgcolor="#F8FAFC", padding=12, border_radius=10, border=ft.border.all(1, "#E2E8F0"),
                ),
            ]
            self.modal_mgr.booked_success_dialog.open = True

            self.save_status_text.value = f"Встреча на {payload['date']} в {payload['start']} успешно записана!"
            self.save_status_text.color = "#2E7D32"
            self.selected_time = {"start": "", "end": "", "reason": ""}
            self.slot_info_badge.visible = False
            self.refresh_slots()
            self.modal_mgr.on_data_changed()
        except Exception as err:
            self.save_status_text.value = f"Ошибка записи: {err}"
            self.save_status_text.color = "#DC2626"
        self.page.update()

    def build_view(self) -> ft.Control:
        step1_card = ft.Container(
            bgcolor=ft.colors.WHITE, border_radius=20, padding=20, border=ft.border.all(1, "#E2E8F0"),
            content=ft.Column(
                controls=[
                    ft.Row([
                        build_oneui_badge("1"),
                        ft.Text("Сделка amoCRM", size=15, weight=ft.FontWeight.W_700, color="#1E293B"),
                    ], spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                    ft.Row(
                        controls=[
                            self.deal_url_input,
                            ft.ElevatedButton("Найти сделку", icon=ft.icons.SAVED_SEARCH_ROUNDED, bgcolor="#0C66E4", color=ft.colors.WHITE, height=48, style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=14)), on_click=self.on_find_deal),
                            ft.OutlinedButton("Сбросить", icon=ft.icons.RESTART_ALT_ROUNDED, height=48, style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=14)), on_click=self.clear_form),
                        ],
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    self.info_card,
                ],
                spacing=14,
            ),
        )

        step2_card = ft.Container(
            bgcolor=ft.colors.WHITE, border_radius=20, padding=20, border=ft.border.all(1, "#E2E8F0"),
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Row([build_oneui_badge("2"), ft.Text("Параметры и доступные слоты", size=15, weight=ft.FontWeight.W_700, color="#1E293B")], spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                            self.created_by_badge,
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN, vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    ft.Row(controls=[self.date_input, self.meeting_type_dropdown, self.host_manager_dropdown], spacing=12, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                    ft.Container(height=2),
                    ft.Row(
                        controls=[
                            ft.Text("Сетка времени на выбранную дату:", size=13, weight=ft.FontWeight.W_600, color="#475569"),
                            ft.IconButton(icon=ft.icons.SYNC_ROUNDED, icon_size=18, tooltip="Обновить слоты", icon_color="#0C66E4", on_click=lambda e: self.refresh_slots()),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN, vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    self.slots_row,
                    ft.Row(
                        controls=[
                            self.custom_time_input,
                            ft.OutlinedButton("Задать время", height=42, style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=14)), on_click=self.check_custom_time),
                            self.slot_info_badge,
                        ],
                        vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=10,
                    ),
                ],
                spacing=14,
            ),
        )

        step3_card = ft.Container(
            bgcolor=ft.colors.WHITE, border_radius=20, padding=20, border=ft.border.all(1, "#E2E8F0"),
            content=ft.Column(
                controls=[
                    ft.Row([build_oneui_badge("3"), ft.Text("Завершение бронирования", size=15, weight=ft.FontWeight.W_700, color="#1E293B")], spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                    self.call_url_input,
                    ft.Row(controls=[self.btn_book_meeting], spacing=12, vertical_alignment=ft.CrossAxisAlignment.CENTER),
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