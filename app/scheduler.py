"""Фоновая проверка сроков: напоминания, переход в «Просрочено» / «Требует
проверки» и периодическая эскалация, пока изменение не подтверждено убранным."""
from __future__ import annotations

import logging
from datetime import timedelta

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler

import config
from app import cards, db, keyboards, utils

log = logging.getLogger(__name__)


async def _notify(bot: Bot, change: dict, text: str) -> None:
    chat_id = change.get("card_chat_id") or config.CARD_CHAT_ID
    if not chat_id:
        return
    try:
        await bot.send_message(
            chat_id=chat_id,
            message_thread_id=config.CARD_THREAD_ID,
            text=text,
            reply_markup=keyboards.kb_notice(change["id"]),
        )
    except Exception:  # сеть, бот удалён из чата и т.п. — не роняем весь цикл
        log.exception("не удалось отправить уведомление по изменению #%s", change["id"])


async def check_deadlines(bot: Bot) -> None:
    now_ = utils.now()
    changes = await db.list_open_changes()

    for change in changes:
        target = utils.from_iso(change["target_at"])
        reminder_at = target - timedelta(minutes=config.REMINDER_MINUTES_BEFORE)

        if change["status"] == utils.STATUS_ACTIVE:
            if not change["reminder_sent"] and reminder_at <= now_ < target:
                await _notify(bot, change, cards.build_reminder_text(change))
                await db.update_change(change["id"], reminder_sent=1)

            if now_ >= target:
                new_status = utils.STATUS_OVERDUE if change["has_deadline"] else utils.STATUS_NEEDS_CHECK
                await db.update_change(change["id"], status=new_status, last_notice_at=now_)
                await _notify(bot, change, cards.build_expired_text(change))
                refreshed = await db.get_change(change["id"])
                await cards.refresh_card(bot, refreshed)

        elif change["status"] in (utils.STATUS_OVERDUE, utils.STATUS_NEEDS_CHECK):
            last_notice = utils.from_iso(change["last_notice_at"]) if change["last_notice_at"] else target
            if now_ - last_notice >= timedelta(minutes=config.ESCALATION_MINUTES):
                await _notify(bot, change, cards.build_overdue_text(change))
                await db.update_change(change["id"], last_notice_at=now_)


def setup_scheduler(bot: Bot) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone=config.TZ)
    scheduler.add_job(check_deadlines, "interval", seconds=60, args=[bot], id="check_deadlines")
    scheduler.start()
    return scheduler
