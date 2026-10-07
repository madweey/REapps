import flet as ft
from apps.core.sheets import RepairDataSync


class RepairSettingsView(ft.UserControl):
    def __init__(self, page: ft.Page):
        super().__init__()
        self.page = page
        self.data = RepairDataSync.get_data()
        self.status_msg = ft.Text("", size=13, weight=ft.FontWeight.BOLD)
        
        # Добавлены заглушки title и content, чтобы Flet не выдавал ошибку
        self.edit_dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text(""),
            content=ft.Container()
        )
        if self.edit_dialog not in self.page.overlay:
            self.page.overlay.append(self.edit_dialog)

    def build(self):
        sync_btn = ft.ElevatedButton(
            "Синхронизировать с Таблицей (Сохранить)",
            icon=ft.icons.CLOUD_UPLOAD_ROUNDED,
            bgcolor="#15803D", color="white", height=44,
            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10)),
            on_click=self.on_sync_click
        )
        
        pull_btn = ft.OutlinedButton(
            "Скачать из Таблицы",
            icon=ft.icons.CLOUD_DOWNLOAD_ROUNDED, height=44,
            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10)),
            on_click=self.on_pull_click
        )

        self.tabs = ft.Tabs(
            selected_index=0,
            animation_duration=300,
            tabs=[
                ft.Tab(text="Базовые ставки", content=self.build_rates_tab()),
                ft.Tab(text="Коэффициенты", content=self.build_coeffs_tab()),
                ft.Tab(text="Этапы Инженерии", content=self.build_stages_tab("eng_stages")),
                ft.Tab(text="Этапы Отделки", content=self.build_stages_tab("fin_stages")),
            ],
            expand=True,
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
                        ], spacing=2, expand=True),
                        pull_btn, sync_btn
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    self.status_msg,
                    ft.Container(
                        bgcolor=ft.colors.WHITE, border=ft.border.all(1, "#E2E8F0"), border_radius=12, padding=10,
                        content=self.tabs, expand=True
                    )
                ]
            )
        )

    def on_sync_click(self, e):
        self.status_msg.value = "Синхронизация с Google Таблицей..."
        self.status_msg.color = "#0C66E4"
        self.update()
        try:
            RepairDataSync.save_and_push(self.data)
            self.status_msg.value = "База успешно выгружена в Google Таблицу!"
            self.status_msg.color = "#15803D"
        except Exception as ex:
            self.status_msg.value = f"Ошибка выгрузки: {ex}"
            self.status_msg.color = "#DC2626"
        self.update()

    def on_pull_click(self, e):
        self.status_msg.value = "Скачивание данных из Google Таблицы..."
        self.status_msg.color = "#0C66E4"
        self.update()
        try:
            self.data = RepairDataSync.pull_from_cloud()
            self.status_msg.value = "База успешно обновлена из Google Таблицы!"
            self.status_msg.color = "#15803D"
            self.refresh_ui()
        except Exception as ex:
            self.status_msg.value = f"Ошибка скачивания: {ex}"
            self.status_msg.color = "#DC2626"
            self.update()

    def refresh_ui(self):
        self.tabs.tabs[0].content = self.build_rates_tab()
        self.tabs.tabs[1].content = self.build_coeffs_tab()
        self.tabs.tabs[2].content = self.build_stages_tab("eng_stages")
        self.tabs.tabs[3].content = self.build_stages_tab("fin_stages")
        self.update()

    def build_rates_tab(self):
        def make_tf(label, key):
            def on_c(e):
                try: self.data["base_rates"][key] = float(e.control.value.replace(",", "."))
                except: pass
            return ft.TextField(label=label, value=str(self.data["base_rates"].get(key, "")), on_change=on_c, width=300, border_radius=8)

        def make_tf_str(label, key):
            def on_c(e): self.data["base_rates"][key] = e.control.value
            return ft.TextField(label=label, value=str(self.data["base_rates"].get(key, "")), on_change=on_c, width=400, border_radius=8)

        return ft.ListView(
            padding=20, spacing=24,
            controls=[
                ft.Text("💰 Стоимость работ (База за м²)", weight=ft.FontWeight.BOLD, size=15),
                ft.Row([make_tf("Инженерия (Работа)", "engineering_work"), make_tf("Отделка (Работа)", "finishing_work")]),
                ft.Text("🧱 Стоимость черновых материалов (База за м²)", weight=ft.FontWeight.BOLD, size=15),
                ft.Row([make_tf("Инженерия (Материалы)", "engineering_mat"), make_tf("Отделка (Материалы)", "finishing_mat")]),
                ft.Text("⚙ Системные настройки (ID Шаблонов и Папок)", weight=ft.FontWeight.BOLD, size=15),
                make_tf_str("Шаблон Инженерия", "template_eng"),
                make_tf_str("Шаблон Отделка", "template_fin"),
                make_tf_str("Шаблон Комплекс", "template_complex"),
                make_tf_str("ID Папки Google Drive", "folder_id"),
            ]
        )

    def build_coeffs_tab(self):
        rows = []
        for idx, c in enumerate(self.data["coefficients"]):
            pct = int(round(c["value"] * 100))
            bg_col = "#EBF3FC" if pct > 0 else "#F1F5F9"
            fg_col = "#0C66E4" if pct > 0 else "#64748B"
            rows.append(
                ft.Container(
                    bgcolor="#F8FAFC", border=ft.border.all(1, "#E2E8F0"), border_radius=12, padding=12,
                    content=ft.Row([
                        ft.Column([
                            ft.Text(c["name"], size=13, weight=ft.FontWeight.BOLD, color="#1E293B"),
                            ft.Text(f"ID: {c['id']} | База: {c['type']}", size=11, color="#64748B"),
                        ], expand=True, spacing=2),
                        ft.Container(content=ft.Text(f"+{pct}%", weight=ft.FontWeight.BOLD, color=fg_col), bgcolor=bg_col, padding=6, border_radius=6),
                        ft.IconButton(ft.icons.EDIT_ROUNDED, icon_color="#0C66E4", on_click=lambda e, i=idx: self.open_coeff_editor(i)),
                        ft.IconButton(ft.icons.DELETE_ROUNDED, icon_color="#EF4444", on_click=lambda e, i=idx: self.delete_item("coefficients", i)),
                    ])
                )
            )
        return ft.Container(
            padding=20,
            content=ft.Column([
                ft.Row([ft.ElevatedButton("Добавить коэффициент", icon=ft.icons.ADD, on_click=lambda e: self.open_coeff_editor(-1))]),
                ft.ListView(controls=rows, expand=True, spacing=8)
            ])
        )

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
        return ft.Container(
            padding=20,
            content=ft.Column([
                ft.Row([ft.ElevatedButton("Добавить этап", icon=ft.icons.ADD, on_click=lambda e: self.open_stage_editor(key_type, -1))]),
                ft.ListView(controls=rows, expand=True, spacing=8)
            ])
        )

    def delete_item(self, list_key, idx):
        self.data[list_key].pop(idx)
        self.refresh_ui()

    def open_coeff_editor(self, idx):
        is_new = (idx == -1)
        c = {"id": "", "name": "", "value": 0.0, "type": "Отделка"} if is_new else self.data["coefficients"][idx]

        id_tf = ft.TextField(label="ID Ключ (напр. floor_laminate)", value=c["id"])
        name_tf = ft.TextField(label="Название", value=c["name"])
        val_tf = ft.TextField(label="Надбавка (0.05 = 5%)", value=str(c["value"]))
        type_dd = ft.Dropdown(label="База", value=c["type"], options=[ft.dropdown.Option("Отделка"), ft.dropdown.Option("Инженерия"), ft.dropdown.Option("Все")])

        def save(e):
            try: v = float(val_tf.value.replace(",", "."))
            except: v = 0.0
            new_c = {"id": id_tf.value, "name": name_tf.value, "value": v, "type": type_dd.value}
            if is_new: self.data["coefficients"].append(new_c)
            else: self.data["coefficients"][idx] = new_c
            self.edit_dialog.open = False
            self.refresh_ui()

        self.edit_dialog.title = ft.Text("Добавить коэффициент" if is_new else "Редактировать коэффициент")
        self.edit_dialog.content = ft.Column([id_tf, name_tf, val_tf, type_dd], tight=True, spacing=10)
        self.edit_dialog.actions = [ft.ElevatedButton("Сохранить", on_click=save)]
        self.edit_dialog.open = True
        self.page.update()

    def open_stage_editor(self, list_key, idx):
        is_new = (idx == -1)
        s = {"num": 1, "title": "", "w_share": 0.0, "m_share": 0.0, "days": 10, "w_desc": "", "m_desc": ""} if is_new else self.data[list_key][idx]

        num_tf = ft.TextField(label="Номер", value=str(s["num"]), width=80)
        title_tf = ft.TextField(label="Название этапа", value=s["title"], expand=True)
        ws_tf = ft.TextField(label="Доля Работ (напр. 0.15)", value=str(s["w_share"]), width=170)
        ms_tf = ft.TextField(label="Доля Мат. (напр. 0.12)", value=str(s["m_share"]), width=170)
        d_tf = ft.TextField(label="Срок/Вес (дней)", value=str(s["days"]), width=140)
        wd_tf = ft.TextField(label="Описание работ", value=s["w_desc"], multiline=True)
        md_tf = ft.TextField(label="Описание материалов", value=s["m_desc"], multiline=True)

        def save(e):
            try:
                new_s = {
                    "num": int(num_tf.value), "title": title_tf.value,
                    "w_share": float(ws_tf.value.replace(",", ".")), "m_share": float(ms_tf.value.replace(",", ".")),
                    "days": float(d_tf.value.replace(",", ".")),
                    "w_desc": wd_tf.value, "m_desc": md_tf.value
                }
                if is_new: self.data[list_key].append(new_s)
                else: self.data[list_key][idx] = new_s
                self.edit_dialog.open = False
                self.refresh_ui()
            except ValueError:
                pass

        self.edit_dialog.title = ft.Text("Новый этап" if is_new else "Редактировать этап")
        self.edit_dialog.content = ft.Column([
            ft.Row([num_tf, title_tf]),
            ft.Row([ws_tf, ms_tf, d_tf]),
            wd_tf, md_tf
        ], tight=True, spacing=10, width=500)
        self.edit_dialog.actions = [ft.ElevatedButton("Сохранить", on_click=save)]
        self.edit_dialog.open = True
        self.page.update()