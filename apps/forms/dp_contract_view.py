import math
import re
from datetime import datetime, timedelta
import flet as ft

# --- Заглушка для базы данных ---
def fetch_project_from_sheets(deal_link: str) -> dict:
    if not deal_link:
        return None
    
    # Извлекаем ID сделки из ссылки amoCRM
    deal_id = deal_link
    match = re.search(r'detail/(\d+)', deal_link)
    if match:
        deal_id = match.group(1)

    # Имитация данных из таблицы (без ФИО, телефона и адреса)
    return {
        "project_id": "1923Д ЖК Шагал",
        "area": 69.0,
        "cost": 307395.0,
        "start_date": "06.10.2026",
        "dev_days": 75, # Срок разработки в рабочих днях из таблицы
        "style": "Мид сенчури",
        "keys": "На руках",
        "state": "Голый бетон",
        "source": "Рекомендация чат",
        "manager": "Дмитрий Смирнов",
        "cycle_days": "12 дня",
        "files_link": "https://disk.yandex.ru/d/CI9ANWu9XRiJ2w",
        "video_link": "https://disk.yandex.ru/i/fyWAcizIJHRPuA",
        "notes": "Клиенты проживают в Испании и планируют 3 года там еще прожить. На встрече были Ольга и Андрей (супруг). Объект по итогу планирует обустраиваться для молодой семьи (2 взрослых. 2 ребенка). Изначальный ориентир по бюджету порядка 5 млн, но понимают что возможен рост как цен, так и бюджета. Обратились к нам начитавшись отзывов о том, насколько классно и качественно мы делаем -- достаточно лояльно к нам относятся."
    }

def add_working_days(start_date_str: str, working_days: int) -> str:
    """Функция прибавления рабочих дней (пропускает субботу и воскресенье)"""
    try:
        dt = datetime.strptime(start_date_str, "%d.%m.%Y")
        added = 0
        while added < working_days:
            dt += timedelta(days=1)
            if dt.weekday() < 5:  # 0-4 это Пн-Пт
                added += 1
        return dt.strftime("%d.%m.%Y")
    except ValueError:
        return "Ошибка формата даты"


