"""Инлайн-клавиатуры для мастера создания и карточек изменений."""
from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

import config
from app import utils

# ------------------------------------------------------------- навигация

def with_back(kb: InlineKeyboardMarkup, callback_data: str = "wback") -> InlineKeyboardMarkup:
    """Добавляет строку с кнопкой «Назад» под уже готовой клавиатурой."""
    b = InlineKeyboardBuilder()
    for row in kb.inline_keyboard:
        b.row(*row)
    b.row(InlineKeyboardButton(text="◀️ Назад", callback_data=callback_data))
    return b.as_markup()


def only_back(callback_data: str = "wback") -> InlineKeyboardMarkup:
    """Клавиатура для шагов со свободным вводом текста — там только «Назад»."""
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text="◀️ Назад", callback_data=callback_data))
    return b.as_markup()


def only_cancel() -> InlineKeyboardMarkup:
    """Для разовых всплывающих запросов текста (например, своя дата продления)."""
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text="❌ Отмена", callback_data="dismiss"))
    return b.as_markup()


def with_dismiss(kb: InlineKeyboardMarkup) -> InlineKeyboardMarkup:
    """Добавляет «Отмена» — закрывает всплывающий экран, ни на что не влияя."""
    b = InlineKeyboardBuilder()
    for row in kb.inline_keyboard:
        b.row(*row)
    b.row(InlineKeyboardButton(text="❌ Отмена", callback_data="dismiss"))
    return b.as_markup()


# --------------------------------------------------------------- шаг 1: тип

def kb_type() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for t in config.CHANGE_TYPES:
        b.button(text=t, callback_data=f"wtype:{t}")
    b.adjust(2)
    return b.as_markup()


# ------------------------------------------------------- шаг 2: где действует

def kb_scope() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="Все боты", callback_data="wscope:all")
    b.button(text="Выбрать одного бота", callback_data="wscope:one")
    b.button(text="Выбрать несколько ботов", callback_data="wscope:many")
    b.adjust(1)
    return b.as_markup()


def kb_bots_single() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for code in config.BOTS:
        b.button(text=code, callback_data=f"wbot:{code}")
    b.adjust(2)
    return b.as_markup()


def kb_bots_multi(selected: set[str]) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for code in config.BOTS:
        mark = "✅" if code in selected else "⬜"
        b.button(text=f"{mark} {code}", callback_data=f"wbotm:{code}")
    b.adjust(2)
    b.row(InlineKeyboardButton(text="Готово ▶️", callback_data="wbots_done"))
    return b.as_markup()


# --------------------------------------------------------------- срок действия

def kb_deadline_mode() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="Выбрать дату и время", callback_data="wdeadline:pick")
    b.button(text="Нет точной даты", callback_data="wdeadline:nodate")
    b.adjust(1)
    return b.as_markup()


def kb_check_options() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for code, label in config.CHECK_QUICK_OPTIONS:
        b.button(text=label, callback_data=f"wcheck:{code}")
    b.button(text="Выбрать дату и время", callback_data="wcheck:pick")
    b.adjust(1)
    return b.as_markup()


# ---------------------------------------------------------------- ответственный

def kb_responsible(employees) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for emp in employees:
        name = utils.display_name(emp["username"], emp["full_name"])
        b.button(text=name, callback_data=f"wresp:{emp['tg_id']}")
    b.adjust(1)
    return b.as_markup()


# --------------------------------------------------------------------- карточка

def kb_card_active(change_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="✅ Убрано", callback_data=f"done:{change_id}")
    b.button(text="⏰ Продлить", callback_data=f"extend:{change_id}")
    b.button(text="✏ Изменить", callback_data=f"edit:{change_id}")
    b.adjust(1)
    return b.as_markup()


def kb_notice(change_id: int) -> InlineKeyboardMarkup:
    """Клавиатура для напоминаний/просрочек — без пункта «Изменить»."""
    b = InlineKeyboardBuilder()
    b.button(text="✅ Убрано", callback_data=f"done:{change_id}")
    b.button(text="⏰ Продлить", callback_data=f"extend:{change_id}")
    b.adjust(1)
    return b.as_markup()


def kb_extend_options(change_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for code, label in config.EXTEND_OPTIONS:
        b.button(text=label, callback_data=f"extend_opt:{change_id}:{code}")
    b.button(text="Выбрать дату и время", callback_data=f"extend_opt:{change_id}:pick")
    b.adjust(1)
    return with_dismiss(b.as_markup())


def kb_done_multi(change_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="✅ Да, везде", callback_data=f"done_all:{change_id}")
    b.button(text="Выбрать боты", callback_data=f"done_pick:{change_id}")
    b.adjust(1)
    return with_dismiss(b.as_markup())


def kb_done_pick(change_id: int, bots: list[str], bots_done: dict[str, bool]) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for code in bots:
        mark = "✅" if bots_done.get(code) else "🔴"
        b.button(text=f"{mark} {code}", callback_data=f"done_toggle:{change_id}:{code}")
    b.adjust(2)
    b.row(InlineKeyboardButton(text="Готово ▶️", callback_data=f"done_confirm:{change_id}"))
    return with_back(b.as_markup(), f"done_back:{change_id}")


def kb_edit_deadline_mode(change_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="Выбрать дату и время", callback_data=f"edeadline:{change_id}:pick")
    b.button(text="Нет точной даты", callback_data=f"edeadline:{change_id}:nodate")
    b.adjust(1)
    return with_back(b.as_markup(), f"editmenu:{change_id}")


def kb_edit_check_options(change_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for code, label in config.CHECK_QUICK_OPTIONS:
        b.button(text=label, callback_data=f"echeck:{change_id}:{code}")
    b.button(text="Выбрать дату и время", callback_data=f"echeck:{change_id}:pick")
    b.adjust(1)
    return with_back(b.as_markup(), f"edeadline:{change_id}:back")


def kb_edit_responsible(change_id: int, employees) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for emp in employees:
        name = utils.display_name(emp["username"], emp["full_name"])
        b.button(text=name, callback_data=f"eresp:{change_id}:{emp['tg_id']}")
    b.adjust(1)
    return with_back(b.as_markup(), f"editmenu:{change_id}")


def kb_edit_menu(change_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="Описание", callback_data=f"editf:{change_id}:desc")
    b.button(text="Боты", callback_data=f"editf:{change_id}:bots")
    b.button(text="Срок", callback_data=f"editf:{change_id}:deadline")
    b.button(text="Ответственный", callback_data=f"editf:{change_id}:resp")
    b.adjust(1)
    return with_dismiss(b.as_markup())
