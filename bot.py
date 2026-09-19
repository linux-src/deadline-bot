"""Точка входа: сборка бота, роутеров и планировщика."""
from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage

import config
from app import db
from app.handlers import card_actions, debug as debug_handlers, lists as lists_handlers, registration, wizard
from app.middlewares import AutoRegisterMiddleware
from app.scheduler import setup_scheduler


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    if not config.BOT_TOKEN:
        raise SystemExit("Не задан BOT_TOKEN — заполни .env (см. .env.example)")

    await db.init_db()

    bot = Bot(token=config.BOT_TOKEN, default=DefaultBotProperties(parse_mode=None))
    me = await bot.get_me()

    dp = Dispatcher(storage=MemoryStorage())
    dp["bot_username"] = me.username

    dp.message.middleware(AutoRegisterMiddleware())
    dp.callback_query.middleware(AutoRegisterMiddleware())

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
