import os
import subprocess
import threading
import flet as ft
from apps.core.ai_engine import extract_audio_to_folder


def AudioExtractorView(page: ft.Page):
    # Папка сохранения по умолчанию: папка «Загрузки» пользователя
    default_download_dir = os.path.join(os.path.expanduser("~"), "Downloads")
    if not os.path.exists(default_download_dir):
        default_download_dir = os.path.expanduser("~")

    chosen_folder = {"path": default_download_dir}
    chosen_video_file = {"path": ""}

    status_text = ft.Text("", size=13, weight=ft.FontWeight.W_500)
    progress_bar = ft.ProgressBar(visible=False, color="#0C66E4", height=4)
    result_box = ft.Container(visible=False)

    source_mode_dropdown = ft.Dropdown(
        label="Источник видео",
        value="Файл с видео",
        width=180,
        height=48,
        text_size=13,
        label_style=ft.TextStyle(size=12, color="#64748B"),
        filled=True,
        fill_color="#F1F5F9",
        border=ft.InputBorder.NONE,
        border_radius=12,
        options=[
            ft.dropdown.Option("Файл с видео"),
            ft.dropdown.Option("Ссылка на видео"),
        ],
    )

    video_url_input = ft.TextField(
        label="Ссылка на видео (Яндекс.Диск или прямая)",
        hint_text="https://disk.yandex.ru/i/...",
        expand=True,
        height=48,
        text_size=13,
        label_style=ft.TextStyle(size=12, color="#64748B"),
        filled=True,
        fill_color="#F1F5F9",
        border=ft.InputBorder.NONE,
        border_radius=12,
        visible=False,
    )

    selected_video_label = ft.Text("Файл не выбран (MP4, MOV, MKV, AVI, WEBM)", size=12, color="#64748B", expand=True)

    def on_video_picked(e: ft.FilePickerResultEvent):
        if e.files and len(e.files) > 0:
            vf = e.files[0]
            chosen_video_file["path"] = vf.path
            selected_video_label.value = f"Выбран файл: {vf.name} ({round(vf.size / (1024*1024), 2)} МБ)"
            selected_video_label.color = "#0C66E4"
            selected_video_label.weight = ft.FontWeight.W_600
        page.update()

    video_file_picker = ft.FilePicker(on_result=on_video_picked)
    if video_file_picker not in page.overlay:
        page.overlay.append(video_file_picker)

    pick_video_btn = ft.ElevatedButton(
        "Выбрать видеофайл",
        icon=ft.icons.VIDEO_FILE_ROUNDED,
        bgcolor="#EBF3FC",
        color="#0C66E4",
        height=48,
        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=12)),
        on_click=lambda e: video_file_picker.pick_files(
            allow_multiple=False,
            allowed_extensions=["mp4", "mov", "mkv", "avi", "webm", "m4v"]
        ),
    )

    video_file_row = ft.Row(
        controls=[pick_video_btn, selected_video_label],
        spacing=12,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
        visible=True,
        expand=True,
    )

    def on_source_mode_change(e):
        is_url = (source_mode_dropdown.value == "Ссылка на видео")
        video_url_input.visible = is_url
        video_file_row.visible = not is_url
        page.update()

    source_mode_dropdown.on_change = on_source_mode_change

    custom_name_input = ft.TextField(
        label="Название итогового аудиофайла (необязательно)",
        hint_text="Например: Встреча_Иванов_2026",
        height=48,
        text_size=13,
        label_style=ft.TextStyle(size=12, color="#64748B"),
        filled=True,
        fill_color="#F1F5F9",
        border=ft.InputBorder.NONE,
        border_radius=12,
        expand=True,
    )

    save_dir_label = ft.Text(f"Папка: {chosen_folder['path']}", size=12, color="#475569", expand=True)

    def on_folder_picked(e: ft.FilePickerResultEvent):
        if e.path:
            chosen_folder["path"] = e.path
            save_dir_label.value = f"Папка: {e.path}"
        page.update()

    dir_picker = ft.FilePicker(on_result=on_folder_picked)
    if dir_picker not in page.overlay:
        page.overlay.append(dir_picker)

    pick_folder_btn = ft.OutlinedButton(
        "Изменить папку",
        icon=ft.icons.FOLDER_OPEN_ROUNDED,
        height=44,
        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=12)),
        on_click=lambda e: dir_picker.get_directory_path(dialog_title="Выберите папку для сохранения аудио"),
    )

    def open_saved_folder(target_file_path):
        if not target_file_path or not os.path.exists(target_file_path):
            return
        if sys.platform == "win32":
            subprocess.run(["explorer", "/select,", os.path.normpath(target_file_path)])
        else:
            folder = os.path.dirname(target_file_path)
            subprocess.run(["open" if sys.platform == "darwin" else "xdg-open", folder])

    def do_extraction(e):
        is_url = (source_mode_dropdown.value == "Ссылка на видео")
        source_val = video_url_input.value.strip() if is_url else chosen_video_file["path"]

        if not source_val:
            status_text.value = "Укажите ссылку или выберите видеофайл!"
            status_text.color = "#DC2626"
            page.update()
            return

        out_dir = chosen_folder["path"]
        if not os.path.exists(out_dir):
            try:
                os.makedirs(out_dir, exist_ok=True)
            except Exception as err:
                status_text.value = f"Не удалось создать целевую папку: {err}"
                status_text.color = "#DC2626"
                page.update()
                return

        extract_btn.disabled = True
        progress_bar.visible = True
        result_box.visible = False
        status_text.value = "Начало процесса извлечения..."
        status_text.color = "#0C66E4"
        page.update()

        def _worker():
            try:
                def prog(msg):
                    status_text.value = msg
                    page.update()

                out_file = extract_audio_to_folder(
                    source_type="url" if is_url else "file",
                    source_val=source_val,
                    output_folder=out_dir,
                    custom_name=custom_name_input.value.strip(),
                    progress_callback=prog
                )

                file_size_mb = round(os.path.getsize(out_file) / (1024 * 1024), 2)
                status_text.value = "Готово! Аудиодорожка успешно извлечена."
                status_text.color = "#15803D"

                result_box.content = ft.Container(
                    bgcolor="#F0FDF4",
                    border=ft.border.all(1, "#BBF7D0"),
                    border_radius=12,
                    padding=16,
                    content=ft.Row(
                        controls=[
                            ft.Icon(ft.icons.CHECK_CIRCLE_ROUNDED, color="#15803D", size=26),
                            ft.Column([
                                ft.Text(f"Файл сохранен: {os.path.basename(out_file)} ({file_size_mb} МБ)", size=13, weight=ft.FontWeight.BOLD, color="#166534"),
                                ft.Text(f"Путь: {out_file}", size=11, color="#15803D"),
                            ], expand=True, spacing=2),
                            ft.ElevatedButton(
                                "Показать в папке",
                                icon=ft.icons.FOLDER_ROUNDED,
                                bgcolor="#15803D",
                                color="#FFFFFF",
                                style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10)),
                                on_click=lambda ev, p=out_file: open_saved_folder(p),
                            )
                        ],
                        spacing=12,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    )
                )
                result_box.visible = True

            except Exception as ex:
                status_text.value = f"Ошибка: {ex}"
                status_text.color = "#DC2626"
            finally:
                extract_btn.disabled = False
                progress_bar.visible = False
                page.update()

        threading.Thread(target=_worker, daemon=True).start()

    extract_btn = ft.ElevatedButton(
        "🎧 Извлечь аудио (MP3)",
        icon=ft.icons.HEADSET_ROUNDED,
        bgcolor="#0C66E4",
        color=ft.colors.WHITE,
        height=48,
        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=12)),
        on_click=do_extraction,
    )

    card = ft.Container(
        bgcolor=ft.colors.WHITE,
        border=ft.border.all(1, "#E2E8F0"),
        border_radius=18,
        padding=24,
        content=ft.Column(
            spacing=16,
            controls=[
                ft.Text("Параметры извлечения", size=16, weight=ft.FontWeight.BOLD, color="#1E293B"),
                ft.Row([source_mode_dropdown, video_file_row, video_url_input], spacing=10),
                custom_name_input,
                ft.Container(
                    bgcolor="#F8FAFC",
                    border=ft.border.all(1, "#E2E8F0"),
                    border_radius=12,
                    padding=14,
                    content=ft.Row(
                        controls=[
                            ft.Icon(ft.icons.FOLDER_SPECIAL_ROUNDED, color="#0C66E4", size=22),
                            save_dir_label,
                            pick_folder_btn,
                        ],
                        spacing=12,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    )
                ),
                extract_btn,
                progress_bar,
                status_text,
                result_box,
            ]
        )
    )

    return ft.Container(
        padding=24,
        content=ft.Column(
            controls=[
                ft.Text("Извлечение звука (Аудио экстрактор)", size=24, weight=ft.FontWeight.BOLD, color="#0F172A"),
                ft.Text("Быстрое извлечение MP3-аудиодорожки из видеофайла или по ссылке Яндекс.Диска с сохранением на ПК", size=13, color="#64748B"),
                ft.Container(height=4),
                card,
            ],
            spacing=16,
            scroll=ft.ScrollMode.AUTO,
        ),
        expand=True,
    )