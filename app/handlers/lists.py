"""Команды /active и /today."""
from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from app import cards, db, utils

router = Router(name="lists")


def _line(idx: int, change: dict) -> str:
    emoji = utils.STATUS_EMOJI[change["status"]]
    label = cards.deadline_field_label(change)
    target_at = utils.from_iso(change["target_at"])
    return f"{emoji} {idx}. {change['description']}\n{label} {utils.fmt_rel(target_at)}"


@router.message(Command("active"))
async def cmd_active(message: Message) -> None:
    changes = await db.list_open_changes()
    if not changes:
        await message.answer("Сейчас нет ни одного активного временного изменения. 🎉")
        return
    lines = ["Активные временные изменения", ""]
    lines.extend(_line(i, c) for i, c in enumerate(changes, start=1))
    await message.answer("\n\n".join(lines) if len(lines) > 2 else lines[0])


@router.message(Command("today"))
async def cmd_today(message: Message) -> None:
    changes = await db.list_open_changes()
    today = utils.now().date()
    todays = [
        c
        for c in changes
        if utils.from_iso(c["target_at"]).date() == today
        or c["status"] in (utils.STATUS_OVERDUE, utils.STATUS_NEEDS_CHECK)
    ]
    if not todays:
        await message.answer("На сегодня ничего убирать/проверять не нужно. 🎉")
        return
    lines = ["Сегодня нужно обработать", ""]
    lines.extend(_line(i, c) for i, c in enumerate(todays, start=1))
    await message.answer("\n\n".join(lines))
