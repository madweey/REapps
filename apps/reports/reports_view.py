import threading
from datetime import datetime, timedelta
import flet as ft

from apps.reports.reports_api import fetch_deals_data_full
from apps.reports.reports_rejects import is_rejected, filter_rejected, get_reject_reason
from apps.reports.reports_contracts import evaluate_contract
from apps.reports.reports_leads import is_target_lead, parse_area

def ReportsDashboardView(page: ft.Page):
    state = {
        "headers": [],
        "raw_data": [],
        "start_date": None,
        "end_date": None,
        "active_detail": None, 
        "columns_config": [], 
        "target_excluded_reasons": [], 
        "reject_included_reasons": [], 
        "contract_filter_mode": "by_signing", 
        "contract_types": {"dp": True, "rem1": True, "rem2": True}
    }
    
    status_text = ft.Text("Загрузка данных из таблицы...", size=14, color="#64748B")
    loading_ring = ft.ProgressRing(width=24, height=24, stroke_width=3, color="#0C66E4")
    loading_view = ft.Row([loading_ring, status_text], alignment=ft.MainAxisAlignment.CENTER)

    total_leads_val = ft.Text("0", size=32, weight=ft.FontWeight.BOLD, color="#1E293B")
    target_leads_val = ft.Text("0", size=32, weight=ft.FontWeight.BOLD, color="#0C66E4")
    signed_val = ft.Text("0", size=32, weight=ft.FontWeight.BOLD, color="#15803D")
    rejected_val = ft.Text("0", size=32, weight=ft.FontWeight.BOLD, color="#DC2626")
    
    budget_val = ft.Text("0 ₽", size=20, weight=ft.FontWeight.W_700, color="#1E293B")
    area_val = ft.Text("0 м²", size=20, weight=ft.FontWeight.W_700, color="#1E293B")

    detail_title = ft.Text("", size=18, weight=ft.FontWeight.BOLD, color="#1E293B")
    data_table_wrapper = ft.Row(scroll=ft.ScrollMode.ALWAYS)
    detail_filters_row = ft.Row(spacing=10, wrap=True)
    
    detail_section = ft.Column([
        ft.Divider(height=1, color="#E2E8F0"),
        ft.Row([detail_title, ft.Container(expand=True), detail_filters_row]),
        ft.Container(content=data_table_wrapper, border=ft.border.all(1, "#E2E8F0"), border_radius=12, padding=10)
    ], visible=False)

    def get_row_flags(r, start_dt, end_dt):
        d = r.get("_date_obj")
        in_creation = False
        if start_dt and end_dt:
            if d and (start_dt.replace(hour=0, minute=0, second=0) <= d <= end_dt.replace(hour=23, minute=59, second=59)):
                in_creation = True
        elif not start_dt:
            in_creation = True
            
        is_contract, c_budget = evaluate_contract(
            r, state["contract_filter_mode"], state["contract_types"], 
            start_dt, end_dt, in_creation
        )
        is_rej = is_rejected(r)
        is_target = is_target_lead(r, state["target_excluded_reasons"])
        
        return in_creation, is_contract, c_budget, is_rej, is_target

    def calculate_metrics():
        if not state["raw_data"]: return
        start_dt, end_dt = state["start_date"], state["end_date"]
        
        total = target = signed = rejected = 0
        sum_budget = sum_area = 0.0
        
        for r in state["raw_data"]:
            in_creation, is_contract, c_budget, is_rej, is_target = get_row_flags(r, start_dt, end_dt)

            if is_contract:
                signed += 1
                sum_budget += c_budget

            if in_creation:
                total += 1
                if is_rej: rejected += 1
                if is_target: target += 1
                sum_area += parse_area(r.get("S, м2", "0"))

        total_leads_val.value = str(total)
        target_leads_val.value = str(target)
        signed_val.value = str(signed)
        rejected_val.value = str(rejected)
        budget_val.value = f"{int(sum_budget):,} ₽".replace(",", " ")
        area_val.value = f"{sum_area:g} м²"
        
        refresh_data_table()
        page.update()

    def build_metric_card(title: str, val_control: ft.Control, icon: str, bg_color: str, icon_color: str, mode_key: str):
        def on_click(e):
            state["active_detail"] = mode_key
            refresh_data_table()
        return ft.Container(
            expand=True, bgcolor="#FFFFFF", border=ft.border.all(1, "#E2E8F0"), border_radius=16, padding=20,
            on_click=on_click, ink=True,
            content=ft.Column([
                ft.Row([
                    ft.Container(bgcolor=bg_color, padding=8, border_radius=8, content=ft.Icon(icon, color=icon_color, size=20)),
                    ft.Text(title, size=13, weight=ft.FontWeight.W_600, color="#64748B", expand=True)
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                ft.Container(height=8), val_control
            ])
        )

    def set_preset_dates(preset: str):
        now = datetime.now()
        if preset == "today": return now, now
        if preset == "week": return now - timedelta(days=now.weekday()), now
        if preset == "month": return now.replace(day=1), now
        return None, None

    date_start_picker = ft.DatePicker(on_change=lambda e: update_custom_dates())
    date_end_picker = ft.DatePicker(on_change=lambda e: update_custom_dates())
    page.overlay.extend([date_start_picker, date_end_picker])

    btn_start_date = ft.OutlinedButton("Дата С", icon=ft.icons.CALENDAR_TODAY, on_click=lambda e: date_start_picker.pick_date(), visible=False)
    btn_end_date = ft.OutlinedButton("Дата ПО", icon=ft.icons.CALENDAR_TODAY, on_click=lambda e: date_end_picker.pick_date(), visible=False)

    def update_custom_dates():
        if date_start_picker.value:
            btn_start_date.text = date_start_picker.value.strftime("%d.%m.%Y")
            state["start_date"] = date_start_picker.value
        if date_end_picker.value:
            btn_end_date.text = date_end_picker.value.strftime("%d.%m.%Y")
            state["end_date"] = date_end_picker.value
        calculate_metrics()

    def on_period_change(e):
        val = period_dropdown.value
        if val == "custom":
            btn_start_date.visible = True
            btn_end_date.visible = True
        else:
            btn_start_date.visible = False
            btn_end_date.visible = False
            sd, ed = set_preset_dates(val)
            state["start_date"], state["end_date"] = sd, ed
            calculate_metrics()
        page.update()

    period_dropdown = ft.Dropdown(
        value="month", width=200, height=40, text_size=13, content_padding=10, border_radius=8,
        options=[
            ft.dropdown.Option("today", "Сегодня"), ft.dropdown.Option("week", "Текущая неделя"),
            ft.dropdown.Option("month", "Текущий месяц"), ft.dropdown.Option("all", "За всё время"),
            ft.dropdown.Option("custom", "Произвольный период"),
        ],
        on_change=on_period_change
    )
    state["start_date"], state["end_date"] = set_preset_dates("month")

    # ================= УНИВЕРСАЛЬНЫЙ DRAG & ДОП ДИАЛОГ ==================
    def build_draggable_list_dialog(title_text, desc_text, all_items, selected_items, on_save_callback):
        selected_list = [x for x in selected_items if x in all_items]
        unselected_list = [x for x in all_items if x not in selected_list]
        
        list_view = ft.ListView(spacing=8, height=450, padding=10)
        dlg = ft.AlertDialog(modal=True)

        def render_list():
            list_view.controls.clear()
            if desc_text:
                list_view.controls.append(ft.Text(desc_text, size=12, color="#64748B"))
                list_view.controls.append(ft.Container(height=5))
                
            # БЛОК 1: ВЫБРАННЫЕ ФИЛЬТРЫ
            list_view.controls.append(ft.Text("Выбранные фильтры", weight=ft.FontWeight.BOLD, size=14, color="#0F172A"))
            if not selected_list:
                list_view.controls.append(ft.Text("Ничего не выбрано", color="#94A3B8", size=12, italic=True))

            for i, name in enumerate(selected_list):
                def make_on_accept(target_idx):
                    def _on_accept(e):
                        src_ctrl = page.get_control(e.src_id)
                        dragged = src_ctrl.data
                        if dragged in selected_list:
                            src_idx = selected_list.index(dragged)
                            selected_list.pop(src_idx)
                            selected_list.insert(target_idx, dragged)
                            render_list()
                    return _on_accept
                
                def make_on_will_accept():
                    def _on_will_accept(e):
                        e.control.content.content.border = ft.border.all(2, "#0C66E4")
                        e.control.update()
                    return _on_will_accept
                    
                def make_on_leave():
                    def _on_leave(e):
                        e.control.content.content.border = ft.border.all(1, "#E2E8F0")
                        e.control.update()
                    return _on_leave

                def make_uncheck(item_name):
                    def _uncheck(ev):
                        selected_list.remove(item_name)
                        unselected_list.insert(0, item_name)
                        render_list()
                    return _uncheck

                item_content = ft.Container(
                    padding=ft.padding.symmetric(horizontal=10, vertical=6),
                    border=ft.border.all(1, "#E2E8F0"), border_radius=8, bgcolor="#F8FAFC",
                    content=ft.Row([
                        ft.Icon(ft.icons.DRAG_INDICATOR, color="#64748B", size=20, tooltip="Зажмите и двигайте для смены порядка"),
                        ft.Checkbox(value=True, on_change=make_uncheck(name)),
                        ft.Text(name, expand=True, size=13, weight=ft.FontWeight.W_600, color="#1E293B"),
                    ])
                )
                
                drag_ctrl = ft.Draggable(group="dnd", data=name, content=item_content, content_when_dragging=ft.Container(opacity=0.4, content=item_content))
                drop_target = ft.DragTarget(group="dnd", content=drag_ctrl, on_accept=make_on_accept(i), on_will_accept=make_on_will_accept(), on_leave=make_on_leave())
                list_view.controls.append(drop_target)

            # РАЗДЕЛИТЕЛЬНАЯ ЧЕРТА
            list_view.controls.append(ft.Divider(height=28, thickness=1.5, color="#CBD5E1"))
            
            # БЛОК 2: НЕИСПОЛЬЗОВАННЫЕ ФИЛЬТРЫ
            list_view.controls.append(ft.Text("Неиспользованные фильтры", weight=ft.FontWeight.BOLD, size=14, color="#0F172A"))
            
            if not unselected_list:
                list_view.controls.append(ft.Text("Все элементы задействованы", color="#94A3B8", size=12, italic=True))

            for name in unselected_list:
                def make_check(item_name):
                    def _check(ev):
                        unselected_list.remove(item_name)
                        selected_list.append(item_name)
                        render_list()
                    return _check

                list_view.controls.append(
                    ft.Container(
                        padding=ft.padding.symmetric(horizontal=10, vertical=6),
                        border=ft.border.all(1, "#E2E8F0"), border_radius=8, bgcolor="#FFFFFF",
                        content=ft.Row([
                            ft.Icon(ft.icons.DRAG_INDICATOR, color=ft.colors.TRANSPARENT, size=20),
                            ft.Checkbox(value=False, on_change=make_check(name)),
                            ft.Text(name, expand=True, size=13, color="#64748B"),
                        ])
                    )
                )
            page.update()

        def save_and_close(e):
            dlg.open = False
            page.update()
            on_save_callback(selected_list.copy(), unselected_list.copy())

        render_list()
        dlg.title = ft.Text(title_text, size=16, weight=ft.FontWeight.BOLD)
        dlg.content = ft.Container(width=450, height=520, content=list_view)
        dlg.actions = [
            ft.TextButton("Отмена", on_click=lambda e: (setattr(dlg, 'open', False), page.update())), 
            ft.TextButton("Сохранить", on_click=save_and_close)
        ]
        page.overlay.append(dlg)
        dlg.open = True
        page.update()

    def open_columns_selector(e):
        all_cols = [c["name"] for c in state["columns_config"]]
        selected_cols = [c["name"] for c in state["columns_config"] if c["visible"]]
        def on_save(selected, unselected):
            new_cfg = [{"name": c, "visible": True} for c in selected]
            new_cfg.extend([{"name": c, "visible": False} for c in unselected])
            state["columns_config"] = new_cfg
            refresh_data_table()
        build_draggable_list_dialog("Настройка столбцов", "Зажмите иконку ⠿ у выбранных столбцов, чтобы перетащить их в нужное место.", all_cols, selected_cols, on_save)

    def open_target_exclusion_filter(e):
        unique_reasons = sorted(set(get_reject_reason(r) for r in state["raw_data"] if is_rejected(r)))
        def on_save(selected, unselected):
            state["target_excluded_reasons"] = selected
            calculate_metrics()
        build_draggable_list_dialog("Исключить нецелевые отказы", "Эти причины отказов НЕ будут считаться целевыми лидами:", unique_reasons, state["target_excluded_reasons"], on_save)

    def open_reject_inclusion_filter(e):
        unique_reasons = sorted(set(get_reject_reason(r) for r in state["raw_data"] if is_rejected(r)))
        def on_save(selected, unselected):
            state["reject_included_reasons"] = selected
            refresh_data_table()
        build_draggable_list_dialog("Фильтр причин отказа", "Выберите причины для отображения в таблице:", unique_reasons, state["reject_included_reasons"], on_save)

    def open_contract_filters(e):
        mode_dropdown = ft.Dropdown(
            value=state["contract_filter_mode"],
            options=[
                ft.dropdown.Option("by_signing", "Общие договора (по дате подписания)"),
                ft.dropdown.Option("by_creation", "Заявка/договор (по дате захода лида)"),
            ],
            width=380, height=45, text_size=13
        )
        dp_cb = ft.Checkbox(label="ДП", value=state["contract_types"]["dp"])
        r1_cb = ft.Checkbox(label="Ремонт 1 (Инженерка)", value=state["contract_types"]["rem1"])
        r2_cb = ft.Checkbox(label="Ремонт 2 (Отделка)", value=state["contract_types"]["rem2"])

        def on_save(ev):
            state["contract_filter_mode"] = mode_dropdown.value
            state["contract_types"]["dp"] = dp_cb.value
            state["contract_types"]["rem1"] = r1_cb.value
            state["contract_types"]["rem2"] = r2_cb.value
            dlg.open = False
            calculate_metrics()

        dlg = ft.AlertDialog(
            title=ft.Text("Параметры договоров", weight=ft.FontWeight.BOLD, size=16),
            content=ft.Container(
                width=400,
                content=ft.Column([
                    ft.Text("Режим расчета периода:", weight=ft.FontWeight.W_600, size=13),
                    mode_dropdown,
                    ft.Container(height=10),
                    ft.Text("Учитывать типы договоров:", weight=ft.FontWeight.W_600, size=13),
                    dp_cb, r1_cb, r2_cb
                ], tight=True)
            ),
            actions=[ft.TextButton("Применить", on_click=on_save)]
        )
        page.overlay.append(dlg)
        dlg.open = True
        page.update()

    def refresh_data_table():
        if not state["active_detail"]:
            detail_section.visible = False
            page.update()
            return

        detail_section.visible = True
        detail_filters_row.controls.clear()
        
        btn_cols = ft.OutlinedButton("Настроить столбцы", icon=ft.icons.VIEW_COLUMN_ROUNDED, on_click=open_columns_selector, height=36)
        detail_filters_row.controls.append(btn_cols)

        display_rows = []
        mode = state["active_detail"]
        start_dt, end_dt = state["start_date"], state["end_date"]
        
        for r in state["raw_data"]:
            in_creation, is_contract, c_budget, is_rej, is_target = get_row_flags(r, start_dt, end_dt)

            if mode == "target":
                if not in_creation or not is_target: continue
            elif mode == "signed":
                if not is_contract: continue
            elif mode == "rejected":
                if not in_creation or not is_rej: continue
                if not filter_rejected(r, state["reject_included_reasons"]): continue
            elif mode == "all":
                if not in_creation: continue

            display_rows.append(r)

        if mode == "all": detail_title.value = f"Все лиды ({len(display_rows)})"
        elif mode == "target": 
            detail_title.value = f"Целевые лиды ({len(display_rows)})"
            detail_filters_row.controls.insert(0, ft.OutlinedButton("Логика целевых", icon=ft.icons.FILTER_ALT_ROUNDED, on_click=open_target_exclusion_filter, height=36))
        elif mode == "signed": 
            detail_title.value = f"Договоры ({len(display_rows)})"
            detail_filters_row.controls.insert(0, ft.OutlinedButton("Параметры договоров", icon=ft.icons.SETTINGS_ROUNDED, on_click=open_contract_filters, height=36))
        elif mode == "rejected": 
            detail_title.value = f"Отказы ({len(display_rows)})"
            detail_filters_row.controls.insert(0, ft.OutlinedButton("Фильтр причин", icon=ft.icons.FILTER_ALT_ROUNDED, on_click=open_reject_inclusion_filter, height=36))

        visible_cols_config = [c for c in state["columns_config"] if c["visible"]]
        columns = [ft.DataColumn(ft.Text(c["name"], weight=ft.FontWeight.BOLD)) for c in visible_cols_config]
        rows = []
        
        for r in display_rows[:300]: 
            cells = []
            for c in visible_cols_config:
                col_name = c["name"]
                val = str(r.get(col_name, ""))
                if "http" in val:
                    content_ui = ft.Text("Ссылка", color="#0C66E4", style=ft.TextStyle(decoration=ft.TextDecoration.UNDERLINE), selectable=True)
                    cell = ft.DataCell(ft.Container(content=content_ui, width=150, clip_behavior=ft.ClipBehavior.HARD_EDGE), on_tap=lambda e, url=val: page.launch_url(url))
                else:
                    content_ui = ft.Text(val, size=12, selectable=True)
                    cell = ft.DataCell(ft.Container(content=content_ui, width=180, clip_behavior=ft.ClipBehavior.HARD_EDGE))
                cells.append(cell)
            rows.append(ft.DataRow(cells=cells))

        if not rows:
            data_table_wrapper.controls = [ft.Text("Нет данных по заданным фильтрам", color="#64748B", italic=True)]
        else:
            data_table_wrapper.controls = [ft.DataTable(columns=columns, rows=rows, column_spacing=20, heading_row_height=40, data_row_max_height=48)]
            
        page.update()

    cards_row = ft.Row([
        build_metric_card("Всего лидов", total_leads_val, ft.icons.PEOPLE_ALT_ROUNDED, "#F1F5F9", "#64748B", "all"),
        build_metric_card("Целевые", target_leads_val, ft.icons.STAR_ROUNDED, "#EFF6FF", "#0C66E4", "target"),
        build_metric_card("Договоры", signed_val, ft.icons.VERIFIED_ROUNDED, "#F0FDF4", "#15803D", "signed"),
        build_metric_card("Отказы", rejected_val, ft.icons.CANCEL_ROUNDED, "#FEF2F2", "#DC2626", "rejected"),
    ], spacing=16)

    filter_row = ft.Row([
        ft.Text("Период:", size=14, weight=ft.FontWeight.W_600, color="#334155"),
        period_dropdown, btn_start_date, btn_end_date,
        ft.Container(expand=True),
        ft.OutlinedButton("Обновить из таблицы", icon=ft.icons.REFRESH_ROUNDED, height=40, on_click=lambda e: load_data_thread())
    ], vertical_alignment=ft.CrossAxisAlignment.CENTER)

    main_content = ft.Column([
        ft.Text("Аналитика Сделок", size=24, weight=ft.FontWeight.BOLD, color="#0F172A"),
        ft.Container(height=8), filter_row, ft.Container(height=16), cards_row, ft.Container(height=16),
        ft.Row([
            ft.Container(expand=True, bgcolor="#FFFFFF", border=ft.border.all(1, "#E2E8F0"), border_radius=16, padding=24, content=ft.Column([ft.Text("Касса (ДП + Ремонт)", size=14, weight=ft.FontWeight.BOLD, color="#64748B"), budget_val])),
            ft.Container(expand=True, bgcolor="#FFFFFF", border=ft.border.all(1, "#E2E8F0"), border_radius=16, padding=24, content=ft.Column([ft.Text("Суммарная площадь", size=14, weight=ft.FontWeight.BOLD, color="#64748B"), area_val]))
        ], spacing=16),
        detail_section
    ], visible=False)

    def load_data_thread():
        main_content.visible = False
        loading_view.visible = True
        state["active_detail"] = None
        page.update()
        
        def _worker():
            try:
                headers, raw = fetch_deals_data_full()
                state["headers"] = headers
                state["raw_data"] = raw
                
                if not state["columns_config"]:
                    default_visible = ["Ссылка на сделку", "ID сделки", "Название ЖК", "Имя воронки", "Имя ответственного"]
                    for h in headers:
                        if h:
                            state["columns_config"].append({
                                "name": h,
                                "visible": h in default_visible
                            })
                            
                calculate_metrics()
                loading_view.visible = False
                main_content.visible = True
            except Exception as ex:
                status_text.value = f"Ошибка загрузки данных: {ex}"
                status_text.color = "#DC2626"
                loading_ring.visible = False
            page.update()
            
        threading.Thread(target=_worker, daemon=True).start()

    load_data_thread()

    return ft.Container(padding=30, content=ft.Column([loading_view, main_content], expand=True, scroll=ft.ScrollMode.AUTO), expand=True)