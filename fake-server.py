from datetime import datetime
from zoneinfo import ZoneInfo

def timezone_offsets(timezone_name):
    tz = ZoneInfo(timezone_name)

    def fmt(dt):
        offset = int(dt.utcoffset().total_seconds() // 60)
        hours, minutes = divmod(abs(offset), 60)
        sign = "+" if offset >= 0 else "-"
        return f"UTC{sign}{hours}:{minutes:02d}"

    winter = datetime(2026, 1, 15, tzinfo=tz)
    summer = datetime(2026, 7, 15, tzinfo=tz)

    return f"{fmt(winter)}{fmt(summer)}"

print(timezone_offsets("Atlantic/Reykjavik"))
# UTC+1:00UTC+2:00