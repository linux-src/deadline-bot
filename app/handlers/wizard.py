"""Пошаговое создание временного изменения: /temp."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, User

import config
from app import cards, db, keyboards, utils
from app.states import Wizard

router = Router(name="wizard")


async def begin_wizard(message: Message, state: FSMContext, user: User) -> None:
    await state.clear()
    await state.update_data(
        creator_id=user.id,
        creator_username=user.username,
        creator_name=user.full_name,
    )
    await state.set_state(Wizard.choosing_type)
    await message.answer("Что добавляем?", reply_markup=keyboards.kb_type())


@router.message(Command("temp"))
async def cmd_temp(message: Message, state: FSMContext) -> None:
    await begin_wizard(message, state, message.from_user)


# --------------------------------------------------------------- шаг 1: тип

@router.callback_query(Wizard.choosing_type, F.data.startswith("wtype:"))
async def on_type(callback: CallbackQuery, state: FSMContext) -> None:
    change_type = callback.data.split(":", 1)[1]
    await callback.answer()
    if change_type == "Другое":
        await state.set_state(Wizard.entering_custom_type)
        await callback.message.edit_text("Опиши коротко, что за тип изменения:")
        return
    await state.update_data(change_type=change_type)
    await state.set_state(Wizard.choosing_scope)
    await callback.message.edit_text("Где действует изменение?", reply_markup=keyboards.kb_scope())


@router.message(Wizard.entering_custom_type)
async def on_custom_type(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    if not text:
        await message.answer("Напиши коротко, что за тип изменения текстом.")
        return
    await state.update_data(change_type=text)
    await state.set_state(Wizard.choosing_scope)
    await message.answer("Где действует изменение?", reply_markup=keyboards.kb_scope())


# --------------------------------------------------------- шаг 2: где действует

@router.callback_query(Wizard.choosing_scope, F.data.startswith("wscope:"))
async def on_scope(callback: CallbackQuery, state: FSMContext) -> None:
    scope = callback.data.split(":", 1)[1]
    await callback.answer()
    if scope == "all":
        await state.update_data(bots=list(config.BOTS), all_bots=True)
        await state.set_state(Wizard.entering_description)
        await callback.message.edit_text("Что именно изменили?\n\nНапример: «Баннер о повышенном курсе»")
    elif scope == "one":
        await state.set_state(Wizard.choosing_bot_single)
        await callback.message.edit_text("Выбери бота:", reply_markup=keyboards.kb_bots_single())
    else:
        await state.update_data(bots_multi_selected=[])
        await state.set_state(Wizard.choosing_bots_multi)
        await callback.message.edit_text(
            "Выбери ботов (можно несколько), потом нажми «Готово»:",
            reply_markup=keyboards.kb_bots_multi(set()),
        )


@router.callback_query(Wizard.choosing_bot_single, F.data.startswith("wbot:"))
async def on_bot_single(callback: CallbackQuery, state: FSMContext) -> None:
    code = callback.data.split(":", 1)[1]
    await callback.answer()
    await state.update_data(bots=[code], all_bots=False)
    await state.set_state(Wizard.entering_description)
    await callback.message.edit_text("Что именно изменили?\n\nНапример: «Баннер о повышенном курсе»")


@router.callback_query(Wizard.choosing_bots_multi, F.data.startswith("wbotm:"))
async def on_bot_multi_toggle(callback: CallbackQuery, state: FSMContext) -> None:
    code = callback.data.split(":", 1)[1]
    data = await state.get_data()
    selected = set(data.get("bots_multi_selected", []))
    selected.symmetric_difference_update({code})
    await state.update_data(bots_multi_selected=list(selected))
    await callback.answer()
    await callback.message.edit_reply_markup(reply_markup=keyboards.kb_bots_multi(selected))


@router.callback_query(Wizard.choosing_bots_multi, F.data == "wbots_done")
async def on_bots_multi_done(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    selected = data.get("bots_multi_selected", [])
    if not selected:
        await callback.answer("Выбери хотя бы одного бота", show_alert=True)
        return
    await callback.answer()
    await state.update_data(bots=selected, all_bots=False)
    await state.set_state(Wizard.entering_description)
    await callback.message.edit_text("Что именно изменили?\n\nНапример: «Баннер о повышенном курсе»")


# ------------------------------------------------------------- шаг 3: описание

@router.message(Wizard.entering_description)
async def on_description(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    if not text:
        await message.answer("Нужно текстовое описание. Что именно изменили?")
        return
    await state.update_data(description=text)
    await state.set_state(Wizard.choosing_deadline_mode)
    await message.answer("Когда это нужно убрать?", reply_markup=keyboards.kb_deadline_mode())


# ------------------------------------------------------------- срок действия

@router.callback_query(Wizard.choosing_deadline_mode, F.data.startswith("wdeadline:"))
async def on_deadline_mode(callback: CallbackQuery, state: FSMContext) -> None:
    mode = callback.data.split(":", 1)[1]
    await callback.answer()
    if mode == "pick":
        await state.set_state(Wizard.entering_deadline_datetime)
        await callback.message.edit_text(
            "Укажи дату и время, когда убрать (например: 20:00, 12.09 20:00 или 12.09.2026 20:00):"
        )
    else:
        await state.set_state(Wizard.choosing_check_option)
        await callback.message.edit_text(
            "Когда нужно проверить, актуально ли изменение?",
            reply_markup=keyboards.kb_check_options(),
        )


@router.message(Wizard.entering_deadline_datetime)
async def on_deadline_datetime(message: Message, state: FSMContext) -> None:
    dt = utils.parse_datetime(message.text or "")
    if dt is None:
        await message.answer("Не понял дату. Формат: 20:00, 12.09 20:00 или 12.09.2026 20:00")
        return
    await state.update_data(has_deadline=True, target_at=utils.to_iso(dt))
    await _ask_responsible(message.answer, state)


@router.callback_query(Wizard.choosing_check_option, F.data.startswith("wcheck:"))
async def on_check_option(callback: CallbackQuery, state: FSMContext) -> None:
    code = callback.data.split(":", 1)[1]
    await callback.answer()
    if code == "pick":
        await state.set_state(Wizard.entering_check_datetime)
        await callback.message.edit_text(
            "Укажи дату и время проверки (например: 20:00, 12.09 20:00):"
        )
        return
    dt = utils.apply_check_quick_option(code)
    await state.update_data(has_deadline=False, target_at=utils.to_iso(dt))
    await _ask_responsible(callback.message.edit_text, state)


@router.message(Wizard.entering_check_datetime)
async def on_check_datetime(message: Message, state: FSMContext) -> None:
    dt = utils.parse_datetime(message.text or "")
    if dt is None:
        await message.answer("Не понял дату. Формат: 20:00, 12.09 20:00 или 12.09.2026 20:00")
        return
    await state.update_data(has_deadline=False, target_at=utils.to_iso(dt))
    await _ask_responsible(message.answer, state)


async def _ask_responsible(send, state: FSMContext) -> None:
    await state.set_state(Wizard.choosing_responsible)
    employees = await db.list_employees()
    if not employees:
        await send("Пока нет ни одного известного сотрудника. Попроси коллегу написать боту /start, затем повтори.")
        await state.clear()
        return
    await send("Кто отвечает за контроль этого изменения?", reply_markup=keyboards.kb_responsible(employees))


# ---------------------------------------------------------------- ответственный

@router.callback_query(Wizard.choosing_responsible, F.data.startswith("wresp:"))
async def on_responsible(callback: CallbackQuery, state: FSMContext) -> None:
    tg_id = int(callback.data.split(":", 1)[1])
    emp = await db.get_employee(tg_id)
    if emp is None:
        await callback.answer("Сотрудник не найден", show_alert=True)
        return
    await callback.answer()
    data = await state.get_data()

    change_id = await db.create_change(
        change_type=data["change_type"],
        description=data["description"],
        bots=data["bots"],
        all_bots=data.get("all_bots", False),
        has_deadline=data["has_deadline"],
        target_at=utils.from_iso(data["target_at"]),
        created_by_id=data["creator_id"],
        created_by_username=data.get("creator_username"),
        created_by_name=data.get("creator_name"),
        responsible_id=emp["tg_id"],
        responsible_username=emp["username"],
        responsible_name=emp["full_name"],
    )
    await state.clear()

    change = await db.get_change(change_id)
    text = cards.build_card_text(change)
    kb = keyboards.kb_card_active(change_id)

    target_chat = config.CARD_CHAT_ID or callback.message.chat.id
    thread_id = config.CARD_THREAD_ID if config.CARD_CHAT_ID else None
    sent = await callback.bot.send_message(
        chat_id=target_chat,
        message_thread_id=thread_id,
        text=text,
        reply_markup=kb,
    )
    await db.set_card_message(change_id, sent.chat.id, sent.message_id)

    note = "" if config.CARD_CHAT_ID else "\n\n⚠ CARD_CHAT_ID не настроен — карточка опубликована прямо здесь."
    await callback.message.edit_text("Готово! Карточка опубликована в чат поддержки. ✅" + note)
