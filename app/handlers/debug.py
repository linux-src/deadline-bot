"""Ловит апдейты, которые не подошли ни под один хендлер выше, и пишет
в лог, что именно это было — иначе aiogram молча пишет только
"Update ... is not handled" без деталей, и разобраться, что сломалось
в чате, невозможно. Роутер должен подключаться последним."""
from __future__ import annotations

import logging

from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

router = Router(name="debug_fallback")
log = logging.getLogger("unhandled")


@router.message()
async def on_unhandled_message(message: Message, state: FSMContext) -> None:
    current_state = await state.get_state()
    log.warning(
        "необработанное сообщение: chat_id=%s chat_type=%s from=%s state=%s text=%r",
        message.chat.id,
        message.chat.type,
        message.from_user.id if message.from_user else None,
        current_state,
        message.text,
    )


@router.callback_query()
async def on_unhandled_callback(callback: CallbackQuery, state: FSMContext) -> None:
    current_state = await state.get_state()
    log.warning(
        "необработанный callback: chat_id=%s from=%s state=%s data=%r",
        callback.message.chat.id if callback.message else None,
        callback.from_user.id if callback.from_user else None,
        current_state,
        callback.data,
    )
    await callback.answer("Кнопка устарела, начни заново", show_alert=True)
