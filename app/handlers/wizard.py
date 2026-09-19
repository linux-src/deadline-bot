"""Пошаговое создание временного изменения: /temp.

Навигация построена вокруг стека history в данных FSM: перед переходом
на следующий шаг текущий шаг кладётся в стек, а кнопка «Назад» (wback)
просто снимает верхний шаг со стека и перерисовывает его — так что
неправильный выбор на любом шаге не требует переначинать мастер заново.
"""
from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message, User

import config
from app import cards, db, keyboards, utils
from app.states import Wizard

router = Router(name="wizard")

STEP_STATE = {
    "type": Wizard.choosing_type,
    "custom_type": Wizard.entering_custom_type,
    "scope": Wizard.choosing_scope,
    "bot_single": Wizard.choosing_bot_single,
    "bots_multi": Wizard.choosing_bots_multi,
    "description": Wizard.entering_description,
    "deadline_mode": Wizard.choosing_deadline_mode,
    "deadline_datetime": Wizard.entering_deadline_datetime,
    "check_option": Wizard.choosing_check_option,
    "check_datetime": Wizard.entering_check_datetime,
    "responsible": Wizard.choosing_responsible,
}


async def _render(step: str, state: FSMContext) -> tuple[str, InlineKeyboardMarkup]:
    data = await state.get_data()

    if step == "type":
        return "Что добавляем?", keyboards.kb_type()
    if step == "custom_type":
        return "Опиши коротко, что за тип изменения:", keyboards.only_back()
    if step == "scope":
        return "Где действует изменение?", keyboards.with_back(keyboards.kb_scope())
    if step == "bot_single":
        return "Выбери бота:", keyboards.with_back(keyboards.kb_bots_single())
    if step == "bots_multi":
        selected = set(data.get("bots_multi_selected", []))
        return (
            "Выбери ботов (можно несколько), потом нажми «Готово»:",
            keyboards.with_back(keyboards.kb_bots_multi(selected)),
        )
    if step == "description":
        return "Что именно изменили?\n\nНапример: «Баннер о повышенном курсе»", keyboards.only_back()
    if step == "deadline_mode":
        return "Когда это нужно убрать?", keyboards.with_back(keyboards.kb_deadline_mode())
    if step == "deadline_datetime":
        return (
            "Укажи дату и время, когда убрать (например: 20:00, 12.09 20:00 или 12.09.2026 20:00):",
            keyboards.only_back(),
        )
    if step == "check_option":
        return (
            "Когда нужно проверить, актуально ли изменение?",
            keyboards.with_back(keyboards.kb_check_options()),
        )
    if step == "check_datetime":
        return "Укажи дату и время проверки (например: 20:00, 12.09 20:00):", keyboards.only_back()
    if step == "responsible":
        employees = await db.list_employees()
        if not employees:
            return (
                "Пока нет ни одного известного сотрудника. Попроси коллегу написать боту /start, "
                "затем нажми «Назад» и попробуй снова.",
                keyboards.only_back(),
            )
        return (
            "Кто отвечает за контроль этого изменения?",
            keyboards.with_back(keyboards.kb_responsible(employees)),
        )
    raise ValueError(f"неизвестный шаг мастера: {step}")


async def _clear_stale_markup(state: FSMContext, bot) -> None:
    """Гасит кнопки на предыдущем сообщении мастера, чтобы их нельзя было
    случайно нажать после того, как разговор ушёл на следующий шаг —
    именно так путали бота, тыкая в кнопки старой, уже неактуальной карточки."""
    data = await state.get_data()
    chat_id = data.get("last_chat_id")
    message_id = data.get("last_message_id")
    if not chat_id or not message_id:
        return
    try:
        await bot.edit_message_reply_markup(chat_id=chat_id, message_id=message_id, reply_markup=None)
    except Exception:
        pass


async def _goto(step: str, state: FSMContext, send) -> None:
    await state.set_state(STEP_STATE[step])
    text, kb = await _render(step, state)
    sent = await send(text, reply_markup=kb)
    if sent is not None:
        await state.update_data(last_chat_id=sent.chat.id, last_message_id=sent.message_id)


async def _advance(current_step: str, next_step: str, state: FSMContext, send) -> None:
    data = await state.get_data()
    history = data.get("history", [])
    history.append(current_step)
    await state.update_data(history=history)
    await _clear_stale_markup(state, send.__self__.bot)
    await _goto(next_step, state, send)


@router.callback_query(F.data == "wback")
async def on_back(callback: CallbackQuery, state: FSMContext) -> None:
    current_state = await state.get_state()
    if current_state is None or not current_state.startswith("Wizard:"):
        await callback.answer()
        return
    data = await state.get_data()
    history = data.get("history", [])
    if not history:
        await callback.answer("Это первый шаг")
        return
    prev_step = history.pop()
    await state.update_data(history=history)
    await callback.answer()
    await _goto(prev_step, state, callback.message.edit_text)


async def begin_wizard(message: Message, state: FSMContext, user: User) -> None:
    # если пользователь бросил предыдущую попытку /temp на середине — гасим
    # кнопки на том старом сообщении, иначе в чате будет несколько
    # прошлых "Что добавляем?" с рабочими на вид, но неактуальными кнопками
    await _clear_stale_markup(state, message.bot)
    await state.clear()
    await state.update_data(
        creator_id=user.id,
        creator_username=user.username,
        creator_name=user.full_name,
        history=[],
    )
    await _goto("type", state, message.answer)


