import flet as ft
from apps.core.sheets import get_all_template_links, add_template_link, delete_template_link


def LinksView(page: ft.Page):
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
            ft.dropdown.Option("КП"),
            ft.dropdown.Option("Смета"),
            ft.dropdown.Option("Договор"),
            ft.dropdown.Option("Презентация"),
            ft.dropdown.Option("Другое"),
        ],
    )

    # ----------------------------------------------------
    # Модальное окно добавления новой ссылки
    # ----------------------------------------------------
    new_cat_dropdown = ft.Dropdown(
        label="Категория",
        value="КП",
        dense=True,
        options=[
            ft.dropdown.Option("КП"),
            ft.dropdown.Option("Смета"),
            ft.dropdown.Option("Договор"),
            ft.dropdown.Option("Презентация"),
            ft.dropdown.Option("Другое"),
        ],
    )
    new_title_input = ft.TextField(
        label="Название шаблона",
        hint_text="Например: Шаблон КП Премиум (Google Презентация)",
        dense=True,
    )
    new_url_input = ft.TextField(
        label="Ссылка (URL)",
        hint_text="https://docs.google.com/presentation/...",
        dense=True,
    )
    new_desc_input = ft.TextField(
        label="Примечание / Описание",
        hint_text="Основной шаблон для генерации КП",
        multiline=True,
        min_lines=2,
        dense=True,
    )
    modal_error = ft.Text("", size=12, color=ft.colors.RED_600)

    def on_confirm_add(e):
        title = new_title_input.value.strip()
        url = new_url_input.value.strip()
        cat = new_cat_dropdown.value or "КП"
        desc = new_desc_input.value.strip()

        if not title or not url:
            modal_error.value = "Заполните название и вставьте ссылку!"
            page.update()
            return

        try:
            status_text.value = "Сохранение ссылки в Google Таблицу..."
            status_text.color = ft.colors.BLUE_700
            page.update()

            add_template_link(cat, title, url, desc)
            add_dialog.open = False
            status_text.value = f"Шаблон '{title}' успешно добавлен!"
            status_text.color = ft.colors.GREEN_700
            load_links()
        except Exception as err:
            modal_error.value = f"Ошибка добавления: {err}"
            page.update()

    add_dialog = ft.AlertDialog(
        title=ft.Text("Добавить ссылку на шаблон"),
        content=ft.Container(
            content=ft.Column(
                controls=[new_cat_dropdown, new_title_input, new_url_input, new_desc_input, modal_error],
                spacing=12,
                tight=True,
            ),
            width=480,
        ),
        actions=[
            ft.TextButton("Отмена", on_click=lambda e: setattr(add_dialog, "open", False) or page.update()),
            ft.ElevatedButton("Сохранить", bgcolor=ft.colors.BLUE_700, color=ft.colors.WHITE, on_click=on_confirm_add),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )
    if add_dialog not in page.overlay:
        page.overlay.append(add_dialog)

    def open_add_modal(e):
        new_title_input.value = ""
        new_url_input.value = ""
        new_desc_input.value = ""
        modal_error.value = ""
        add_dialog.open = True
        page.update()

    # ----------------------------------------------------
    # Карточка ссылки
    # ----------------------------------------------------
    def render_link_card(item: dict) -> ft.Control:
        idx = item["row_idx"]
        url = item.get("url", "")

        def handle_delete(e, r_idx=idx, t=item.get("title", "")):
            try:
                delete_template_link(r_idx)
                status_text.value = f"Шаблон '{t}' удалён!"
                status_text.color = ft.colors.GREEN_700
                load_links()
            except Exception as err:
                status_text.value = f"Ошибка удаления: {err}"
                status_text.color = ft.colors.RED_700
                page.update()

        def copy_url(e, u=url):
            page.set_clipboard(u)
            status_text.value = "Ссылка скопирована в буфер обмена!"
            status_text.color = ft.colors.GREEN_700
            page.update()

        cat = item.get("category", "КП")
        is_kp = cat == "КП"
        badge_color = ft.colors.BLUE_50 if is_kp else ft.colors.AMBER_50
        border_color = ft.colors.BLUE_200 if is_kp else ft.colors.AMBER_300
        text_color = ft.colors.BLUE_900 if is_kp else ft.colors.AMBER_900

        cat_badge = ft.Container(
            content=ft.Text(cat, size=11, weight=ft.FontWeight.BOLD, color=text_color),
            padding=ft.padding.symmetric(horizontal=8, vertical=4),
            bgcolor=badge_color,
            border=ft.border.all(1, border_color),
            border_radius=6,
        )

        return ft.Card(
            elevation=2,
            content=ft.Container(
                padding=14,
                border_radius=8,
                bgcolor=ft.colors.WHITE,
                content=ft.Column(
                    controls=[
                        ft.Row(
                            controls=[
                                ft.Row([cat_badge, ft.Text(item.get("title", ""), size=15, weight=ft.FontWeight.BOLD)], spacing=8),
                                ft.Text(f"📅 {item.get('created_at', '')}", size=12, color=ft.colors.GREY_600),
                            ],
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        ),
                        ft.Text(f"URL: {url}", size=12, color=ft.colors.BLUE_700, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                        ft.Text(f"Примечание: {item['desc']}", size=12, italic=True, color=ft.colors.GREY_700) if item.get("desc") else ft.Container(),
                        ft.Row(
                            controls=[
                                ft.ElevatedButton("Открыть шаблон", icon=ft.icons.OPEN_IN_NEW, on_click=lambda e, u=url: page.launch_url(u)),
                                ft.OutlinedButton("Скопировать ссылку", icon=ft.icons.COPY, on_click=copy_url),
                                ft.IconButton(icon=ft.icons.DELETE_OUTLINE, tooltip="Удалить", icon_color=ft.colors.RED_400, on_click=handle_delete),
                            ],
                            spacing=8,
                        ),
                    ],
                    spacing=8,
                ),
            ),
        )

    # ----------------------------------------------------
    # Загрузка и отрисовка
    # ----------------------------------------------------
    def load_links(e=None):
        cards_column.controls.clear()
        status_text.value = "Загрузка ссылок..."
        status_text.color = ft.colors.BLUE_700
        page.update()

        try:
            items = get_all_template_links()
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
                                ft.Icon(ft.icons.LINK_OFF, size=48, color=ft.colors.GREY_400),
                                ft.Text("Шаблоны пока не добавлены", size=16, weight=ft.FontWeight.BOLD, color=ft.colors.GREY_700),
                                ft.Text("Нажмите кнопку 'Добавить ссылку', чтобы привязать Google Презентацию или Смету.", size=13, color=ft.colors.GREY_500),
                            ],
                            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                            spacing=8,
                        ),
                    )
                )
            else:
                for it in filtered:
                    cards_column.controls.append(render_link_card(it))

            status_text.value = ""
        except Exception as err:
            status_text.value = f"Ошибка чтения ссылок: {err}"
            status_text.color = ft.colors.RED_700
        page.update()

    cat_filter.on_change = load_links
    load_links()

    header_block = ft.Container(
        padding=ft.padding.only(bottom=10),
        content=ft.Row(
            controls=[
                ft.Column(
                    controls=[
                        ft.Text("Шаблоны документов и презентаций", size=22, weight=ft.FontWeight.BOLD),
                        ft.Text("Ссылки на Google Презентации и Сметы для генерации документов", size=13, color=ft.colors.GREY_600),
                    ],
                    spacing=2,
                ),
                ft.Row(
                    controls=[
                        cat_filter,
                        ft.ElevatedButton(
                            "Добавить ссылку",
                            icon=ft.icons.ADD_LINK,
                            bgcolor=ft.colors.BLUE_700,
                            color=ft.colors.WHITE,
                            height=45,
                            on_click=open_add_modal,
                        ),
                        ft.OutlinedButton("Обновить", icon=ft.icons.REFRESH, height=45, on_click=load_links),
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
            controls=[
                header_block,
                ft.Divider(height=1),
                status_text,
                cards_column,
            ],
            spacing=10,
            expand=True,
        ),
        expand=True,
    )