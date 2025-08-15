state_table = {
    "Unoccupied": 1.00,
    "Exploited": 0.65,
    "Fortified": 0.65,
    "Stronghold": 0.65,
    "Controlled": 0.65
}

def control_points_from_merits_gained(system_state: str, net_merits: int) -> int:
    multiplier = state_table.get(system_state, 1.0)

    gross_merits = round(net_merits / multiplier)
    system_control_points = round(gross_merits * 0.25)

    return system_control_points
