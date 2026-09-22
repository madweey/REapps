import flet as ft
from apps.core.sheets import get_all_analyses, get_all_prompts
from apps.core.ai_engine import analyze_batch_summaries_with_gemini


def BatchAnalysisView(page: ft.Page):
    status_text = ft.Text("", size=13, weight=ft.FontWeight.W_500)
    progress_bar = ft.ProgressBar(visible=False, color=ft.colors.BLUE_700)

    selected_rows = {}
    analyses_data = []

    type_filter = ft.Dropdown(
        label="Тип коммуникации",
        value="Все типы",
        width=220,
        height=45,
        dense=True,
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
    )

    batch_output = ft.TextField(
        label="Сводный аналитический отчет РОПа",
        multiline=True,
        min_lines=14,
        max_lines=25,
        read_only=True,
    )

    items_list_view = ft.Column(spacing=6, scroll=ft.ScrollMode.AUTO, height=220)

    def toggle_select_all(select: bool):
        for idx in selected_rows:
            selected_rows[idx] = select
        refresh_checkboxes()

    def refresh_checkboxes():
        for ctrl in items_list_view.controls:
            if hasattr(ctrl, "data") and ctrl.data in selected_rows:
                ctrl.value = selected_rows[ctrl.data]
        page.update()

    def load_analyses_list(e=None):
        nonlocal analyses_data
        items_list_view.controls.clear()
        selected_rows.clear()
        status_text.value = "Загрузка истории разборов..."
        status_text.color = ft.colors.BLUE_700
        page.update()

        try:
            analyses_data = get_all_analyses()
            selected_type = type_filter.value

            filtered = [
                a for a in analyses_data
                if selected_type == "Все типы" or a.get("comm_type") == selected_type
            ]

            if not filtered:
                items_list_view.controls.append(ft.Text("Разборы не найдены в листе 'Разборы'", italic=True))
            else:
                for a in filtered:
                    idx = a["row_idx"]
                    selected_rows[idx] = False

                    def on_chk_changed(e, r_idx=idx):
                        selected_rows[r_idx] = e.control.value

                    chk = ft.Checkbox(
                        label=f"{a.get('date', '')} | {a.get('comm_type', '')} | {a.get('client_deal', '')} | {a.get('author', '')}",
                        value=False,
                        data=idx,
                        on_change=on_chk_changed,
                    )
                    items_list_view.controls.append(chk)

            status_text.value = ""
        except Exception as err:
            status_text.value = f"Ошибка: {err}"
            status_text.color = ft.colors.RED_700
        page.update()

    def run_batch_analysis(e):
        chosen_items = [
            a for a in analyses_data
            if selected_rows.get(a["row_idx"])
        ]

        if not chosen_items:
            status_text.value = "Отметьте галочками хотя бы один разбор для анализа!"
            status_text.color = ft.colors.RED_700
            page.update()
            return

        p_text = meta_prompt_input.value.strip()
        if not p_text:
            status_text.value = "Введите текст задачи для ИИ!"
            status_text.color = ft.colors.RED_700
            page.update()
            return

        run_btn.disabled = True
        progress_bar.visible = True
        status_text.value = f"Анализ {len(chosen_items)} встреч нейросетью Gemini..."
        status_text.color = ft.colors.BLUE_700
        page.update()

        try:
            result = analyze_batch_summaries_with_gemini(chosen_items, p_text)
            batch_output.value = result
            status_text.value = "Сводный отчет готов!"
            status_text.color = ft.colors.GREEN_700
        except Exception as err:
            status_text.value = f"Ошибка генерации: {err}"
            status_text.color = ft.colors.RED_700
        finally:
            run_btn.disabled = False
            progress_bar.visible = False
            page.update()

    run_btn = ft.ElevatedButton(
        "Сформировать сводный отчет",
        icon=ft.icons.ANALYTICS,
        bgcolor=ft.colors.BLUE_700,
        color=ft.colors.WHITE,
        height=45,
        on_click=run_batch_analysis,
    )

    type_filter.on_change = load_analyses_list
    load_analyses_list()

    return ft.Container(
        padding=20,
        content=ft.Column(
            controls=[
                ft.Text("Анализ разборов (Пакетный)", size=22, weight=ft.FontWeight.BOLD),
                ft.Text("Сравнительный анализ и поиск закономерностей по группе встреч для РОПа", size=13, color=ft.colors.GREY_600),
                ft.Divider(height=1),
                ft.Row(
                    controls=[
                        type_filter,
                        ft.OutlinedButton("Выбрать все", on_click=lambda e: toggle_select_all(True)),
                        ft.OutlinedButton("Снять выделение", on_click=lambda e: toggle_select_all(False)),
                        ft.IconButton(icon=ft.icons.REFRESH, tooltip="Обновить список", on_click=load_analyses_list),
                    ],
                    spacing=10,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                ft.Container(
                    content=items_list_view,
                    padding=10,
                    border=ft.border.all(1, ft.colors.OUTLINE_VARIANT),
                    border_radius=8,
                    bgcolor=ft.colors.WHITE,
                ),
                meta_prompt_input,
                ft.Row(
                    controls=[
                        run_btn,
                        ft.OutlinedButton("Скопировать отчет", icon=ft.icons.COPY, height=45, on_click=lambda e: page.set_clipboard(batch_output.value) or setattr(status_text, "value", "Отчет скопирован!") or page.update()),
                    ],
                    spacing=10,
                ),
                progress_bar,
                status_text,
                batch_output,
            ],
            spacing=12,
            scroll=ft.ScrollMode.AUTO,
        ),
        expand=True,
    )