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
    rate_fin: float = 41405.0
    total_fin: float = 3105375.0
    grand_total: float = 4767525.0
    selected_type: str = "complex"
    spec_lines: list = []

    # Новые параметры для комплексного ремонта
    has_furniture: bool = False
    furniture_cost: float = 0.0
    has_appliances: bool = False
    appliances_cost: float = 0.0


current_repair_state = RepairState()