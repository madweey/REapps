import os
import flet as ft
from datetime import datetime
from apps.core.sheets import get_all_prompts, save_analysis
from apps.core.auth import get_all_accounts
from apps.core.ai_engine import download_file_stream, extract_audio_with_ffmpeg, analyze_audio_with_gemini


def SingleAnalysisView(page: ft.Page, current_user: dict | None = None):
    current_username = (current_user.get("name") if current_user else "Сотрудник").strip()

    try:
        accs = get_all_accounts()
        account_names = sorted(list(set(a["name"] for a in accs if a.get("name"))))
    except Exception:
        account_names = [current_username] if current_username else []

    if current_username and current_username not in account_names:
        account_names.insert(0, current_username)

    source_url_input = ft.TextField(
        label="Ссылка на аудио (mp3) или видео (Яндекс.Диск)",
        hint_text="https://disk.yandex.ru/i/... или https://vats.../record.mp3",
        expand=True,
        height=48,
        text_size=13,
        label_style=ft.TextStyle(size=12, color="#64748B"),
        filled=True,
        fill_color="#F1F5F9",
        border=ft.InputBorder.NONE,
        border_radius=12,
    )

    client_deal_input = ft.TextField(
        label="Клиент / Сделка",
        hint_text="Иванов / Сделка #12345",
        width=220,
        height=48,
        text_size=13,
        label_style=ft.TextStyle(size=12, color="#64748B"),
        filled=True,
        fill_color="#F1F5F9",
        border=ft.InputBorder.NONE,
        border_radius=12,
    )

    speaker_dropdown = ft.Dropdown(
        label="Кто вел разговор",
        value=current_username if current_username in account_names else (account_names[0] if account_names else ""),
        width=220,
        height=48,
        text_size=13,
        label_style=ft.TextStyle(size=12, color="#64748B"),
        filled=True,
        fill_color="#F1F5F9",
        border=ft.InputBorder.NONE,
        border_radius=12,
        options=[ft.dropdown.Option(name) for name in account_names],
    )

    comm_type_dropdown = ft.Dropdown(
        label="Тип коммуникации",
        value="Онлайн встреча (презентация)",
        width=240,
        height=48,
        text_size=13,
        label_style=ft.TextStyle(size=12, color="#64748B"),
        filled=True,
        fill_color="#F1F5F9",
        border=ft.InputBorder.NONE,
        border_radius=12,
        options=[
            ft.dropdown.Option("Первичный звонок КЦ"),
            ft.dropdown.Option("Онлайн встреча (презентация)"),
            ft.dropdown.Option("Встреча с дизайнером"),
            ft.dropdown.Option("Выезд с прорабом / Замер"),
            ft.dropdown.Option("Вопросы по договору"),
            ft.dropdown.Option("Другое"),
        ],
    )

    prompt_dropdown = ft.Dropdown(
        label="Шаблон промта",
        expand=True,
        height=48,
        text_size=13,
        label_style=ft.TextStyle(size=12, color="#64748B"),
        filled=True,
        fill_color="#F1F5F9",
        border=ft.InputBorder.NONE,
        border_radius=12,
        options=[],
    )

    custom_prompt_input = ft.TextField(
        label="Инструкция / Промт для нейросети",
        hint_text="Опишите задачу анализа или отредактируйте шаблон...",
        multiline=True,
        min_lines=4,
        max_lines=8,
        text_size=13,
        label_style=ft.TextStyle(size=12, color="#64748B"),
        filled=True,
        fill_color="#F1F5F9",
        border=ft.InputBorder.NONE,
        border_radius=12,
    )

    status_text = ft.Text("", size=13, weight=ft.FontWeight.W_500)
    progress_bar = ft.ProgressBar(visible=False, color="#0C66E4", height=4)

    summary_output = ft.TextField(
        label="Краткое резюме (для CRM)",
        multiline=True,
        min_lines=3,
        max_lines=5,
        text_size=13,
        label_style=ft.TextStyle(size=12, color="#64748B"),
        filled=True,
        fill_color="#F8FAFC",
        border=ft.InputBorder.NONE,
        border_radius=12,
    )

    report_output = ft.TextField(
        label="Полный отчет ИИ (структурированный разбор)",
        multiline=True,
        min_lines=10,
        max_lines=18,
        read_only=True,
        text_size=13,
        label_style=ft.TextStyle(size=12, color="#64748B"),
        filled=True,
        fill_color="#F8FAFC",
        border=ft.InputBorder.NONE,
        border_radius=12,
    )

    transcription_output = ft.TextField(
        label="Полная транскрипция разговора",
        multiline=True,
        min_lines=8,
        max_lines=20,
        read_only=True,
        text_size=13,
        label_style=ft.TextStyle(size=12, color="#64748B"),
        filled=True,
        fill_color="#F8FAFC",
        border=ft.InputBorder.NONE,
        border_radius=12,
    )

    raw_prompts = []

    def load_prompts_into_dropdown():
        nonlocal raw_prompts
        try:
            raw_prompts = get_all_prompts()
            prompt_dropdown.options = [ft.dropdown.Option(p["title"]) for p in raw_prompts]
            if raw_prompts:
                prompt_dropdown.value = raw_prompts[0]["title"]
                custom_prompt_input.value = raw_prompts[0]["prompt_text"]
            page.update()
        except Exception:
            pass

    def on_prompt_selected(e):
        selected_title = prompt_dropdown.value
        for p in raw_prompts:
            if p["title"] == selected_title:
                custom_prompt_input.value = p["prompt_text"]
                page.update()
                break

    prompt_dropdown.on_change = on_prompt_selected

    def run_analysis(e):
        url = source_url_input.value.strip()
        prompt_text_val = custom_prompt_input.value.strip()

        if not url:
            status_text.value = "Вставьте ссылку на файл!"
            status_text.color = "#DC2626"
            page.update()
            return

        if not prompt_text_val:
            status_text.value = "Выберите или введите текст промта!"
            status_text.color = "#DC2626"
            page.update()
            return

        run_btn.disabled = True
        progress_bar.visible = True
        status_text.value = "Скачивание медиафайла..."
        status_text.color = "#0C66E4"
        page.update()

        try:
            local_filename = f"media_{int(datetime.now().timestamp())}.dat"
            local_raw_path = download_file_stream(url, local_filename)

            status_text.value = "Сжатие звуковой дорожки (ffmpeg)..."
            page.update()
            compressed_audio_path = extract_audio_with_ffmpeg(local_raw_path)

            status_text.value = "Обработка в Google Gemini..."
            page.update()
            ai_res = analyze_audio_with_gemini(compressed_audio_path, prompt_text_val)

            summary_output.value = ai_res["summary"]
            report_output.value = ai_res["full_report"]
            transcription_output.value = ai_res["transcription"]

            status_text.value = "Анализ успешно завершен!"
            status_text.color = "#15803D"

            for p in (local_raw_path, compressed_audio_path):
                if p and os.path.exists(p) and p != local_raw_path:
                    try:
                        os.remove(p)
                    except Exception:
                        pass
        except Exception as err:
            status_text.value = f"Ошибка анализа: {err}"
            status_text.color = "#DC2626"
        finally:
            run_btn.disabled = False
            progress_bar.visible = False
            page.update()

    def on_save_to_table(e):
        if not report_output.value and not transcription_output.value:
            status_text.value = "Сначала проведите анализ разговора!"
            status_text.color = "#DC2626"
            page.update()
            return

        chosen_speaker = (speaker_dropdown.value or current_username).strip()

        payload = {
            "author": chosen_speaker,
            "comm_type": comm_type_dropdown.value or "",
            "client_deal": client_deal_input.value.strip() or "Без названия",
            "source_url": source_url_input.value.strip(),
            "prompt_title": prompt_dropdown.value or "Пользовательский",
            "summary": summary_output.value.strip(),
            "transcription": transcription_output.value.strip(),
            "full_ai_report": report_output.value.strip(),
        }

        try:
            save_analysis(payload)
            status_text.value = f"Разбор сохранён в лист 'Разборы' (Вел: {chosen_speaker})!"
            status_text.color = "#15803D"
            page.update()
        except Exception as err:
            status_text.value = f"Ошибка сохранения: {err}"
            status_text.color = "#DC2626"
            page.update()

    run_btn = ft.ElevatedButton(
        "Запустить AI-анализ",
        icon=ft.icons.AUTO_AWESOME_ROUNDED,
        bgcolor="#0C66E4",
        color=ft.colors.WHITE,
        height=46,
        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=12)),
        on_click=run_analysis,
    )

    save_btn = ft.ElevatedButton(
        "Сохранить результат в таблицу",
        icon=ft.icons.SAVE_ROUNDED,
        bgcolor="#15803D",
        color=ft.colors.WHITE,
        height=46,
        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=12)),
        on_click=on_save_to_table,
    )

    copy_btn = ft.OutlinedButton(
        "Скопировать отчет",
        icon=ft.icons.COPY_ALL_ROUNDED,
        height=46,
        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=12)),
        on_click=lambda e: page.set_clipboard(report_output.value) or page.show_snack_bar(ft.SnackBar(ft.Text("Отчет скопирован!"), duration=1500)),
    )

    load_prompts_into_dropdown()

    # Карточка параметров анализа One UI
    input_card = ft.Container(
        bgcolor=ft.colors.WHITE,
        border=ft.border.all(1, "#E2E8F0"),
        border_radius=18,
        padding=20,
        content=ft.Column(
            spacing=14,
            controls=[
                ft.Row([source_url_input, client_deal_input, speaker_dropdown, comm_type_dropdown], spacing=10),
                ft.Row([
                    prompt_dropdown,
                    ft.OutlinedButton(
                        "Обновить промты",
                        icon=ft.icons.REFRESH_ROUNDED,
                        height=48,
                        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=12)),
                        on_click=lambda e: load_prompts_into_dropdown(),
                    ),
                ], spacing=10),
                custom_prompt_input,
                ft.Row([run_btn, save_btn, copy_btn], spacing=10),
                progress_bar,
                status_text,
            ]
        )
    )

    # Карточка результатов One UI
    results_card = ft.Container(
        bgcolor=ft.colors.WHITE,
        border=ft.border.all(1, "#E2E8F0"),
        border_radius=18,
        padding=20,
        content=ft.Column(
            spacing=14,
            controls=[
                ft.Text("Результаты обработки", size=15, weight=ft.FontWeight.BOLD, color="#1E293B"),
                summary_output,
                report_output,
                transcription_output,
            ]
        )
    )

    return ft.Container(
        padding=24,
        content=ft.Column(
            controls=[
                ft.Text("Разбор звонка / встречи", size=24, weight=ft.FontWeight.BOLD, color="#0F172A"),
                ft.Text("Автоматическая транскрибация видеозаписей с Яндекс.Диска и звонков с анализом через Gemini", size=13, color="#64748B"),
                ft.Container(height=4),
                input_card,
                results_card,
            ],
            spacing=16,
            scroll=ft.ScrollMode.AUTO,
        ),
        expand=True,
    )