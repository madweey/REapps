import os
import flet as ft
from datetime import datetime
from apps.core.sheets import get_all_prompts, save_analysis
from apps.core.ai_engine import download_file_stream, extract_audio_with_ffmpeg, analyze_audio_with_gemini


def SingleAnalysisView(page: ft.Page, current_user: dict | None = None):
    current_username = (current_user.get("name") if current_user else "Сотрудник").strip()

    source_url_input = ft.TextField(
        label="Ссылка на аудио (mp3) или видео (Яндекс.Диск)",
        hint_text="https://disk.yandex.ru/i/... или https://vats.../record.mp3",
        width=520,
        height=45,
    )

    client_deal_input = ft.TextField(
        label="Клиент / Сделка",
        hint_text="Иванов / Сделка #12345",
        width=250,
        height=45,
    )

    comm_type_dropdown = ft.Dropdown(
        label="Тип коммуникации",
        value="Онлайн встреча (презентация)",
        width=260,
        height=45,
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
        width=380,
        height=45,
        options=[],
    )

    custom_prompt_input = ft.TextField(
        label="Инструкция / Промт для нейросети",
        hint_text="Опишите задачу анализа или отредактируйте шаблон...",
        multiline=True,
        min_lines=3,
        max_lines=7,
        width=1050,
    )

    status_text = ft.Text("", size=13, weight=ft.FontWeight.W_500)
    progress_bar = ft.ProgressBar(visible=False, color="#1976D2", width=1050)

    summary_output = ft.TextField(
        label="Краткое резюме (для CRM)",
        multiline=True,
        min_lines=3,
        max_lines=5,
        width=1050,
    )

    report_output = ft.TextField(
        label="Полный отчет ИИ (структурированный разбор)",
        multiline=True,
        min_lines=10,
        max_lines=18,
        read_only=True,
        width=1050,
    )

    transcription_output = ft.TextField(
        label="Полная транскрипция разговора",
        multiline=True,
        min_lines=10,
        max_lines=20,
        read_only=True,
        width=1050,
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
            status_text.color = "#D32F2F"
            page.update()
            return

        if not prompt_text_val:
            status_text.value = "Выберите или введите текст промта!"
            status_text.color = "#D32F2F"
            page.update()
            return

        run_btn.disabled = True
        progress_bar.visible = True
        status_text.value = "Скачивание медиафайла..."
        status_text.color = "#1976D2"
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
            status_text.color = "#388E3C"

            for p in (local_raw_path, compressed_audio_path):
                if p and os.path.exists(p) and p != local_raw_path:
                    try:
                        os.remove(p)
                    except Exception:
                        pass
        except Exception as err:
            status_text.value = f"Ошибка анализа: {err}"
            status_text.color = "#D32F2F"
        finally:
            run_btn.disabled = False
            progress_bar.visible = False
            page.update()

    def on_save_to_table(e):
        if not report_output.value and not transcription_output.value:
            status_text.value = "Сначала проведите анализ разговора!"
            status_text.color = "#D32F2F"
            page.update()
            return

        payload = {
            "author": current_username,
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
            status_text.value = "Разбор сохранён в лист 'Разборы'!"
            status_text.color = "#388E3C"
            page.update()
        except Exception as err:
            status_text.value = f"Ошибка сохранения: {err}"
            status_text.color = "#D32F2F"
            page.update()

    run_btn = ft.ElevatedButton(
        "Запустить AI-анализ",
        icon=ft.icons.AUTO_AWESOME,
        bgcolor="#1976D2",
        color="#FFFFFF",
        height=45,
        on_click=run_analysis,
    )

    load_prompts_into_dropdown()

    return ft.Container(
        padding=20,
        content=ft.Column(
            controls=[
                ft.Text("Разбор звонка / встречи", size=22, weight=ft.FontWeight.BOLD),
                ft.Text("Автоматическая транскрибация видеозаписей с Яндекс.Диска и звонков с анализом через Gemini", size=13, color="#616161"),
                ft.Divider(height=1),
                ft.Row(
                    controls=[source_url_input, client_deal_input, comm_type_dropdown],
                    spacing=10,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                ft.Row(
                    controls=[
                        prompt_dropdown,
                        ft.OutlinedButton("Обновить промты", icon=ft.icons.REFRESH, height=45, on_click=lambda e: load_prompts_into_dropdown()),
                    ],
                    spacing=10,
                ),
                custom_prompt_input,
                ft.Row(
                    controls=[
                        run_btn,
                        ft.ElevatedButton("Сохранить результат в таблицу", icon=ft.icons.SAVE, bgcolor="#388E3C", color="#FFFFFF", height=45, on_click=on_save_to_table),
                        ft.OutlinedButton("Скопировать отчет", icon=ft.icons.COPY, height=45, on_click=lambda e: page.set_clipboard(report_output.value) or setattr(status_text, "value", "Отчет скопирован!") or page.update()),
                    ],
                    spacing=10,
                ),
                progress_bar,
                status_text,
                summary_output,
                report_output,
                transcription_output,
            ],
            spacing=12,
            scroll=ft.ScrollMode.AUTO,
        ),
        expand=True,
    )