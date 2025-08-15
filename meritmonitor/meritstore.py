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

    def sum_personal(self):
        this_week = weekly_key()
        self.live_personal_by_system.setdefault(this_week, {})

        return sum(self.live_personal_by_system[this_week].values())

    def sum_system(self):
        this_week = weekly_key()
        self.live_control_points_by_system.setdefault(this_week, {})

        return sum(self.live_control_points_by_system[weekly_key()].values())

    def get_live_control_points_by_system(self):
        this_week = weekly_key()
        self.live_control_points_by_system.setdefault(this_week, {})

        return self.live_control_points_by_system[this_week]
