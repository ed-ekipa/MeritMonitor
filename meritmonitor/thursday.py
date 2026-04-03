from datetime import datetime, timedelta, timezone


def get_last_thursday() -> datetime:
    now = datetime.now(timezone.utc)
    thursday = now - timedelta(days=(now.weekday() + 4) % 7)
    thursday = thursday.replace(hour=7, minute=0, second=0, microsecond=0)
    return thursday
