"""Мидлварь, которая незаметно регистрирует любого написавшего боту
пользователя в таблице employees — чтобы его можно было выбрать
«Ответственным» без отдельной команды /register."""
from __future__ import annotations

from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, User

from app import db


class AutoRegisterMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user: User | None = data.get("event_from_user")
        if user is not None and not user.is_bot:
            await db.upsert_employee(user.id, user.username, user.full_name)
        return await handler(event, data)