@router.message(Command("temp"))
async def cmd_temp(message: Message, state: FSMContext) -> None:
    await begin_wizard(message, state, message.from_user)


# --------------------------------------------------------------- шаг 1: тип

@router.callback_query(Wizard.choosing_type, F.data.startswith("wtype:"))
async def on_type(callback: CallbackQuery, state: FSMContext) -> None:
    change_type = callback.data.split(":", 1)[1]
    await callback.answer()
    if change_type == "Другое":
        await _advance("type", "custom_type", state, callback.message.edit_text)
        return
    await state.update_data(change_type=change_type)
    await _advance("type", "scope", state, callback.message.edit_text)


@router.message(Wizard.entering_custom_type)
async def on_custom_type(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    if not text:
        await message.answer("Напиши коротко, что за тип изменения текстом.")
        return
    await state.update_data(change_type=text)
    await _advance("custom_type", "scope", state, message.answer)


# --------------------------------------------------------- шаг 2: где действует

@router.callback_query(Wizard.choosing_scope, F.data.startswith("wscope:"))
async def on_scope(callback: CallbackQuery, state: FSMContext) -> None:
    scope = callback.data.split(":", 1)[1]
    await callback.answer()
    if scope == "all":
        await state.update_data(bots=list(config.BOTS), all_bots=True)
        await _advance("scope", "description", state, callback.message.edit_text)
    elif scope == "one":
        await _advance("scope", "bot_single", state, callback.message.edit_text)
    else:
        await state.update_data(bots_multi_selected=[])
        await _advance("scope", "bots_multi", state, callback.message.edit_text)


@router.callback_query(Wizard.choosing_bot_single, F.data.startswith("wbot:"))
async def on_bot_single(callback: CallbackQuery, state: FSMContext) -> None:
    code = callback.data.split(":", 1)[1]
    await callback.answer()
    await state.update_data(bots=[code], all_bots=False)
    await _advance("bot_single", "description", state, callback.message.edit_text)


@router.callback_query(Wizard.choosing_bots_multi, F.data.startswith("wbotm:"))
async def on_bot_multi_toggle(callback: CallbackQuery, state: FSMContext) -> None:
    code = callback.data.split(":", 1)[1]
    data = await state.get_data()
    selected = set(data.get("bots_multi_selected", []))
    selected.symmetric_difference_update({code})
    await state.update_data(bots_multi_selected=list(selected))
    await callback.answer()
    await callback.message.edit_reply_markup(reply_markup=keyboards.with_back(keyboards.kb_bots_multi(selected)))


@router.callback_query(Wizard.choosing_bots_multi, F.data == "wbots_done")
async def on_bots_multi_done(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    selected = data.get("bots_multi_selected", [])
    if not selected:
        await callback.answer("Выбери хотя бы одного бота", show_alert=True)
        return
    await callback.answer()
    await state.update_data(bots=selected, all_bots=False)
    await _advance("bots_multi", "description", state, callback.message.edit_text)


# ------------------------------------------------------------- шаг 3: описание

@router.message(Wizard.entering_description)
async def on_description(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    if not text:
        await message.answer("Нужно текстовое описание. Что именно изменили?")
        return
    await state.update_data(description=text)
    await _advance("description", "deadline_mode", state, message.answer)


# ------------------------------------------------------------- срок действия

@router.callback_query(Wizard.choosing_deadline_mode, F.data.startswith("wdeadline:"))
async def on_deadline_mode(callback: CallbackQuery, state: FSMContext) -> None:
    mode = callback.data.split(":", 1)[1]
    await callback.answer()
    if mode == "pick":
        await _advance("deadline_mode", "deadline_datetime", state, callback.message.edit_text)
    else:
        await _advance("deadline_mode", "check_option", state, callback.message.edit_text)


@router.message(Wizard.entering_deadline_datetime)
async def on_deadline_datetime(message: Message, state: FSMContext) -> None:
    dt = utils.parse_datetime(message.text or "")
    if dt is None:
        await message.answer("Не понял дату. Формат: 20:00, 12.09 20:00 или 12.09.2026 20:00")
        return
    await state.update_data(has_deadline=True, target_at=utils.to_iso(dt))
    await _advance("deadline_datetime", "responsible", state, message.answer)


@router.callback_query(Wizard.choosing_check_option, F.data.startswith("wcheck:"))
async def on_check_option(callback: CallbackQuery, state: FSMContext) -> None:
    code = callback.data.split(":", 1)[1]
    await callback.answer()
    if code == "pick":
        await _advance("check_option", "check_datetime", state, callback.message.edit_text)
        return
    dt = utils.apply_check_quick_option(code)
    await state.update_data(has_deadline=False, target_at=utils.to_iso(dt))
    await _advance("check_option", "responsible", state, callback.message.edit_text)


@router.message(Wizard.entering_check_datetime)
async def on_check_datetime(message: Message, state: FSMContext) -> None:
    dt = utils.parse_datetime(message.text or "")
    if dt is None:
        await message.answer("Не понял дату. Формат: 20:00, 12.09 20:00 или 12.09.2026 20:00")
        return
    await state.update_data(has_deadline=False, target_at=utils.to_iso(dt))
    await _advance("check_datetime", "responsible", state, message.answer)


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