class DpContractFormView(ft.UserControl):
    def __init__(self):
        super().__init__()
        self.project_data = None

    def build(self):
        # 1. Поиск по ссылке amoCRM
        self.search_input = ft.TextField(
            label="Ссылка на сделку amoCRM", hint_text="https://...amocrm.ru/leads/detail/12345678", 
            expand=True, height=48, text_size=13, border_radius=12,
            filled=True, fill_color="#F8FAFC"
        )
        self.search_btn = ft.ElevatedButton(
            "Найти в базе", icon=ft.icons.SEARCH_ROUNDED, 
            bgcolor="#0C66E4", color="#FFFFFF", height=48,
            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=12)),
            on_click=self.on_search
        )

        # 2. Ручные поля ввода
        self.client_info_input = ft.TextField(
            label="Телефон и ФИО", hint_text="89096552569 Кононович Ольга Сергеевна", 
            height=48, text_size=13, border_radius=12
        )
        self.address_input = ft.TextField(
            label="Адрес и Этаж", hint_text="г. Москва, ул. Петра Кончаловского, д. 7, корп. 2, кв. 160 (Этаж 4)", 
            height=48, text_size=13, border_radius=12
        )
        
        self.status_dd = ft.Dropdown(
            label="Статус договора", value="Подписан (Оплачена первая часть)",
            options=[ft.dropdown.Option("Подписан (Оплачена первая часть)"), ft.dropdown.Option("На согласовании"), ft.dropdown.Option("Отправлен")],
            height=48, text_size=13, border_radius=12, expand=True
        )
        self.esign_dd = ft.Dropdown(
            label="Подписание по ЭП", value="Нет",
            options=[ft.dropdown.Option("Да"), ft.dropdown.Option("Нет")],
            height=48, text_size=13, border_radius=12, width=150
        )
        self.type_dd = ft.Dropdown(
            label="Тип проекта", value="Онлайн ДП",
            options=[ft.dropdown.Option("Онлайн ДП"), ft.dropdown.Option("Оффлайн ДП"), ft.dropdown.Option("Технический проект")],
            height=48, text_size=13, border_radius=12, expand=True
        )
        self.discount_input = ft.TextField(label="Скидка (%)", value="10", height=48, text_size=13, border_radius=12, width=120)
        self.measure_date_input = ft.TextField(label="Дата замера", hint_text="08.10 или 09.10 ориентировочно", height=48, text_size=13, border_radius=12, expand=True)
        self.chat_members_input = ft.TextField(label="Кого добавить в чат", hint_text="Андрей (супруг) @bigoonotation", height=48, text_size=13, border_radius=12, expand=True)

        # 3. Результат генерации
        self.result_text = ft.TextField(
            multiline=True, read_only=True, expand=True, min_lines=15, 
            text_size=13, border_color="#E2E8F0", border_radius=12,
            bgcolor="#F8FAFC"
        )
        self.generate_btn = ft.ElevatedButton(
            "Сгенерировать сообщение", icon=ft.icons.AUTO_AWESOME_ROUNDED, 
            bgcolor="#15803D", color="#FFFFFF", height=48, expand=True,
            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=12)),
            on_click=self.on_generate, disabled=True
        )
        self.copy_btn = ft.ElevatedButton(
            "Скопировать", icon=ft.icons.COPY_ALL_ROUNDED, 
            bgcolor="#0C66E4", color="#FFFFFF", height=48,
            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=12)),
            on_click=self.on_copy, disabled=True
        )

        # Компоновка интерфейса
        search_row = ft.Row([self.search_input, self.search_btn], spacing=12)
        
        self.manual_form = ft.Column(
            spacing=16,
            visible=False,
            controls=[
                ft.Text("Ручные параметры", size=15, weight=ft.FontWeight.BOLD, color="#1E293B"),
                self.client_info_input,
                self.address_input,
                ft.Row([self.status_dd, self.esign_dd]),
                ft.Row([self.type_dd, self.discount_input]),
                self.measure_date_input,
                self.chat_members_input,
                ft.Row([self.generate_btn])
            ]
        )

        left_column = ft.Container(
            expand=True,
            padding=20,
            bgcolor="#FFFFFF",
            border=ft.border.all(1, "#E2E8F0"),
            border_radius=16,
            content=ft.Column([
                ft.Text("Формирование отчета ДП", size=20, weight=ft.FontWeight.BOLD, color="#0F172A"),
                ft.Text("Поиск данных по ссылке на сделку и ручная донастройка параметров.", size=13, color="#64748B"),
                ft.Container(height=10),
                search_row,
                ft.Divider(height=30, color="#E2E8F0"),
                self.manual_form
            ], scroll=ft.ScrollMode.AUTO)
        )

        right_column = ft.Container(
            width=450,
            padding=20,
            bgcolor="#FFFFFF",
            border=ft.border.all(1, "#E2E8F0"),
            border_radius=16,
            content=ft.Column([
                ft.Row([
                    ft.Text("Готовое сообщение", size=16, weight=ft.FontWeight.BOLD, color="#1E293B"),
                    self.copy_btn
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                ft.Container(height=8),
                self.result_text
            ])
        )

        return ft.Container(
            padding=24, expand=True,
            content=ft.Row([left_column, right_column], expand=True, spacing=24, vertical_alignment=ft.CrossAxisAlignment.START)
        )

    def on_search(self, e):
        query = self.search_input.value.strip()
        data = fetch_project_from_sheets(query)
        
        if data:
            self.project_data = data
            self.manual_form.visible = True
            self.generate_btn.disabled = False
            self.update()
            e.page.show_snack_bar(ft.SnackBar(ft.Text("Данные успешно загружены! Заполните недостающие поля."), bgcolor="#15803D"))
        else:
            e.page.show_snack_bar(ft.SnackBar(ft.Text("Введите корректную ссылку на сделку."), bgcolor="#DC2626"))

    def on_generate(self, e):
        if not self.project_data:
            return

        d = self.project_data
        
        # 1. Расчет стоимости за м2
        cost_per_m2 = 0
        if d["area"] > 0:
            cost_per_m2 = int(round(d["cost"] / d["area"]))

        # 2. Расчет даты финиша (Только рабочие дни)
        finish_date = add_working_days(d["start_date"], d["dev_days"])

        # Форматирование скидки
        discount_val = self.discount_input.value.strip()
        if discount_val and "%" not in discount_val:
            discount_val += "%"

        # Сборка финального текста
        msg = f"{d['project_id']}\n"
        msg += f"{self.client_info_input.value.strip()}\n"
        msg += f"Адрес: {self.address_input.value.strip()}\n"
        msg += f"Площадь: {d['area']:g} м2\n"
        msg += f"Договор на {self.type_dd.value} {self.status_dd.value}\n"
        msg += f"Подписание по ЭП: {self.esign_dd.value}\n"
        msg += f"Стоимость за м2: {cost_per_m2} р.\n"
        msg += f"Стоимость: {int(d['cost'])} р.\n"
        msg += f"Скидка: {discount_val}\n"
        msg += f"Тип проекта: {self.type_dd.value}\n"
        msg += f"Старт: {d['start_date']}\n"
        msg += f"Финиш: {finish_date}\n"
        msg += f"Стиль: {d['style']}\n"
        msg += f"Ключи: {d['keys']}\n"
        msg += f"Дата замера: {self.measure_date_input.value.strip()}\n"
        msg += f"Состояние: {d['state']}\n"
        msg += f"Источник: {d['source']}\n"
        msg += f"Менеджер: {d['manager']}\n"
        msg += f"Цикл сделки: {d['cycle_days']}\n"
        msg += f"Кого добавить в чат: {self.chat_members_input.value.strip()}\n"
        msg += f"Файлы от заказчика: {d['files_link']}\n"
        msg += f"Видео с онлайн встречи: {d['video_link']}\n"
        msg += f"Примечания от КЦ: {d['notes']}"

        self.result_text.value = msg
        self.copy_btn.disabled = False
        self.update()

    def on_copy(self, e):
        e.page.set_clipboard(self.result_text.value)
        e.page.show_snack_bar(ft.SnackBar(ft.Text("Скопировано в буфер обмена!"), duration=2000))