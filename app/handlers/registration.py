"""Служебные команды: /start, /help, /chatid."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

router = Router(name="registration")

WELCOME_TEXT = (
    "Привет! Я слежу за временными изменениями (баннеры, акции, загрузочные экраны и т.д.), "
    "чтобы они не оставались висеть навсегда.\n\n"
    "Команды:\n"
    "/temp — создать новое временное изменение\n"
    "/active — все активные изменения\n"
    "/today — что нужно сделать сегодня\n\n"
    "Ты уже добавлен в список сотрудников и можешь быть выбран ответственным."
)


def _start_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="➕ Новое временное изменение", callback_data="start_temp")]]
    )


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, command: CommandObject) -> None:
    if command.args == "temp" and message.chat.type == "private":
        from app.handlers.wizard import begin_wizard  # локальный импорт, чтобы не плодить циклы

        await begin_wizard(message, state, message.from_user)
        return

    if message.chat.type == "private":
        await message.answer(WELCOME_TEXT, reply_markup=_start_keyboard())
    else:
        # в группе шаги мастера с вводом текста до бота не доходят (privacy mode),
        # поэтому кнопку создания здесь вообще не показываем
        await message.answer(WELCOME_TEXT)


@router.callback_query(F.data == "start_temp")
async def start_temp_button(callback: CallbackQuery, state: FSMContext) -> None:
    from app.handlers.wizard import begin_wizard  # локальный импорт, чтобы не плодить циклы

    if callback.message.chat.type != "private":
        await callback.answer("Открой личный чат со мной, там и создадим", show_alert=True)
        return
    await callback.answer()
    await begin_wizard(callback.message, state, callback.from_user)


@router.message(Command("chatid"))
async def cmd_chatid(message: Message) -> None:
    thread = getattr(message, "message_thread_id", None)
    text = f"chat_id: {message.chat.id}"
    if thread:
        text += f"\nthread_id (topic): {thread}"
    await message.answer(text)
