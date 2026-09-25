import flet as ft
from apps.calculator.repair_sheets import load_repair_settings


class RepairRoomsCalculatorView(ft.UserControl):
    def __init__(self):
        super().__init__()
        self.settings = load_repair_settings(force_reload=True)

        self.state_options = [
            ("state_bare_concrete", "Голый бетон (база)"),
            ("state_bare_blocks", "Бетон с пер. в 1 блок (+5%)"),
            ("state_wb_no_demo", "Вайтбокс без демонтажа (база)"),
            ("state_wb_demo", "Вайтбокс с демонтажем (+20%)"),
            ("state_builder_finish", "Отделка от застройщика (+25%)"),
            ("state_secondary_demo", "Вторичка с демонтажем (+25%)"),
            ("state_secondary_done", "Вторичка (демонтаж выполнен) (+5%)"),
        ]

        self.rooms_data = []
        self.bathrooms_data = []

        self.eng_selection = {
            "el_extended": False,
            "el_lines": False,
            "el_low_current": False,
            "plumb_leak_protect": False,
            "sound_zips": False,
            "sound_frame": False,
        }

    def build(self):
        # 1. Верхние параметры
        self.area_input = ft.TextField(
            label="Площадь объекта (м²)",
            value="75",
            width=180,
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

        self.rooms_count_dropdown = ft.Dropdown(
            label="Кол-во комнат (без СУ)",
            value="2",
            width=180,
            height=48,
            text_size=13,
            label_style=ft.TextStyle(size=12, color="#64748B"),
            filled=True,
            fill_color="#F1F5F9",
            border=ft.InputBorder.NONE,
            border_radius=12,
            options=[ft.dropdown.Option(str(i)) for i in range(1, 7)],
            on_change=self.on_rooms_count_change,
        )

        self.baths_count_dropdown = ft.Dropdown(
            label="Кол-во санузлов",
            value="1",
            width=150,
            height=48,
            text_size=13,
            label_style=ft.TextStyle(size=12, color="#64748B"),
            filled=True,
            fill_color="#F1F5F9",
            border=ft.InputBorder.NONE,
            border_radius=12,
            options=[ft.dropdown.Option(str(i)) for i in range(1, 4)],
            on_change=self.on_baths_count_change,
        )

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
            label=ft.Text("Потолок > 3.0 м (+10%)", size=12),
            selected=False,
            on_select=self.on_ceil_high_toggle,
        )

        self.rooms_container = ft.Column(spacing=12)
        self.bathrooms_container = ft.Column(spacing=12)

        # Результаты в правой колонке
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

        # Базовая карточка
        self.card_base = self._card_wrap("Базовые параметры объекта", [
            ft.Row([self.area_input, self.repair_type_seg], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            ft.Container(height=4),
            ft.Row([self.rooms_count_dropdown, self.baths_count_dropdown, self.ceil_high_chip], vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=10),
            ft.Container(height=4),
            self.state_dropdown,
        ])

        # Общая инженерия
        self.eng_chips_row = ft.Row([
            ft.Chip(label=ft.Text("Расширенная электрика (100+ точек) (+10%)", size=12), data="el_extended", on_select=self.on_eng_chip_toggle),
            ft.Chip(label=ft.Text("Линии под подсветку / карнизы (+5%)", size=12), data="el_lines", on_select=self.on_eng_chip_toggle),
            ft.Chip(label=ft.Text("Слаботочка / щит роутера (+5%)", size=12), data="el_low_current", on_select=self.on_eng_chip_toggle),
            ft.Chip(label=ft.Text("Защита от протечек (+5%)", size=12), data="plumb_leak_protect", on_select=self.on_eng_chip_toggle),
            ft.Chip(label=ft.Text("Шумоизоляция ЗИПС (+10%)", size=12), data="sound_zips", on_select=self.on_eng_chip_toggle),
            ft.Chip(label=ft.Text("Шумоизоляция Каркасная (+15%)", size=12), data="sound_frame", on_select=self.on_eng_chip_toggle),
        ], wrap=True, spacing=8, run_spacing=8)

        self.card_eng = self._card_wrap("Общая инженерия и шумоизоляция", [
            self.eng_chips_row
        ])

        self.rebuild_room_cards()
        self.rebuild_bath_cards()

        left_column = ft.Column(
            scroll=ft.ScrollMode.AUTO,
            expand=True,
            spacing=16,
            controls=[
                self.card_base,
                self.card_eng,
                ft.Text("Отделка комнат (без санузлов)", size=16, weight=ft.FontWeight.BOLD, color="#1E293B"),
                self.rooms_container,
                ft.Text("Санузлы", size=16, weight=ft.FontWeight.BOLD, color="#1E293B"),
                self.bathrooms_container,
            ]
        )

        right_column = ft.Container(
            width=410,
            padding=20,
            bgcolor="#F8FAFC",
            border=ft.border.all(1, "#E2E8F0"),
            border_radius=18,
            content=ft.Column(
                spacing=12,
                controls=[
                    ft.Row([
                        ft.Text("Итоговая смета (Тест)", size=18, weight=ft.FontWeight.BOLD, color="#1E293B"),
                        self.selected_type_badge
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    self.total_cost_text,
                    self.rate_per_m2_text,
                    self.range_text,
                    ft.Divider(height=1, color="#E2E8F0"),
                    self.eng_part_text,
                    self.fin_part_text,
                    ft.Divider(height=1, color="#E2E8F0"),
                    ft.Text("Покомнатная спецификация:", size=14, weight=ft.FontWeight.W_600, color="#334155"),
                    ft.Container(content=self.summary_list, expand=True, height=270),
                    ft.ElevatedButton(
                        "Скопировать покомнатный расчет",
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
            padding=16,
            content=ft.Column(
                spacing=10,
                controls=[
                    ft.Text(title, size=15, weight=ft.FontWeight.BOLD, color="#1E293B"),
                    *controls
                ]
            )
        )

    def _get_items_by_cat(self, cat: str) -> list[tuple[str, str]]:
        raw_items = self.settings.get("raw_items", [])
        filtered = [it for it in raw_items if it.get("category") == cat]
        res = []
        for it in filtered:
            val = it.get("value", 0.0)
            pct = int(round(val * 100)) if val <= 1.0 else int(round(val))
            lbl = f"{it['title']} (+{pct}%)" if pct > 0 else it["title"]
            res.append((it["id"], lbl))
        return res

    def on_rooms_count_change(self, e):
        self.rebuild_room_cards()
        self.recalculate()
        self.update()

    def on_baths_count_change(self, e):
        self.rebuild_bath_cards()
        self.recalculate()
        self.update()

    def rebuild_room_cards(self):
        count = int(self.rooms_count_dropdown.value or 2)
        while len(self.rooms_data) < count:
            idx = len(self.rooms_data) + 1
            name = "Кухня-гостиная" if idx == 1 else f"Комната {idx}"
            self.rooms_data.append({
                "name": name,
                "floor": "base",
                "wall": "base",
                "ceil": "base",
                "door": "base",
                "plinth": "base",
            })
        self.rooms_data = self.rooms_data[:count]

        controls = []
        for i, room in enumerate(self.rooms_data):
            controls.append(self._render_single_room_card(i, room))
        self.rooms_container.controls = controls

    def rebuild_bath_cards(self):
        count = int(self.baths_count_dropdown.value or 1)
        while len(self.bathrooms_data) < count:
            idx = len(self.bathrooms_data) + 1
            name = "Основной санузел" if idx == 1 else f"Санузел {idx} (Гостевой)"
            self.bathrooms_data.append({
                "name": name,
                "tile": "base",
                "ceil": "base",
                "installation": False,
            })
        self.bathrooms_data = self.bathrooms_data[:count]

        controls = []
        for i, bath in enumerate(self.bathrooms_data):
            controls.append(self._render_single_bath_card(i, bath))
        self.bathrooms_container.controls = controls

    def _render_single_room_card(self, idx: int, data: dict) -> ft.Container:
        def on_chip(e, category, val):
            if e.data == "true":
                self.rooms_data[idx][category] = val
            else:
                self.rooms_data[idx][category] = "base"
            self.rebuild_room_cards()
            self.recalculate()
            self.update()

        floor_opts = [("base", "Ламинат (база)")] + self._get_items_by_cat("floor")
        wall_opts = [("base", "Обои (база)")] + self._get_items_by_cat("wall")
        ceil_opts = [("base", "Натяжной стандарт (база)")] + self._get_items_by_cat("ceil")

        floor_chips = [
            ft.Chip(label=ft.Text(label, size=11), selected=(data["floor"] == val), on_select=lambda e, v=val: on_chip(e, "floor", v))
            for val, label in floor_opts
        ]

        wall_chips = [
            ft.Chip(label=ft.Text(label, size=11), selected=(data["wall"] == val), on_select=lambda e, v=val: on_chip(e, "wall", v))
            for val, label in wall_opts
        ]

        ceil_chips = [
            ft.Chip(label=ft.Text(label, size=11), selected=(data["ceil"] == val), on_select=lambda e, v=val: on_chip(e, "ceil", v))
            for val, label in ceil_opts
        ]

        door_plinth = [
            ft.Chip(label=ft.Text("Скрытые двери Invisible (+5%)", size=11), selected=(data["door"] == "door_hidden"), on_select=lambda e: on_chip(e, "door", "door_hidden" if e.data == "true" else "base")),
            ft.Chip(label=ft.Text("Скрытый теневой плинтус (+5%)", size=11), selected=(data["plinth"] == "plinth_hidden"), on_select=lambda e: on_chip(e, "plinth", "plinth_hidden" if e.data == "true" else "base")),
        ]

        return ft.Container(
            bgcolor="#FFFFFF",
            border=ft.border.all(1, "#E2E8F0"),
            border_radius=14,
            padding=14,
            content=ft.Column(
                spacing=8,
                controls=[
                    ft.Row([
                        ft.Icon(ft.icons.MEETING_ROOM_ROUNDED, size=16, color="#0C66E4"),
                        ft.Text(data["name"], size=14, weight=ft.FontWeight.BOLD, color="#1E293B"),
                    ], spacing=6),
                    ft.Text("Полы:", size=11, color="#64748B", weight=ft.FontWeight.W_600),
                    ft.Row(floor_chips, wrap=True, spacing=6, run_spacing=6),
                    ft.Text("Стены:", size=11, color="#64748B", weight=ft.FontWeight.W_600),
                    ft.Row(wall_chips, wrap=True, spacing=6, run_spacing=6),
                    ft.Text("Потолок:", size=11, color="#64748B", weight=ft.FontWeight.W_600),
                    ft.Row(ceil_chips, wrap=True, spacing=6, run_spacing=6),
                    ft.Row(door_plinth, wrap=True, spacing=6, run_spacing=6),
                ]
            )
        )

    def _render_single_bath_card(self, idx: int, data: dict) -> ft.Container:
        def on_bath_chip(e, category, val):
            if e.data == "true":
                self.bathrooms_data[idx][category] = val
            else:
                self.bathrooms_data[idx][category] = "base"
            self.rebuild_bath_cards()
            self.recalculate()
            self.update()

        def on_inst_toggle(e):
            self.bathrooms_data[idx]["installation"] = not self.bathrooms_data[idx]["installation"]
            self.recalculate()
            self.update()

        tile_opts = [("base", "Формат 60х60 (база)")] + self._get_items_by_cat("tile")

        tile_chips = [
            ft.Chip(label=ft.Text(label, size=11), selected=(data["tile"] == val), on_select=lambda e, v=val: on_bath_chip(e, "tile", v))
            for val, label in tile_opts
        ]

        inst_chip = ft.Chip(
            label=ft.Text("Монтаж инсталляции (+5%)", size=11),
            selected=data["installation"],
            on_select=on_inst_toggle,
        )

        return ft.Container(
            bgcolor="#FFFFFF",
            border=ft.border.all(1, "#E2E8F0"),
            border_radius=14,
            padding=14,
            content=ft.Column(
                spacing=8,
                controls=[
                    ft.Row([
                        ft.Icon(ft.icons.BATHTUB_ROUNDED, size=16, color="#0C66E4"),
                        ft.Text(data["name"], size=14, weight=ft.FontWeight.BOLD, color="#1E293B"),
                    ], spacing=6),
                    ft.Text("Керамогранит:", size=11, color="#64748B", weight=ft.FontWeight.W_600),
                    ft.Row(tile_chips, wrap=True, spacing=6, run_spacing=6),
                    ft.Row([inst_chip], wrap=True, spacing=6),
                ]
            )
        )

    def on_eng_chip_toggle(self, e):
        chip = e.control
        key = chip.data
        chip.selected = not chip.selected
        self.eng_selection[key] = chip.selected
        self.recalculate()
        self.update()

    def on_ceil_high_toggle(self, e):
        self.ceil_high_chip.selected = not self.ceil_high_chip.selected
        self.recalculate()
        self.update()

    def on_type_change(self, e):
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

        base_eng = float(self.settings.get("base_engineering", 22162.0))
        base_fin = float(self.settings.get("base_finishing", 40931.0))
        coeffs = self.settings.get("coefficients", {})

        k_eng = 0.0
        k_fin = 0.0

        selected_type = list(self.repair_type_seg.selected)[0]

        # 1. Состояние объекта и потолок
        state_data = coeffs.get(self.state_dropdown.value, {})
        k_eng += state_data.get("value", 0.0)

        if self.ceil_high_chip.selected:
            c_val = coeffs.get("ceil_high", {}).get("value", 0.10)
            k_eng += c_val
            k_fin += c_val

        # 2. Общая инженерия
        for key, is_sel in self.eng_selection.items():
            if is_sel:
                c_val = coeffs.get(key, {}).get("value", 0.05)
                k_eng += c_val

        # 3. Покомнатная отделка
        num_rooms = max(len(self.rooms_data), 1)
        room_fin_k_sum = 0.0

        spec_lines = [
            f"Состояние: {state_data.get('title', 'Голый бетон')}",
            f"Высота потолков: {'> 3.0 м (+10%)' if self.ceil_high_chip.selected else 'Стандарт до 3.0 м (база)'}",
        ]

        for r in self.rooms_data:
            r_k = 0.0
            
            # Полы
            floor_val = r.get("floor", "base")
            if floor_val != "base":
                r_k += coeffs.get(floor_val, {}).get("value", 0.05)
                floor_title = coeffs.get(floor_val, {}).get("title", "Ламинат")
            else:
                floor_title = "Ламинат (база)"

            # Стены
            wall_val = r.get("wall", "base")
            if wall_val != "base":
                r_k += coeffs.get(wall_val, {}).get("value", 0.05)
                wall_title = coeffs.get(wall_val, {}).get("title", "Обои")
            else:
                wall_title = "Обои (база)"

            # Потолок
            ceil_val = r.get("ceil", "base")
            if ceil_val != "base":
                r_k += coeffs.get(ceil_val, {}).get("value", 0.05)
                ceil_title = coeffs.get(ceil_val, {}).get("title", "Натяжной стандарт")
            else:
                ceil_title = "Натяжной стандарт (база)"

            # Двери и плинтуса
            door_val = r.get("door", "base")
            if door_val == "door_hidden":
                r_k += coeffs.get("door_hidden", {}).get("value", 0.05)
                door_title = "Скрытые Invisible"
            else:
                door_title = "Обычные распашные (база)"

            plinth_val = r.get("plinth", "base")
            if plinth_val == "plinth_hidden":
                r_k += coeffs.get("plinth_hidden", {}).get("value", 0.05)
                plinth_title = "Скрытый теневой"
            else:
                plinth_title = "Стандартный накладной (база)"

            room_fin_k_sum += r_k
            spec_lines.append(
                f"• {r['name']}: {floor_title}, {wall_title}, {ceil_title}, {door_title}, {plinth_title}"
            )

        avg_room_k = room_fin_k_sum / num_rooms
        k_fin += avg_room_k

        # 4. Санузлы
        num_baths = max(len(self.bathrooms_data), 1)
        bath_k_sum = 0.0
        for b in self.bathrooms_data:
            tile_key = b.get("tile", "base")
            if tile_key != "base":
                bath_k_sum += coeffs.get(tile_key, {}).get("value", 0.05)
                tile_title = coeffs.get(tile_key, {}).get("title", "Керамогранит")
            else:
                tile_title = "Керамогранит 60х60 (база)"

            inst_str = "Инсталляция" if b.get("installation") else "Без инсталляции (база)"
            if b.get("installation"):
                k_eng += 0.05 / num_baths

            spec_lines.append(f"• {b['name']}: {tile_title}, {inst_str}")

        k_fin += (bath_k_sum / num_baths) * 0.3

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

        self.summary_list.controls = [
            ft.Text(item, size=13, color="#334155") for item in spec_lines
        ]

    def copy_summary_to_clipboard(self, e):
        sel = list(self.repair_type_seg.selected)[0]
        type_str = "Комплекс (Инженерия + Отделка)"
        if sel == "engineering":
            type_str = "Инженерный ремонт"
        elif sel == "finishing":
            type_str = "Отделочные работы"

        text = (
            f"📊 ПОКОМНАТНЫЙ РАСЧЕТ РЕМОНТА\n"
            f"Тип: {type_str}\n"
            f"Площадь: {self.area_input.value} м²\n"
            f"Ставка: {self.rate_per_m2_text.value}\n"
            f"Итоговая смета: {self.total_cost_text.value}\n"
            f"{self.range_text.value}\n\n"
            f"Спецификация по помещениям:\n" + "\n".join([c.value for c in self.summary_list.controls])
        )
        e.page.set_clipboard(text)
        e.page.show_snack_bar(ft.SnackBar(ft.Text("Покомнатный расчет скопирован!"), duration=2000))

    def refresh_settings(self, e):
        self.settings = load_repair_settings(force_reload=True)
        self.rebuild_room_cards()
        self.rebuild_bath_cards()
        self.recalculate()
        self.update()
        e.page.show_snack_bar(ft.SnackBar(ft.Text("Тарифы обновлены из Google Таблицы!"), duration=2000))