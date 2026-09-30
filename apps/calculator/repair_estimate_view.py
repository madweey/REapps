import flet as ft
from apps.calculator.repair_state import current_repair_state
from apps.calculator.repair_estimate_service import (
    calculate_engineering_stages,
    generate_engineering_estimate_presentation,
    load_repair_estimate_settings
)


class RepairEstimateView(ft.UserControl):
    def build(self):
        self.cfg = load_repair_estimate_settings()

        # Поля ввода данных заказчика
        self.address_input = ft.TextField(
            label="ЖК / Адрес объекта",
            value=current_repair_state.address or "ЖК «Тринити»",
            width=260,
            height=46,
            text_size=13,
            filled=True,
            fill_color="#F8FAFC",
            border_radius=12,
            border_color="#CBD5E1",
            on_change=self.on_data_change,
        )

        self.client_input = ft.TextField(
            label="Имя заказчика",
            value=current_repair_state.client_name or "Александр",
            width=200,
            height=46,
            text_size=13,
            filled=True,
            fill_color="#F8FAFC",
            border_radius=12,
            border_color="#CBD5E1",
            on_change=self.on_data_change,
        )

        self.sync_chip = ft.Chip(
            label=ft.Text("Синхронизировано с Калькулятором", size=11, color="#0C66E4"),
            bgcolor="#EBF3FC",
            disabled=True,
        )

        # Карточки итоговых цифр
        self.total_budget_text = ft.Text("0 ₽", size=26, weight=ft.FontWeight.W_800, color="#0C66E4")
        self.total_m2_text = ft.Text("0 ₽ / м²", size=14, weight=ft.FontWeight.W_600, color="#64748B")
        self.work_cost_text = ft.Text("0 ₽", size=18, weight=ft.FontWeight.BOLD, color="#1E293B")
        self.mat_cost_text = ft.Text("0 ₽", size=18, weight=ft.FontWeight.BOLD, color="#1E293B")
        self.duration_text = ft.Text("0 раб. дней", size=18, weight=ft.FontWeight.BOLD, color="#1E293B")

        self.table_column = ft.Column(spacing=6)

        self.generate_btn = ft.ElevatedButton(
            "📄 Сгенерировать презентацию КП (Google Slides)",
            icon=ft.icons.SLIDESHOW_ROUNDED,
            bgcolor="#0C66E4",
            color="#FFFFFF",
            height=46,
            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=12)),
            on_click=self.on_generate_click,
        )

        self.progress_bar = ft.ProgressBar(visible=False, color="#0C66E4")
        self.status_text = ft.Text("", size=12, color="#64748B", visible=False)

        top_header_card = ft.Container(
            bgcolor="#FFFFFF",
            border=ft.border.all(1, "#E2E8F0"),
            border_radius=16,
            padding=18,
            content=ft.Column(
                spacing=14,
                controls=[
                    ft.Row([
                        ft.Text("Коммерческое предложение: Инженерный ремонт", size=17, weight=ft.FontWeight.BOLD, color="#1E293B"),
                        self.sync_chip
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    ft.Row([
                        self.address_input,
                        self.client_input,
                        ft.Text(f"Площадь: {current_repair_state.area:g} м²\nСостояние: {current_repair_state.state_title}", size=12, color="#475569")
                    ], spacing=16, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                ]
            )
        )

        summary_metrics_card = ft.Container(
            bgcolor="#FFFFFF",
            border=ft.border.all(1, "#E2E8F0"),
            border_radius=16,
            padding=16,
            content=ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_AROUND,
                controls=[
                    ft.Column([
                        ft.Text("Итого ремонт + материалы", size=12, color="#64748B"),
                        self.total_budget_text,
                        self.total_m2_text
                    ], horizontal_alignment=ft.CrossAxisAlignment.START),
                    ft.Column([
                        ft.Text("Стоимость работ", size=12, color="#64748B"),
                        self.work_cost_text,
                        ft.Text("из расчета калькулятора", size=11, color="#94A3B8")
                    ], horizontal_alignment=ft.CrossAxisAlignment.START),
                    ft.Column([
                        ft.Text("Черновые материалы", size=12, color="#64748B"),
                        self.mat_cost_text,
                        ft.Text(f"{int(round(self.cfg['material_rate'])):,} ₽/м²".replace(",", " "), size=11, color="#94A3B8")
                    ], horizontal_alignment=ft.CrossAxisAlignment.START),
                    ft.Column([
                        ft.Text("Срок ремонта", size=12, color="#64748B"),
                        self.duration_text,
                        ft.Text("график 7 этапов", size=11, color="#94A3B8")
                    ], horizontal_alignment=ft.CrossAxisAlignment.START),
                ]
            )
        )

        stages_card = ft.Container(
            bgcolor="#FFFFFF",
            border=ft.border.all(1, "#E2E8F0"),
            border_radius=16,
            padding=16,
            expand=True,
            content=ft.Column(
                scroll=ft.ScrollMode.AUTO,
                spacing=10,
                controls=[
                    ft.Text("График и стоимость 7 этапов инженерного ремонта:", size=14, weight=ft.FontWeight.BOLD, color="#1E293B"),
                    self.table_column
                ]
            )
        )

        bottom_actions = ft.Container(
            padding=ft.padding.only(top=6),
            content=ft.Column(
                spacing=8,
                controls=[
                    self.progress_bar,
                    self.status_text,
                    self.generate_btn,
                ]
            )
        )

        self.recalc_view()

        return ft.Container(
            padding=ft.padding.all(20),
            expand=True,
            content=ft.Column(
                expand=True,
                spacing=14,
                controls=[
                    top_header_card,
                    summary_metrics_card,
                    stages_card,
                    bottom_actions,
                ]
            )
        )

    def on_data_change(self, e):
        current_repair_state.address = self.address_input.value
        current_repair_state.client_name = self.client_input.value

    def recalc_view(self):
        area = current_repair_state.area
        work_cost = current_repair_state.total_eng

        model = calculate_engineering_stages(
            area=area,
            work_total=work_cost,
            has_demolition=current_repair_state.has_demolition,
            material_rate=self.cfg["material_rate"],
            custom_stages=self.cfg["stages"]
        )

        self.total_budget_text.value = f"{int(round(model['grand_total'])):,} ₽".replace(",", " ")
        self.total_m2_text.value = f"{int(round(model['grand_per_m2'])):,} ₽ / м²".replace(",", " ")
        self.work_cost_text.value = f"{int(round(model['work_total'])):,} ₽".replace(",", " ")
        self.mat_cost_text.value = f"{int(round(model['mat_total'])):,} ₽".replace(",", " ")
        self.duration_text.value = f"{model['total_days']} раб. дней (~{model['total_months']} мес.)"

        rows = []
        rows.append(
            ft.Container(
                bgcolor="#F1F5F9",
                border_radius=8,
                padding=ft.padding.symmetric(horizontal=12, vertical=8),
                content=ft.Row([
                    ft.Text("Этап", size=12, weight=ft.FontWeight.BOLD, color="#475569", expand=3),
                    ft.Text("Срок", size=12, weight=ft.FontWeight.BOLD, color="#475569", expand=1),
                    ft.Text("Работы", size=12, weight=ft.FontWeight.BOLD, color="#475569", expand=2),
                    ft.Text("Материалы", size=12, weight=ft.FontWeight.BOLD, color="#475569", expand=2),
                    ft.Text("Итого", size=12, weight=ft.FontWeight.BOLD, color="#475569", expand=2),
                ])
            )
        )

        for s in model["stages"]:
            rows.append(
                ft.Container(
                    border=ft.border.only(bottom=ft.border.BorderSide(1, "#F1F5F9")),
                    padding=ft.padding.symmetric(horizontal=12, vertical=8),
                    content=ft.Row([
                        ft.Text(s["title"], size=12, weight=ft.FontWeight.W_600, color="#1E293B", expand=3),
                        ft.Text(f"{s['days']} раб. дн.", size=12, color="#64748B", expand=1),
                        ft.Text(f"{int(round(s['work_cost'])):,} ₽".replace(",", " "), size=12, color="#334155", expand=2),
                        ft.Text(f"{int(round(s['mat_cost'])):,} ₽".replace(",", " "), size=12, color="#334155", expand=2),
                        ft.Text(f"{int(round(s['stage_total'])):,} ₽".replace(",", " "), size=12, weight=ft.FontWeight.BOLD, color="#0C66E4", expand=2),
                    ])
                )
            )

        self.table_column.controls = rows

    def on_generate_click(self, e):
        self.generate_btn.disabled = True
        self.progress_bar.visible = True
        self.status_text.visible = True
        self.status_text.value = "Создание презентации и заполнение 7 этапов..."
        self.update()

        try:
            res = generate_engineering_estimate_presentation({
                "area": current_repair_state.area,
                "work_cost": current_repair_state.total_eng,
                "has_demolition": current_repair_state.has_demolition,
                "address": self.address_input.value,
                "client_name": self.client_input.value,
                "state": current_repair_state.state_title,
            })

            self.status_text.value = "Готово!"
            self.progress_bar.visible = False
            self.generate_btn.disabled = False
            self.update()

            def close_dialog(dlg_e):
                dialog.open = False
                e.page.update()

            dialog = ft.AlertDialog(
                title=ft.Text("✅ Смета успешно создана!"),
                content=ft.Container(
                    width=420,
                    content=ft.Column(
                        tight=True,
                        spacing=12,
                        controls=[
                            ft.Text(f"Файл: {res['title']}", size=13, weight=ft.FontWeight.BOLD),
                            ft.ElevatedButton(
                                "📄 Открыть PDF",
                                icon=ft.icons.PICTURE_AS_PDF_ROUNDED,
                                bgcolor="#0C66E4",
                                color="#FFFFFF",
                                url=res["pdf_url"]
                            ),
                            ft.OutlinedButton(
                                "🖥 Открыть Google Презентацию",
                                icon=ft.icons.OPEN_IN_NEW_ROUNDED,
                                url=res["edit_url"]
                            )
                        ]
                    )
                ),
                actions=[ft.TextButton("Закрыть", on_click=close_dialog)],
                actions_alignment=ft.MainAxisAlignment.END,
            )
            
            if dialog not in e.page.overlay:
                e.page.overlay.append(dialog)
            dialog.open = True
            e.page.update()

        except Exception as ex:
            self.status_text.value = f"Ошибка: {ex}"
            self.progress_bar.visible = False
            self.generate_btn.disabled = False
            self.update()