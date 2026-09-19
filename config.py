"""Конфигурация бота: всё, что приходит из переменных окружения / .env."""
from __future__ import annotations

import os
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent


def _env(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name, default)
    return value.strip() if isinstance(value, str) else value


BOT_TOKEN: str = _env("BOT_TOKEN", "") or ""

_card_chat_id = _env("CARD_CHAT_ID", "")
CARD_CHAT_ID: int | None = int(_card_chat_id) if _card_chat_id else None

_card_thread_id = _env("CARD_THREAD_ID", "")
CARD_THREAD_ID: int | None = int(_card_thread_id) if _card_thread_id else None

BOTS: list[str] = [b.strip() for b in (_env("BOTS", "TATI,DREAM,SECRET,IMREQ,ZAKON") or "").split(",") if b.strip()]

TIMEZONE_NAME: str = _env("TIMEZONE", "Europe/Moscow") or "Europe/Moscow"
TZ = ZoneInfo(TIMEZONE_NAME)

REMINDER_MINUTES_BEFORE: int = int(_env("REMINDER_MINUTES_BEFORE", "60") or "60")
ESCALATION_MINUTES: int = int(_env("ESCALATION_MINUTES", "45") or "45")

DB_PATH: str = _env("DB_PATH", "data/deadline_bot.db") or "data/deadline_bot.db"
if not os.path.isabs(DB_PATH):
    DB_PATH = str(BASE_DIR / DB_PATH)

CHANGE_TYPES: list[str] = [
    "Баннер",
    "Загрузочный экран",
    "Текст",
    "Кнопка",
    "Акция",
    "Фон",
    "Другое",
]

CHECK_QUICK_OPTIONS: list[tuple[str, str]] = [
    ("2h", "Через 2 часа"),
    ("4h", "Через 4 часа"),
    ("evening", "Сегодня вечером"),
    ("tomorrow", "Завтра"),
]

EXTEND_OPTIONS: list[tuple[str, str]] = [
    ("1h", "+1 час"),
    ("2h", "+2 часа"),
    ("3h", "+3 часа"),
    ("eod", "До конца дня"),
    ("tomorrow", "До завтра"),
]
