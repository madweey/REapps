import calendar
import datetime
import math
import threading
import flet as ft
from apps.calculator.dp_calc import calculate_dp
from apps.calculator.kp_generator import generate_kp_presentation, format_money
from apps.core.sheets import get_dp_tariffs_info


def DPView(page: ft.Page, current_user: dict | None = None):
    user_name = current_user.get("name", "Менеджер") if current_user else "Менеджер"

    # Поля ввода параметров One UI
    client_name_input = ft.TextField(
        label="Имя клиента",
        hint_text="Например: Иван Иванов",
        prefix_icon=ft.icons.PERSON_OUTLINE_ROUNDED,
        height=48,
        text_size=13,
        label_style=ft.TextStyle(size=12, color="#64748B"),
        filled=True,
        fill_color="#F8FAFC",
        border_radius=12,
        border_color="#CBD5E1",
        expand=True,
    )
    address_input = ft.TextField(
        label="Адрес объекта",
        hint_text="Например: г. Москва, ЖК 'Сердце Столицы'",
        prefix_icon=ft.icons.LOCATION_ON_OUTLINED,
        height=48,
        text_size=13,
        label_style=ft.TextStyle(size=12, color="#64748B"),
        filled=True,
        fill_color="#F8FAFC",
        border_radius=12,
        border_color="#CBD5E1",
        expand=True,
    )
    area_input = ft.TextField(
        label="Площадь помещения (м²)",
        hint_text="Например: 75",
        keyboard_type=ft.KeyboardType.NUMBER,
        prefix_icon=ft.icons.SQUARE_FOOT_ROUNDED,
        height=48,
        text_size=13,
        label_style=ft.TextStyle(size=12, color="#64748B"),
        filled=True,
        fill_color="#F8FAFC",
        border_radius=12,
        border_color="#CBD5E1",
        width=210,
    )

    promo_dropdown = ft.Dropdown(
        label="Условия акции / Скидка",
        value="Нет",
        height=48,
        text_size=13,
        label_style=ft.TextStyle(size=12, color="#64748B"),
        filled=True,
        fill_color="#F8FAFC",
        border_radius=12,
        border_color="#CBD5E1",
        width=290,
        options=[
            ft.dropdown.Option("Нет"),
            ft.dropdown.Option("Компенсация ДП"),
            ft.dropdown.Option("10% IT"),
            ft.dropdown.Option("15% Яндекс"),
            ft.dropdown.Option("Повторное обращение"),
            ft.dropdown.Option("3% за быстрое подписание"),
            ft.dropdown.Option("5% за быстрое подписание"),
            ft.dropdown.Option("7% за быстрое подписание"),
            ft.dropdown.Option("10% за рек"),
        ],
    )

    promo_input = ft.TextField(
        label="Текст акции для презентации",
        hint_text="Сформируется автоматически при выборе акции или введите свой...",
        prefix_icon=ft.icons.CAMPAIGN_OUTLINED,
        height=48,
        text_size=13,
        label_style=ft.TextStyle(size=12, color="#64748B"),
        filled=True,
        fill_color="#F8FAFC",
        border_radius=12,
        border_color="#CBD5E1",
        expand=True,
    )

    # Виджеты тарифа ДП (Онлайн)
    dp_cost_text = ft.Text("0 руб.", size=22, weight=ft.FontWeight.BOLD, color="#0C66E4")
    dp_third_text = ft.Text("0 руб.", size=14, weight=ft.FontWeight.BOLD, color="#0C66E4")
    dp_price_m2_text = ft.Text("0 руб./м²", size=13, color="#64748B")
    dp_deadline_text = ft.Text("-", size=13, weight=ft.FontWeight.W_600, color="#1E293B")
    dp_target_text = ft.Text("Загрузка...", size=12, color="#475569")
    dp_adv_text = ft.Text("Загрузка...", size=12, color="#475569")

    # Виджеты тарифа ОДП (С сопровождением)
    odp_cost_text = ft.Text("0 руб.", size=22, weight=ft.FontWeight.BOLD, color="#1E293B")
    odp_third_text = ft.Text("0 руб.", size=14, weight=ft.FontWeight.BOLD, color="#1E293B")
    odp_price_m2_text = ft.Text("0 руб./м²", size=13, color="#64748B")
    odp_deadline_text = ft.Text("-", size=13, weight=ft.FontWeight.W_600, color="#1E293B")
    odp_target_text = ft.Text("Загрузка...", size=12, color="#475569")
    odp_adv_text = ft.Text("Загрузка...", size=12, color="#475569")

    status_ring = ft.ProgressRing(width=20, height=20, stroke_width=2.5, color="#0C66E4", visible=False)
    status_text = ft.Text("", size=12, weight=ft.FontWeight.W_500)
    result_card = ft.Container(visible=False)

    calc_state = {"data": None, "discount_val": 0.0}

    def load_tariffs_sheet_info_async():
        def _worker():
            try:
                info = get_dp_tariffs_info()
                dp_target_text.value = info.get("online", {}).get("target", "-")
                dp_adv_text.value = info.get("online", {}).get("advantages", "-")
                odp_target_text.value = info.get("full", {}).get("target", "-")
                odp_adv_text.value = info.get("full", {}).get("advantages", "-")
                page.update()
            except Exception:
                pass
        threading.Thread(target=_worker, daemon=True).start()

    def get_promo_config(option_name: str) -> tuple[float, str]:
        today = datetime.date.today()

        def end_of_month_str() -> str:
            last_day = calendar.monthrange(today.year, today.month)[1]
            return datetime.date(today.year, today.month, last_day).strftime("%d.%m.%Y")

        def plus_days_str(days: int) -> str:
            return (today + datetime.timedelta(days=days)).strftime("%d.%m.%Y")

        if option_name == "Компенсация ДП":
            return 0.0, f"Компенсация стоимости Дизайн-проекта при подписании договора до {end_of_month_str()}"
        elif option_name == "10% IT":
            return 10.0, f"Скидка 10% сотрудникам IT компаний. Действительна до {plus_days_str(7)}"
        elif option_name == "15% Яндекс":
            return 15.0, f"Скидка 15% сотрудникам Яндекс. Действительна до {plus_days_str(7)}"
        elif option_name == "Повторное обращение":
            return 10.0, f"Скидка 10% при повторном обращении. Действительна до {plus_days_str(7)}"
        elif option_name == "3% за быстрое подписание":
            return 3.0, f"Скидка 3% при подписании договора до {plus_days_str(5)}"
        elif option_name == "5% за быстрое подписание":
            return 5.0, f"Скидка 5% при подписании договора до {plus_days_str(3)}"
        elif option_name == "7% за быстрое подписание":
            return 7.0, f"Скидка 7% при подписании договора до {plus_days_str(2)}"
        elif option_name == "10% за рек":
            return 10.0, f"Скидка 10% при подписании договора до {plus_days_str(7)}"
        else:
            return 0.0, ""

    def on_promo_changed(e=None):
        disc_val, auto_text = get_promo_config(promo_dropdown.value or "Нет")
        calc_state["discount_val"] = disc_val
        promo_input.value = auto_text
        update_calculations()

    promo_dropdown.on_change = on_promo_changed

    def update_calculations(e=None):
        try:
            area_val = float(str(area_input.value).replace(",", ".").strip() or "0")
        except ValueError:
            area_val = 0.0

        disc_val = calc_state["discount_val"]
        res = calculate_dp(area_val, disc_val, "percent")
        calc_state["data"] = res

        dp_total = res["dp"]["total_cost"]
        odp_total = res["odp"]["total_cost"]

        dp_cost_text.value = format_money(dp_total)
        dp_third_text.value = format_money(round(dp_total / 3.0))
        dp_price_m2_text.value = f"{format_money(res['dp']['price_m2'])} / м²"
        dp_deadline_text.value = str(res["dp"]["deadline"])

        odp_cost_text.value = format_money(odp_total)
        odp_third_text.value = format_money(round(odp_total / 3.0))
        odp_price_m2_text.value = f"{format_money(res['odp']['price_m2'])} / м²"
        odp_deadline_text.value = str(res["odp"]["deadline"])

        page.update()

    area_input.on_change = update_calculations

    def copy_pdf_link(url: str):
        try:
            page.set_clipboard(url)
        except Exception:
            pass
        status_text.value = "Ссылка на PDF скопирована!"
        status_text.color = "#15803D"
        page.update()

    def handle_generate_kp(e):
        if not calc_state["data"] or calc_state["data"]["area"] <= 0:
            status_text.value = "Сначала укажите площадь помещения!"
            status_text.color = "#DC2626"
            page.update()
            return

        generate_btn.disabled = True
        status_ring.visible = True
        status_text.value = "Создание презентации и PDF..."
        status_text.color = "#0C66E4"
        result_card.visible = False
        page.update()

        try:
            res_kp = generate_kp_presentation(
                calc_data=calc_state["data"],
                client_name=client_name_input.value or "",
                address=address_input.value or "",
                promo_text=promo_input.value or "",
                user_name=user_name,
            )

            status_ring.visible = False
            status_text.value = "КП успешно сформировано!"
            status_text.color = "#15803D"

            result_card.content = ft.Container(
                bgcolor="#F0FDF4",
                border=ft.border.all(1, "#BBF7D0"),
                border_radius=14,
                padding=14,
                content=ft.Row(
                    controls=[
                        ft.Icon(ft.icons.CHECK_CIRCLE_ROUNDED, color="#15803D", size=24),
                        ft.Text("Готовое коммерческое предложение:", weight=ft.FontWeight.BOLD, size=13, color="#166534"),
                        ft.ElevatedButton(
                            "Открыть готовый PDF",
                            icon=ft.icons.PICTURE_AS_PDF_ROUNDED,
                            bgcolor="#DC2626",
                            color=ft.colors.WHITE,
                            height=38,
                            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10)),
                            url=res_kp["pdf_url"],
                        ),
                        ft.OutlinedButton(
                            "Открыть презентацию",
                            icon=ft.icons.SLIDESHOW_ROUNDED,
                            height=38,
                            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10)),
                            url=res_kp["presentation_url"],
                        ),
                        ft.IconButton(
                            icon=ft.icons.COPY_ALL_ROUNDED,
                            tooltip="Скопировать ссылку на PDF",
                            icon_color="#15803D",
                            on_click=lambda ev: copy_pdf_link(res_kp["pdf_url"]),
                        ),
                    ],
                    spacing=10,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
            )
            result_card.visible = True

        except Exception as ex:
            status_ring.visible = False
            status_text.value = f"Ошибка создания КП: {ex}"
            status_text.color = "#DC2626"
        finally:
            generate_btn.disabled = False
            page.update()

    # Перемещенная кнопка генерации КП
    generate_btn = ft.ElevatedButton(
        "Сгенерировать КП в PDF",
        icon=ft.icons.AUTO_AWESOME_ROUNDED,
        bgcolor="#0C66E4",
        color=ft.colors.WHITE,
        height=42,
        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=12)),
        on_click=handle_generate_kp,
    )

    update_calculations()

    # Карточка Тарифа Онлайн
    card_dp = ft.Container(
        expand=True,
        bgcolor=ft.colors.WHITE,
        border=ft.border.all(1, "#E2E8F0"),
        border_radius=16,
        padding=18,
        content=ft.Column(
            controls=[
                ft.Row(
                    controls=[
                        ft.Container(
                            content=ft.Icon(ft.icons.COMPUTER_ROUNDED, color="#0C66E4", size=20),
                            bgcolor="#EBF3FC",
                            padding=8,
                            border_radius=10,
                        ),
                        ft.Column(
                            controls=[
                                ft.Text("Тариф: ДП (Онлайн разработка)", size=15, weight=ft.FontWeight.BOLD, color="#1E293B"),
                                ft.Text("Дистанционная разработка полного дизайн-проекта", size=11, color="#64748B"),
                            ],
                            spacing=1,
                        ),
                    ],
                    spacing=10,
                ),
                ft.Divider(height=1, color="#F1F5F9"),
                ft.Row(
                    controls=[
                        ft.Column([ft.Text("Итоговая стоимость:", size=11, color="#64748B"), dp_cost_text], spacing=2),
                        ft.Column([ft.Text("Цена за м²:", size=11, color="#64748B"), dp_price_m2_text], spacing=2, horizontal_alignment=ft.CrossAxisAlignment.END),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
                ft.Container(
                    padding=ft.padding.symmetric(horizontal=12, vertical=8),
                    border_radius=10,
                    bgcolor="#EBF3FC",
                    content=ft.Row(
                        controls=[
                            ft.Icon(ft.icons.PAYMENTS_OUTLINED, size=18, color="#0C66E4"),
                            ft.Text("Оплата 1/3 (этап):", size=12, weight=ft.FontWeight.W_600, color="#0C66E4"),
                            dp_third_text,
                        ],
                        spacing=8,
                        alignment=ft.MainAxisAlignment.START,
                    ),
                ),
                ft.Row(
                    controls=[
                        ft.Icon(ft.icons.ACCESS_TIME_ROUNDED, size=17, color="#64748B"),
                        ft.Text("Срок разработки:", size=12, color="#64748B"),
                        dp_deadline_text,
                    ],
                    spacing=6,
                ),
                ft.Divider(height=1, color="#F1F5F9"),
                ft.Column(
                    controls=[
                        ft.Row([ft.Icon(ft.icons.CHECK_CIRCLE_OUTLINE_ROUNDED, size=15, color="#0C66E4"), ft.Text("Кому подойдет:", size=12, weight=ft.FontWeight.BOLD, color="#1E293B")], spacing=6),
                        dp_target_text,
                        ft.Container(height=4),
                        ft.Row([ft.Icon(ft.icons.STAR_BORDER_ROUNDED, size=15, color="#0C66E4"), ft.Text("Преимущества:", size=12, weight=ft.FontWeight.BOLD, color="#1E293B")], spacing=6),
                        dp_adv_text,
                    ],
                    spacing=4,
                ),
            ],
            spacing=12,
        ),
    )

    # Карточка Тарифа С сопровождением
    card_odp = ft.Container(
        expand=True,
        bgcolor=ft.colors.WHITE,
        border=ft.border.all(1, "#E2E8F0"),
        border_radius=16,
        padding=18,
        content=ft.Column(
            controls=[
                ft.Row(
                    controls=[
                        ft.Container(
                            content=ft.Icon(ft.icons.SUPPORT_AGENT_ROUNDED, color="#1E293B", size=20),
                            bgcolor="#F1F5F9",
                            padding=8,
                            border_radius=10,
                        ),
                        ft.Column(
                            controls=[
                                ft.Text("Тариф: ОДП (С сопровождением)", size=15, weight=ft.FontWeight.BOLD, color="#1E293B"),
                                ft.Text("Максимальный пакет с выездами дизайнера в салоны", size=11, color="#64748B"),
                            ],
                            spacing=1,
                        ),
                    ],
                    spacing=10,
                ),
                ft.Divider(height=1, color="#F1F5F9"),
                ft.Row(
                    controls=[
                        ft.Column([ft.Text("Итоговая стоимость:", size=11, color="#64748B"), odp_cost_text], spacing=2),
                        ft.Column([ft.Text("Цена за м²:", size=11, color="#64748B"), odp_price_m2_text], spacing=2, horizontal_alignment=ft.CrossAxisAlignment.END),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
                ft.Container(
                    padding=ft.padding.symmetric(horizontal=12, vertical=8),
                    border_radius=10,
                    bgcolor="#F1F5F9",
                    content=ft.Row(
                        controls=[
                            ft.Icon(ft.icons.PAYMENTS_OUTLINED, size=18, color="#1E293B"),
                            ft.Text("Оплата 1/3 (этап):", size=12, weight=ft.FontWeight.W_600, color="#1E293B"),
                            odp_third_text,
                        ],
                        spacing=8,
                        alignment=ft.MainAxisAlignment.START,
                    ),
                ),
                ft.Row(
                    controls=[
                        ft.Icon(ft.icons.ACCESS_TIME_ROUNDED, size=17, color="#64748B"),
                        ft.Text("Срок разработки:", size=12, color="#64748B"),
                        odp_deadline_text,
                    ],
                    spacing=6,
                ),
                ft.Divider(height=1, color="#F1F5F9"),
                ft.Column(
                    controls=[
                        ft.Row([ft.Icon(ft.icons.CHECK_CIRCLE_OUTLINE_ROUNDED, size=15, color="#1E293B"), ft.Text("Кому подойдет:", size=12, weight=ft.FontWeight.BOLD, color="#1E293B")], spacing=6),
                        odp_target_text,
                        ft.Container(height=4),
                        ft.Row([ft.Icon(ft.icons.STAR_BORDER_ROUNDED, size=15, color="#1E293B"), ft.Text("Преимущества:", size=12, weight=ft.FontWeight.BOLD, color="#1E293B")], spacing=6),
                        odp_adv_text,
                    ],
                    spacing=4,
                ),
            ],
            spacing=12,
        ),
    )

    load_tariffs_sheet_info_async()

    header_block = ft.Container(
        padding=ft.padding.only(left=24, right=24, top=20, bottom=10),
        content=ft.Column(
            controls=[
                ft.Text("Калькулятор Дизайн-Проекта (ДП)", size=22, weight=ft.FontWeight.BOLD, color="#0F172A"),
                ft.Text("Расчет тарифов Онлайн и С сопровождением с генерацией презентации", size=13, color="#64748B"),
                ft.Divider(height=1, color="#E2E8F0"),
            ],
            spacing=4,
        ),
    )

    scrollable_body = ft.Container(
        padding=ft.padding.only(left=24, right=24, bottom=24),
        expand=True,
        content=ft.Column(
            controls=[
                ft.Text("Параметры объекта и клиента", size=15, weight=ft.FontWeight.BOLD, color="#1E293B"),
                ft.Row(controls=[client_name_input, address_input], spacing=12),
                ft.Row(controls=[area_input, promo_dropdown, promo_input], spacing=12),
                ft.Container(height=4),
                # Верхняя плашка действий с кнопкой генерации КП
                ft.Row(
                    controls=[
                        ft.Text("Сравнение тарифов и условий", size=15, weight=ft.FontWeight.BOLD, color="#1E293B"),
                        ft.Row(
                            controls=[
                                status_ring,
                                status_text,
                                generate_btn,
                            ],
                            spacing=10,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                result_card,
                ft.Row(controls=[card_dp, card_odp], spacing=16, vertical_alignment=ft.CrossAxisAlignment.START),
            ],
            spacing=14,
            scroll=ft.ScrollMode.AUTO,
        ),
    )

    return ft.Column(
        controls=[header_block, scrollable_body],
        spacing=0,
        expand=True,
    )