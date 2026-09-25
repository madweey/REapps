import flet as ft
from apps.calculator.repair_sheets import (
    load_repair_settings,
    add_repair_work,
    delete_repair_work,
)


class RepairSettingsView(ft.UserControl):
    def __init__(self, page: ft.Page):
        super().__init__()
        self.page = page
        self.category_filter = "all"
        self.item_to_delete = None

        self.categories_map = [
            ("all", "Все разделы"),
            ("floor", "Полы"),
            ("wall", "Стены"),
            ("ceil", "Потолки"),
            ("tile", "Санузел (Керамогранит)"),
            ("door", "Двери"),
            ("plinth", "Плинтуса"),
            ("eng", "Инженерия"),
            ("sound", "Шумоизоляция"),
            ("state", "Состояние объекта"),
        ]

    def build(self):
        # 1. Поля формы добавления
        self.title_input = ft.TextField(
            label="Наименование работы / материала",
            hint_text="Например: Пробковое покрытие или Обои под покраску",
            expand=True,
            height=48,
            text_size=13,
            label_style=ft.TextStyle(size=12, color="#64748B"),
            filled=True,
            fill_color="#F1F5F9",
            border=ft.InputBorder.NONE,
            border_radius=12,
        )

        self.category_dd = ft.Dropdown(
            label="Категория (Помещение/Узел)",
            value="floor",
            width=230,
            height=48,
            text_size=13,
            label_style=ft.TextStyle(size=12, color="#64748B"),
            filled=True,
            fill_color="#F1F5F9",
            border=ft.InputBorder.NONE,
            border_radius=12,
            options=[
                ft.dropdown.Option("floor", "Полы"),
                ft.dropdown.Option("wall", "Стены"),
                ft.dropdown.Option("ceil", "Потолки"),
                ft.dropdown.Option("tile", "Санузел"),
                ft.dropdown.Option("door", "Двери"),
                ft.dropdown.Option("plinth", "Плинтуса"),
                ft.dropdown.Option("eng", "Инженерия"),
                ft.dropdown.Option("sound", "Шумоизоляция"),
                ft.dropdown.Option("state", "Состояние объекта"),
            ],
        )

        self.coeff_input = ft.TextField(
            label="Надбавка (%)",
            hint_text="5, 10, 15",
            value="5",
            width=130,
            height=48,
            text_size=13,
            label_style=ft.TextStyle(size=12, color="#64748B"),
            filled=True,
            fill_color="#F1F5F9",
            border=ft.InputBorder.NONE,
            border_radius=12,
            keyboard_type=ft.KeyboardType.NUMBER,
        )

        self.base_dd = ft.Dropdown(
            label="База начисления",
            value="Отделка",
            width=170,
            height=48,
            text_size=13,
            label_style=ft.TextStyle(size=12, color="#64748B"),
            filled=True,
            fill_color="#F1F5F9",
            border=ft.InputBorder.NONE,
            border_radius=12,
            options=[
                ft.dropdown.Option("Отделка"),
                ft.dropdown.Option("Инженерия"),
                ft.dropdown.Option("Все"),
            ],
        )

        self.btn_add = ft.ElevatedButton(
            "Добавить работу",
            icon=ft.icons.ADD_TASK_ROUNDED,
            bgcolor="#0C66E4",
            color=ft.colors.WHITE,
            height=48,
            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=12)),
            on_click=self.on_add_click,
        )

        self.status_msg = ft.Text("", size=12, weight=ft.FontWeight.W_500)

        # 2. Карточка создания новой работы
        create_card = ft.Container(
            bgcolor=ft.colors.WHITE,
            border=ft.border.all(1, "#E2E8F0"),
            border_radius=18,
            padding=20,
            content=ft.Column(
                spacing=12,
                controls=[
                    ft.Row([
                        ft.Icon(ft.icons.POST_ADD_ROUNDED, color="#0C66E4", size=20),
                        ft.Text("Добавление работы / материала в справочник", size=15, weight=ft.FontWeight.BOLD, color="#1E293B"),
                    ], spacing=8),
                    ft.Text("Ключ ID сгенерируется автоматически. Запись мгновенно попадёт на лист «Настройка_Ремонт».", size=12, color="#64748B"),
                    ft.Row([self.title_input, self.category_dd], spacing=10),
                    ft.Row([self.coeff_input, self.base_dd, self.btn_add], spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                    self.status_msg,
                ]
            )
        )

        # 3. Фильтры категорий (чипсы)
        filter_chips = []
        for cat_key, cat_label in self.categories_map:
            chip = ft.Chip(
                label=ft.Text(cat_label, size=12),
                selected=(self.category_filter == cat_key),
                data=cat_key,
                on_select=self.on_filter_chip_select,
            )
            filter_chips.append(chip)

        self.filter_row = ft.Row(filter_chips, wrap=True, spacing=6, run_spacing=6)

        # 4. Список существующих работ
        self.items_list = ft.Column(spacing=8)

        list_card = ft.Container(
            bgcolor=ft.colors.WHITE,
            border=ft.border.all(1, "#E2E8F0"),
            border_radius=18,
            padding=20,
            content=ft.Column(
                spacing=12,
                controls=[
                    ft.Row([
                        ft.Text("Текущие позиции и коэффициенты", size=15, weight=ft.FontWeight.BOLD, color="#1E293B"),
                        ft.IconButton(
                            icon=ft.icons.REFRESH_ROUNDED,
                            icon_size=20,
                            tooltip="Обновить из Google Таблицы",
                            icon_color="#0C66E4",
                            on_click=self.refresh_table,
                        ),
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    self.filter_row,
                    ft.Divider(height=1, color="#E2E8F0"),
                    self.items_list,
                ]
            )
        )

        # Диалог подтверждения удаления
        self.delete_confirm_text = ft.Text("", size=13)
        self.delete_dialog = ft.AlertDialog(
            title=ft.Row([ft.Icon(ft.icons.DELETE_OUTLINE_ROUNDED, color="#EF4444"), ft.Text("Удаление работы", size=16, weight=ft.FontWeight.BOLD)]),
            content=self.delete_confirm_text,
            actions=[
                ft.TextButton("Отмена", on_click=lambda e: setattr(self.delete_dialog, "open", False) or self.page.update()),
                ft.ElevatedButton("Удалить", bgcolor="#EF4444", color=ft.colors.WHITE, on_click=self.on_confirm_delete),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )

        if self.delete_dialog not in self.page.overlay:
            self.page.overlay.append(self.delete_dialog)

        self.load_data()

        return ft.Container(
            padding=24,
            content=ft.Column(
                spacing=16,
                scroll=ft.ScrollMode.AUTO,
                controls=[
                    ft.Text("База работ ремонта", size=24, weight=ft.FontWeight.BOLD, color="#0F172A"),
                    ft.Text("Управление расценками, материалами и коэффициентами калькулятора", size=13, color="#64748B"),
                    ft.Container(height=4),
                    create_card,
                    list_card,
                ]
            )
        )

    def on_filter_chip_select(self, e):
        chip = e.control
        self.category_filter = chip.data
        for c in self.filter_row.controls:
            c.selected = (c.data == self.category_filter)
        self.load_data()
        self.update()

    def on_add_click(self, e):
        title = self.title_input.value.strip()
        if not title:
            self.status_msg.value = "Введите название работы / материала!"
            self.status_msg.color = "#DC2626"
            self.update()
            return

        try:
            coeff_val = float(str(self.coeff_input.value).replace(",", ".").strip())
        except ValueError:
            coeff_val = 0.0

        cat = self.category_dd.value
        base_t = self.base_dd.value

        self.btn_add.disabled = True
        self.status_msg.value = "Сохранение в Google Таблицу..."
        self.status_msg.color = "#0C66E4"
        self.update()

        ok = add_repair_work(cat, title, coeff_val, base_t)
        self.btn_add.disabled = False

        if ok:
            self.title_input.value = ""
            self.status_msg.value = f"Позиция «{title}» успешно добавлена в таблицу!"
            self.status_msg.color = "#15803D"
            self.load_data()
        else:
            self.status_msg.value = "Ошибка при сохранении в Google Таблицу!"
            self.status_msg.color = "#DC2626"

        self.update()

    def open_delete_modal(self, item: dict):
        self.item_to_delete = item
        self.delete_confirm_text.value = f"Удалить позицию «{item['title']}» (строка {item['row_idx']}) из таблицы?"
        self.delete_dialog.open = True
        self.page.update()

    def on_confirm_delete(self, e):
        if self.item_to_delete:
            delete_repair_work(self.item_to_delete["row_idx"])
            self.delete_dialog.open = False
            self.item_to_delete = None
            self.load_data()
            self.page.update()

    def refresh_table(self, e):
        load_repair_settings(force_reload=True)
        self.load_data()
        self.update()
        self.page.show_snack_bar(ft.SnackBar(ft.Text("Справочник обновлен!"), duration=2000))

    def load_data(self):
        settings = load_repair_settings()
        items = settings.get("raw_items", [])

        if self.category_filter != "all":
            items = [it for it in items if it.get("category") == self.category_filter]

        rows = []
        for it in items:
            pct_val = int(round(it["value"] * 100)) if it["value"] <= 1.0 else int(round(it["value"]))
            sign_str = f"+{pct_val}%" if pct_val > 0 else f"{pct_val}%"
            badge_bg = "#EBF3FC" if pct_val > 0 else "#F1F5F9"
            badge_fg = "#0C66E4" if pct_val > 0 else "#64748B"

            row_container = ft.Container(
                bgcolor="#F8FAFC",
                border=ft.border.all(1, "#E2E8F0"),
                border_radius=12,
                padding=ft.padding.symmetric(horizontal=14, vertical=10),
                content=ft.Row(
                    controls=[
                        ft.Column([
                            ft.Text(it["title"], size=13, weight=ft.FontWeight.W_600, color="#1E293B"),
                            ft.Row([
                                ft.Text(f"ID: {it['id']}", size=11, color="#94A3B8"),
                                ft.Text(f"• База: {it['base']}", size=11, color="#64748B"),
                                ft.Text(f"• Строка: {it['row_idx']}", size=11, color="#94A3B8"),
                            ], spacing=6),
                        ], spacing=3, expand=True),
                        ft.Container(
                            content=ft.Text(sign_str, size=12, weight=ft.FontWeight.BOLD, color=badge_fg),
                            bgcolor=badge_bg,
                            padding=ft.padding.symmetric(horizontal=8, vertical=4),
                            border_radius=8,
                        ),
                        ft.IconButton(
                            icon=ft.icons.DELETE_OUTLINE_ROUNDED,
                            icon_color="#EF4444",
                            icon_size=18,
                            tooltip="Удалить из таблицы",
                            on_click=lambda e, item=it: self.open_delete_modal(item),
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                )
            )
            rows.append(row_container)

        if not rows:
            self.items_list.controls = [
                ft.Container(
                    padding=20,
                    alignment=ft.alignment.center,
                    content=ft.Text("В этом разделе пока нет добавленных позиций", size=13, color="#94A3B8", italic=True)
                )
            ]
        else:
            self.items_list.controls = rows