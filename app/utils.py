"""Разбор и форматирование дат, статусы, вспомогательные мелочи."""
from __future__ import annotations

import re
from datetime import datetime, timedelta

import config

STATUS_ACTIVE = "active"
STATUS_OVERDUE = "overdue"
STATUS_NEEDS_CHECK = "needs_check"
STATUS_COMPLETED = "completed"

STATUS_EMOJI = {
    STATUS_ACTIVE: "🟡",
    STATUS_OVERDUE: "🔴",
    STATUS_NEEDS_CHECK: "🟠",
    STATUS_COMPLETED: "✅",
}

STATUS_TEXT = {
    STATUS_ACTIVE: "Активно",
    STATUS_OVERDUE: "Просрочено",
    STATUS_NEEDS_CHECK: "Требует проверки",
    STATUS_COMPLETED: "Завершено",
}


def now() -> datetime:
    return datetime.now(config.TZ)


def to_iso(dt: datetime) -> str:
    return dt.astimezone(config.TZ).isoformat()


def from_iso(value: str) -> datetime:
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=config.TZ)
    return dt.astimezone(config.TZ)


_TIME_RE = re.compile(r"^(\d{1,2}):(\d{2})$")
_DATE_TIME_RE = re.compile(r"^(\d{1,2})\.(\d{1,2})\s+(\d{1,2}):(\d{2})$")
_FULL_DATE_TIME_RE = re.compile(r"^(\d{1,2})\.(\d{1,2})\.(\d{4})\s+(\d{1,2}):(\d{2})$")


def parse_datetime(text: str, base: datetime | None = None) -> datetime | None:
    """Понимает форматы: "20:00", "12.09 20:00", "12.09.2026 20:00"."""
    text = text.strip()
    base = base or now()

    m = _FULL_DATE_TIME_RE.match(text)
    if m:
        day, month, year, hour, minute = map(int, m.groups())
        try:
            return datetime(year, month, day, hour, minute, tzinfo=config.TZ)
        except ValueError:
            return None

    m = _DATE_TIME_RE.match(text)
    if m:
        day, month, hour, minute = map(int, m.groups())
        year = base.year
        try:
            candidate = datetime(year, month, day, hour, minute, tzinfo=config.TZ)
        except ValueError:
            return None
        # если дата уже далеко в прошлом - скорее всего имелся в виду следующий год
        if candidate < base - timedelta(days=1):
            try:
                candidate = candidate.replace(year=year + 1)
            except ValueError:
                pass
        return candidate

    m = _TIME_RE.match(text)
    if m:
        hour, minute = map(int, m.groups())
        if not (0 <= hour < 24 and 0 <= minute < 60):
            return None
        candidate = base.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if candidate <= base:
            candidate += timedelta(days=1)
        return candidate

    return None


def fmt_abs(dt: datetime) -> str:
    """Формат для карточки: "12.09 в 14:20"."""
    return dt.strftime("%d.%m в %H:%M")


def fmt_rel(dt: datetime, base: datetime | None = None) -> str:
    """Формат для списков /active, /today: "сегодня в 20:00", "завтра в 12:00", "15.09 в 00:00"."""
    base = base or now()
    if dt.date() == base.date():
        return f"сегодня в {dt.strftime('%H:%M')}"
    if dt.date() == (base + timedelta(days=1)).date():
        return f"завтра в {dt.strftime('%H:%M')}"
    return dt.strftime("%d.%m в %H:%M")


def apply_check_quick_option(code: str, base: datetime | None = None) -> datetime | None:
    base = base or now()
    if code == "2h":
        return base + timedelta(hours=2)
    if code == "4h":
        return base + timedelta(hours=4)
    if code == "evening":
        candidate = base.replace(hour=20, minute=0, second=0, microsecond=0)
        if candidate <= base:
            candidate += timedelta(days=1)
        return candidate
    if code == "tomorrow":
        candidate = (base + timedelta(days=1)).replace(hour=12, minute=0, second=0, microsecond=0)
        return candidate
    return None


def apply_extend_option(code: str, base: datetime | None = None) -> datetime | None:
    base = base or now()
    if code == "1h":
        return base + timedelta(hours=1)
    if code == "2h":
        return base + timedelta(hours=2)
    if code == "3h":
        return base + timedelta(hours=3)
    if code == "eod":
        return base.replace(hour=23, minute=59, second=0, microsecond=0)
    if code == "tomorrow":
        return (base + timedelta(days=1)).replace(hour=12, minute=0, second=0, microsecond=0)
    return None


def display_name(username: str | None, full_name: str | None) -> str:
    if username:
        return f"@{username}"
    return full_name or "неизвестно"
