import flet as ft
from apps.calculator.repair_state import current_repair_state
from apps.calculator.repair_estimate_service import (
    load_base_rates_and_coefficients,
    generate_universal_estimate_presentation
)


class RepairRoomsCalculatorView(ft.UserControl):
    def __init__(self):
        super().__init__()
        self.settings = load_base_rates_and_coefficients()

        self.state_options = []
        for cat in ["engineering", "finishing", "all"]:
            for k, v in self.settings["coefficients"].get(cat, {}).items():
                if k.startswith("state_"):
                    pct = int(round(v["value"] * 100))
                    lbl = f"{v['name']} (+{pct}%)" if pct > 0 else v["name"]
                    if (k, lbl) not in self.state_options:
                        self.state_options.append((k, lbl))
                        
        if not self.state_options:
            self.state_options = [("state_bare_concrete", "Голый бетон")]

        self.rooms_data = []
        self.bathrooms_data = []
        self.eng_selection = {}

    def build(self):
        self.area_input = ft.TextField(
            label="Площадь (м²)",
            hint_text="Введите площадь...",
            value="", width=140, height=46, text_size=13,
            filled=True, fill_color="#F8FAFC", border_radius=12, border_color="#CBD5E1",
            keyboard_type=ft.KeyboardType.NUMBER, on_change=self.on_param_change,
        )

        self.repair_type_seg = ft.SegmentedButton(
            selected={"complex"},
            allow_multiple_selection=False,
            on_change=self.on_type_change,
            segments=[
                ft.Segment(value="complex", label=ft.Text("Комплекс", size=12, weight=ft.FontWeight.W_600)),
                ft.Segment(value="engineering", label=ft.Text("Инженерный", size=12, weight=ft.FontWeight.W_600)),
                ft.Segment(value="finishing", label=ft.Text("Отделочные", size=12, weight=ft.FontWeight.W_600)),
            ],
        )

        self.rooms_count_dropdown = ft.Dropdown(
            label="Комнат (без СУ)", value="1", width=150, height=46, text_size=13,
            filled=True, fill_color="#F8FAFC", border_radius=12, border_color="#CBD5E1",
            options=[ft.dropdown.Option(str(i)) for i in range(1, 7)], on_change=self.on_rooms_count_change,
        )

        self.baths_count_dropdown = ft.Dropdown(
            label="Санузлов", value="1", width=130, height=46, text_size=13,
            filled=True, fill_color="#F8FAFC", border_radius=12, border_color="#CBD5E1",
            options=[ft.dropdown.Option(str(i)) for i in range(1, 4)], on_change=self.on_baths_count_change,
        )

        self.state_dropdown = ft.Dropdown(
            label="Состояние объекта", value=self.state_options[0][0], expand=True, height=46, text_size=13,
            filled=True, fill_color="#F8FAFC", border_radius=12, border_color="#CBD5E1",
            options=[ft.dropdown.Option(k, v) for k, v in self.state_options], on_change=self.on_param_change,
        )

        self.ceil_high_chip = ft.Chip(label=ft.Text("Потолок > 3.0 м (+10%)", size=12), selected=False, on_select=self.on_ceil_high_toggle)

        self.reset_btn = ft.OutlinedButton(
            "Сбросить параметры", icon=ft.icons.RESTART_ALT_ROUNDED, icon_color="#EF4444", height=38,
            style=ft.ButtonStyle(color="#EF4444", side={"default": ft.BorderSide(1, "#FCA5A5")}, shape=ft.RoundedRectangleBorder(radius=10)),
            on_click=self.on_reset_click,
        )

        self.furniture_check = ft.Checkbox(label="Мебель", value=False, on_change=self.on_param_change)
        self.furniture_input = ft.TextField(label="Бюджет на мебель (₽)", value="1500000", width=200, height=40, text_size=12, disabled=True, on_change=self.on_param_change)
        self.appliances_check = ft.Checkbox(label="Бытовая техника", value=False, on_change=self.on_param_change)
        self.appliances_input = ft.TextField(label="Бюджет на технику (₽)", value="1000000", width=200, height=40, text_size=12, disabled=True, on_change=self.on_param_change)

        self.total_cost_text = ft.Text("0 ₽", size=28, weight=ft.FontWeight.W_800, color="#0C66E4")
        self.rate_per_m2_text = ft.Text("0 ₽/м²", size=16, weight=ft.FontWeight.W_700, color="#1E293B")
        self.range_text = ft.Text("Ориентир ~70%: от 0 до 0 ₽", size=12, color="#64748B")
        self.eng_part_text = ft.Text("Инженерный блок: 0 ₽", size=12, color="#475569")
        self.fin_part_text = ft.Text("Отделочный блок: 0 ₽", size=12, color="#475569")
        self.extras_part_text = ft.Text("Опции под ключ: 0 ₽", size=12, color="#475569", visible=True)
        self.selected_type_badge = ft.Container(
            content=ft.Text("Комплекс", size=11, weight=ft.FontWeight.BOLD, color="#0C66E4"),
            bgcolor="#EBF3FC", padding=ft.padding.symmetric(horizontal=10, vertical=4), border_radius=8,
        )
        self.summary_list = ft.ListView(expand=True, spacing=4, auto_scroll=False)

        self.generate_estimate_btn = ft.ElevatedButton(
            "Сформировать смету", icon=ft.icons.DESCRIPTION_ROUNDED, bgcolor="#15803D", color="#FFFFFF",
            height=42, expand=True, visible=True, style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10)),
            on_click=self.open_estimate_dialog,
        )

        self.copy_btn = ft.ElevatedButton(
            "Скопировать расчет", icon=ft.icons.COPY_ALL_ROUNDED, bgcolor="#0C66E4", color="#FFFFFF",
            height=42, expand=True, style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10)),
            on_click=self.copy_summary_to_clipboard,
        )

        self.eng_chips_row = ft.Row(wrap=True, spacing=8, run_spacing=8)
        self.rooms_cards_column = ft.Column(spacing=12)
        self.baths_cards_column = ft.Column(spacing=12)

        self._build_eng_chips()
        self.rebuild_room_data_structures()

        self.card_base = self._card_wrap("1. Базовые параметры объекта", [
            ft.Row([self.area_input, self.repair_type_seg], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            ft.Row([self.rooms_count_dropdown, self.baths_count_dropdown, self.ceil_high_chip], spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            self.state_dropdown,
            ft.Row([self.reset_btn], alignment=ft.MainAxisAlignment.START),
        ])
        self.card_eng = self._card_wrap("2. Общая инженерия и шумоизоляция", [self.eng_chips_row])
        self.card_rooms = self._card_wrap("3. Отделка комнат (без санузлов)", [self.rooms_cards_column])
        self.card_baths = self._card_wrap("4. Санузлы", [self.baths_cards_column])
        
        self.card_complex_extras = self._card_wrap("5. Опции под ключ (Мебель и Техника)", [
            ft.Row([self.furniture_check, self.furniture_input], alignment=ft.MainAxisAlignment.START),
            ft.Row([self.appliances_check, self.appliances_input], alignment=ft.MainAxisAlignment.START),
        ])

        left_column = ft.Column(
            scroll=ft.ScrollMode.AUTO, expand=True, spacing=16,
            controls=[self.card_base, self.card_eng, self.card_rooms, self.card_baths, self.card_complex_extras]
        )

        right_column = ft.Container(
            width=390, padding=18, bgcolor="#F8FAFC", border=ft.border.all(1, "#E2E8F0"), border_radius=18,
            content=ft.Column(
                spacing=10,
                controls=[
                    ft.Row([ft.Text("Итоговая смета", size=17, weight=ft.FontWeight.BOLD, color="#1E293B"), self.selected_type_badge], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    self.total_cost_text, self.rate_per_m2_text, self.range_text,
                    ft.Divider(height=1, color="#E2E8F0"),
                    self.eng_part_text, self.fin_part_text, self.extras_part_text,
                    ft.Divider(height=1, color="#E2E8F0"),
                    ft.Text("Спецификация:", size=13, weight=ft.FontWeight.W_700, color="#334155"),
                    ft.Container(content=self.summary_list, expand=True, height=270),
                    ft.Row([self.copy_btn, self.generate_estimate_btn], spacing=8),
                    ft.OutlinedButton("Обновить тарифы из Таблицы", icon=ft.icons.REFRESH_ROUNDED, height=40, style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10)), on_click=self.refresh_settings)
                ]
            )
        )

        self.recalculate()
        return ft.Container(padding=ft.padding.only(left=20, top=14, right=20, bottom=20), expand=True, content=ft.Row([left_column, right_column], expand=True, spacing=18))

    def _card_wrap(self, title: str, controls: list) -> ft.Container:
        return ft.Container(bgcolor="#FFFFFF", border=ft.border.all(1, "#E2E8F0"), border_radius=16, padding=16, content=ft.Column(spacing=10, controls=[ft.Text(title, size=14, weight=ft.FontWeight.BOLD, color="#1E293B"), *controls]))

    def _get_items_by_prefix(self, prefix: str) -> list[tuple[str, str]]:
        res = []
        for cat in ["finishing", "engineering", "all"]:
            for k, v in self.settings["coefficients"].get(cat, {}).items():
                if k.startswith(prefix) and k != "ceil_high":
                    pct = int(round(v["value"] * 100))
                    lbl = f"{v['name']} (+{pct}%)" if pct > 0 else v["name"]
                    if (k, lbl) not in res: res.append((k, lbl))
        return res

    def _build_eng_chips(self):
        eng_items = []
        for cat in ["engineering", "all"]:
            for k, v in self.settings["coefficients"].get(cat, {}).items():
                if k.startswith("el_") or k.startswith("plumb_") or k.startswith("sound_"):
                    pct = int(round(v["value"] * 100))
                    lbl = f"{v['name']} (+{pct}%)" if pct > 0 else v["name"]
                    if (k, lbl) not in eng_items: eng_items.append((k, lbl))

        chips = []
        for key, label in eng_items:
            if key not in self.eng_selection: self.eng_selection[key] = False
            chips.append(ft.Chip(label=ft.Text(label, size=11), data=key, selected=self.eng_selection[key], on_select=self.on_eng_chip_toggle))
        self.eng_chips_row.controls = chips

    def on_eng_chip_toggle(self, e):
        chip = e.control
        key = chip.data
        is_selected = (e.data == "true" or e.data is True)
        chip.selected = is_selected
        self.eng_selection[key] = is_selected
        self.recalculate()
        self.update()

    def on_ceil_high_toggle(self, e):
        self.ceil_high_chip.selected = (e.data == "true" or e.data is True)
        self.recalculate()
        self.update()

    def on_rooms_count_change(self, e):
        self.rebuild_room_data_structures()
        self.recalculate()
        self.update()

    def on_baths_count_change(self, e):
        self.rebuild_room_data_structures()
        self.recalculate()
        self.update()

    def on_reset_click(self, e):
        self.area_input.value = ""
        self.repair_type_seg.selected = {"complex"}
        self.rooms_count_dropdown.value = "1"
        self.baths_count_dropdown.value = "1"
        self.state_dropdown.value = self.state_options[0][0] if self.state_options else "state_bare_concrete"
        self.ceil_high_chip.selected = False
        self.furniture_check.value = False
        self.appliances_check.value = False

        for k in self.eng_selection: self.eng_selection[k] = False
        for c in self.eng_chips_row.controls: c.selected = False

        self.rooms_data.clear()
        self.bathrooms_data.clear()
        self.rebuild_room_data_structures()
        self.recalculate()
        self.update()

    def rebuild_room_data_structures(self):
        r_count = int(self.rooms_count_dropdown.value or 1)
        while len(self.rooms_data) < r_count:
            idx = len(self.rooms_data) + 1
            name = "Кухня-гостиная" if idx == 1 else f"Комната {idx}"
            self.rooms_data.append({"name": name, "floor": "base", "wall": "base", "ceil": "base", "door": "base", "plinth": "base"})
        self.rooms_data = self.rooms_data[:r_count]

        b_count = int(self.baths_count_dropdown.value or 1)
        while len(self.bathrooms_data) < b_count:
            idx = len(self.bathrooms_data) + 1
            name = "Основной санузел" if idx == 1 else f"Санузел {idx} (Гостевой)"
            self.bathrooms_data.append({"name": name, "tile_floor": "base", "tile_wall": "base", "ceil": "base", "installation": False})
        self.bathrooms_data = self.bathrooms_data[:b_count]

        self.rooms_cards_column.controls = [self._render_single_room_card(i, room) for i, room in enumerate(self.rooms_data)]
        self.baths_cards_column.controls = [self._render_single_bath_card(i, bath) for i, bath in enumerate(self.bathrooms_data)]

    def _render_single_room_card(self, idx: int, data: dict) -> ft.Container:
        def on_chip(e, category, val):
            self.rooms_data[idx][category] = val if (e.data == "true" or e.data is True) else "base"
            self.rebuild_room_data_structures()
            self.recalculate()
            self.update()

        floor_opts = [("base", "Ламинат")] + self._get_items_by_prefix("floor_")
        wall_opts = [("base", "Обои")] + self._get_items_by_prefix("wall_")
        ceil_opts = [("base", "Натяжной стандарт")] + self._get_items_by_prefix("ceil_")
        door_opts = self._get_items_by_prefix("door_")
        plinth_opts = self._get_items_by_prefix("plinth_")

        floor_chips = [ft.Chip(label=ft.Text(lbl, size=11), selected=(data["floor"] == v), on_select=lambda e, val=v: on_chip(e, "floor", val)) for v, lbl in floor_opts]
        wall_chips = [ft.Chip(label=ft.Text(lbl, size=11), selected=(data["wall"] == v), on_select=lambda e, val=v: on_chip(e, "wall", val)) for v, lbl in wall_opts]
        ceil_chips = [ft.Chip(label=ft.Text(lbl, size=11), selected=(data["ceil"] == v), on_select=lambda e, val=v: on_chip(e, "ceil", val)) for v, lbl in ceil_opts]
        door_plinth = [ft.Chip(label=ft.Text(lbl, size=11), selected=(data["door"] == v), on_select=lambda e, val=v: on_chip(e, "door", val)) for v, lbl in door_opts] + \
                      [ft.Chip(label=ft.Text(lbl, size=11), selected=(data["plinth"] == v), on_select=lambda e, val=v: on_chip(e, "plinth", val)) for v, lbl in plinth_opts]

        return ft.Container(
            bgcolor="#F8FAFC", border=ft.border.all(1, "#E2E8F0"), border_radius=12, padding=12,
            content=ft.Column(
                spacing=6,
                controls=[
                    ft.Row([ft.Icon(ft.icons.MEETING_ROOM_ROUNDED, size=16, color="#0C66E4"), ft.Text(data["name"], size=13, weight=ft.FontWeight.BOLD, color="#1E293B")], spacing=6),
                    ft.Text("Напольное покрытие:", size=11, color="#64748B", weight=ft.FontWeight.W_600), ft.Row(floor_chips, wrap=True, spacing=6, run_spacing=6),
                    ft.Text("Отделка стен:", size=11, color="#64748B", weight=ft.FontWeight.W_600), ft.Row(wall_chips, wrap=True, spacing=6, run_spacing=6),
                    ft.Text("Потолочное покрытие:", size=11, color="#64748B", weight=ft.FontWeight.W_600), ft.Row(ceil_chips, wrap=True, spacing=6, run_spacing=6),
                    ft.Text("Опционально:", size=11, color="#64748B", weight=ft.FontWeight.W_600), ft.Row(door_plinth, wrap=True, spacing=6, run_spacing=6),
                ]
            )
        )

    def _render_single_bath_card(self, idx: int, data: dict) -> ft.Container:
        def on_bath_chip(e, category, val):
            self.bathrooms_data[idx][category] = val if (e.data == "true" or e.data is True) else "base"
            self.rebuild_room_data_structures()
            self.recalculate()
            self.update()

        def on_inst_toggle(e):
            self.bathrooms_data[idx]["installation"] = (e.data == "true" or e.data is True)
            self.recalculate()
            self.update()

        tile_opts = [("base", "Формат 60х60")] + self._get_items_by_prefix("tile_")
        tile_floor_chips = [ft.Chip(label=ft.Text(lbl, size=11), selected=(data.get("tile_floor", "base") == v), on_select=lambda e, val=v: on_bath_chip(e, "tile_floor", val)) for v, lbl in tile_opts]
        tile_wall_chips = [ft.Chip(label=ft.Text(lbl, size=11), selected=(data.get("tile_wall", "base") == v), on_select=lambda e, val=v: on_bath_chip(e, "tile_wall", val)) for v, lbl in tile_opts]
        inst_chip = ft.Chip(label=ft.Text("Монтаж инсталляции (+5%)", size=11), selected=data["installation"], on_select=on_inst_toggle)

        return ft.Container(
            bgcolor="#F8FAFC", border=ft.border.all(1, "#E2E8F0"), border_radius=12, padding=12,
            content=ft.Column(
                spacing=6,
                controls=[
                    ft.Row([ft.Icon(ft.icons.BATHTUB_ROUNDED, size=16, color="#0C66E4"), ft.Text(data["name"], size=13, weight=ft.FontWeight.BOLD, color="#1E293B")], spacing=6),
                    ft.Text("Керамогранит на пол:", size=11, color="#64748B", weight=ft.FontWeight.W_600), ft.Row(tile_floor_chips, wrap=True, spacing=6, run_spacing=6),
                    ft.Text("Керамогранит на стены:", size=11, color="#64748B", weight=ft.FontWeight.W_600), ft.Row(tile_wall_chips, wrap=True, spacing=6, run_spacing=6),
                    ft.Text("Сантехнические модули:", size=11, color="#64748B", weight=ft.FontWeight.W_600), ft.Row([inst_chip], wrap=True, spacing=6),
                ]
            )
        )

    def on_type_change(self, e):
        self.recalculate()
        self.update()

    def on_param_change(self, e):
        self.recalculate()
        self.update()
        
    def _apply_coef(self, key: str, k_eng: float, k_fin: float) -> tuple[float, float, str]:
        name = ""
        if key in self.settings["coefficients"].get("engineering", {}):
            val = self.settings["coefficients"]["engineering"][key]["value"]
            name = self.settings["coefficients"]["engineering"][key]["name"]
            k_eng += val
        if key in self.settings["coefficients"].get("finishing", {}):
            val = self.settings["coefficients"]["finishing"][key]["value"]
            name = self.settings["coefficients"]["finishing"][key]["name"]
            k_fin += val
        if key in self.settings["coefficients"].get("all", {}):
            val = self.settings["coefficients"]["all"][key]["value"]
            name = self.settings["coefficients"]["all"][key]["name"]
            k_eng += val
            k_fin += val
        return k_eng, k_fin, name

    def recalculate(self):
        if not hasattr(self, "summary_list") or self.summary_list is None: return

        area_raw = str(self.area_input.value).replace(",", ".").strip()
        try: area = float(area_raw) if area_raw else 0.0
        except ValueError: area = 0.0

        base_eng = float(self.settings.get("base_rates", {}).get("engineering", 22162.0))
        base_fin = float(self.settings.get("base_rates", {}).get("finishing", 41405.0))

        k_eng = 0.0
        k_fin = 0.0

        selected_type = list(self.repair_type_seg.selected)[0]
        self.card_complex_extras.visible = (selected_type == "complex")

        state_key = self.state_dropdown.value
        k_eng, k_fin, clean_state_title = self._apply_coef(state_key, k_eng, k_fin)
        if not clean_state_title: clean_state_title = "Голый бетон"
        if self.ceil_high_chip.selected: k_eng, k_fin, _ = self._apply_coef("ceil_high", k_eng, k_fin)

        for key, is_sel in self.eng_selection.items():
            if is_sel: k_eng, k_fin, _ = self._apply_coef(key, k_eng, k_fin)

        num_rooms = max(len(self.rooms_data), 1)
        room_fin_k_sum = 0.0

        clean_state_title = clean_state_title.replace(' (база)', '').replace('(база)', '')
        spec_lines = [
            f"Состояние: {clean_state_title}",
            f"Высота потолков: {'> 3.0 м (+10%)' if self.ceil_high_chip.selected else 'Стандарт до 3.0 м'}",
        ]

        for r in self.rooms_data:
            r_k = 0.0
            floor_val = r.get("floor", "base")
            floor_title = "Ламинат"
            if floor_val != "base": _, k_add, floor_title = self._apply_coef(floor_val, 0.0, 0.0); r_k += k_add

            wall_val = r.get("wall", "base")
            wall_title = "Обои"
            if wall_val != "base": _, k_add, wall_title = self._apply_coef(wall_val, 0.0, 0.0); r_k += k_add

            ceil_val = r.get("ceil", "base")
            ceil_title = "Натяжной стандарт"
            if ceil_val != "base": _, k_add, ceil_title = self._apply_coef(ceil_val, 0.0, 0.0); r_k += k_add

            door_val = r.get("door", "base")
            door_title = "Обычные распашные"
            if door_val != "base": _, k_add, door_title = self._apply_coef(door_val, 0.0, 0.0); r_k += k_add

            plinth_val = r.get("plinth", "base")
            plinth_title = "Стандартный накладной"
            if plinth_val != "base": _, k_add, plinth_title = self._apply_coef(plinth_val, 0.0, 0.0); r_k += k_add

            room_fin_k_sum += r_k
            spec_lines.extend([f"\n• {r['name']}:", f"  - Пол: {floor_title}", f"  - Стены: {wall_title}", f"  - Потолок: {ceil_title}", f"  - Двери: {door_title}", f"  - Плинтус: {plinth_title}"])

        avg_room_k = room_fin_k_sum / num_rooms
        k_fin += avg_room_k

        num_baths = max(len(self.bathrooms_data), 1)
        bath_k_sum = 0.0
        for b in self.bathrooms_data:
            tile_floor_key = b.get("tile_floor", "base")
            tile_floor_title = "Формат 60х60"
            if tile_floor_key != "base": _, k_add, tile_floor_title = self._apply_coef(tile_floor_key, 0.0, 0.0); bath_k_sum += k_add * 0.4

            tile_wall_key = b.get("tile_wall", "base")
            tile_wall_title = "Формат 60х60"
            if tile_wall_key != "base": _, k_add, tile_wall_title = self._apply_coef(tile_wall_key, 0.0, 0.0); bath_k_sum += k_add * 0.6

            inst_str = "Инсталляция" if b.get("installation") else "Без инсталляции"
            if b.get("installation"): k_eng += 0.05 / num_baths
            spec_lines.extend([f"\n• {b['name']}:", f"  - Керамогранит (Пол): {tile_floor_title}", f"  - Керамогранит (Стены): {tile_wall_title}", f"  - Сантехника: {inst_str}"])

        k_fin += (bath_k_sum / num_baths) * 0.3
        
        # Исправлено: Разделяем стоимость мебели и техники
        f_cost = 0.0
        a_cost = 0.0
        if selected_type == "complex":
            self.furniture_input.disabled = not self.furniture_check.value
            self.appliances_input.disabled = not self.appliances_check.value
            
            if self.furniture_check.value:
                try: f_cost = float(str(self.furniture_input.value).replace(" ", "").replace(",", "."))
                except ValueError: pass
            if self.appliances_check.value:
                try: a_cost = float(str(self.appliances_input.value).replace(" ", "").replace(",", "."))
                except ValueError: pass

        extras_total = f_cost + a_cost

        rate_eng = base_eng * (1.0 + k_eng)
        rate_fin = base_fin * (1.0 + k_fin)

        total_eng = rate_eng * area
        total_fin = rate_fin * area

        if selected_type == "engineering":
            rate_active, total_active, type_label = rate_eng, total_eng, "Инженерный ремонт"
            self.eng_part_text.visible, self.fin_part_text.visible, self.extras_part_text.visible = True, False, False
        elif selected_type == "finishing":
            rate_active, total_active, type_label = rate_fin, total_fin, "Отделочные работы"
            self.eng_part_text.visible, self.fin_part_text.visible, self.extras_part_text.visible = False, True, False
        else:
            rate_active, total_active, type_label = rate_eng + rate_fin, total_eng + total_fin + extras_total, "Комплекс (Инженерия + Отделка)"
            self.eng_part_text.visible, self.fin_part_text.visible, self.extras_part_text.visible = True, True, True

        min_range, max_range = total_active * 0.85, total_active * 1.15

        self.selected_type_badge.content.value = type_label
        self.total_cost_text.value = f"{int(round(total_active)):,} ₽".replace(",", " ")
        self.rate_per_m2_text.value = f"{int(round(rate_active)):,} ₽/м²".replace(",", " ")
        self.range_text.value = f"Ориентир ~70%: от {int(round(min_range)):,} до {int(round(max_range)):,} ₽".replace(",", " ")
        self.eng_part_text.value = f"Инженерный блок: {int(round(total_eng)):,} ₽ ({int(round(rate_eng)):,} ₽/м²)"
        self.fin_part_text.value = f"Отделочный блок: {int(round(total_fin)):,} ₽ ({int(round(rate_fin)):,} ₽/м²)"
        self.extras_part_text.value = f"Опции под ключ: {int(round(extras_total)):,} ₽"

        summary_controls = []
        for line in spec_lines:
            if not line: continue
            if line.startswith("\n•") or line.startswith("•"):
                summary_controls.extend([ft.Container(height=4), ft.Text(line.strip(), size=12, weight=ft.FontWeight.BOLD, color="#1E293B")])
            elif line.startswith("  -"):
                summary_controls.append(ft.Container(padding=ft.padding.only(left=12), content=ft.Text(line.strip(), size=11, color="#475569")))
            else:
                summary_controls.append(ft.Text(line, size=12, color="#334155"))
        self.summary_list.controls = summary_controls

        current_repair_state.area = area
        current_repair_state.rate_eng, current_repair_state.total_eng = rate_eng, total_eng
        current_repair_state.rate_fin, current_repair_state.total_fin = rate_fin, total_fin
        current_repair_state.grand_total = total_active
        current_repair_state.selected_type = selected_type
        current_repair_state.state_title = clean_state_title
        current_repair_state.has_demolition = ("demo" in str(self.state_dropdown.value).lower() or "вторичка" in clean_state_title.lower())
        current_repair_state.spec_lines = spec_lines
        
        current_repair_state.has_furniture = self.furniture_check.value
        current_repair_state.furniture_cost = f_cost
        current_repair_state.has_appliances = self.appliances_check.value
        current_repair_state.appliances_cost = a_cost

    def open_estimate_dialog(self, e):
        if current_repair_state.area <= 0: return e.page.show_snack_bar(ft.SnackBar(ft.Text("Сначала укажите площадь!"), duration=2000))

        address_input = ft.TextField(label="ЖК / Адрес объекта", value=current_repair_state.address or "", hint_text="Например: ЖК «Тринити», кв. 42", height=48, text_size=13, filled=True, fill_color="#F8FAFC", border_radius=12)
        client_input = ft.TextField(label="Имя заказчика", value=current_repair_state.client_name or "", hint_text="Например: Александр", height=48, text_size=13, filled=True, fill_color="#F8FAFC", border_radius=12)
        status_label = ft.Text("", size=12, color="#0C66E4")
        gen_prog = ft.ProgressBar(visible=False, color="#0C66E4")

        def on_confirm_generate(dlg_e):
            addr, cl_name = address_input.value.strip() or "Объект", client_input.value.strip() or "Заказчик"
            current_repair_state.address, current_repair_state.client_name = addr, cl_name
            submit_btn.disabled = True
            gen_prog.visible, status_label.value, status_label.color = True, "Генерация презентации и PDF...", "#0C66E4"
            dlg_e.page.update()

            try:
                res = generate_universal_estimate_presentation({
                    "repair_type": current_repair_state.selected_type, "area": current_repair_state.area,
                    "eng_cost": current_repair_state.total_eng, "fin_cost": current_repair_state.total_fin,
                    "furniture_cost": current_repair_state.furniture_cost, "appliances_cost": current_repair_state.appliances_cost,
                    "has_demolition": current_repair_state.has_demolition, "address": addr, "client_name": cl_name,
                    "state": current_repair_state.state_title,
                })
                dialog.open = False
                dlg_e.page.update()

                success_dlg = ft.AlertDialog(
                    title=ft.Row([ft.Icon(ft.icons.CHECK_CIRCLE_ROUNDED, color="#15803D", size=24), ft.Text("Смета успешно создана!", size=16, weight=ft.FontWeight.BOLD)], spacing=8),
                    content=ft.Container(
                        width=440, content=ft.Column(
                            tight=True, spacing=12,
                            controls=[
                                ft.Text(f"Файл: {res['title']}", size=12, weight=ft.FontWeight.W_600, color="#1E293B"),
                                ft.ElevatedButton("📄 Открыть PDF", icon=ft.icons.PICTURE_AS_PDF_ROUNDED, bgcolor="#0C66E4", color="#FFFFFF", height=44, style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10)), url=res["pdf_url"]),
                                ft.OutlinedButton("🖥 Открыть Google Презентацию", icon=ft.icons.OPEN_IN_NEW_ROUNDED, height=44, style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10)), url=res["edit_url"]),
                            ]
                        )
                    ),
                    actions=[ft.TextButton("Закрыть", on_click=lambda ev: setattr(success_dlg, "open", False) or ev.page.update())],
                )
                if success_dlg not in dlg_e.page.overlay: dlg_e.page.overlay.append(success_dlg)
                success_dlg.open = True
                dlg_e.page.update()
            except Exception as ex:
                status_label.value, status_label.color, submit_btn.disabled, gen_prog.visible = f"Ошибка: {ex}", "#DC2626", False, False
                dlg_e.page.update()

        submit_btn = ft.ElevatedButton("Создать презентацию и PDF", icon=ft.icons.SLIDESHOW_ROUNDED, bgcolor="#15803D", color="#FFFFFF", height=44, style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10)), on_click=on_confirm_generate)
        
        selected_type = list(self.repair_type_seg.selected)[0]
        dlg_title = {"engineering": "Смета: Инженерный ремонт", "finishing": "Смета: Отделочные работы"}.get(selected_type, "Смета: Комплексный ремонт")

        dialog = ft.AlertDialog(
            title=ft.Row([ft.Icon(ft.icons.REQUEST_QUOTE_ROUNDED, color="#15803D", size=22), ft.Text(dlg_title, size=16, weight=ft.FontWeight.BOLD)], spacing=8),
            content=ft.Container(width=420, content=ft.Column(tight=True, spacing=12, controls=[ft.Text(f"Параметры: {current_repair_state.area:g} м² | {self.total_cost_text.value}", size=12, color="#64748B"), address_input, client_input, gen_prog, status_label])),
            actions=[ft.TextButton("Отмена", on_click=lambda ev: setattr(dialog, "open", False) or ev.page.update()), submit_btn],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        if dialog not in e.page.overlay: e.page.overlay.append(dialog)
        dialog.open = True
        e.page.update()

    def copy_summary_to_clipboard(self, e):
        sel = list(self.repair_type_seg.selected)[0]
        type_str = {"engineering": "Инженерный ремонт", "finishing": "Отделочные работы"}.get(sel, "Комплекс (Инженерия + Отделка)")
        raw_lines = [c.value if isinstance(c, ft.Text) else f"  {c.content.value}" for c in self.summary_list.controls if isinstance(c, ft.Text) or (isinstance(c, ft.Container) and isinstance(c.content, ft.Text))]
        text = f"📊 ПОКОМНАТНЫЙ РАСЧЕТ РЕМОНТА\nТип: {type_str}\nПлощадь: {self.area_input.value or '0'} м²\nСтавка: {self.rate_per_m2_text.value}\nИтоговая смета: {self.total_cost_text.value}\n{self.range_text.value}\n\nСпецификация по помещениям:\n" + "\n".join(raw_lines)
        e.page.set_clipboard(text)
        e.page.show_snack_bar(ft.SnackBar(ft.Text("Покомнатный расчет скопирован!"), duration=2000))

    def refresh_settings(self, e):
        self.settings = load_base_rates_and_coefficients()
        self.state_options.clear()
        for cat in ["engineering", "finishing", "all"]:
            for k, v in self.settings["coefficients"].get(cat, {}).items():
                if k.startswith("state_"):
                    pct = int(round(v["value"] * 100))
                    lbl = f"{v['name']} (+{pct}%)" if pct > 0 else v["name"]
                    if (k, lbl) not in self.state_options: self.state_options.append((k, lbl))
        if not self.state_options: self.state_options = [("state_bare_concrete", "Голый бетон")]
        self._build_eng_chips()
        self.rebuild_room_data_structures()
        self.recalculate()
        self.update()
        e.page.show_snack_bar(ft.SnackBar(ft.Text("Тарифы обновлены из локальной базы!"), duration=2000))