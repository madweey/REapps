import flet as ft
from apps.core.sheets import get_all_prompts, add_prompt, delete_prompt, update_prompt


def PromptsView(page: ft.Page):
    status_text = ft.Text("", size=13, weight=ft.FontWeight.W_500)
    cards_column = ft.Column(spacing=12, scroll=ft.ScrollMode.AUTO, expand=True)

    cat_filter = ft.Dropdown(
        label="Фильтр по категории",
        value="Все категории",
        width=210,
        height=48,
        text_size=13,
        label_style=ft.TextStyle(size=12, color="#64748B"),
        filled=True,
        fill_color="#F1F5F9",
        border=ft.InputBorder.NONE,
        border_radius=12,
        options=[
            ft.dropdown.Option("Все категории"),
            ft.dropdown.Option("Встречи"),
            ft.dropdown.Option("Звонки КЦ"),
            ft.dropdown.Option("Продажи"),
            ft.dropdown.Option("Анализ пачки"),
            ft.dropdown.Option("Другое"),
        ],
    )

    # ==========================================
    # МОДАЛЬНОЕ ОКНО СОЗДАНИЯ ПРОМТА
    # ==========================================
    new_cat_dropdown = ft.Dropdown(
        label="Категория",
        value="Встречи",
        height=48,
        text_size=13,
        label_style=ft.TextStyle(size=12, color="#64748B"),
        filled=True,
        fill_color="#F1F5F9",
        border=ft.InputBorder.NONE,
        border_radius=12,
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
        height=48,
        text_size=13,
        label_style=ft.TextStyle(size=12, color="#64748B"),
        filled=True,
        fill_color="#F1F5F9",
        border=ft.InputBorder.NONE,
        border_radius=12,
    )
    new_prompt_input = ft.TextField(
        label="Инструкция для ИИ (Текст промта)",
        hint_text="Опишите, что нейросеть должна найти в разговоре...",
        multiline=True,
        min_lines=6,
        max_lines=12,
        text_size=13,
        label_style=ft.TextStyle(size=12, color="#64748B"),
        filled=True,
        fill_color="#F1F5F9",
        border=ft.InputBorder.NONE,
        border_radius=12,
    )
    modal_error = ft.Text("", size=12, color="#EF4444")

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
            status_text.color = "#0C66E4"
            page.update()

            add_prompt(title, cat, p_text)
            add_dialog.open = False
            status_text.value = f"Промт '{title}' успешно добавлен!"
            status_text.color = "#15803D"
            load_prompts()
        except Exception as err:
            modal_error.value = f"Ошибка добавления: {err}"
            page.update()

    add_dialog = ft.AlertDialog(
        title=ft.Row([
            ft.Icon(ft.icons.POST_ADD_ROUNDED, color="#0C66E4", size=22),
            ft.Text("Создать новый шаблон промта", size=16, weight=ft.FontWeight.BOLD),
        ], spacing=8),
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
            ft.ElevatedButton("Сохранить в таблицу", bgcolor="#0C66E4", color=ft.colors.WHITE, style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=12)), on_click=on_confirm_add),
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

    # ==========================================
    # МОДАЛЬНОЕ ОКНО РЕДАКТИРОВАНИЯ ПРОМТА (КАРАНДАШ)
    # ==========================================
    edit_row_idx = {"val": None}
    edit_title_input = ft.TextField(
        label="Название промта",
        height=48,
        text_size=13,
        label_style=ft.TextStyle(size=12, color="#64748B"),
        filled=True,
        fill_color="#F1F5F9",
        border=ft.InputBorder.NONE,
        border_radius=12,
    )
    edit_cat_dropdown = ft.Dropdown(
        label="Категория",
        height=48,
        text_size=13,
        label_style=ft.TextStyle(size=12, color="#64748B"),
        filled=True,
        fill_color="#F1F5F9",
        border=ft.InputBorder.NONE,
        border_radius=12,
        options=[
            ft.dropdown.Option("Встречи"),
            ft.dropdown.Option("Звонки КЦ"),
            ft.dropdown.Option("Продажи"),
            ft.dropdown.Option("Анализ пачки"),
            ft.dropdown.Option("Другое"),
        ],
    )
    edit_prompt_input = ft.TextField(
        label="Инструкция для ИИ (Текст промта)",
        multiline=True,
        min_lines=6,
        max_lines=12,
        text_size=13,
        label_style=ft.TextStyle(size=12, color="#64748B"),
        filled=True,
        fill_color="#F1F5F9",
        border=ft.InputBorder.NONE,
        border_radius=12,
    )
    edit_modal_error = ft.Text("", size=12, color="#EF4444")

    def on_confirm_edit(e):
        title = edit_title_input.value.strip()
        cat = edit_cat_dropdown.value or "Встречи"
        p_text = edit_prompt_input.value.strip()
        r_idx = edit_row_idx["val"]

        if not title or not p_text:
            edit_modal_error.value = "Заполните название и текст инструкции!"
            page.update()
            return

        try:
            status_text.value = f"Обновление строки {r_idx} в Google Таблице..."
            status_text.color = "#0C66E4"
            page.update()

            update_prompt(r_idx, title, cat, p_text)
            edit_dialog.open = False
            status_text.value = f"Промт '{title}' успешно обновлён!"
            status_text.color = "#15803D"
            load_prompts()
        except Exception as err:
            edit_modal_error.value = f"Ошибка изменения: {err}"
            page.update()

    edit_dialog = ft.AlertDialog(
        title=ft.Row([
            ft.Icon(ft.icons.EDIT_NOTE_ROUNDED, color="#0C66E4", size=22),
            ft.Text("Редактировать промт", size=16, weight=ft.FontWeight.BOLD),
        ], spacing=8),
        content=ft.Container(
            content=ft.Column(
                controls=[edit_title_input, edit_cat_dropdown, edit_prompt_input, edit_modal_error],
                spacing=12,
                tight=True,
            ),
            width=540,
        ),
        actions=[
            ft.TextButton("Отмена", on_click=lambda e: setattr(edit_dialog, "open", False) or page.update()),
            ft.ElevatedButton("Сохранить изменения", bgcolor="#0C66E4", color=ft.colors.WHITE, style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=12)), on_click=on_confirm_edit),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )
    if edit_dialog not in page.overlay:
        page.overlay.append(edit_dialog)

    def open_edit_modal(item: dict):
        edit_row_idx["val"] = item["row_idx"]
        edit_title_input.value = item.get("title", "")
        edit_cat_dropdown.value = item.get("category", "Встречи")
        edit_prompt_input.value = item.get("prompt_text", "")
        edit_modal_error.value = ""
        edit_dialog.open = True
        page.update()

    # ==========================================
    # КАРТОЧКА ПРОМТА В ONE UI СТИЛЕ
    # ==========================================
    def render_prompt_card(item: dict) -> ft.Control:
        idx = item["row_idx"]

        def handle_delete(e, r_idx=idx, t=item.get("title", "")):
            try:
                delete_prompt(r_idx)
                status_text.value = f"Промт '{t}' удалён!"
                status_text.color = "#15803D"
                load_prompts()
            except Exception as err:
                status_text.value = f"Ошибка удаления: {err}"
                status_text.color = "#DC2626"
                page.update()

        cat = item.get("category", "Встречи")
        return ft.Container(
            bgcolor="#FFFFFF",
            border=ft.border.all(1, "#E2E8F0"),
            border_radius=18,
            padding=16,
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Row(
                                controls=[
                                    ft.Container(
                                        content=ft.Text(cat, size=11, weight=ft.FontWeight.BOLD, color="#0C66E4"),
                                        padding=ft.padding.symmetric(horizontal=10, vertical=4),
                                        bgcolor="#EBF3FC",
                                        border_radius=8,
                                    ),
                                    ft.Text(item.get("title", ""), size=15, weight=ft.FontWeight.BOLD, color="#1E293B"),
                                ],
                                spacing=8,
                            ),
                            ft.Text(f"📅 {item.get('created_at', '')}", size=11, color="#64748B"),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                    ft.Container(
                        content=ft.Text(item.get("prompt_text", ""), size=13, color="#334155"),
                        padding=12,
                        bgcolor="#F8FAFC",
                        border=ft.border.all(1, "#F1F5F9"),
                        border_radius=12,
                    ),
                    ft.Row(
                        controls=[
                            ft.ElevatedButton(
                                "Скопировать текст",
                                icon=ft.icons.COPY_ALL_ROUNDED,
                                height=38,
                                bgcolor="#F1F5F9",
                                color="#1E293B",
                                elevation=0,
                                style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10)),
                                on_click=lambda e, t=item.get("prompt_text", ""): page.set_clipboard(t) or page.show_snack_bar(ft.SnackBar(ft.Text("Текст промта скопирован!"), duration=1500)),
                            ),
                            ft.Row([
                                ft.IconButton(
                                    icon=ft.icons.EDIT_OUTLINED,
                                    tooltip="Редактировать промт",
                                    icon_color="#0C66E4",
                                    icon_size=20,
                                    on_click=lambda e, it=item: open_edit_modal(it),
                                ),
                                ft.IconButton(
                                    icon=ft.icons.DELETE_OUTLINE_ROUNDED,
                                    tooltip="Удалить промт",
                                    icon_color="#EF4444",
                                    icon_size=20,
                                    on_click=handle_delete,
                                ),
                            ], spacing=2)
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                ],
                spacing=10,
            ),
        )

    def load_prompts(e=None):
        cards_column.controls.clear()
        status_text.value = "Загрузка промтов..."
        status_text.color = "#0C66E4"
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
                                ft.Icon(ft.icons.PSYCHOLOGY_ALT_ROUNDED, size=48, color="#94A3B8"),
                                ft.Text("Промты пока не добавлены", size=15, weight=ft.FontWeight.BOLD, color="#64748B"),
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
            status_text.color = "#DC2626"
        page.update()

    cat_filter.on_change = load_prompts
    load_prompts()

    header_block = ft.Container(
        padding=ft.padding.only(bottom=10),
        content=ft.Row(
            controls=[
                ft.Column(
                    controls=[
                        ft.Text("Библиотека AI-промтов", size=24, weight=ft.FontWeight.BOLD, color="#0F172A"),
                        ft.Text("Шаблоны инструкций для анализа разговоров нейросетью Gemini", size=13, color="#64748B"),
                    ],
                    spacing=2,
                ),
                ft.Row(
                    controls=[
                        cat_filter,
                        ft.ElevatedButton(
                            "Создать промт",
                            icon=ft.icons.ADD_ROUNDED,
                            bgcolor="#0C66E4",
                            color=ft.colors.WHITE,
                            height=48,
                            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=12)),
                            on_click=open_add_modal,
                        ),
                        ft.OutlinedButton(
                            "Обновить",
                            icon=ft.icons.REFRESH_ROUNDED,
                            height=48,
                            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=12)),
                            on_click=load_prompts,
                        ),
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
        padding=24,
        content=ft.Column(
            controls=[header_block, ft.Divider(height=1, color="#E2E8F0"), status_text, cards_column],
            spacing=12,
            expand=True,
        ),
        expand=True,
    )