"""Обработка кнопок на карточке: Убрано / Продлить / Изменить."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

import config
from app import cards, db, keyboards, utils
from app.states import EditFlow, ExtendFlow

router = Router(name="card_actions")


def _parse(data: str) -> list[str]:
    return data.split(":")


async def _blocked_in_group(callback: CallbackQuery, bot_username: str) -> bool:
    """Проверяет, что для ввода текста мы в личке — иначе сообщение до бота
    не дойдёт (privacy mode в группах). Возвращает True, если шаг заблокирован."""
    if callback.message.chat.type == "private":
        return False
    await callback.answer(
        f"Для ввода текста напиши мне в личку (@{bot_username}) — из группы сообщение до меня не дойдёт",
        show_alert=True,
    )
    return True


@router.callback_query(F.data == "dismiss")
async def on_dismiss(callback: CallbackQuery, state: FSMContext) -> None:
    """Закрывает всплывающий экран (меню/подтверждение), не трогая карточку."""
    await state.clear()
    await callback.answer()
    try:
        await callback.message.delete()
    except Exception:
        pass


@router.callback_query(F.data.startswith("done_back:"))
async def on_done_back(callback: CallbackQuery) -> None:
    change_id = int(_parse(callback.data)[1])
    await callback.answer()
    await callback.message.edit_text(
        "Изменение убрано во всех ботах?", reply_markup=keyboards.kb_done_multi(change_id)
    )


# ------------------------------------------------------------------- Убрано

async def _complete_change(bot, change_id: int, user) -> None:
    change = await db.get_change(change_id)
    bots_done = {b: True for b in change["bots"]}
    await db.update_change(
        change_id,
        status=utils.STATUS_COMPLETED,
        bots_done=bots_done,
        removed_at=utils.now(),
        confirmed_by_username=utils.display_name(user.username, user.full_name),
    )
    change = await db.get_change(change_id)
    await cards.refresh_card(bot, change)


@router.callback_query(F.data.startswith("done:"))
async def on_done(callback: CallbackQuery) -> None:
    change_id = int(_parse(callback.data)[1])
    change = await db.get_change(change_id)
    if not change:
        await callback.answer("Изменение не найдено", show_alert=True)
        return
    if change["status"] == utils.STATUS_COMPLETED:
        await callback.answer("Уже завершено")
        return
    await callback.answer()
    if len(change["bots"]) > 1:
        await callback.message.answer(
            "Изменение убрано во всех ботах?", reply_markup=keyboards.kb_done_multi(change_id)
        )
    else:
        await _complete_change(callback.bot, change_id, callback.from_user)


@router.callback_query(F.data.startswith("done_all:"))
async def on_done_all(callback: CallbackQuery) -> None:
    change_id = int(_parse(callback.data)[1])
    await callback.answer()
    await _complete_change(callback.bot, change_id, callback.from_user)
    await callback.message.delete()


@router.callback_query(F.data.startswith("done_pick:"))
async def on_done_pick(callback: CallbackQuery) -> None:
    change_id = int(_parse(callback.data)[1])
    change = await db.get_change(change_id)
    await callback.answer()
    await callback.message.edit_text(
        "Отметь, в каких ботах убрано:",
        reply_markup=keyboards.kb_done_pick(change_id, change["bots"], change["bots_done"]),
    )


@router.callback_query(F.data.startswith("done_toggle:"))
async def on_done_toggle(callback: CallbackQuery) -> None:
    _, change_id_s, code = _parse(callback.data)
    change_id = int(change_id_s)
    change = await db.get_change(change_id)
    bots_done = change["bots_done"]
    bots_done[code] = not bots_done.get(code, False)
    await db.update_change(change_id, bots_done=bots_done)
    await callback.answer()
    await callback.message.edit_reply_markup(
        reply_markup=keyboards.kb_done_pick(change_id, change["bots"], bots_done)
    )


@router.callback_query(F.data.startswith("done_confirm:"))
async def on_done_confirm(callback: CallbackQuery) -> None:
    change_id = int(_parse(callback.data)[1])
    change = await db.get_change(change_id)
    await callback.answer()
    if change["bots"] and all(change["bots_done"].get(b) for b in change["bots"]):
        await _complete_change(callback.bot, change_id, callback.from_user)
    else:
        await cards.refresh_card(callback.bot, change)
    await callback.message.delete()


# ----------------------------------------------------------------- Продлить

@router.callback_query(F.data.startswith("extend:"))
async def on_extend(callback: CallbackQuery) -> None:
    change_id = int(_parse(callback.data)[1])
    await callback.answer()
    await callback.message.answer("На сколько продлить?", reply_markup=keyboards.kb_extend_options(change_id))


async def _apply_extend(bot, change_id: int, new_dt) -> None:
    change = await db.get_change(change_id)
    old_dt = utils.from_iso(change["target_at"])
    await db.update_change(
        change_id,
        target_at=new_dt,
        status=utils.STATUS_ACTIVE,
        reminder_sent=0,
        last_notice_at=None,
    )
    change = await db.get_change(change_id)
    await cards.refresh_card(bot, change)
    label = cards.deadline_field_label(change)
    note = (
        "⏰ Срок обновлён.\n\n"
        f"{label}:\n"
        f"было — {utils.fmt_abs(old_dt)}\n"
        f"стало — {utils.fmt_abs(new_dt)}"
    )
    if change.get("card_chat_id"):
        await bot.send_message(
            chat_id=change["card_chat_id"],
            message_thread_id=config.CARD_THREAD_ID,
            text=note,
        )


@router.callback_query(F.data.startswith("extend_opt:"))
async def on_extend_opt(callback: CallbackQuery, state: FSMContext, bot_username: str) -> None:
    _, change_id_s, code = _parse(callback.data)
    change_id = int(change_id_s)
    if code == "pick":
        if await _blocked_in_group(callback, bot_username):
            return
        await state.set_state(ExtendFlow.entering_custom_datetime)
        await state.update_data(change_id=change_id)
        await callback.answer()
        await callback.message.edit_text(
            "Укажи новую дату и время (например: 22:00 или 13.09 10:00):",
            reply_markup=keyboards.only_cancel(),
        )
        return
    new_dt = utils.apply_extend_option(code)
    await callback.answer()
    await _apply_extend(callback.bot, change_id, new_dt)
    await callback.message.delete()


@router.message(ExtendFlow.entering_custom_datetime)
async def on_extend_custom(message: Message, state: FSMContext) -> None:
    dt = utils.parse_datetime(message.text or "")
    if dt is None:
        await message.answer("Не понял дату. Формат: 20:00, 12.09 20:00 или 12.09.2026 20:00")
        return
    data = await state.get_data()
    change_id = data["change_id"]
    await state.clear()
    await _apply_extend(message.bot, change_id, dt)
    await message.answer("Срок продлён ✅")


# ------------------------------------------------------------------ Изменить

@router.callback_query(F.data.startswith("edit:"))
async def on_edit(callback: CallbackQuery) -> None:
    change_id = int(_parse(callback.data)[1])
    await callback.answer()
    await callback.message.answer("Что изменить?", reply_markup=keyboards.kb_edit_menu(change_id))


@router.callback_query(F.data.startswith("editmenu:"))
async def on_edit_menu_back(callback: CallbackQuery, state: FSMContext) -> None:
    change_id = int(_parse(callback.data)[1])
    await state.clear()
    await callback.answer()
    await callback.message.edit_text("Что изменить?", reply_markup=keyboards.kb_edit_menu(change_id))


@router.callback_query(F.data.startswith("editf:"))
async def on_edit_field(callback: CallbackQuery, state: FSMContext, bot_username: str) -> None:
    _, change_id_s, field = _parse(callback.data)
    change_id = int(change_id_s)
    change = await db.get_change(change_id)

    if field == "desc":
        if await _blocked_in_group(callback, bot_username):
            return
        await callback.answer()
        await state.set_state(EditFlow.editing_description)
        await state.update_data(change_id=change_id)
        await callback.message.edit_text("Новое описание:", reply_markup=keyboards.only_back(f"editmenu:{change_id}"))
    elif field == "bots":
        await callback.answer()
        await state.set_state(EditFlow.choosing_bots_multi)
        await state.update_data(change_id=change_id, selected=list(change["bots"]))
        await callback.message.edit_text(
            "Выбери ботов, потом «Готово»:",
            reply_markup=keyboards.with_back(keyboards.kb_bots_multi(set(change["bots"])), f"editmenu:{change_id}"),
        )
    elif field == "deadline":
        await callback.answer()
        await callback.message.edit_text(
            "Когда это нужно убрать?", reply_markup=keyboards.kb_edit_deadline_mode(change_id)
        )
    elif field == "resp":
        await callback.answer()
        employees = await db.list_employees()
        await callback.message.edit_text(
            "Кто отвечает за контроль этого изменения?",
            reply_markup=keyboards.kb_edit_responsible(change_id, employees),
        )


@router.callback_query(F.data.startswith("edeadline:"))
async def on_edit_deadline_mode(callback: CallbackQuery, state: FSMContext, bot_username: str) -> None:
    _, change_id_s, mode = _parse(callback.data)
    change_id = int(change_id_s)
    if mode == "pick":
        if await _blocked_in_group(callback, bot_username):
            return
        await callback.answer()
        await state.set_state(EditFlow.editing_datetime)
        await state.update_data(change_id=change_id, mode="deadline")
        await callback.message.edit_text(
            "Укажи новую дату и время удаления:",
            reply_markup=keyboards.only_back(f"editmenu:{change_id}"),
        )
    elif mode == "back":
        await callback.answer()
        await callback.message.edit_text(
            "Когда это нужно убрать?", reply_markup=keyboards.kb_edit_deadline_mode(change_id)
        )
    else:
        await callback.answer()
        await callback.message.edit_text(
            "Когда нужно проверить, актуально ли изменение?",
            reply_markup=keyboards.kb_edit_check_options(change_id),
        )


async def _apply_deadline_edit(bot, change_id: int, has_deadline: bool, new_dt) -> None:
    await db.update_change(
        change_id,
        has_deadline=has_deadline,
        target_at=new_dt,
        status=utils.STATUS_ACTIVE,
        reminder_sent=0,
        last_notice_at=None,
    )
    change = await db.get_change(change_id)
    await cards.refresh_card(bot, change)


@router.callback_query(F.data.startswith("echeck:"))
async def on_edit_check_option(callback: CallbackQuery, state: FSMContext, bot_username: str) -> None:
    _, change_id_s, code = _parse(callback.data)
    change_id = int(change_id_s)
    if code == "pick":
        if await _blocked_in_group(callback, bot_username):
            return
        await callback.answer()
        await state.set_state(EditFlow.editing_datetime)
        await state.update_data(change_id=change_id, mode="check")
        await callback.message.edit_text(
            "Укажи новую дату и время проверки:",
            reply_markup=keyboards.only_back(f"editmenu:{change_id}"),
        )
        return
    await callback.answer()
    dt = utils.apply_check_quick_option(code)
    await _apply_deadline_edit(callback.bot, change_id, has_deadline=False, new_dt=dt)
    await callback.message.edit_text("Срок обновлён ✅")


@router.message(EditFlow.editing_datetime)
async def on_edit_datetime_text(message: Message, state: FSMContext) -> None:
    dt = utils.parse_datetime(message.text or "")
    if dt is None:
        await message.answer("Не понял дату. Формат: 20:00, 12.09 20:00 или 12.09.2026 20:00")
        return
    data = await state.get_data()
    change_id = data["change_id"]
    mode = data["mode"]
    await state.clear()
    await _apply_deadline_edit(message.bot, change_id, has_deadline=(mode == "deadline"), new_dt=dt)
    await message.answer("Срок обновлён ✅")


@router.message(EditFlow.editing_description)
async def on_edit_description_text(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    if not text:
        await message.answer("Нужно текстовое описание.")
        return
    data = await state.get_data()
    change_id = data["change_id"]
    await state.clear()
    await db.update_change(change_id, description=text)
    change = await db.get_change(change_id)
    await cards.refresh_card(message.bot, change)
    await message.answer("Описание обновлено ✅")


@router.callback_query(EditFlow.choosing_bots_multi, F.data.startswith("wbotm:"))
async def on_edit_bots_toggle(callback: CallbackQuery, state: FSMContext) -> None:
    code = callback.data.split(":", 1)[1]
    data = await state.get_data()
    selected = set(data.get("selected", []))
    selected.symmetric_difference_update({code})
    await state.update_data(selected=list(selected))
    await callback.answer()
    await callback.message.edit_reply_markup(
        reply_markup=keyboards.with_back(keyboards.kb_bots_multi(selected), f"editmenu:{data['change_id']}")
    )


@router.callback_query(EditFlow.choosing_bots_multi, F.data == "wbots_done")
async def on_edit_bots_done(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    selected = data.get("selected", [])
    if not selected:
        await callback.answer("Выбери хотя бы одного бота", show_alert=True)
        return
    change_id = data["change_id"]
    await state.clear()
    change = await db.get_change(change_id)
    bots_done = {b: change["bots_done"].get(b, False) for b in selected}
    all_bots_flag = set(selected) == set(config.BOTS)
    await db.update_change(change_id, bots=selected, bots_done=bots_done, all_bots=all_bots_flag)
    change = await db.get_change(change_id)
    await callback.answer()
    await cards.refresh_card(callback.bot, change)
    await callback.message.edit_text("Список ботов обновлён ✅")


@router.callback_query(F.data.startswith("eresp:"))
async def on_edit_responsible(callback: CallbackQuery) -> None:
    _, change_id_s, tg_id_s = _parse(callback.data)
    change_id = int(change_id_s)
    tg_id = int(tg_id_s)
    emp = await db.get_employee(tg_id)
    if not emp:
        await callback.answer("Сотрудник не найден", show_alert=True)
        return
    await db.update_change(
        change_id,
        responsible_id=emp["tg_id"],
        responsible_username=emp["username"],
        responsible_name=emp["full_name"],
    )
    change = await db.get_change(change_id)
    await callback.answer("Ответственный обновлён")
    await cards.refresh_card(callback.bot, change)
    await callback.message.edit_text("Ответственный обновлён ✅")
