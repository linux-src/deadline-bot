"""Мидлварь, которая незаметно регистрирует любого написавшего боту
пользователя в таблице employees — чтобы его можно было выбрать
«Ответственным» без отдельной команды /register."""
from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject, User

from app import db

log = logging.getLogger("trace")


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


class TraceMiddleware(BaseMiddleware):
    """Логирует каждое входящее сообщение/callback с текущим состоянием
    мастера — временно, чтобы найти, на каком именно шаге застревают."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        state = data.get("state")
        current_state = await state.get_state() if state else None
        user = data.get("event_from_user")
        chat_id = None
        payload = None
        if isinstance(event, Message):
            chat_id = event.chat.id
            payload = f"text={event.text!r}"
        elif isinstance(event, CallbackQuery):
            chat_id = event.message.chat.id if event.message else None
            payload = f"data={event.data!r}"
        log.info(
            "chat=%s user=%s state=%s %s",
            chat_id,
            user.id if user else None,
            current_state,
            payload,
        )
        return await handler(event, data)
