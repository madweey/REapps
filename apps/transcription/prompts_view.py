import flet as ft
from apps.core.sheets import get_all_prompts, add_prompt, delete_prompt


def PromptsView(page: ft.Page):
    status_text = ft.Text("", size=13, weight=ft.FontWeight.W_500)
    cards_column = ft.Column(spacing=10, scroll=ft.ScrollMode.AUTO, expand=True)

    cat_filter = ft.Dropdown(
        label="Фильтр по категории",
        value="Все категории",
        width=200,
        height=45,
        dense=True,
        options=[
            ft.dropdown.Option("Все категории"),
            ft.dropdown.Option("Встречи"),
            ft.dropdown.Option("Звонки КЦ"),
            ft.dropdown.Option("Продажи"),
            ft.dropdown.Option("Анализ пачки"),
            ft.dropdown.Option("Другое"),
        ],
    )

    # Модальное окно создания промта
    new_cat_dropdown = ft.Dropdown(
        label="Категория",
        value="Встречи",
        dense=True,
        options=[
            ft.dropdown.Option("Встречи"),
            ft.dropdown.Option("Звонки КЦ"),
            ft.dropdown.Option("Продажи"),
            ft.dropdown.Option("Анализ пачки"),
            ft.dropdown.Option("Другое"),
        ],
    )
    new_title_input = ft.TextField(
        label="Название промта",
        hint_text="Например: Анализ скрытых возражений",
        dense=True,
    )
    new_prompt_input = ft.TextField(
        label="Инструкция для ИИ (Текст промта)",
        hint_text="Опишите, что нейросеть должна найти в разговоре...",
        multiline=True,
        min_lines=6,
        max_lines=12,
        dense=True,
    )
    modal_error = ft.Text("", size=12, color=ft.colors.RED_600)

    def on_confirm_add(e):
        title = new_title_input.value.strip()
        cat = new_cat_dropdown.value or "Встречи"
        p_text = new_prompt_input.value.strip()

        if not title or not p_text:
            modal_error.value = "Заполните название и текст инструкции!"
            page.update()
            return

        try:
            status_text.value = "Сохранение промта в Google Таблицу..."
            status_text.color = ft.colors.BLUE_700
            page.update()

            add_prompt(title, cat, p_text)
            add_dialog.open = False
            status_text.value = f"Промт '{title}' успешно добавлен!"
            status_text.color = ft.colors.GREEN_700
            load_prompts()
        except Exception as err:
            modal_error.value = f"Ошибка добавления: {err}"
            page.update()

    add_dialog = ft.AlertDialog(
        title=ft.Text("Создать новый шаблон промта"),
        content=ft.Container(
            content=ft.Column(
                controls=[new_title_input, new_cat_dropdown, new_prompt_input, modal_error],
                spacing=12,
                tight=True,
            ),
            width=540,
        ),
        actions=[
            ft.TextButton("Отмена", on_click=lambda e: setattr(add_dialog, "open", False) or page.update()),
            ft.ElevatedButton("Сохранить в таблицу", bgcolor=ft.colors.BLUE_700, color=ft.colors.WHITE, on_click=on_confirm_add),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )
    if add_dialog not in page.overlay:
        page.overlay.append(add_dialog)

    def open_add_modal(e):
        new_title_input.value = ""
        new_prompt_input.value = ""
        modal_error.value = ""
        add_dialog.open = True
        page.update()

    def render_prompt_card(item: dict) -> ft.Control:
        idx = item["row_idx"]

        def handle_delete(e, r_idx=idx, t=item.get("title", "")):
            try:
                delete_prompt(r_idx)
                status_text.value = f"Промт '{t}' удалён!"
                status_text.color = ft.colors.GREEN_700
                load_prompts()
            except Exception as err:
                status_text.value = f"Ошибка удаления: {err}"
                status_text.color = ft.colors.RED_700
                page.update()

        cat = item.get("category", "Встречи")
        return ft.Card(
            elevation=1,
            content=ft.Container(
                padding=14,
                border_radius=8,
                bgcolor=ft.colors.WHITE,
                content=ft.Column(
                    controls=[
                        ft.Row(
                            controls=[
                                ft.Row(
                                    controls=[
                                        ft.Container(
                                            content=ft.Text(cat, size=11, weight=ft.FontWeight.BOLD, color=ft.colors.BLUE_900),
                                            padding=ft.padding.symmetric(horizontal=8, vertical=4),
                                            bgcolor=ft.colors.BLUE_50,
                                            border=ft.border.all(1, ft.colors.BLUE_200),
                                            border_radius=6,
                                        ),
                                        ft.Text(item.get("title", ""), size=15, weight=ft.FontWeight.BOLD),
                                    ],
                                    spacing=8,
                                ),
                                ft.Text(f"📅 {item.get('created_at', '')}", size=12, color=ft.colors.GREY_600),
                            ],
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        ),
                        ft.Container(
                            content=ft.Text(item.get("prompt_text", ""), size=13, color=ft.colors.BLACK87),
                            padding=10,
                            bgcolor=ft.colors.SURFACE_VARIANT,
                            border_radius=6,
                        ),
                        ft.Row(
                            controls=[
                                ft.OutlinedButton(
                                    "Скопировать текст",
                                    icon=ft.icons.COPY,
                                    on_click=lambda e, t=item.get("prompt_text", ""): page.set_clipboard(t) or setattr(status_text, "value", "Текст скопирован!") or page.update(),
                                ),
                                ft.IconButton(
                                    icon=ft.icons.DELETE_OUTLINE,
                                    tooltip="Удалить промт",
                                    icon_color=ft.colors.RED_400,
                                    on_click=handle_delete,
                                ),
                            ],
                            spacing=8,
                        ),
                    ],
                    spacing=8,
                ),
            ),
        )

    def load_prompts(e=None):
        cards_column.controls.clear()
        status_text.value = "Загрузка промтов..."
        status_text.color = ft.colors.BLUE_700
        page.update()

        try:
            items = get_all_prompts()
            selected_cat = cat_filter.value

            filtered = [
                it for it in items
                if selected_cat == "Все категории" or it.get("category") == selected_cat
            ]

            if not filtered:
                cards_column.controls.append(
                    ft.Container(
                        alignment=ft.alignment.center,
                        padding=40,
                        content=ft.Column(
                            controls=[
                                ft.Icon(ft.icons.PSYCHOLOGY_ALT, size=48, color=ft.colors.GREY_400),
                                ft.Text("Промты пока не добавлены", size=16, weight=ft.FontWeight.BOLD, color=ft.colors.GREY_700),
                            ],
                            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                    )
                )
            else:
                for it in filtered:
                    cards_column.controls.append(render_prompt_card(it))

            status_text.value = ""
        except Exception as err:
            status_text.value = f"Ошибка чтения: {err}"
            status_text.color = ft.colors.RED_700
        page.update()

    cat_filter.on_change = load_prompts
    load_prompts()

    header_block = ft.Container(
        padding=ft.padding.only(bottom=10),
        content=ft.Row(
            controls=[
                ft.Column(
                    controls=[
                        ft.Text("Библиотека AI-промтов", size=22, weight=ft.FontWeight.BOLD),
                        ft.Text("Шаблоны инструкций для анализа разговоров нейросетью Gemini", size=13, color=ft.colors.GREY_600),
                    ],
                    spacing=2,
                ),
                ft.Row(
                    controls=[
                        cat_filter,
                        ft.ElevatedButton(
                            "Создать промт",
                            icon=ft.icons.ADD,
                            bgcolor=ft.colors.BLUE_700,
                            color=ft.colors.WHITE,
                            height=45,
                            on_click=open_add_modal,
                        ),
                        ft.OutlinedButton("Обновить", icon=ft.icons.REFRESH, height=45, on_click=load_prompts),
                    ],
                    spacing=10,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
    )

    return ft.Container(
        padding=20,
        content=ft.Column(
            controls=[header_block, ft.Divider(height=1), status_text, cards_column],
            spacing=10,
            expand=True,
        ),
        expand=True,
    )