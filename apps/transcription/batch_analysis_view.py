import flet as ft
from apps.core.sheets import get_all_analyses
from apps.core.ai_engine import analyze_batch_summaries_with_gemini


def BatchAnalysisView(page: ft.Page):
    status_text = ft.Text("", size=13, weight=ft.FontWeight.W_500)
    progress_bar = ft.ProgressBar(visible=False, color="#0C66E4", height=4)

    selected_rows = {}
    analyses_data = []

    type_filter = ft.Dropdown(
        label="Тип коммуникации",
        value="Все типы",
        width=260,
        height=48,
        text_size=13,
        label_style=ft.TextStyle(size=12, color="#64748B"),
        filled=True,
        fill_color="#F1F5F9",
        border=ft.InputBorder.NONE,
        border_radius=12,
        options=[
            ft.dropdown.Option("Все типы"),
            ft.dropdown.Option("Первичный звонок КЦ"),
            ft.dropdown.Option("Онлайн встреча (презентация)"),
            ft.dropdown.Option("Встреча с дизайнером"),
            ft.dropdown.Option("Выезд с прорабом / Замер"),
            ft.dropdown.Option("Вопросы по договору"),
        ],
    )

    meta_prompt_input = ft.TextField(
        label="Мета-промт для анализа группы встреч",
        value="Проанализируй эти встречи. Выдели топ-5 главных причин, почему клиенты не принимают решение сразу, и дай рекомендации, как менеджерам усилить презентацию.",
        multiline=True,
        min_lines=3,
        max_lines=6,
        text_size=13,
        label_style=ft.TextStyle(size=12, color="#64748B"),
        filled=True,
        fill_color="#F1F5F9",
        border=ft.InputBorder.NONE,
        border_radius=12,
    )

    batch_output = ft.TextField(
        label="Сводный аналитический отчет РОПа",
        multiline=True,
        min_lines=12,
        max_lines=24,
        read_only=True,
        text_size=13,
        label_style=ft.TextStyle(size=12, color="#64748B"),
        filled=True,
        fill_color="#F8FAFC",
        border=ft.InputBorder.NONE,
        border_radius=12,
    )

    items_list_view = ft.Column(spacing=8, scroll=ft.ScrollMode.AUTO)

    def toggle_select_all(select: bool):
        for idx in selected_rows:
            selected_rows[idx] = select
        refresh_checkboxes()

    def refresh_checkboxes():
        for row_ctrl in items_list_view.controls:
            chk = getattr(row_ctrl, "chk_control", None)
            if chk and hasattr(chk, "data") and chk.data in selected_rows:
                chk.value = selected_rows[chk.data]
        page.update()

    def render_item_row(a: dict) -> ft.Control:
        idx = a["row_idx"]
        selected_rows[idx] = False

        def on_chk_changed(e, r_idx=idx):
            selected_rows[r_idx] = e.control.value

        chk = ft.Checkbox(
            value=False,
            data=idx,
            active_color="#0C66E4",
            shape=ft.RoundedRectangleBorder(radius=4),
            on_change=on_chk_changed,
        )

        comm_type = a.get("comm_type", "Встреча")
        client_deal = a.get("client_deal", "Без названия")
        author = a.get("author", "Не указан")
        date_str = a.get("date", "")

        row_container = ft.Container(
            bgcolor="#F8FAFC",
            border=ft.border.all(1, "#F1F5F9"),
            border_radius=12,
            padding=ft.padding.symmetric(horizontal=12, vertical=8),
            content=ft.Row(
                controls=[
                    chk,
                    ft.Text(f"📅 {date_str}", size=12, color="#64748B", weight=ft.FontWeight.W_500),
                    ft.Container(
                        content=ft.Text(comm_type, size=11, color="#0C66E4", weight=ft.FontWeight.BOLD),
                        bgcolor="#EBF3FC",
                        padding=ft.padding.symmetric(horizontal=8, vertical=3),
                        border_radius=6,
                    ),
                    ft.Text(f"💼 {client_deal}", size=13, weight=ft.FontWeight.W_600, color="#1E293B", expand=True),
                    ft.Text(f"👤 {author}", size=12, color="#64748B"),
                ],
                spacing=10,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        )
        row_container.chk_control = chk
        return row_container

    def load_analyses_list(e=None):
        nonlocal analyses_data
        items_list_view.controls.clear()
        selected_rows.clear()
        status_text.value = "Загрузка истории разборов..."
        status_text.color = "#0C66E4"
        page.update()

        try:
            analyses_data = get_all_analyses()
            selected_type = type_filter.value

            filtered = [
                a for a in analyses_data
                if selected_type == "Все типы" or a.get("comm_type") == selected_type
            ]

            if not filtered:
                items_list_view.controls.append(
                    ft.Container(
                        alignment=ft.alignment.center,
                        padding=20,
                        content=ft.Text("Разборы не найдены в листе 'Разборы'", italic=True, color="#94A3B8"),
                    )
                )
            else:
                for a in filtered:
                    items_list_view.controls.append(render_item_row(a))

            status_text.value = ""
        except Exception as err:
            status_text.value = f"Ошибка: {err}"
            status_text.color = "#DC2626"
        page.update()

    def run_batch_analysis(e):
        chosen_items = [
            a for a in analyses_data
            if selected_rows.get(a["row_idx"])
        ]

        if not chosen_items:
            status_text.value = "Отметьте галочками хотя бы один разбор для анализа!"
            status_text.color = "#DC2626"
            page.update()
            return

        p_text = meta_prompt_input.value.strip()
        if not p_text:
            status_text.value = "Введите текст задачи для ИИ!"
            status_text.color = "#DC2626"
            page.update()
            return

        run_btn.disabled = True
        progress_bar.visible = True
        status_text.value = f"Анализ {len(chosen_items)} встреч нейросетью Gemini..."
        status_text.color = "#0C66E4"
        page.update()

        try:
            result = analyze_batch_summaries_with_gemini(chosen_items, p_text)
            batch_output.value = result
            status_text.value = "Сводный отчет готов!"
            status_text.color = "#15803D"
        except Exception as err:
            status_text.value = f"Ошибка генерации: {err}"
            status_text.color = "#DC2626"
        finally:
            run_btn.disabled = False
            progress_bar.visible = False
            page.update()

    run_btn = ft.ElevatedButton(
        "Сформировать сводный отчет",
        icon=ft.icons.ANALYTICS_ROUNDED,
        bgcolor="#0C66E4",
        color=ft.colors.WHITE,
        height=46,
        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=12)),
        on_click=run_batch_analysis,
    )

    copy_btn = ft.OutlinedButton(
        "Скопировать отчет",
        icon=ft.icons.COPY_ALL_ROUNDED,
        height=46,
        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=12)),
        on_click=lambda e: page.set_clipboard(batch_output.value) or page.show_snack_bar(ft.SnackBar(ft.Text("Отчет скопирован!"), duration=1500)),
    )

    type_filter.on_change = load_analyses_list
    load_analyses_list()

    # Карточка выбора встреч
    selection_card = ft.Container(
        bgcolor=ft.colors.WHITE,
        border=ft.border.all(1, "#E2E8F0"),
        border_radius=18,
        padding=20,
        content=ft.Column(
            spacing=14,
            controls=[
                ft.Row(
                    controls=[
                        type_filter,
                        ft.OutlinedButton(
                            "Выбрать все",
                            height=48,
                            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=12)),
                            on_click=lambda e: toggle_select_all(True),
                        ),
                        ft.OutlinedButton(
                            "Снять выделение",
                            height=48,
                            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=12)),
                            on_click=lambda e: toggle_select_all(False),
                        ),
                        ft.IconButton(
                            icon=ft.icons.REFRESH_ROUNDED,
                            tooltip="Обновить список",
                            icon_color="#0C66E4",
                            on_click=load_analyses_list,
                        ),
                    ],
                    spacing=10,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                ft.Container(
                    content=items_list_view,
                    height=240,
                    padding=6,
                ),
            ],
        ),
    )

    # Карточка задачи и результата
    analysis_card = ft.Container(
        bgcolor=ft.colors.WHITE,
        border=ft.border.all(1, "#E2E8F0"),
        border_radius=18,
        padding=20,
        content=ft.Column(
            spacing=14,
            controls=[
                meta_prompt_input,
                ft.Row([run_btn, copy_btn], spacing=10),
                progress_bar,
                status_text,
                batch_output,
            ],
        ),
    )

    return ft.Container(
        padding=24,
        content=ft.Column(
            controls=[
                ft.Text("Анализ разборов (Пакетный)", size=24, weight=ft.FontWeight.BOLD, color="#0F172A"),
                ft.Text("Сравнительный анализ и поиск закономерностей по группе встреч для РОПа", size=13, color="#64748B"),
                ft.Container(height=4),
                selection_card,
                analysis_card,
            ],
            spacing=16,
            scroll=ft.ScrollMode.AUTO,
        ),
        expand=True,
    )