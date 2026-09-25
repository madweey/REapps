import flet as ft
from apps.calculator.repair_sheets import load_repair_settings


class RepairCalculatorView(ft.UserControl):
    def __init__(self):
        super().__init__()
        self.settings = load_repair_settings()

        self.state_options = [
            ("state_bare_concrete", "Голый бетон (база)"),
            ("state_bare_blocks", "Бетон с пер. в 1 блок (+5%)"),
            ("state_wb_no_demo", "Вайтбокс без демонтажа (база)"),
            ("state_wb_demo", "Вайтбокс с демонтажем (+20%)"),
            ("state_builder_finish", "Отделка от застройщика (+25%)"),
            ("state_secondary_demo", "Вторичка с демонтажем (+25%)"),
            ("state_secondary_done", "Вторичка (демонтаж выполнен) (+5%)"),
        ]

        # Одиночный выбор (Choice)
        self.chips_selection = {
            "floor": "base",
            "wall": "base",
            "ceil": "base",
            "tile": "base",
            "door": "base",
            "plinth": "base",
            "sound": "base",
        }

        # Множественный выбор инженерных опций
        self.eng_selection = {
            "el_extended": False,
            "el_lines": False,
            "el_low_current": False,
            "plumb_leak_protect": False,
            "plumb_installation": False,
        }

    def build(self):
        # 1. Поле ввода площади
        self.area_input = ft.TextField(
            label="Площадь объекта (м²)",
            value="75",
            width=190,
            height=48,
            text_size=13,
            label_style=ft.TextStyle(size=12, color="#64748B"),
            filled=True,
            fill_color="#F1F5F9",
            border=ft.InputBorder.NONE,
            border_radius=12,
            keyboard_type=ft.KeyboardType.NUMBER,
            on_change=self.on_param_change,
        )

        # 2. Сегментированный переключатель типа ремонта (One UI стиль)
        self.repair_type_seg = ft.SegmentedButton(
            selected={"complex"},
            allow_multiple_selection=False,
            on_change=self.on_type_change,
            segments=[
                ft.Segment(value="complex", label=ft.Text("Комплекс", size=12)),
                ft.Segment(value="engineering", label=ft.Text("Инженерный", size=12)),
                ft.Segment(value="finishing", label=ft.Text("Отделочные", size=12)),
            ],
        )

        # 3. Состояние объекта и высота потолка
        self.state_dropdown = ft.Dropdown(
            label="Состояние объекта",
            value="state_bare_concrete",
            expand=True,
            height=48,
            text_size=13,
            label_style=ft.TextStyle(size=12, color="#64748B"),
            filled=True,
            fill_color="#F1F5F9",
            border=ft.InputBorder.NONE,
            border_radius=12,
            options=[ft.dropdown.Option(k, v) for k, v in self.state_options],
            on_change=self.on_param_change,
        )

        self.ceil_high_chip = ft.Chip(
            label=ft.Text("Высота потолка > 3.0 м (+10%)", size=12),
            selected=False,
            on_select=self.on_ceil_high_toggle,
        )

        # 4. Правая колонка с результатами
        self.total_cost_text = ft.Text("0 ₽", size=30, weight=ft.FontWeight.BOLD, color="#0C66E4")
        self.rate_per_m2_text = ft.Text("0 ₽/м²", size=18, weight=ft.FontWeight.W_600, color="#1E293B")
        self.range_text = ft.Text("Ориентир ~70%: от 0 до 0 ₽", size=13, color="#64748B")
        self.eng_part_text = ft.Text("Инженерный блок: 0 ₽", size=13, color="#475569")
        self.fin_part_text = ft.Text("Отделочный блок: 0 ₽", size=13, color="#475569")
        self.selected_type_badge = ft.Container(
            content=ft.Text("Тип: Комплекс", size=11, weight=ft.FontWeight.BOLD, color="#0C66E4"),
            bgcolor="#EBF3FC",
            padding=ft.padding.symmetric(horizontal=10, vertical=5),
            border_radius=8,
        )
        self.summary_list = ft.ListView(expand=True, spacing=6, auto_scroll=False)

        # Плитки инженерии сверх базы (вместо наползающих чекбоксов)
        self.eng_chips_row = self._build_eng_multi_chips([
            ("el_extended", "Пакет расширенной электрики (100+ точек, щит) (+10%)"),
            ("el_lines", "Линии под подсветку / электрокарнизы (+5%)"),
            ("el_low_current", "Вывод слаботочки / щит роутера (+5%)"),
            ("plumb_leak_protect", "Защита от протечек (Neptun/Аквасторож) (+5%)"),
            ("plumb_installation", "Монтаж инсталляции (+5%)"),
        ])

        # Чипсы чистовой отделки
        self.floor_chips = self._build_choice_row("floor", [
            ("base", "Ламинат (база)"),
            ("floor_quartz", "Кварцвинил (+5%)"),
            ("floor_eng_board", "Инж. доска (+10%)"),
            ("floor_parquet", "Паркет (+15%)"),
            ("floor_granite_part", "Керамогранит часть (+5%)"),
        ])

        self.wall_chips = self._build_choice_row("wall", [
            ("base", "Обои (база)"),
            ("wall_wallpaper_paint", "Обои под покр. (+5%)"),
            ("wall_paint", "Под покраску (+15%)"),
            ("wall_decor", "Декоративка (+15%)"),
            ("wall_microcement", "Микроцемент (+20%)"),
        ])

        self.ceil_chips = self._build_choice_row("ceil", [
            ("base", "Натяжной стандарт (база)"),
            ("ceil_shadow", "Теневой профиль (+5%)"),
            ("ceil_tracks", "С треками (+5%)"),
            ("ceil_tracks_shadow", "Треки + Теневой (+10%)"),
            ("ceil_gkl", "ГКЛ в 2 слоя (+20%)"),
        ])

        self.tile_chips = self._build_choice_row("tile", [
            ("base", "Формат 60х60 (база)"),
            ("tile_bath_60x120", "Формат 60х120 (+5%)"),
            ("tile_bath_120x120", "Формат 120х120 (+10%)"),
            ("tile_bath_120x200", "Крупноформат 120х200 (+15%)"),
        ])

        self.door_chips = self._build_choice_row("door", [
            ("base", "Обычные распашные (база)"),
            ("door_hidden", "Скрытые Invisible (+5%)"),
        ])

        self.plinth_chips = self._build_choice_row("plinth", [
            ("base", "Стандартные накладные (база)"),
            ("plinth_hidden", "Скрытые / теневые (+5%)"),
        ])

        self.sound_chips = self._build_choice_row("sound", [
            ("base", "Не требуется (база)"),
            ("sound_zips", "ЗИПС (+10%)"),
            ("sound_frame", "Каркасная (+15%)"),
        ])

        self.moldings_chip = ft.Chip(
            label=ft.Text("Молдинги / лепнина (+5%)", size=12),
            selected=False,
            on_select=self.on_moldings_toggle,
        )

        # Контейнеры-карточки (Мягкий стиль One UI)
        self.card_base = self._card_wrap("Базовые параметры объекта", [
            ft.Row([self.area_input, self.repair_type_seg], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            ft.Container(height=4),
            ft.Row([self.state_dropdown, self.ceil_high_chip], vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=12),
        ])

        self.card_eng = self._card_wrap("Инженерия сверх базы", [
            self.eng_chips_row
        ])

        self.card_finishing = self._card_wrap("Чистовые покрытия", [
            ft.Text("Полы:", size=12, weight=ft.FontWeight.W_600, color="#64748B"),
            self.floor_chips,
            ft.Container(height=4),
            ft.Text("Стены:", size=12, weight=ft.FontWeight.W_600, color="#64748B"),
            self.wall_chips,
            ft.Container(height=4),
            ft.Text("Потолок:", size=12, weight=ft.FontWeight.W_600, color="#64748B"),
            self.ceil_chips,
        ])

        self.card_details = self._card_wrap("Узлы, санузел и шумоизоляция", [
            ft.Text("Керамогранит в санузле:", size=12, weight=ft.FontWeight.W_600, color="#64748B"),
            self.tile_chips,
            ft.Container(height=4),
            ft.Text("Двери:", size=12, weight=ft.FontWeight.W_600, color="#64748B"),
            self.door_chips,
            ft.Container(height=4),
            ft.Text("Плинтуса и декор:", size=12, weight=ft.FontWeight.W_600, color="#64748B"),
            ft.Row([self.plinth_chips, self.moldings_chip], wrap=True, spacing=8),
            ft.Container(height=4),
            ft.Text("Шумоизоляция:", size=12, weight=ft.FontWeight.W_600, color="#64748B"),
            self.sound_chips,
        ])

        left_column = ft.Column(
            scroll=ft.ScrollMode.AUTO,
            expand=True,
            spacing=16,
            controls=[
                self.card_base,
                self.card_eng,
                self.card_finishing,
                self.card_details,
            ]
        )

        right_column = ft.Container(
            width=390,
            padding=20,
            bgcolor="#F8FAFC",
            border=ft.border.all(1, "#E2E8F0"),
            border_radius=18,
            content=ft.Column(
                spacing=12,
                controls=[
                    ft.Row([
                        ft.Text("Итоговая смета", size=18, weight=ft.FontWeight.BOLD, color="#1E293B"),
                        self.selected_type_badge
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    self.total_cost_text,
                    self.rate_per_m2_text,
                    self.range_text,
                    ft.Divider(height=1, color="#E2E8F0"),
                    self.eng_part_text,
                    self.fin_part_text,
                    ft.Divider(height=1, color="#E2E8F0"),
                    ft.Text("Спецификация комплектации:", size=14, weight=ft.FontWeight.W_600, color="#334155"),
                    ft.Container(content=self.summary_list, expand=True, height=270),
                    ft.ElevatedButton(
                        "Скопировать расчет",
                        icon=ft.icons.COPY_ALL_ROUNDED,
                        bgcolor="#0C66E4",
                        color="#FFFFFF",
                        height=44,
                        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=12)),
                        on_click=self.copy_summary_to_clipboard
                    ),
                    ft.OutlinedButton(
                        "Обновить тарифы из Таблицы",
                        icon=ft.icons.REFRESH_ROUNDED,
                        height=44,
                        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=12)),
                        on_click=self.refresh_settings
                    )
                ]
            )
        )

        self.recalculate()
        return ft.Container(
            padding=ft.padding.only(left=20, top=14, right=20, bottom=20),
            expand=True,
            content=ft.Row([left_column, right_column], expand=True, spacing=18)
        )

    def _card_wrap(self, title: str, controls: list) -> ft.Container:
        return ft.Container(
            bgcolor="#FFFFFF",
            border=ft.border.all(1, "#E2E8F0"),
            border_radius=18,
            padding=18,
            content=ft.Column(
                spacing=12,
                controls=[
                    ft.Text(title, size=15, weight=ft.FontWeight.BOLD, color="#1E293B"),
                    *controls
                ]
            )
        )

    def _build_eng_multi_chips(self, options: list) -> ft.Row:
        row_chips = []
        for key, label in options:
            chip = ft.Chip(
                label=ft.Text(label, size=12),
                selected=self.eng_selection.get(key, False),
                data=key,
                on_select=self.on_eng_chip_toggle,
            )
            row_chips.append(chip)
        return ft.Row(row_chips, wrap=True, spacing=8, run_spacing=8)

    def on_eng_chip_toggle(self, e):
        chip = e.control
        key = chip.data
        chip.selected = not chip.selected
        self.eng_selection[key] = chip.selected
        self.recalculate()
        self.update()

    def _build_choice_row(self, group_name: str, options: list) -> ft.Row:
        row_chips = []
        for val, label in options:
            chip = ft.Chip(
                label=ft.Text(label, size=12),
                selected=(val == self.chips_selection[group_name]),
                data={"group": group_name, "value": val},
                on_select=self.on_chip_select,
            )
            row_chips.append(chip)
        return ft.Row(row_chips, wrap=True, spacing=6, run_spacing=6)

    def on_chip_select(self, e):
        chip = e.control
        group = chip.data["group"]
        val = chip.data["value"]
        if e.data == "true":
            self.chips_selection[group] = val
        else:
            self.chips_selection[group] = "base"

        target_row = getattr(self, f"{group}_chips", None)
        if target_row:
            for c in target_row.controls:
                c.selected = (c.data["value"] == self.chips_selection[group])

        self.recalculate()
        self.update()

    def on_ceil_high_toggle(self, e):
        self.ceil_high_chip.selected = not self.ceil_high_chip.selected
        self.recalculate()
        self.update()

    def on_moldings_toggle(self, e):
        self.moldings_chip.selected = not self.moldings_chip.selected
        self.recalculate()
        self.update()

    def on_type_change(self, e):
        sel = list(self.repair_type_seg.selected)[0]
        self.card_eng.visible = (sel in ("complex", "engineering"))
        self.card_finishing.visible = (sel in ("complex", "finishing"))
        self.card_details.visible = True
        self.recalculate()
        self.update()

    def on_param_change(self, e):
        self.recalculate()
        self.update()

    def recalculate(self):
        try:
            area = float(str(self.area_input.value).replace(",", ".").strip())
        except ValueError:
            area = 0.0

        base_eng = self.settings.get("base_engineering", 22162.0)
        base_fin = self.settings.get("base_finishing", 40931.0)
        coeffs = self.settings.get("coefficients", {})

        k_eng = 0.0
        k_fin = 0.0

        selected_type = list(self.repair_type_seg.selected)[0]

        # 1. Состояние объекта
        selected_state = self.state_dropdown.value
        state_data = coeffs.get(selected_state, {})
        k_eng += state_data.get("value", 0.0)
        state_title = state_data.get("title", "Голый бетон")

        # 2. Высота потолков
        if self.ceil_high_chip.selected:
            c_val = coeffs.get("ceil_high", {}).get("value", 0.10)
            k_eng += c_val
            k_fin += c_val

        # 3. Инженерия (мульти-чипсы)
        for key, is_sel in self.eng_selection.items():
            if is_sel:
                c_info = coeffs.get(key, {})
                c_val = c_info.get("value", 0.0)
                c_base = c_info.get("base", "Инженерия")
                if c_base == "Инженерия":
                    k_eng += c_val
                elif c_base == "Отделка":
                    k_fin += c_val
                elif c_base == "Все":
                    k_eng += c_val
                    k_fin += c_val

        # 4. Чипсы отделки
        for grp, key in self.chips_selection.items():
            if key != "base":
                c_info = coeffs.get(key, {})
                c_val = c_info.get("value", 0.0)
                c_base = c_info.get("base", "Отделка")
                if c_base == "Инженерия":
                    k_eng += c_val
                elif c_base == "Отделка":
                    k_fin += c_val
                elif c_base == "Все":
                    k_eng += c_val
                    k_fin += c_val

        # 5. Молдинги
        if self.moldings_chip.selected:
            k_fin += coeffs.get("moldings", {}).get("value", 0.05)

        rate_eng = base_eng * (1.0 + k_eng)
        rate_fin = base_fin * (1.0 + k_fin)

        total_eng = rate_eng * area
        total_fin = rate_fin * area

        if selected_type == "engineering":
            rate_active = rate_eng
            total_active = total_eng
            type_label = "Инженерный ремонт"
            self.eng_part_text.visible = True
            self.fin_part_text.visible = False
        elif selected_type == "finishing":
            rate_active = rate_fin
            total_active = total_fin
            type_label = "Отделочные работы"
            self.eng_part_text.visible = False
            self.fin_part_text.visible = True
        else:
            rate_active = rate_eng + rate_fin
            total_active = total_eng + total_fin
            type_label = "Комплекс (Инженерия + Отделка)"
            self.eng_part_text.visible = True
            self.fin_part_text.visible = True

        min_range = total_active * 0.85
        max_range = total_active * 1.15

        self.selected_type_badge.content.value = f"Тип: {type_label}"
        self.total_cost_text.value = f"{int(round(total_active)):,} ₽".replace(",", " ")
        self.rate_per_m2_text.value = f"{int(round(rate_active)):,} ₽/м²".replace(",", " ")
        self.range_text.value = f"Ориентир ~70%: от {int(round(min_range)):,} до {int(round(max_range)):,} ₽".replace(",", " ")
        self.eng_part_text.value = f"Инженерный блок: {int(round(total_eng)):,} ₽ ({int(round(rate_eng)):,} ₽/м²)"
        self.fin_part_text.value = f"Отделочный блок: {int(round(total_fin)):,} ₽ ({int(round(rate_fin)):,} ₽/м²)"

        spec_lines = []
        show_eng = selected_type in ("complex", "engineering")
        show_fin = selected_type in ("complex", "finishing")

        if show_eng:
            spec_lines.append(f"Состояние: {state_title}")
            spec_lines.append(f"Высота потолков: {'> 3.0 м (+10%)' if self.ceil_high_chip.selected else 'Стандарт до 3.0 м (база)'}")

            plumb_list = ["Коллекторная разводка (база)"]
            if self.eng_selection.get("plumb_leak_protect"):
                plumb_list.append("Защита от протечек")
            if self.eng_selection.get("plumb_installation"):
                plumb_list.append("Инсталляция")
            spec_lines.append(f"Сантехника: {', '.join(plumb_list)}")

            el_list = []
            if self.eng_selection.get("el_extended"):
                el_list.append("Расширенная (100+ точек)")
            else:
                el_list.append("Базовая электрика")
            if self.eng_selection.get("el_lines"):
                el_list.append("Линии карнизов/подсветки")
            if self.eng_selection.get("el_low_current"):
                el_list.append("Слаботочка/роутер")
            spec_lines.append(f"Электрика: {', '.join(el_list)}")

            sound_val = self.chips_selection.get("sound", "base")
            sound_title = "Не требуется (база)"
            if sound_val == "sound_zips":
                sound_title = "ЗИПС"
            elif sound_val == "sound_frame":
                sound_title = "Каркасная"
            spec_lines.append(f"Шумоизоляция: {sound_title}")

        if show_fin:
            floor_map = {
                "base": "Ламинат (база)",
                "floor_quartz": "Кварцвинил",
                "floor_eng_board": "Инженерная доска",
                "floor_parquet": "Паркет",
                "floor_granite_part": "Керамогранит (часть)",
            }
            spec_lines.append(f"Полы: {floor_map.get(self.chips_selection.get('floor'), 'Ламинат (база)')}")

            wall_map = {
                "base": "Обои (база)",
                "wall_wallpaper_paint": "Обои под покраску",
                "wall_paint": "Стена под покраску",
                "wall_decor": "Декоративная штукатурка",
                "wall_microcement": "Микроцемент",
            }
            spec_lines.append(f"Стены: {wall_map.get(self.chips_selection.get('wall'), 'Обои (база)')}")

            ceil_map = {
                "base": "Натяжной стандарт (база)",
                "ceil_shadow": "Теневой профиль",
                "ceil_tracks": "С треками",
                "ceil_tracks_shadow": "Треки + Теневой",
                "ceil_gkl": "ГКЛ в 2 слоя",
            }
            spec_lines.append(f"Потолок: {ceil_map.get(self.chips_selection.get('ceil'), 'Натяжной стандарт (база)')}")

            tile_map = {
                "base": "Формат 60х60 (база)",
                "tile_bath_60x120": "Формат 60х120",
                "tile_bath_120x120": "Формат 120х120",
                "tile_bath_120x200": "Крупный 120х200",
            }
            spec_lines.append(f"Керамогранит СУ: {tile_map.get(self.chips_selection.get('tile'), 'Формат 60х60 (база)')}")

            spec_lines.append(f"Двери: {'Скрытые Invisible' if self.chips_selection.get('door') == 'door_hidden' else 'Обычные распашные (база)'}")
            spec_lines.append(f"Плинтуса: {'Скрытые / теневые' if self.chips_selection.get('plinth') == 'plinth_hidden' else 'Стандартные накладные (база)'}")
            if self.moldings_chip.selected:
                spec_lines.append("Декор: Молдинги / лепнина")

        self.summary_list.controls = [
            ft.Text(f"• {item}", size=13, color="#334155") for item in spec_lines
        ]

    def copy_summary_to_clipboard(self, e):
        sel = list(self.repair_type_seg.selected)[0]
        type_str = "Комплекс (Инженерия + Отделка)"
        if sel == "engineering":
            type_str = "Инженерный ремонт"
        elif sel == "finishing":
            type_str = "Отделочные работы"

        text = (
            f"📊 ЭКСПРЕСС-ОЦЕНКА РЕМОНТА (точность ~70%)\n"
            f"Тип: {type_str}\n"
            f"Площадь: {self.area_input.value} м²\n"
            f"Ставка: {self.rate_per_m2_text.value}\n"
            f"Итоговая смета: {self.total_cost_text.value}\n"
            f"{self.range_text.value}\n\n"
            f"Спецификация:\n" + "\n".join([c.value for c in self.summary_list.controls])
        )
        e.page.set_clipboard(text)
        e.page.show_snack_bar(ft.SnackBar(ft.Text("Расчет скопирован в буфер обмена!"), duration=2000))

    def refresh_settings(self, e):
        self.settings = load_repair_settings(force_reload=True)
        self.recalculate()
        self.update()
        e.page.show_snack_bar(ft.SnackBar(ft.Text("Тарифы обновлены из Google Таблицы!"), duration=2000))