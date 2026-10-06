from datetime import datetime, timezone


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def as_utc(value: datetime) -> datetime:
    """SQLite hands back naive datetimes; treat them as the UTC they were stored as."""
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
