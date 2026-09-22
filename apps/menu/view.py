import flet as ft
from apps.core.styles import (
    BG_COLOR,
    SURFACE_COLOR,
    PRIMARY_COLOR,
    TEXT_MAIN,
    TEXT_MUTED,
)


def get_menu_view(page, switch_view, app_state):
    def notify(msg):
        page.snack_bar = ft.SnackBar(ft.Text(msg), bgcolor=PRIMARY_COLOR, open=True)
        page.update()

    def menu_card(title, subtitle, icon, on_click=None, tag=None, is_active=True):
        badge = None
        if tag:
            badge = ft.Container(
                content=ft.Text(tag, size=10, weight=ft.FontWeight.BOLD, color=TEXT_MUTED),
                bgcolor="#E2E8F0",
                padding=4,
                border_radius=8,
            )

        return ft.Container(
            content=ft.Row(
                [
                    ft.Container(
                        content=ft.Icon(
                            icon,
                            color=SURFACE_COLOR if is_active else "#94A3B8",
                            size=20,
                        ),
                        bgcolor=PRIMARY_COLOR if is_active else "#CBD5E1",
                        padding=12,
                        border_radius=10,
                    ),
                    ft.Column(
                        [
                            ft.Row(
                                [
                                    ft.Text(
                                        title,
                                        size=15,
                                        weight=ft.FontWeight.BOLD,
                                        color=TEXT_MAIN if is_active else TEXT_MUTED,
                                    ),
                                    badge if badge else ft.Container(),
                                ],
                                spacing=6,
                            ),
                            ft.Text(
                                subtitle,
                                size=12,
                                color=TEXT_MUTED,
                                max_lines=1,
                                overflow=ft.TextOverflow.ELLIPSIS,
                            ),
                        ],
                        spacing=2,
                        expand=True,
                    ),
                    ft.Icon(
                        ft.Icons.CHEVRON_RIGHT_ROUNDED,
                        color="#94A3B8" if is_active else "#CBD5E1",
                        size=22,
                    ),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=14,
            bgcolor=SURFACE_COLOR,
            border_radius=12,
            ink=is_active,
            on_click=on_click if is_active else lambda _: notify("Раздел находится в разработке"),
        )

    return ft.Container(
        content=ft.Column(
            [
                ft.Container(height=12),
                ft.Container(
                    content=ft.Column(
                        [
                            ft.Row(
                                [
                                    ft.Text("РЕМОНТ ЭКСПЕРТ", size=10, weight=ft.FontWeight.BOLD, color=TEXT_MUTED),
                                    ft.Container(
                                        content=ft.Row(
                                            [
                                                ft.Icon(ft.Icons.CIRCLE, size=7, color=app_state["status_color"]),
                                                ft.Text(
                                                    app_state["status_text"],
                                                    size=10,
                                                    weight=ft.FontWeight.W_600,
                                                    color=app_state["status_color"],
                                                ),
                                            ],
                                            spacing=5,
                                        ),
                                        bgcolor=SURFACE_COLOR,
                                        padding=6,
                                        border_radius=16,
                                    ),
                                ],
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            ),
                            ft.Text("Ассистент менеджера", size=24, weight=ft.FontWeight.BOLD, color=TEXT_MAIN),
                            ft.Text("Выберите рабочий модуль для продолжения", size=13, color=TEXT_MUTED),
                        ],
                        spacing=4,
                    ),
                    padding=16,
                ),
                ft.Container(
                    content=ft.Column(
                        [
                            menu_card(
                                title="Калькулятор и КП",
                                subtitle="Расчет объекта, подбор ЖК и тарифов",
                                icon=ft.Icons.CALCULATE_ROUNDED,
                                on_click=lambda _: switch_view("calc"),
                                is_active=True,
                            ),
                            menu_card(
                                title="Формы",
                                subtitle="Передача встреч и статусные отчеты",
                                icon=ft.Icons.ASSIGNMENT_ROUNDED,
                                tag="Скоро",
                                is_active=False,
                            ),
                            menu_card(
                                title="Транскрибация",
                                subtitle="Анализ звонков и протоколов",
                                icon=ft.Icons.RECORD_VOICE_OVER_ROUNDED,
                                tag="Скоро",
                                is_active=False,
                            ),
                            menu_card(
                                title="Отчеты",
                                subtitle="Сводная статистика и конверсии",
                                icon=ft.Icons.INSIGHTS_ROUNDED,
                                tag="Скоро",
                                is_active=False,
                            ),
                        ],
                        spacing=10,
                    ),
                    padding=16,
                ),
            ],
            scroll=ft.ScrollMode.AUTO,
        ),
        expand=True,
        bgcolor=BG_COLOR,
    )