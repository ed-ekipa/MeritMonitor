from datetime import datetime, timedelta

def get_last_thursday() -> datetime:
    now = datetime.utcnow()
    thursday = now - timedelta(days=(now.weekday() + 4) % 7)
    thursday = thursday.replace(hour=7, minute=0, second=0, microsecond=0)
    return thursday
