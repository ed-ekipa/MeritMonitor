from meritmonitor.thursday import get_last_thursday


def weekly_key() -> int:
    return int(get_last_thursday().timestamp())


class MeritStore:
    live_personal_by_system = {}
    live_control_points_by_system = {}

    def add_personal(self, system: str, amount: int):
        this_week = weekly_key()
        self.live_personal_by_system.setdefault(this_week, {}).setdefault(system, 0)

        self.live_personal_by_system[this_week][system] += amount

    def add_control_points(self, system:str, amount: int):
        this_week = weekly_key()
        self.live_control_points_by_system.setdefault(this_week, {}).setdefault(system, 0)

        self.live_control_points_by_system[this_week][system] += amount

    def sum_personal(self) -> int:
        this_week = weekly_key()
        self.live_personal_by_system.setdefault(this_week, {})

        return sum(self.live_personal_by_system[this_week].values())

    def sum_system(self) -> int:
        this_week = weekly_key()
        self.live_control_points_by_system.setdefault(this_week, {})

        return sum(self.live_control_points_by_system[this_week].values())

    def get_control_points_by_system_report(self) -> str:
        this_week = weekly_key()
        self.live_control_points_by_system.setdefault(this_week, {})
        control_points_by_system = self.live_control_points_by_system[this_week]
        text = ""
        for system in sorted(control_points_by_system):
            s = int(control_points_by_system[system])
            text += f"- `{system}`: **{s}**\n"
        return text
