"""Точка входа: сборка бота, роутеров и планировщика."""
from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand

import config
from app import db
from app.handlers import card_actions, debug as debug_handlers, lists as lists_handlers, registration, wizard
from app.middlewares import AutoRegisterMiddleware, TraceMiddleware
from app.scheduler import setup_scheduler

BOT_COMMANDS = [
    BotCommand(command="temp", description="Создать новое временное изменение"),
    BotCommand(command="active", description="Все активные временные изменения"),
    BotCommand(command="today", description="Что нужно сделать сегодня"),
    BotCommand(command="chatid", description="ID этого чата (для настройки CARD_CHAT_ID)"),
]


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    if not config.BOT_TOKEN:
        raise SystemExit("Не задан BOT_TOKEN — заполни .env (см. .env.example)")

    await db.init_db()

    bot = Bot(token=config.BOT_TOKEN, default=DefaultBotProperties(parse_mode=None))
    await bot.set_my_commands(BOT_COMMANDS)

    dp = Dispatcher(storage=MemoryStorage())

    dp.message.middleware(AutoRegisterMiddleware())
    dp.callback_query.middleware(AutoRegisterMiddleware())
    dp.message.middleware(TraceMiddleware())
    dp.callback_query.middleware(TraceMiddleware())

    dp.include_router(registration.router)
    dp.include_router(wizard.router)
    dp.include_router(card_actions.router)
    dp.include_router(lists_handlers.router)
    dp.include_router(debug_handlers.router)

    setup_scheduler(bot)

    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    finally:
        await db.close_db()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
