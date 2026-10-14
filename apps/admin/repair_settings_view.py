import re
import flet as ft
from apps.core.sheets import RepairDataSync

PREFIX_MAP = {
    "Общие: Состояние объекта": "state",
    "Общие: Перегородки": "part",
    "Общие: Стяжка пола": "screed",
    "Общие: Сантех. узел": "manifold",
    "Жилые комнаты: Пол": "floor",
    "Жилые комнаты: Стены": "wall",
    "Жилые комнаты: Потолок": "ceil",
    "Жилые комнаты: Двери": "door",
    "Жилые комнаты: Плинтус": "plinth",
    "Жилые комнаты: Шумоизоляция (Стены)": "soundwall",
    "Жилые комнаты: Шумоизоляция (Потолок)": "soundceil",
    "Санузлы: Керамогранит (Пол/Стены)": "tile",
    "Санузлы: Потолок": "ceil",
    "Другое (Вручную)": "custom"
}

def transliterate(text: str) -> str:
    ru_map = {
        'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'e',
        'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm',
        'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
        'ф': 'f', 'х': 'h', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'sch',
        'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya', ' ': '_'
    }
    cleaned = str(text).lower().strip()
    result = []
    for ch in cleaned:
        if ch in ru_map:
            result.append(ru_map[ch])
        elif ch.isalnum() or ch == '_':
            result.append(ch)
    slug = "".join(result)
    slug = re.sub(r'_+', '_', slug).strip('_')
    return slug[:25]


