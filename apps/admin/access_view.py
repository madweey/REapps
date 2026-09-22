import flet as ft
from apps.core.auth import get_all_accounts, update_user_permissions, add_new_user


def AccessView(page: ft.Page, current_user: dict | None = None):
    status_text = ft.Text("", size=13, weight=ft.FontWeight.W_500)
    data_table_container = ft.Column(scroll=ft.ScrollMode.AUTO)

    new_name_input = ft.TextField(label="Имя сотрудника", width=280, height=45)
    new_pwd_input = ft.TextField(label="Пароль", password=True, can_reveal_password=True, width=280, height=45)
    new_role_input = ft.Dropdown(
        label="Должность",
        value="Менеджер",
        width=280,
        height=45,
        options=[
            ft.dropdown.Option("Менеджер"),
            ft.dropdown.Option("Старший менеджер"),
            ft.dropdown.Option("РОП"),
            ft.dropdown.Option("Директор"),
            ft.dropdown.Option("Администратор"),
        ],
    )
    new_user_error = ft.Text("", size=12, color=ft.colors.RED_700)

    add_dialog = ft.AlertDialog(
        title=ft.Text("Добавление сотрудника"),
        content=ft.Container(
            content=ft.Column(
                controls=[new_name_input, new_pwd_input, new_role_input, new_user_error],
                spacing=10,
                tight=True,
            ),
            width=320,
        ),
        actions=[
            ft.TextButton("Отмена", on_click=lambda e: setattr(add_dialog, "open", False) or page.update()),
            ft.ElevatedButton("Создать", icon=ft.icons.CHECK, bgcolor=ft.colors.BLUE_700, color=ft.colors.WHITE, on_click=lambda e: handle_add_user()),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )

    if add_dialog not in page.overlay:
        page.overlay.append(add_dialog)

    def handle_add_user():
        name_val = new_name_input.value.strip()
        pwd_val = new_pwd_input.value.strip()
        role_val = new_role_input.value.strip()

        if not name_val or not pwd_val:
            new_user_error.value = "Заполните имя и пароль!"
            page.update()
            return

        is_admin_role = role_val.lower() in ("директор", "роп", "руководитель", "администратор")
        payload = {
            "name": name_val,
            "password": pwd_val,
            "role": role_val,
            "can_meetings": True,
            "can_transcription": True,
            "can_calculator": True,
            "can_reports": True,
            "can_access_settings": is_admin_role,
        }

        if add_new_user(payload):
            add_dialog.open = False
            new_name_input.value = ""
            new_pwd_input.value = ""
            new_user_error.value = ""
            status_text.value = f"Сотрудник {name_val} успешно добавлен!"
            status_text.color = ft.colors.GREEN_700
            refresh_table()
        else:
            new_user_error.value = "Ошибка при сохранении в таблицу!"
            page.update()

    def on_switch_toggle(row_idx: int, field_key: str, new_value: bool, user_obj: dict):
        user_obj[field_key] = new_value
        status_text.value = f"Сохранение прав для {user_obj['name']}..."
        status_text.color = ft.colors.BLUE_700
        page.update()

        perms = {
            "can_meetings": user_obj.get("can_meetings", True),
            "can_transcription": user_obj.get("can_transcription", True),
            "can_calculator": user_obj.get("can_calculator", True),
            "can_reports": user_obj.get("can_reports", True),
            "can_access_settings": user_obj.get("can_access_settings", False),
        }

        if update_user_permissions(row_idx, perms):
            status_text.value = f"Права сотрудника {user_obj['name']} обновлены!"
            status_text.color = ft.colors.GREEN_700
        else:
            status_text.value = f"Ошибка записи прав для {user_obj['name']}!"
            status_text.color = ft.colors.RED_700
        page.update()

    def refresh_table(e=None):
        data_table_container.controls.clear()
        status_text.value = "Загрузка доступов из таблицы..."
        status_text.color = ft.colors.BLUE_700
        page.update()

        accounts = get_all_accounts()
        if not accounts:
            data_table_container.controls.append(ft.Text("Список сотрудников пуст или нет доступа к листу 'Доступы'", italic=True))
            status_text.value = ""
            page.update()
            return

        table_rows = []
        for acc in accounts:
            row_idx = acc["row_idx"]

            sw_meetings = ft.Switch(
                value=acc["can_meetings"],
                active_color=ft.colors.BLUE_700,
                on_change=lambda e, idx=row_idx, k="can_meetings", u=acc: on_switch_toggle(idx, k, e.control.value, u),
            )
            sw_transcription = ft.Switch(
                value=acc["can_transcription"],
                active_color=ft.colors.BLUE_700,
                on_change=lambda e, idx=row_idx, k="can_transcription", u=acc: on_switch_toggle(idx, k, e.control.value, u),
            )
            sw_calc = ft.Switch(
                value=acc["can_calculator"],
                active_color=ft.colors.BLUE_700,
                on_change=lambda e, idx=row_idx, k="can_calculator", u=acc: on_switch_toggle(idx, k, e.control.value, u),
            )
            sw_reports = ft.Switch(
                value=acc["can_reports"],
                active_color=ft.colors.BLUE_700,
                on_change=lambda e, idx=row_idx, k="can_reports", u=acc: on_switch_toggle(idx, k, e.control.value, u),
            )
            sw_settings = ft.Switch(
                value=acc["can_access_settings"],
                active_color=ft.colors.BLUE_700,
                on_change=lambda e, idx=row_idx, k="can_access_settings", u=acc: on_switch_toggle(idx, k, e.control.value, u),
            )

            table_rows.append(
                ft.DataRow(
                    cells=[
                        ft.DataCell(ft.Text(acc["name"], weight=ft.FontWeight.BOLD)),
                        ft.DataCell(ft.Text(acc["role"], color=ft.colors.GREY_700)),
                        ft.DataCell(sw_meetings),
                        ft.DataCell(sw_transcription),
                        ft.DataCell(sw_calc),
                        ft.DataCell(sw_reports),
                        ft.DataCell(sw_settings),
                    ]
                )
            )

        table = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("Сотрудник", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Должность", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Встречи", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Транскрибация", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Калькулятор", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Отчеты", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Настройки доступа", weight=ft.FontWeight.BOLD)),
            ],
            rows=table_rows,
            heading_row_color=ft.colors.SURFACE_VARIANT,
            border=ft.border.all(1, ft.colors.OUTLINE_VARIANT),
            border_radius=8,
            column_spacing=24,
        )

        data_table_container.controls.append(
            ft.Card(
                elevation=2,
                content=ft.Container(
                    padding=10,
                    content=table,
                ),
            )
        )
        status_text.value = ""
        page.update()

    refresh_table()

    return ft.Container(
        padding=20,
        content=ft.Column(
            controls=[
                ft.Row(
                    controls=[
                        ft.Column(
                            controls=[
                                ft.Text("Управление правами доступа", size=22, weight=ft.FontWeight.BOLD),
                                ft.Text("Настройте видимость разделов системы для каждого сотрудника", size=13, color=ft.colors.GREY_600),
                            ],
                            spacing=2,
                        ),
                        ft.Row(
                            controls=[
                                ft.ElevatedButton("Добавить сотрудника", icon=ft.icons.PERSON_ADD, bgcolor=ft.colors.BLUE_700, color=ft.colors.WHITE, height=42, on_click=lambda e: setattr(add_dialog, "open", True) or page.update()),
                                ft.OutlinedButton("Обновить таблицу", icon=ft.icons.REFRESH, height=42, on_click=refresh_table),
                            ],
                            spacing=10,
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
                ft.Divider(height=1),
                status_text,
                data_table_container,
            ],
            spacing=12,
            scroll=ft.ScrollMode.AUTO,
        ),
        expand=True,
    )