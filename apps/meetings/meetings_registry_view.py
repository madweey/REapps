from datetime import datetime, timedelta
import flet as ft
from apps.core.sheets import get_all_meetings
from apps.meetings.meetings_common import parse_date_safely, MeetingsModalManager


class MeetingsRegistryView:
    def __init__(self, page: ft.Page, account_names: list[str], modal_mgr: MeetingsModalManager):
        self.page = page
        self.account_names = account_names
        self.modal_mgr = modal_mgr
        self.registry_mode = {"all_time": False}
        self._is_loading = False

        self._build_controls()

    def _build_controls(self):
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
        for dp in (self.reg_date_picker_from, self.reg_date_picker_to):
            if dp not in self.page.overlay:
                self.page.overlay.append(dp)

        self.reg_date_from_input = ft.TextField(
            label="С даты", hint_text="ДД.ММ.ГГГГ",
            value=datetime.today().strftime("%d.%m.%Y"),
            text_size=13, label_style=ft.TextStyle(size=12, color="#64748B"),
            width=145, height=48, filled=True, fill_color="#F1F5F9",
            border=ft.InputBorder.NONE, border_radius=14,
        )
        self.reg_date_to_input = ft.TextField(
            label="По дату", hint_text="ДД.ММ.ГГГГ",
            value=(datetime.today() + timedelta(days=7)).strftime("%d.%m.%Y"),
            text_size=13, label_style=ft.TextStyle(size=12, color="#64748B"),
            width=145, height=48, filled=True, fill_color="#F1F5F9",
            border=ft.InputBorder.NONE, border_radius=14,
        )
        self.reg_status_filter = ft.Dropdown(
            label="Статус встречи", value="Все статусы",
            text_size=13, label_style=ft.TextStyle(size=12, color="#64748B"),
            width=230, height=48, filled=True, fill_color="#F1F5F9",
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
            width=200, height=48, filled=True, fill_color="#F1F5F9",
            border=ft.InputBorder.NONE, border_radius=14,
            options=[ft.dropdown.Option("Все ведущие")] + [ft.dropdown.Option(n) for n in self.account_names],
        )
        self.reg_creator_filter = ft.Dropdown(
            label="Кто записал", value="Все авторы",
            text_size=13, label_style=ft.TextStyle(size=12, color="#64748B"),
            width=200, height=48, filled=True, fill_color="#F1F5F9",
            border=ft.InputBorder.NONE, border_radius=14,
            options=[ft.dropdown.Option("Все авторы")] + [ft.dropdown.Option(n) for n in self.account_names],
        )
        self.registry_list = ft.Column(spacing=12, scroll=ft.ScrollMode.AUTO)

    def load_registry_list(self, e=None):
        if self._is_loading:
            return
        self._is_loading = True

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
                    self.registry_list.controls.append(self.modal_mgr.render_meeting_card(item, is_registry=True))
        except Exception as err:
            self.registry_list.controls.clear()
            self.registry_list.controls.append(ft.Text(f"Ошибка фильтрации: {err}", color="#DC2626"))
        finally:
            self._is_loading = False
            self.page.update()

    def build_view(self) -> ft.Control:
        self.load_registry_list()
        filter_card = ft.Container(
            bgcolor=ft.colors.WHITE, border_radius=20, padding=16, border=ft.border.all(1, "#E2E8F0"),
            content=ft.Row(
                controls=[
                    self.reg_date_from_input,
                    ft.IconButton(icon=ft.icons.CALENDAR_TODAY_OUTLINED, icon_size=18, tooltip="С даты", on_click=lambda e: self.reg_date_picker_from.pick_date()),
                    self.reg_date_to_input,
                    ft.IconButton(icon=ft.icons.CALENDAR_TODAY_OUTLINED, icon_size=18, tooltip="По дату", on_click=lambda e: self.reg_date_picker_to.pick_date()),
                    self.reg_status_filter,
                    self.reg_host_filter,
                    self.reg_creator_filter,
                    ft.ElevatedButton("Фильтр", icon=ft.icons.FILTER_ALT_OUTLINED, bgcolor="#0C66E4", color=ft.colors.WHITE, height=48, style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=14)), on_click=lambda e: setattr(self.registry_mode, "all_time", False) or self.load_registry_list()),
                    ft.OutlinedButton("Все встречи", icon=ft.icons.ALL_INCLUSIVE_ROUNDED, height=48, style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=14)), on_click=lambda e: setattr(self.registry_mode, "all_time", True) or self.load_registry_list()),
                ],
                wrap=True, vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=10,
            ),
        )

        return ft.Container(
            padding=24,
            content=ft.Column(
                controls=[
                    ft.Text("Реестр встреч", size=24, weight=ft.FontWeight.BOLD, color="#0F172A"),
                    ft.Text("Полная база и фильтрация всех проведённых и отменённых встреч", size=13, color="#64748B"),
                    ft.Container(height=4),
                    filter_card,
                    self.registry_list,
                ],
                spacing=16, scroll=ft.ScrollMode.AUTO,
            ),
            expand=True,
        )