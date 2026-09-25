from datetime import datetime, timedelta
import flet as ft
from apps.core.sheets import get_all_meetings
from apps.meetings.meetings_common import parse_date_safely, MeetingsModalManager


class MeetingsScheduleView:
    def __init__(self, page: ft.Page, account_names: list[str], modal_mgr: MeetingsModalManager):
        self.page = page
        self.account_names = account_names
        self.modal_mgr = modal_mgr
        self._is_loading = False

        self._build_controls()

    def _build_controls(self):
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
        for dp in (self.sched_date_picker_from, self.sched_date_picker_to):
            if dp not in self.page.overlay:
                self.page.overlay.append(dp)

        self.sched_date_from_input = ft.TextField(
            label="С даты", hint_text="ДД.ММ.ГГГГ",
            value=datetime.today().strftime("%d.%m.%Y"),
            text_size=13, label_style=ft.TextStyle(size=12, color="#64748B"),
            width=145, height=48, filled=True, fill_color="#F1F5F9",
            border=ft.InputBorder.NONE, border_radius=14,
        )
        self.sched_date_to_input = ft.TextField(
            label="По дату", hint_text="ДД.ММ.ГГГГ",
            value=(datetime.today() + timedelta(days=7)).strftime("%d.%m.%Y"),
            text_size=13, label_style=ft.TextStyle(size=12, color="#64748B"),
            width=145, height=48, filled=True, fill_color="#F1F5F9",
            border=ft.InputBorder.NONE, border_radius=14,
        )
        self.sched_host_filter = ft.Dropdown(
            label="Кто проведет", value="Все ведущие",
            text_size=13, label_style=ft.TextStyle(size=12, color="#64748B"),
            width=200, height=48, filled=True, fill_color="#F1F5F9",
            border=ft.InputBorder.NONE, border_radius=14,
            options=[ft.dropdown.Option("Все ведущие")] + [ft.dropdown.Option(n) for n in self.account_names],
        )
        self.sched_creator_filter = ft.Dropdown(
            label="Кто записал", value="Все авторы",
            text_size=13, label_style=ft.TextStyle(size=12, color="#64748B"),
            width=200, height=48, filled=True, fill_color="#F1F5F9",
            border=ft.InputBorder.NONE, border_radius=14,
            options=[ft.dropdown.Option("Все авторы")] + [ft.dropdown.Option(n) for n in self.account_names],
        )
        self.schedule_list = ft.Column(spacing=12, scroll=ft.ScrollMode.AUTO)

    def load_schedule_list(self, e=None):
        if self._is_loading:
            return
        self._is_loading = True

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
                    self.schedule_list.controls.append(self.modal_mgr.render_meeting_card(item, is_registry=False))
        except Exception as err:
            self.schedule_list.controls.clear()
            self.schedule_list.controls.append(ft.Text(f"Ошибка чтения: {err}", color="#DC2626"))
        finally:
            self._is_loading = False
            self.page.update()

    def build_view(self) -> ft.Control:
        self.load_schedule_list()
        filter_card = ft.Container(
            bgcolor=ft.colors.WHITE, border_radius=20, padding=16, border=ft.border.all(1, "#E2E8F0"),
            content=ft.Row(
                controls=[
                    self.sched_date_from_input,
                    ft.IconButton(icon=ft.icons.CALENDAR_TODAY_OUTLINED, icon_size=18, tooltip="С даты", on_click=lambda e: self.sched_date_picker_from.pick_date()),
                    self.sched_date_to_input,
                    ft.IconButton(icon=ft.icons.CALENDAR_TODAY_OUTLINED, icon_size=18, tooltip="По дату", on_click=lambda e: self.sched_date_picker_to.pick_date()),
                    self.sched_host_filter,
                    self.sched_creator_filter,
                    ft.ElevatedButton("Показать", icon=ft.icons.SYNC_ROUNDED, bgcolor="#0C66E4", color=ft.colors.WHITE, height=48, style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=14)), on_click=self.load_schedule_list),
                    ft.OutlinedButton("Сегодня", height=48, style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=14)), on_click=lambda e: setattr(self.sched_date_from_input, "value", datetime.today().strftime("%d.%m.%Y")) or setattr(self.sched_date_to_input, "value", datetime.today().strftime("%d.%m.%Y")) or self.load_schedule_list()),
                    ft.OutlinedButton("На неделю", height=48, style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=14)), on_click=lambda e: setattr(self.sched_date_from_input, "value", datetime.today().strftime("%d.%m.%Y")) or setattr(self.sched_date_to_input, "value", (datetime.today() + timedelta(days=7)).strftime("%d.%m.%Y")) or self.load_schedule_list()),
                ],
                wrap=True, vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=10,
            ),
        )

        return ft.Container(
            padding=24,
            content=ft.Column(
                controls=[
                    ft.Text("Расписание встреч", size=24, weight=ft.FontWeight.BOLD, color="#0F172A"),
                    ft.Text("Просмотр запланированных встреч за произвольный период", size=13, color="#64748B"),
                    ft.Container(height=4),
                    filter_card,
                    self.schedule_list,
                ],
                spacing=16, scroll=ft.ScrollMode.AUTO,
            ),
            expand=True,
        )