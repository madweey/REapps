# apps/calculator/repair_state.py

class RepairState:
    """Глобальное состояние расчёта калькулятора ремонта."""
    area: float = 75.0
    client_name: str = ""
    address: str = ""
    state_title: str = "Голый бетон"
    has_demolition: bool = False

    # Финансовые показатели из калькулятора
    rate_eng: float = 22162.0
    total_eng: float = 1662150.0
    rate_fin: float = 40931.0
    total_fin: float = 3069825.0
    grand_total: float = 4731975.0
    selected_type: str = "complex"
    spec_lines: list = []


current_repair_state = RepairState()