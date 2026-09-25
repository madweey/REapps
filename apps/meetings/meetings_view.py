import flet as ft
from apps.core.auth import get_all_accounts
from apps.meetings.meetings_common import MeetingsModalManager
from apps.meetings.meetings_book_view import MeetingsBookView
from apps.meetings.meetings_schedule_view import MeetingsScheduleView
from apps.meetings.meetings_registry_view import MeetingsRegistryView


class MeetingsController:
    """Диспетчер встреч, объединяющий подмодули назначения, расписания и реестра."""

    def __init__(self, page: ft.Page, current_user: dict | None = None):
        self.page = page
        self.current_user = current_user
        self.current_username = (current_user.get("name") if current_user else "Не указан").strip()

        try:
            accs = get_all_accounts()
            self.account_names = sorted(list(set(a["name"] for a in accs if a.get("name"))))
        except Exception:
            self.account_names = [self.current_username] if self.current_username else []

        # Менеджер модалок
        self.modal_mgr = MeetingsModalManager(
            page=self.page,
            account_names=self.account_names,
            on_data_changed_callback=self._on_meetings_data_changed,
        )

        # Подмодули
        self.book_subview = MeetingsBookView(
            page=self.page,
            current_username=self.current_username,
            account_names=self.account_names,
            modal_mgr=self.modal_mgr,
        )

        self.schedule_subview = MeetingsScheduleView(
            page=self.page,
            account_names=self.account_names,
            modal_mgr=self.modal_mgr,
        )

        self.registry_subview = MeetingsRegistryView(
            page=self.page,
            account_names=self.account_names,
            modal_mgr=self.modal_mgr,
        )

    def _on_meetings_data_changed(self):
        """Синхронизирует расписание, реестр и слоты при любых действиях."""
        self.book_subview.refresh_slots()
        self.schedule_subview.load_schedule_list()
        self.registry_subview.load_registry_list()

    def get_view(self, subview_key: str) -> ft.Control:
        if subview_key == "meetings_book":
            return self.book_subview.build_view()
        elif subview_key == "meetings_schedule":
            return self.schedule_subview.build_view()
        elif subview_key == "meetings_registry":
            return self.registry_subview.build_view()
        return ft.Container()