import flet as ft

# Цветовая палитра
BG_COLOR = "#F1F5F9"
SURFACE_COLOR = "#FFFFFF"
PRIMARY_COLOR = "#0F172A"
TEXT_MAIN = "#0F172A"
TEXT_MUTED = "#64748B"
BORDER_COLOR = "#CBD5E1"
ACCENT_GREEN = "#059669"
ACCENT_RED = "#DC2626"
ACCENT_AMBER = "#D97706"

# Базовый стиль текстовых полей и списков
BASE_FIELD_STYLE = {
    "dense": True,
    "bgcolor": SURFACE_COLOR,
    "border_color": BORDER_COLOR,
    "focused_border_color": PRIMARY_COLOR,
    "border_radius": 8,
    "text_size": 13,
    "label_style": ft.TextStyle(color=TEXT_MUTED, size=12, weight=ft.FontWeight.W_500),
}