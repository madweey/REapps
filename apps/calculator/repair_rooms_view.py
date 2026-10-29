import os
import flet as ft
from apps.calculator.repair_state import current_repair_state
from apps.calculator.repair_estimate_service import (
    load_base_rates_and_coefficients,
    generate_universal_estimate_presentation
)
from apps.calculator.repair_estimate_whitebox_service import generate_whitebox_estimate_presentation
from apps.core.sheets import RepairDataSync

_VIEW_STATE_CACHE = {
    "area": "", "repair_type": "complex", "rooms_count": "1", "baths_count": "1",
    "state_dropdown": None, "ceil_high": False, "global_part": "base",
    "global_screed": "base", "global_manifold": "base", "global_markup": "0.0",
    "furniture": "none", "appliances": "none", "rooms_data": [], "bathrooms_data": []
}

class RepairRoomsCalculatorView(ft.UserControl):
    def __init__(self):
        super().__init__()
        self.settings = load_base_rates_and_coefficients()
        
        # Убрана заглушка default_label, чтобы Голый бетон не дублировался с базой
        self.state_options = self._build_options_list("state_")
        if not self.state_options: 
            self.state_options = [("base", "Голый бетон")]
        
        # Защита от несуществующего кэша (если удалили из админки)
        valid_state_keys = [k for k, v in self.state_options]
        if _VIEW_STATE_CACHE["state_dropdown"] not in valid_state_keys:
            _VIEW_STATE_CACHE["state_dropdown"] = valid_state_keys[0] if valid_state_keys else "base"

        self.rooms_data = _VIEW_STATE_CACHE["rooms_data"]
        self.bathrooms_data = _VIEW_STATE_CACHE["bathrooms_data"]
        self.global_part_val = _VIEW_STATE_CACHE["global_part"]
        self.global_screed_val = _VIEW_STATE_CACHE["global_screed"]
        self.global_manifold_val = _VIEW_STATE_CACHE["global_manifold"]
        self.global_markup_val = _VIEW_STATE_CACHE["global_markup"]

    def _build_options_list(self, prefix: str, default_label: str = None) -> list[tuple[str, str]]:
        res = []
        if default_label: res.append(("base", default_label))
        for cat in ["finishing", "engineering", "all"]:
            for k, v in self.settings["coefficients"].get(cat, {}).items():
                if k.startswith(prefix):
                    pct = int(round(v["value"] * 100))
                    lbl = f"{v['name']} (+{pct}%)" if pct > 0 else (f"{v['name']} ({pct}%)" if pct < 0 else v["name"])
                    if (k, lbl) not in res: res.append((k, lbl))
        return res

    def build(self):
        self.area_input = ft.TextField(label="Площадь (м²)", value=_VIEW_STATE_CACHE["area"], width=140, height=46, text_size=13, filled=True, fill_color="#F8FAFC", border_radius=12, keyboard_type=ft.KeyboardType.NUMBER, on_change=self.on_param_change)
        self.repair_type_seg = ft.SegmentedButton(selected={_VIEW_STATE_CACHE["repair_type"]}, allow_multiple_selection=False, on_change=self.on_param_change, segments=[ft.Segment(value="complex", label=ft.Text("Комплекс", size=12, weight=ft.FontWeight.W_600)), ft.Segment(value="engineering", label=ft.Text("Инженерный", size=12)), ft.Segment(value="finishing", label=ft.Text("Отделочные", size=12))])
        self.rooms_count_dropdown = ft.Dropdown(label="Комнат (без СУ)", value=_VIEW_STATE_CACHE["rooms_count"], width=150, height=46, text_size=13, filled=True, fill_color="#F8FAFC", border_radius=12, options=[ft.dropdown.Option(str(i)) for i in range(1, 7)], on_change=self.on_counts_change)
        self.baths_count_dropdown = ft.Dropdown(label="Санузлов", value=_VIEW_STATE_CACHE["baths_count"], width=130, height=46, text_size=13, filled=True, fill_color="#F8FAFC", border_radius=12, options=[ft.dropdown.Option(str(i)) for i in range(1, 4)], on_change=self.on_counts_change)
        
        # ИСПРАВЛЕНИЕ: Убран expand=True, чтобы не ломать верстку в скролле!
        self.state_dropdown = ft.Dropdown(label="Состояние объекта", value=_VIEW_STATE_CACHE["state_dropdown"], height=46, text_size=13, filled=True, fill_color="#F8FAFC", border_radius=12, options=[ft.dropdown.Option(k, v) for k, v in self.state_options], on_change=self.on_param_change)
        
        self.ceil_high_chip = ft.Chip(label=ft.Text("Потолок > 3.0 м (+10%)", size=12), selected=_VIEW_STATE_CACHE["ceil_high"], on_select=self.on_ceil_high_toggle)

        self.part_dropdown = ft.Dropdown(label="Перегородки", value=_VIEW_STATE_CACHE["global_part"], expand=True, height=46, text_size=12, options=[ft.dropdown.Option(k, v) for k, v in self._build_options_list("part_", "База (Пеноблок)")], on_change=self.on_global_eng_change)
        self.screed_dropdown = ft.Dropdown(label="Стяжка пола", value=_VIEW_STATE_CACHE["global_screed"], expand=True, height=46, text_size=12, options=[ft.dropdown.Option(k, v) for k, v in self._build_options_list("screed_", "База (Полусухая)")], on_change=self.on_global_eng_change)
        self.manifold_dropdown = ft.Dropdown(label="Сантех. узел (на всю квартиру)", value=_VIEW_STATE_CACHE["global_manifold"], expand=True, height=46, text_size=12, options=[ft.dropdown.Option(k, v) for k, v in self._build_options_list("manifold_", "Комфорт (База)")], on_change=self.on_global_eng_change)
        self.markup_dropdown = ft.Dropdown(label="Коэф. сметы (Сложность)", value=_VIEW_STATE_CACHE["global_markup"], expand=True, height=46, text_size=12, options=[ft.dropdown.Option("0.0", "Базовый (+0%)"), ft.dropdown.Option("0.15", "Повышающий (+15%)"), ft.dropdown.Option("0.30", "Высокий (+30%)")], on_change=self.on_global_eng_change)

        self.furniture_dropdown = ft.Dropdown(label="Комплектация мебелью", value=_VIEW_STATE_CACHE["furniture"], options=[ft.dropdown.Option("none", "Без мебели")], expand=True, height=46, text_size=12, on_change=self.on_param_change)
        self.appliances_dropdown = ft.Dropdown(label="Бытовая техника", value=_VIEW_STATE_CACHE["appliances"], options=[ft.dropdown.Option("none", "Без техники")], expand=True, height=46, text_size=12, on_change=self.on_param_change)

        self.total_cost_text = ft.Text("0 ₽", size=28, weight=ft.FontWeight.W_800, color="#0C66E4")
        self.rate_per_m2_text = ft.Text("0 ₽/м²", size=16, weight=ft.FontWeight.W_700, color="#1E293B")
        self.range_text = ft.Text("Ориентир ~70%: от 0 до 0 ₽", size=12, color="#64748B")
        self.eng_part_text = ft.Text("Инженерия: 0 ₽", size=12, color="#475569")
        self.fin_part_text = ft.Text("Отделка: 0 ₽", size=12, color="#475569")
        self.extras_part_text = ft.Text("Опции под ключ: 0 ₽", size=12, color="#475569", visible=True)
        self.selected_type_badge = ft.Container(content=ft.Text("Комплекс", size=11, weight=ft.FontWeight.BOLD, color="#0C66E4"), bgcolor="#EBF3FC", padding=ft.padding.symmetric(horizontal=10, vertical=4), border_radius=8)
        self.summary_list = ft.ListView(expand=True, spacing=4, auto_scroll=False)

        self.generate_estimate_btn = ft.ElevatedButton("Сформировать смету", icon=ft.icons.DESCRIPTION_ROUNDED, bgcolor="#15803D", color="#FFFFFF", height=42, expand=True, style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10)), on_click=self.open_estimate_dialog)
        self.copy_btn = ft.ElevatedButton("Скопировать", icon=ft.icons.COPY_ALL_ROUNDED, bgcolor="#0C66E4", color="#FFFFFF", height=42, expand=True, style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10)), on_click=self.copy_summary_to_clipboard)

        self.rooms_cards_column, self.baths_cards_column = ft.Column(spacing=8), ft.Column(spacing=8)
        self.rebuild_room_data_structures()

        self.card_base = self._card_wrap("1. Базовые параметры объекта", [ft.Row([self.area_input, self.repair_type_seg], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, vertical_alignment=ft.CrossAxisAlignment.CENTER), ft.Row([self.rooms_count_dropdown, self.baths_count_dropdown, self.ceil_high_chip], spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER), self.state_dropdown])
        self.card_global_eng = self._card_wrap("2. Глобальная инженерия (на всю квартиру)", [ft.Row([self.part_dropdown, self.screed_dropdown], spacing=10), ft.Row([self.manifold_dropdown, self.markup_dropdown], spacing=10)])
        self.card_rooms = self._card_wrap("3. Покомнатная спецификация (Жилые)", [self.rooms_cards_column])
        self.card_baths = self._card_wrap("4. Санузлы", [self.baths_cards_column])
        self.card_complex_extras = self._card_wrap("5. Опции под ключ (Мебель и Техника)", [ft.Row([self.furniture_dropdown, self.appliances_dropdown], spacing=10)])

        left_column = ft.Column(scroll=ft.ScrollMode.AUTO, expand=True, spacing=16, controls=[self.card_base, self.card_global_eng, self.card_rooms, self.card_baths, self.card_complex_extras])
        right_column = ft.Container(
            width=390, padding=18, bgcolor="#F8FAFC", border=ft.border.all(1, "#E2E8F0"), border_radius=18,
            content=ft.Column(spacing=10, controls=[
                ft.Row([ft.Text("Итоговая смета", size=17, weight=ft.FontWeight.BOLD, color="#1E293B"), self.selected_type_badge], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                self.total_cost_text, self.rate_per_m2_text, self.range_text, ft.Divider(height=1, color="#E2E8F0"),
                self.eng_part_text, self.fin_part_text, self.extras_part_text, ft.Divider(height=1, color="#E2E8F0"),
                ft.Text("Спецификация:", size=13, weight=ft.FontWeight.W_700, color="#334155"),
                ft.Container(content=self.summary_list, expand=True, height=270),
                ft.Row([self.copy_btn, self.generate_estimate_btn], spacing=8),
                ft.Row([
                    ft.OutlinedButton("Обновить тарифы", icon=ft.icons.REFRESH_ROUNDED, expand=True, height=40, style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10)), on_click=self.refresh_settings),
                    ft.OutlinedButton("Сбросить", icon=ft.icons.REPLAY_ROUNDED, expand=True, height=40, style=ft.ButtonStyle(color="#DC2626", shape=ft.RoundedRectangleBorder(radius=10)), on_click=self.on_reset)
                ], spacing=8)
            ])
        )

        self.recalculate()
        return ft.Container(padding=ft.padding.only(left=20, top=14, right=20, bottom=20), expand=True, content=ft.Row([left_column, right_column], expand=True, spacing=18))

    def _card_wrap(self, title: str, controls: list) -> ft.Container:
        return ft.Container(bgcolor="#FFFFFF", border=ft.border.all(1, "#E2E8F0"), border_radius=16, padding=16, content=ft.Column(spacing=10, controls=[ft.Text(title, size=14, weight=ft.FontWeight.BOLD, color="#1E293B"), *controls]))

    def on_ceil_high_toggle(self, e):
        self.ceil_high_chip.selected = (e.data == "true" or e.data is True)
        self.recalculate()
        self.update()
        
    def on_global_eng_change(self, e):
        self.global_part_val, self.global_screed_val, self.global_manifold_val, self.global_markup_val = self.part_dropdown.value, self.screed_dropdown.value, self.manifold_dropdown.value, self.markup_dropdown.value
        self.recalculate()
        self.update()

    def on_counts_change(self, e):
        self.rebuild_room_data_structures()
        self.recalculate()
        self.update()

    def on_param_change(self, e):
        self.recalculate()
        self.update()

    def on_reset(self, e):
        self.area_input.value = ""
        self.repair_type_seg.selected = {"complex"}
        self.rooms_count_dropdown.value = "1"
        self.baths_count_dropdown.value = "1"
        self.state_dropdown.value = self.state_options[0][0] if self.state_options else "base"
        self.ceil_high_chip.selected = False
        self.part_dropdown.value, self.screed_dropdown.value, self.manifold_dropdown.value, self.markup_dropdown.value = "base", "base", "base", "0.0"
        self.global_part_val, self.global_screed_val, self.global_manifold_val, self.global_markup_val = "base", "base", "base", "0.0"
        self.furniture_dropdown.value, self.appliances_dropdown.value = "none", "none"
        self.rooms_data.clear()
        self.bathrooms_data.clear()
        self.rebuild_room_data_structures()
        self.recalculate()
        self.update()
        e.page.show_snack_bar(ft.SnackBar(ft.Text("Данные калькулятора сброшены"), duration=2000))

    def rebuild_room_data_structures(self):
        r_count = int(self.rooms_count_dropdown.value or 1)
        while len(self.rooms_data) < r_count:
            idx = len(self.rooms_data) + 1
            self.rooms_data.append({"name": "Кухня-гостиная" if idx == 1 else f"Комната {idx}", "floor": None, "wall": None, "ceil": None, "door": None, "plinth": None, "custom": None, "sound_wall": None, "sound_ceil": None, "expanded": False})
        while len(self.rooms_data) > r_count: self.rooms_data.pop()
        for r in self.rooms_data:
            r.setdefault("custom", None)

        b_count = int(self.bathrooms_data) if False else int(self.baths_count_dropdown.value or 1)
        while len(self.bathrooms_data) < b_count:
            idx = len(self.bathrooms_data) + 1
            self.bathrooms_data.append({"name": "Основной санузел" if idx == 1 else f"Санузел {idx}", "tile_floor": None, "tile_wall": None, "ceil": None, "expanded": False})
        while len(self.bathrooms_data) > b_count: self.bathrooms_data.pop()
        self._refresh_room_ui()

    def _refresh_room_ui(self):
        self.rooms_cards_column.controls = [self._render_single_room_card(i, room) for i, room in enumerate(self.rooms_data)]
        self.baths_cards_column.controls = [self._render_single_bath_card(i, bath) for i, bath in enumerate(self.bathrooms_data)]

    def _get_status_icon(self, filled_count: int, required_count: int = 3):
        if filled_count == 0: return ft.Icon(ft.icons.CANCEL_ROUNDED, color=ft.colors.RED_500, size=20)
        elif filled_count >= required_count: return ft.Icon(ft.icons.CHECK_CIRCLE_ROUNDED, color=ft.colors.GREEN_500, size=20)
        else: return ft.Icon(ft.icons.ERROR_ROUNDED, color=ft.colors.YELLOW_600, size=20)

    def _render_single_room_card(self, idx: int, data: dict) -> ft.ExpansionTile:
        def on_chip(e, category, val):
            self.rooms_data[idx][category] = val if (e.data == "true" or e.data is True) else None
            self._refresh_room_ui()
            self.recalculate()
            self.update()

        def on_expand(e): self.rooms_data[idx]["expanded"] = (e.data == "true")
        filled = sum(1 for x in [data["floor"], data["wall"], data["ceil"]] if x is not None)
        header = ft.Row([self._get_status_icon(filled, 3), ft.Text(data["name"], size=14, weight=ft.FontWeight.BOLD, color="#1E293B")], spacing=8)
        sound_wall_opts, sound_ceil_opts = self._build_options_list("soundwall_", "Нет"), self._build_options_list("soundceil_", "Нет")
        floor_opts, wall_opts, ceil_opts = self._build_options_list("floor_", "База (Ламинат)"), self._build_options_list("wall_", "База (Обои)"), self._build_options_list("ceil_", "База (Натяжной)")
        door_opts, plinth_opts, custom_opts = self._build_options_list("door_"), self._build_options_list("plinth_"), self._build_options_list("custom_")

        def make_chips(opts, category): return [ft.Chip(label=ft.Text(lbl, size=11), selected=(data.get(category) == v), on_select=lambda e, val=v: on_chip(e, category, val)) for v, lbl in opts]
        content = ft.Column(spacing=12, controls=[
            ft.Text("ИНЖЕНЕРИЯ ПОМЕЩЕНИЯ", size=11, weight=ft.FontWeight.W_700, color="#94A3B8"),
            ft.Row([ft.Text("Шумка стен:", size=11, color="#64748B", width=80), ft.Row(make_chips(sound_wall_opts, "sound_wall"), wrap=True, spacing=6, expand=True)], spacing=2, vertical_alignment=ft.CrossAxisAlignment.START),
            ft.Row([ft.Text("Шумка потолка:", size=11, color="#64748B", width=80), ft.Row(make_chips(sound_ceil_opts, "sound_ceil"), wrap=True, spacing=6, expand=True)], spacing=2, vertical_alignment=ft.CrossAxisAlignment.START),
            ft.Divider(height=1, color="#CBD5E1"),
            ft.Text("ОТДЕЛОЧНЫЕ РАБОТЫ (Обязательно)", size=11, weight=ft.FontWeight.W_700, color="#94A3B8"),
            ft.Row([ft.Text("Пол:", size=11, color="#64748B", width=80), ft.Row(make_chips(floor_opts, "floor"), wrap=True, spacing=6, expand=True)], spacing=2, vertical_alignment=ft.CrossAxisAlignment.START),
            ft.Divider(height=1, color="#E2E8F0"),
            ft.Row([ft.Text("Стены:", size=11, color="#64748B", width=80), ft.Row(make_chips(wall_opts, "wall"), wrap=True, spacing=6, expand=True)], spacing=2, vertical_alignment=ft.CrossAxisAlignment.START),
            ft.Divider(height=1, color="#E2E8F0"),
            ft.Row([ft.Text("Потолок:", size=11, color="#64748B", width=80), ft.Row(make_chips(ceil_opts, "ceil"), wrap=True, spacing=6, expand=True)], spacing=2, vertical_alignment=ft.CrossAxisAlignment.START),
            ft.Divider(height=1, color="#E2E8F0"),
            ft.Row([ft.Text("Опции:", size=11, color="#64748B", width=80), ft.Row(make_chips(door_opts, "door") + make_chips(plinth_opts, "plinth") + make_chips(custom_opts, "custom"), wrap=True, spacing=6, expand=True)], spacing=2, vertical_alignment=ft.CrossAxisAlignment.START),
        ])
        return ft.ExpansionTile(title=header, initially_expanded=data["expanded"], on_change=on_expand, controls=[ft.Container(content=content, padding=12, bgcolor="#F8FAFC", border_radius=ft.border_radius.only(bottom_left=12, bottom_right=12))])

    def _render_single_bath_card(self, idx: int, data: dict) -> ft.ExpansionTile:
        def on_bath_chip(e, category, val):
            self.bathrooms_data[idx][category] = val if (e.data == "true" or e.data is True) else None
            self._refresh_room_ui()
            self.recalculate()
            self.update()

        def on_expand(e): self.bathrooms_data[idx]["expanded"] = (e.data == "true")
        filled = sum(1 for x in [data["tile_floor"], data["tile_wall"], data["ceil"]] if x is not None)
        header = ft.Row([self._get_status_icon(filled, 3), ft.Text(data["name"], size=14, weight=ft.FontWeight.BOLD, color="#1E293B")], spacing=8)
        tile_opts, ceil_opts = self._build_options_list("tile_", "База (60х60)"), self._build_options_list("ceil_", "База (Натяжной)")

        content = ft.Column(spacing=12, controls=[
            ft.Text("ОТДЕЛОЧНЫЕ РАБОТЫ СУ (Обязательно)", size=11, weight=ft.FontWeight.W_700, color="#94A3B8"),
            ft.Row([ft.Text("Пол:", size=11, color="#64748B", width=80), ft.Row([ft.Chip(label=ft.Text(lbl, size=11), selected=(data["tile_floor"] == v), on_select=lambda e, val=v: on_bath_chip(e, "tile_floor", val)) for v, lbl in tile_opts], wrap=True, spacing=6, expand=True)], spacing=2, vertical_alignment=ft.CrossAxisAlignment.START),
            ft.Divider(height=1, color="#E2E8F0"),
            ft.Row([ft.Text("Стены:", size=11, color="#64748B", width=80), ft.Row([ft.Chip(label=ft.Text(lbl, size=11), selected=(data["tile_wall"] == v), on_select=lambda e, val=v: on_bath_chip(e, "tile_wall", val)) for v, lbl in tile_opts], wrap=True, spacing=6, expand=True)], spacing=2, vertical_alignment=ft.CrossAxisAlignment.START),
            ft.Divider(height=1, color="#E2E8F0"),
            ft.Row([ft.Text("Потолок:", size=11, color="#64748B", width=80), ft.Row([ft.Chip(label=ft.Text(lbl, size=11), selected=(data["ceil"] == v), on_select=lambda e, val=v: on_bath_chip(e, "ceil", val)) for v, lbl in ceil_opts], wrap=True, spacing=6, expand=True)], spacing=2, vertical_alignment=ft.CrossAxisAlignment.START),
        ])
        return ft.ExpansionTile(title=header, initially_expanded=data["expanded"], on_change=on_expand, controls=[ft.Container(content=content, padding=12, bgcolor="#F8FAFC", border_radius=ft.border_radius.only(bottom_left=12, bottom_right=12))])

    def _apply_coef(self, key: str, k_eng: float, k_fin: float) -> tuple[float, float, str]:
        name = ""
        for cat in ["engineering", "finishing", "all"]:
            if key in self.settings["coefficients"].get(cat, {}):
                val = self.settings["coefficients"][cat][key]["value"]
                name = self.settings["coefficients"][cat][key]["name"]
                if cat in ["engineering", "all"]: k_eng += val
                if cat in ["finishing", "all"]: k_fin += val
        return k_eng, k_fin, name

    def recalculate(self):
        if not hasattr(self, "summary_list") or self.summary_list is None: return

        state_val = str(self.state_dropdown.value)
        _, _, check_state_title = self._apply_coef(state_val, 0.0, 0.0)
        is_whitebox_state = ("wb" in state_val.lower() or "вайтбокс" in check_state_title.lower())

        current_segments = [s.value for s in self.repair_type_seg.segments]
        needs_seg_update = False

        if is_whitebox_state and "whitebox" not in current_segments:
            self.repair_type_seg.segments.append(ft.Segment(value="whitebox", label=ft.Text("Вайтбокс", size=12, weight=ft.FontWeight.W_600)))
            needs_seg_update = True
        elif not is_whitebox_state and "whitebox" in current_segments:
            self.repair_type_seg.segments = [s for s in self.repair_type_seg.segments if s.value != "whitebox"]
            if "whitebox" in self.repair_type_seg.selected:
                self.repair_type_seg.selected = {"complex"}
            needs_seg_update = True
            
        if needs_seg_update and getattr(self.repair_type_seg, "page", None):
            self.repair_type_seg.update()

        _VIEW_STATE_CACHE["area"] = str(self.area_input.value)
        _VIEW_STATE_CACHE["repair_type"] = list(self.repair_type_seg.selected)[0]
        _VIEW_STATE_CACHE["rooms_count"] = str(self.rooms_count_dropdown.value)
        _VIEW_STATE_CACHE["baths_count"] = str(self.baths_count_dropdown.value)
        _VIEW_STATE_CACHE["state_dropdown"] = state_val
        _VIEW_STATE_CACHE["ceil_high"] = bool(self.ceil_high_chip.selected)
        _VIEW_STATE_CACHE["global_part"] = str(self.part_dropdown.value)
        _VIEW_STATE_CACHE["global_screed"] = str(self.screed_dropdown.value)
        _VIEW_STATE_CACHE["global_manifold"] = str(self.manifold_dropdown.value)
        _VIEW_STATE_CACHE["global_markup"] = str(self.markup_dropdown.value)
        _VIEW_STATE_CACHE["furniture"] = str(self.furniture_dropdown.value)
        _VIEW_STATE_CACHE["appliances"] = str(self.appliances_dropdown.value)

        try: area = float(str(self.area_input.value).replace(",", ".").strip())
        except ValueError: area = 0.0

        raw_data = RepairDataSync.get_data()
        rates = raw_data.get("base_rates", {})

        furn_market_pct = float(rates.get("furn_market", 20.0))
        furn_aggr_pct = float(rates.get("furn_aggr", 25.0))
        furn_custom_pct = float(rates.get("furn_custom", 35.0))
        self.furniture_dropdown.options = [ft.dropdown.Option("none", "Без мебели"), ft.dropdown.Option("market", f"Маркетплейс (+{int(furn_market_pct)}%)"), ft.dropdown.Option("aggr", f"Агрегаторы (+{int(furn_aggr_pct)}%)"), ft.dropdown.Option("custom", f"Индив. изготовление (+{int(furn_custom_pct)}%)")]

        app_base_pct = float(rates.get("app_base", 10.0))
        app_mid_pct = float(rates.get("app_mid", 15.0))
        app_prem_pct = float(rates.get("app_prem", 25.0))
        self.appliances_dropdown.options = [ft.dropdown.Option("none", "Без техники"), ft.dropdown.Option("base", f"Базовая (+{int(app_base_pct)}%)"), ft.dropdown.Option("mid", f"Средняя (+{int(app_mid_pct)}%)"), ft.dropdown.Option("prem", f"Премиум (+{int(app_prem_pct)}%)")]

        base_eng_work = float(rates.get("engineering_work", 25254.0))
        base_fin_work = float(rates.get("finishing_work", 33024.0))

        k_eng, k_fin = 0.0, 0.0
        selected_type = list(self.repair_type_seg.selected)[0]
        self.card_complex_extras.visible = (selected_type in ["complex", "whitebox"])

        k_eng, k_fin, clean_state_title = self._apply_coef(state_val, k_eng, k_fin)
        if not clean_state_title: clean_state_title = "Голый бетон"
        
        if self.ceil_high_chip.selected:
            k_e_orig, k_f_orig = k_eng, k_fin
            k_eng, k_fin, _ = self._apply_coef("ceil_high", k_eng, k_fin)
            if k_eng == k_e_orig and k_fin == k_f_orig:
                k_eng += 0.10
                k_fin += 0.10

        if self.global_part_val != "base": k_eng, k_fin, _ = self._apply_coef(self.global_part_val, k_eng, k_fin)
        if self.global_screed_val != "base": k_eng, k_fin, _ = self._apply_coef(self.global_screed_val, k_eng, k_fin)
        if self.global_manifold_val != "base": k_eng, k_fin, _ = self._apply_coef(self.global_manifold_val, k_eng, k_fin)

        markup = float(self.global_markup_val)
        k_eng += markup; k_fin += markup
        markup_labels = {"0.0": "Базовый (+0%)", "0.15": "Повышающий (+15%)", "0.30": "Высокий (+30%)"}

        spec_lines = [f"Состояние: {clean_state_title.replace(' (база)', '').replace('(база)', '')}", f"Высота потолков: {'> 3.0 м (+10%)' if self.ceil_high_chip.selected else 'Стандарт до 3.0 м'}", f"Коэф. сложности: {markup_labels.get(self.global_markup_val, 'Базовый (+0%)')}"]

        num_rooms = max(len(self.rooms_data), 1)
        room_fin_k_sum, room_eng_k_sum = 0.0, 0.0

        for r in self.rooms_data:
            r_k_fin, r_k_eng = 0.0, 0.0
            titles = {"floor": "Не выбрано", "wall": "Не выбрано", "ceil": "Не выбрано", "door": "Не выбрано", "plinth": "Не выбрано", "custom": None, "sound_wall": "Нет", "sound_ceil": "Нет"}
            for key, t_dict in [("floor", "Ламинат"), ("wall", "Обои"), ("ceil", "Натяжной стандарт"), ("sound_wall", "Нет"), ("sound_ceil", "Нет")]:
                val = r.get(key)
                if val in ["base", None]: titles[key] = t_dict if val == "base" else ("Нет" if "sound" in key else "Не выбрано")
                elif val: 
                    k_e, k_f, titles[key] = self._apply_coef(val, 0.0, 0.0)
                    r_k_eng += k_e; r_k_fin += k_f

            for key in ["door", "plinth", "custom"]:
                val = r.get(key)
                if val and val != "base": 
                    k_e, k_f, titles[key] = self._apply_coef(val, 0.0, 0.0)
                    r_k_eng += k_e; r_k_fin += k_f

            room_fin_k_sum += r_k_fin; room_eng_k_sum += r_k_eng
            spec_lines.extend([f"\n• {r['name']}:", f"  - Шумка (Стены): {titles['sound_wall']}", f"  - Шумка (Потолок): {titles['sound_ceil']}", f"  - Пол: {titles['floor']}", f"  - Стены: {titles['wall']}", f"  - Потолок: {titles['ceil']}"])
            if titles.get("custom"):
                spec_lines.append(f"  - Доп. работа: {titles['custom']}")

        k_fin += (room_fin_k_sum / num_rooms)
        k_eng += (room_eng_k_sum / num_rooms)

        num_baths = max(len(self.bathrooms_data), 1)
        bath_fin_sum, bath_eng_sum = 0.0, 0.0
        for b in self.bathrooms_data:
            titles = {"tile_floor": "Не выбрано", "tile_wall": "Не выбрано", "ceil": "Не выбрано"}
            for key, share in [("tile_floor", 0.4), ("tile_wall", 0.6), ("ceil", 0.1)]:
                val = b.get(key)
                if val == "base": titles[key] = "Формат 60х60" if "tile" in key else "Натяжной стандарт"
                elif val: 
                    k_e, k_f, titles[key] = self._apply_coef(val, 0.0, 0.0)
                    bath_fin_sum += k_f * share; bath_eng_sum += k_e * share
            spec_lines.extend([f"\n• {b['name']}:", f"  - Пол: {titles['tile_floor']}", f"  - Стены: {titles['tile_wall']}", f"  - Потолок: {titles['ceil']}"])

        k_fin += (bath_fin_sum / num_baths) * 0.3
        k_eng += (bath_eng_sum / num_baths) * 0.3

        rate_eng_work = base_eng_work * (1.0 + k_eng)
        rate_fin_work = base_fin_work * (1.0 + k_fin)
        total_eng_work = rate_eng_work * area
        total_fin_work = rate_fin_work * area

        pct_eng = float(rates.get("eng_mat_pct", 85.0)) / 100.0
        pct_fin = float(rates.get("fin_mat_pct", 120.0)) / 100.0
        
        total_eng_mat = total_eng_work * pct_eng
        total_fin_mat = total_fin_work * pct_fin

        if selected_type == "whitebox":
            total_eng_work = total_eng_work * 0.6
            total_eng_mat = total_eng_mat * 0.6

        total_eng = total_eng_work + total_eng_mat
        total_fin = total_fin_work + total_fin_mat

        f_cost, a_cost = 0.0, 0.0
        if selected_type in ["complex", "whitebox"]:
            repair_total = total_eng + total_fin
            furn_val = self.furniture_dropdown.value
            if furn_val == "market": f_cost = repair_total * (furn_market_pct / 100.0)
            elif furn_val == "aggr": f_cost = repair_total * (furn_aggr_pct / 100.0)
            elif furn_val == "custom": f_cost = repair_total * (furn_custom_pct / 100.0)

            app_val = self.appliances_dropdown.value
            if app_val == "base": a_cost = repair_total * (app_base_pct / 100.0)
            elif app_val == "mid": a_cost = repair_total * (app_mid_pct / 100.0)
            elif app_val == "prem": a_cost = repair_total * (app_prem_pct / 100.0)

        extras_total = f_cost + a_cost
        
        if selected_type == "engineering":
            total_active = total_eng
            type_label = "Инженерный ремонт"
            self.eng_part_text.visible, self.fin_part_text.visible, self.extras_part_text.visible = True, False, False
        elif selected_type == "finishing":
            total_active = total_fin
            type_label = "Отделочные работы"
            self.eng_part_text.visible, self.fin_part_text.visible, self.extras_part_text.visible = False, True, False
        elif selected_type == "whitebox":
            total_active = total_eng + total_fin + extras_total
            type_label = "Сохранение Вайтбокса (Отделка + 60% Инженерии)"
            self.eng_part_text.visible, self.fin_part_text.visible, self.extras_part_text.visible = True, True, True
        else:
            total_active = total_eng + total_fin + extras_total
            type_label = "Комплекс (Инженерия + Отделка)"
            self.eng_part_text.visible, self.fin_part_text.visible, self.extras_part_text.visible = True, True, True

        rate_active = total_active / area if area > 0 else 0

        self.selected_type_badge.content.value = type_label
        self.total_cost_text.value = f"{int(round(total_active)):,} ₽".replace(",", " ")
        self.rate_per_m2_text.value = f"{int(round(rate_active)):,} ₽/м²".replace(",", " ")
        self.range_text.value = f"Ориентир ~70%: от {int(round(total_active * 0.85)):,} до {int(round(total_active * 1.15)):,} ₽".replace(",", " ")
        
        eng_label = "Инженерия (60%)" if selected_type == "whitebox" else "Инженерия"
        self.eng_part_text.value = f"{eng_label}: {int(round(total_eng)):,} ₽ (Работа: {int(round(total_eng_work)):,} ₽ | Мат: {int(round(total_eng_mat)):,} ₽)"
        self.fin_part_text.value = f"Отделка: {int(round(total_fin)):,} ₽ (Работа: {int(round(total_fin_work)):,} ₽ | Мат: {int(round(total_fin_mat)):,} ₽)"
        self.extras_part_text.value = f"Опции под ключ: {int(round(extras_total)):,} ₽"

        summary_controls = []
        for line in spec_lines:
            if line.startswith("\n•") or line.startswith("•"): summary_controls.extend([ft.Container(height=4), ft.Text(line.strip(), size=12, weight=ft.FontWeight.BOLD, color="#1E293B")])
            elif line.startswith("  -"): summary_controls.append(ft.Container(padding=ft.padding.only(left=12), content=ft.Text(line.strip(), size=11, color="#475569")))
            else: summary_controls.append(ft.Text(line, size=12, color="#334155"))
        self.summary_list.controls = summary_controls

        current_repair_state.area = area
        current_repair_state.total_eng = total_eng_work
        current_repair_state.total_fin = total_fin_work
        current_repair_state.eng_mat_cost = total_eng_mat
        current_repair_state.fin_mat_cost = total_fin_mat
        current_repair_state.grand_total = total_active
        current_repair_state.selected_type = selected_type
        current_repair_state.state_title = clean_state_title
        current_repair_state.has_demolition = ("demo" in str(self.state_dropdown.value).lower() or "вторичка" in clean_state_title.lower() or "частичн" in clean_state_title.lower())
        current_repair_state.furniture_cost = f_cost
        current_repair_state.appliances_cost = a_cost

    def open_estimate_dialog(self, e):
        if current_repair_state.area <= 0: return e.page.show_snack_bar(ft.SnackBar(ft.Text("Сначала укажите площадь!"), duration=2000))
        address_input = ft.TextField(label="ЖК / Адрес", value=current_repair_state.address or "", hint_text="Например: ЖК «Тринити», кв. 42", height=48, text_size=13, filled=True, fill_color="#F8FAFC", border_radius=12)
        client_input = ft.TextField(label="Имя заказчика", value=current_repair_state.client_name or "", hint_text="Например: Александр", height=48, text_size=13, filled=True, fill_color="#F8FAFC", border_radius=12)
        status_label = ft.Text("", size=12, color="#0C66E4")
        gen_prog = ft.ProgressBar(visible=False, color="#0C66E4")

        def on_confirm_generate(dlg_e):
            addr, cl_name = address_input.value.strip() or "Объект", client_input.value.strip() or "Заказчик"
            current_repair_state.address, current_repair_state.client_name = addr, cl_name
            submit_btn.disabled = True
            gen_prog.visible, status_label.value, status_label.color = True, "Генерация...", "#0C66E4"
            dlg_e.page.update()
            try:
                if current_repair_state.selected_type == "whitebox":
                    res = generate_whitebox_estimate_presentation({
                        "repair_type": current_repair_state.selected_type, "area": current_repair_state.area,
                        "eng_cost": current_repair_state.total_eng, "fin_cost": current_repair_state.total_fin,
                        "eng_mat_cost": current_repair_state.eng_mat_cost, "fin_mat_cost": current_repair_state.fin_mat_cost,
                        "furniture_cost": current_repair_state.furniture_cost, "appliances_cost": current_repair_state.appliances_cost,
                        "has_demolition": current_repair_state.has_demolition, "address": addr, "client_name": cl_name, "state": current_repair_state.state_title,
                    })
                else:
                    res = generate_universal_estimate_presentation({
                        "repair_type": current_repair_state.selected_type, "area": current_repair_state.area,
                        "eng_cost": current_repair_state.total_eng, "fin_cost": current_repair_state.total_fin,
                        "eng_mat_cost": current_repair_state.eng_mat_cost, "fin_mat_cost": current_repair_state.fin_mat_cost,
                        "furniture_cost": current_repair_state.furniture_cost, "appliances_cost": current_repair_state.appliances_cost,
                        "has_demolition": current_repair_state.has_demolition, "address": addr, "client_name": cl_name, "state": current_repair_state.state_title,
                    })
                    
                dialog.open = False
                dlg_e.page.update()
                success_dlg = ft.AlertDialog(title=ft.Row([ft.Icon(ft.icons.CHECK_CIRCLE_ROUNDED, color="#15803D", size=24), ft.Text("Смета создана!", size=16, weight=ft.FontWeight.BOLD)], spacing=8), content=ft.Container(width=440, content=ft.Column(tight=True, spacing=12, controls=[ft.Text(f"Файл: {res['title']}", size=12, weight=ft.FontWeight.W_600, color="#1E293B"), ft.ElevatedButton("📄 Открыть PDF", icon=ft.icons.PICTURE_AS_PDF_ROUNDED, bgcolor="#0C66E4", color="#FFFFFF", height=44, style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10)), url=res["pdf_url"]), ft.OutlinedButton("🖥 Открыть Презентацию", icon=ft.icons.OPEN_IN_NEW_ROUNDED, height=44, style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10)), url=res["edit_url"])])), actions=[ft.TextButton("Закрыть", on_click=lambda ev: setattr(success_dlg, "open", False) or ev.page.update())])
                if success_dlg not in dlg_e.page.overlay: dlg_e.page.overlay.append(success_dlg)
                success_dlg.open = True
                dlg_e.page.update()
            except Exception as ex:
                status_label.value, status_label.color, submit_btn.disabled, gen_prog.visible = f"Ошибка: {ex}", "#DC2626", False, False
                dlg_e.page.update()

        submit_btn = ft.ElevatedButton("Создать", icon=ft.icons.SLIDESHOW_ROUNDED, bgcolor="#15803D", color="#FFFFFF", height=44, style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10)), on_click=on_confirm_generate)
        dialog = ft.AlertDialog(title=ft.Row([ft.Icon(ft.icons.REQUEST_QUOTE_ROUNDED, color="#15803D", size=22), ft.Text("Смета", size=16, weight=ft.FontWeight.BOLD)], spacing=8), content=ft.Container(width=420, content=ft.Column(tight=True, spacing=12, controls=[ft.Text(f"Параметры: {current_repair_state.area:g} м² | {self.total_cost_text.value}", size=12, color="#64748B"), address_input, client_input, gen_prog, status_label])), actions=[ft.TextButton("Отмена", on_click=lambda ev: setattr(dialog, "open", False) or ev.page.update()), submit_btn], actions_alignment=ft.MainAxisAlignment.END)
        if dialog not in e.page.overlay: e.page.overlay.append(dialog)
        dialog.open = True
        e.page.update()

    def copy_summary_to_clipboard(self, e):
        raw_lines = [c.value if isinstance(c, ft.Text) else f"  {c.content.value}" for c in self.summary_list.controls if isinstance(c, ft.Text) or (isinstance(c, ft.Container) and isinstance(c.content, ft.Text))]
        text = f"📊 ПОКОМНАТНЫЙ РАСЧЕТ РЕМОНТА\nПлощадь: {self.area_input.value or '0'} м²\nСтавка: {self.rate_per_m2_text.value}\nИтого: {self.total_cost_text.value}\n\nСпецификация:\n" + "\n".join(raw_lines)
        e.page.set_clipboard(text)
        e.page.show_snack_bar(ft.SnackBar(ft.Text("Скопировано!"), duration=2000))

    def refresh_settings(self, e):
        e.page.show_snack_bar(ft.SnackBar(ft.Text("Загрузка актуальных тарифов из Google Таблиц..."), duration=2000))
        e.page.update()
        
        # ИСПРАВЛЕНИЕ: Принудительное удаление старого файла кэша перед обновлением
        try:
            local_db_path = RepairDataSync.get_local_path()
            if os.path.exists(local_db_path):
                os.remove(local_db_path)
        except Exception:
            pass

        self.settings = load_base_rates_and_coefficients()
        self.state_options = self._build_options_list("state_")
        if not self.state_options: self.state_options = [("base", "Голый бетон")]
        
        self.state_dropdown.options = [ft.dropdown.Option(k, v) for k, v in self.state_options]
        self.part_dropdown.options = [ft.dropdown.Option(k, v) for k, v in self._build_options_list("part_", "База (Пеноблок)")]
        self.screed_dropdown.options = [ft.dropdown.Option(k, v) for k, v in self._build_options_list("screed_", "База (Полусухая)")]
        self.manifold_dropdown.options = [ft.dropdown.Option(k, v) for k, v in self._build_options_list("manifold_", "Комфорт (База)")]
        
        valid_state_keys = [k for k, v in self.state_options]
        if self.state_dropdown.value not in valid_state_keys:
            self.state_dropdown.value = valid_state_keys[0] if valid_state_keys else "base"
            
        self.rebuild_room_data_structures()
        self.recalculate()
        self.update()
        e.page.show_snack_bar(ft.SnackBar(ft.Text("Тарифы успешно обновлены!"), duration=2000))