class RepairSettingsView(ft.UserControl):
    def __init__(self, page: ft.Page):
        super().__init__()
        self.page = page
        self.data = RepairDataSync.get_data()
        self.data.setdefault("base_rates", {}).setdefault("custom_templates", [])
        self.status_msg = ft.Text("", size=13, weight=ft.FontWeight.BOLD)
        
        self.edit_dialog = ft.AlertDialog(
            modal=True, title=ft.Text(""), content=ft.Container()
        )
        if self.edit_dialog not in self.page.overlay:
            self.page.overlay.append(self.edit_dialog)

    def build(self):
        sync_btn = ft.ElevatedButton("Синхронизировать с Таблицей (Сохранить)", icon=ft.icons.CLOUD_UPLOAD_ROUNDED, bgcolor="#15803D", color="white", height=44, style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10)), on_click=self.on_sync_click)
        pull_btn = ft.OutlinedButton("Скачать из Таблицы", icon=ft.icons.CLOUD_DOWNLOAD_ROUNDED, height=44, style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10)), on_click=self.on_pull_click)

        self.tabs = ft.Tabs(
            selected_index=0, animation_duration=300,
            tabs=[
                ft.Tab(text="Базовые ставки", content=self.build_rates_tab()),
                ft.Tab(text="Работы", content=self.build_coeffs_tab()),
                ft.Tab(text="Этапы Инженерии", content=self.build_stages_tab("eng_stages")),
                ft.Tab(text="Этапы Отделки", content=self.build_stages_tab("fin_stages")),
            ], expand=True,
        )

        return ft.Container(
            padding=24, expand=True,
            content=ft.Column(
                spacing=16,
                controls=[
                    ft.Row([
                        ft.Column([
                            ft.Text("База работ ремонта", size=24, weight=ft.FontWeight.BOLD, color="#0F172A"),
                            ft.Text("Управление расценками, материалами и этапами (Локально + Облако)", size=13, color="#64748B"),
                        ], spacing=2, expand=True), pull_btn, sync_btn
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    self.status_msg,
                    ft.Container(bgcolor=ft.colors.WHITE, border=ft.border.all(1, "#E2E8F0"), border_radius=12, padding=10, content=self.tabs, expand=True)
                ]
            )
        )

    def on_sync_click(self, e):
        self.status_msg.value, self.status_msg.color = "Синхронизация с Google Таблицей...", "#0C66E4"
        self.update()
        try:
            RepairDataSync.save_and_push(self.data)
            self.status_msg.value, self.status_msg.color = "База успешно выгружена в Google Таблицу!", "#15803D"
        except Exception as ex:
            self.status_msg.value, self.status_msg.color = f"Ошибка выгрузки: {ex}", "#DC2626"
        self.update()

    def on_pull_click(self, e):
        self.status_msg.value, self.status_msg.color = "Скачивание данных из Google Таблицы...", "#0C66E4"
        self.update()
        try:
            self.data = RepairDataSync.pull_from_cloud()
            self.data.setdefault("base_rates", {}).setdefault("custom_templates", [])
            self.status_msg.value, self.status_msg.color = "База успешно обновлена из Google Таблицы!", "#15803D"
            self.refresh_ui()
        except Exception as ex:
            self.status_msg.value, self.status_msg.color = f"Ошибка скачивания: {ex}", "#DC2626"
            self.update()

    def refresh_ui(self):
        RepairDataSync.save_local_only(self.data)
        self.tabs.tabs[0].content = self.build_rates_tab()
        self.tabs.tabs[1].content = self.build_coeffs_tab()
        self.tabs.tabs[2].content = self.build_stages_tab("eng_stages")
        self.tabs.tabs[3].content = self.build_stages_tab("fin_stages")
        self.update()

    def build_rates_tab(self):
        def make_tf(label, key, default=""):
            def on_c(e):
                try:
                    self.data["base_rates"][key] = float(e.control.value.replace(",", "."))
                    RepairDataSync.save_local_only(self.data)
                except: pass
            return ft.TextField(label=label, value=str(self.data["base_rates"].get(key, default)), on_change=on_c, width=300, border_radius=8)

        def make_tf_str(label, key):
            def on_c(e):
                self.data["base_rates"][key] = e.control.value
                RepairDataSync.save_local_only(self.data)
            return ft.TextField(label=label, value=str(self.data["base_rates"].get(key, "")), on_change=on_c, width=420, border_radius=8)

        mat_pct_row = ft.Row([
            make_tf("Инженерия (Материалы % от работ)", "eng_mat_pct", "85.0"), 
            make_tf("Отделка (Материалы % от работ)", "fin_mat_pct", "120.0")
        ])

        custom_templates_list = self.data["base_rates"].setdefault("custom_templates", [])
        custom_template_controls = []

        for idx, ct in enumerate(custom_templates_list):
            def on_ct_name(e, i=idx):
                custom_templates_list[i]["name"] = e.control.value
                RepairDataSync.save_local_only(self.data)

            def on_ct_id(e, i=idx):
                custom_templates_list[i]["id"] = e.control.value
                RepairDataSync.save_local_only(self.data)

            def on_ct_del(e, i=idx):
                custom_templates_list.pop(i)
                self.refresh_ui()

            custom_template_controls.append(
                ft.Row([
                    ft.TextField(label="Название шаблона (в Таблице)", value=ct.get("name", ""), width=260, border_radius=8, on_change=on_ct_name),
                    ft.TextField(label="ID Шаблона Google Презентации", value=ct.get("id", ""), width=420, border_radius=8, on_change=on_ct_id),
                    ft.IconButton(ft.icons.DELETE_OUTLINE_ROUNDED, icon_color="#EF4444", tooltip="Удалить шаблон", on_click=on_ct_del),
                ], spacing=10)
            )

        def add_custom_template_field(e):
            custom_templates_list.append({"name": f"Шаблон Новый {len(custom_templates_list) + 1}", "id": ""})
            self.refresh_ui()

        return ft.ListView(
            padding=20, spacing=20,
            controls=[
                ft.Text("💰 Стоимость работ (База за м²)", weight=ft.FontWeight.BOLD, size=15, color="#1E293B"),
                ft.Row([make_tf("Инженерия (Работа)", "engineering_work", "25254.0"), make_tf("Отделка (Работа)", "finishing_work", "33024.0")]),
                
                ft.Text("🧱 Расчет черновых материалов (% от стоимости работ)", weight=ft.FontWeight.BOLD, size=15, color="#1E293B"),
                mat_pct_row,

                ft.Text("🛋 Мебель и Техника (% от итоговой стоимости ремонта)", weight=ft.FontWeight.BOLD, size=15, color="#1E293B"),
                ft.Row([make_tf("Мебель: Маркетплейс (%)", "furn_market", "20"), make_tf("Техника: Базовая (%)", "app_base", "10")]),
                ft.Row([make_tf("Мебель: Агрегаторы (%)", "furn_aggr", "25"), make_tf("Техника: Средняя (%)", "app_mid", "15")]),
                ft.Row([make_tf("Мебель: Индив. изготовление (%)", "furn_custom", "35"), make_tf("Техника: Премиум (%)", "app_prem", "25")]),

                ft.Divider(height=1, color="#E2E8F0"),
                ft.Row([
                    ft.Text("⚙ Системные настройки (ID Шаблонов и Папок)", weight=ft.FontWeight.BOLD, size=15, color="#1E293B"),
                    ft.OutlinedButton("Добавить поле шаблона", icon=ft.icons.ADD_ROUNDED, height=36, on_click=add_custom_template_field),
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                ft.Row([make_tf_str("Шаблон Инженерия", "template_eng"), make_tf_str("Шаблон Отделка", "template_fin")], wrap=True),
                ft.Row([make_tf_str("Шаблон Комплекс", "template_complex"), make_tf_str("Шаблон Вайтбокс", "template_whitebox")], wrap=True),
                make_tf_str("ID Папки Google Drive (для сохранения смет)", "folder_id"),
                *custom_template_controls,
            ]
        )

    def build_coeffs_tab(self):
        rows = []
        for idx, c in enumerate(self.data["coefficients"]):
            pct = int(round(c["value"] * 100))
            sign = "+" if pct > 0 else ""
            bg_col, fg_col = ("#EBF3FC", "#0C66E4") if pct > 0 else ("#F1F5F9", "#64748B")
            rows.append(
                ft.Container(
                    bgcolor="#F8FAFC", border=ft.border.all(1, "#E2E8F0"), border_radius=12, padding=12,
                    content=ft.Row([
                        ft.Column([ft.Text(c["name"], size=13, weight=ft.FontWeight.BOLD, color="#1E293B"), ft.Text(f"ID: {c['id']} | База: {c['type']}", size=11, color="#64748B")], expand=True, spacing=2),
                        ft.Container(content=ft.Text(f"{sign}{pct}%", weight=ft.FontWeight.BOLD, color=fg_col), bgcolor=bg_col, padding=6, border_radius=6),
                        ft.IconButton(ft.icons.EDIT_ROUNDED, icon_color="#0C66E4", on_click=lambda e, i=idx: self.open_coeff_editor(i)),
                        ft.IconButton(ft.icons.DELETE_ROUNDED, icon_color="#EF4444", on_click=lambda e, i=idx: self.delete_item("coefficients", i)),
                    ])
                )
            )
        return ft.Container(padding=20, content=ft.Column([ft.Row([ft.ElevatedButton("Добавить работу", icon=ft.icons.ADD, on_click=lambda e: self.open_coeff_editor(-1))]), ft.ListView(controls=rows, expand=True, spacing=8)]))

    def build_stages_tab(self, key_type="eng_stages"):
        rows = []
        for idx, s in enumerate(self.data[key_type]):
            rows.append(
                ft.Container(
                    bgcolor="#F8FAFC", border=ft.border.all(1, "#E2E8F0"), border_radius=12, padding=12,
                    content=ft.Row([
                        ft.Column([
                            ft.Text(f"{s['num']}. {s['title']}", size=13, weight=ft.FontWeight.BOLD, color="#1E293B"),
                            ft.Text(f"Доли: Работа {int(s['w_share']*100)}% | Мат. {int(s['m_share']*100)}% | Дней: {s['days']}", size=11, color="#64748B"),
                            ft.Text(f"Работы: {s['w_desc'][:60]}...", size=10, color="#94A3B8"),
                        ], expand=True, spacing=2),
                        ft.IconButton(ft.icons.EDIT_ROUNDED, icon_color="#0C66E4", on_click=lambda e, i=idx, kt=key_type: self.open_stage_editor(kt, i)),
                        ft.IconButton(ft.icons.DELETE_ROUNDED, icon_color="#EF4444", on_click=lambda e, i=idx, kt=key_type: self.delete_item(kt, i)),
                    ])
                )
            )
        return ft.Container(padding=20, content=ft.Column([ft.Row([ft.ElevatedButton("Добавить этап", icon=ft.icons.ADD, on_click=lambda e: self.open_stage_editor(key_type, -1))]), ft.ListView(controls=rows, expand=True, spacing=8)]))

    def delete_item(self, list_key, idx):
        self.data[list_key].pop(idx)
        self.status_msg.value, self.status_msg.color = "Удалено локально. Нажмите «Синхронизировать с Таблицей», чтобы отправить в облако.", "#D97706"
        self.refresh_ui()

    def open_coeff_editor(self, idx):
        is_new = (idx == -1)
        c = {"id": "", "name": "", "value": 0.0, "type": "Отделка"} if is_new else self.data["coefficients"][idx]

        init_cat = "Жилые комнаты: Стены"
        if not is_new:
            for cat_name, prefix in PREFIX_MAP.items():
                if c["id"].startswith(prefix + "_"):
                    init_cat = cat_name
                    break

        category_dd = ft.Dropdown(label="Где отображать? (Категория)", value=init_cat, options=[ft.dropdown.Option(k) for k in PREFIX_MAP.keys()], on_change=lambda e: update_preview())
        name_tf = ft.TextField(label="Название (например: Эпоксидная затирка)", value=c["name"], on_change=lambda e: update_preview())
        id_tf = ft.TextField(label="Системный ключ (ID)", value=c["id"], bgcolor="#F8FAFC")
        val_tf = ft.TextField(label="Надбавка (0.05 = 5%)", value=str(c["value"]), expand=True)
        type_dd = ft.Dropdown(label="Куда прибавлять деньги?", value=c["type"], options=[ft.dropdown.Option("Отделка"), ft.dropdown.Option("Инженерия"), ft.dropdown.Option("Все")], expand=True)

        def update_preview():
            if not name_tf.value.strip(): id_tf.value = ""
            else: id_tf.value = f"{PREFIX_MAP.get(category_dd.value, 'custom')}_{transliterate(name_tf.value)}"
            id_tf.update()

        def save(e):
            try: v = float(str(val_tf.value).replace(",", ".").replace(" ", ""))
            except: v = 0.0
            gen_id = id_tf.value.strip()
            if not gen_id:
                gen_id = f"{PREFIX_MAP.get(category_dd.value, 'custom')}_{transliterate(name_tf.value or 'item')}"
            new_c = {"id": gen_id, "name": name_tf.value.strip(), "value": v, "type": type_dd.value}
            if is_new: self.data["coefficients"].append(new_c)
            else: self.data["coefficients"][idx] = new_c
            self.edit_dialog.open = False
            self.status_msg.value, self.status_msg.color = f"Работа «{new_c['name']}» сохранена! Нажмите «Синхронизировать с Таблицей» для отправки в Google Sheets.", "#15803D"
            self.page.update()
            self.refresh_ui()

        self.edit_dialog.title = ft.Text("Добавить новую работу" if is_new else "Редактировать работу")
        self.edit_dialog.content = ft.Container(width=450, content=ft.Column([category_dd, name_tf, ft.Row([val_tf, type_dd], spacing=10), id_tf], tight=True, spacing=14))
        self.edit_dialog.actions = [ft.TextButton("Отмена", on_click=lambda e: setattr(self.edit_dialog, "open", False) or self.page.update()), ft.ElevatedButton("Сохранить", bgcolor="#15803D", color="white", on_click=save)]
        self.edit_dialog.open = True
        self.page.update()

    def open_stage_editor(self, list_key, idx):
        is_new = (idx == -1)
        s = {"num": len(self.data[list_key]) + 1, "title": "", "w_share": 0.0, "m_share": 0.0, "days": 10, "w_desc": "", "m_desc": ""} if is_new else self.data[list_key][idx]
        num_tf = ft.TextField(label="Номер", value=str(s["num"]), width=80)
        title_tf = ft.TextField(label="Название этапа", value=s["title"], expand=True)
        ws_tf = ft.TextField(label="Доля Работ (напр. 0.15)", value=str(s["w_share"]), width=170)
        ms_tf = ft.TextField(label="Доля Мат. (напр. 0.12)", value=str(s["m_share"]), width=170)
        d_tf = ft.TextField(label="Срок/Вес (дней)", value=str(s["days"]), width=140)
        wd_tf = ft.TextField(label="Описание работ", value=s["w_desc"], multiline=True)
        md_tf = ft.TextField(label="Описание материалов", value=s["m_desc"], multiline=True)

        def save(e):
            try:
                new_s = {"num": int(num_tf.value), "title": title_tf.value, "w_share": float(ws_tf.value.replace(",", ".")), "m_share": float(ms_tf.value.replace(",", ".")), "days": float(d_tf.value.replace(",", ".")), "w_desc": wd_tf.value, "m_desc": md_tf.value}
                if is_new: self.data[list_key].append(new_s)
                else: self.data[list_key][idx] = new_s
                self.edit_dialog.open = False
                self.status_msg.value, self.status_msg.color = f"Этап «{new_s['title']}» сохранен! Нажмите «Синхронизировать с Таблицей» для выгрузки.", "#15803D"
                self.page.update()
                self.refresh_ui()
            except ValueError: pass

        self.edit_dialog.title = ft.Text("Новый этап" if is_new else "Редактировать этап")
        self.edit_dialog.content = ft.Column([ft.Row([num_tf, title_tf]), ft.Row([ws_tf, ms_tf, d_tf]), wd_tf, md_tf], tight=True, spacing=10, width=500)
        self.edit_dialog.actions = [ft.TextButton("Отмена", on_click=lambda e: setattr(self.edit_dialog, "open", False) or self.page.update()), ft.ElevatedButton("Сохранить", bgcolor="#15803D", color="white", on_click=save)]
        self.edit_dialog.open = True
        self.page.update()