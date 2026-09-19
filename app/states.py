"""FSM-состояния мастера создания и последующего редактирования изменений."""
from aiogram.fsm.state import State, StatesGroup


class Wizard(StatesGroup):
    choosing_type = State()
    entering_custom_type = State()
    choosing_scope = State()
    choosing_bot_single = State()
    choosing_bots_multi = State()
    entering_description = State()
    choosing_deadline_mode = State()
    entering_deadline_datetime = State()
    choosing_check_option = State()
    entering_check_datetime = State()
    choosing_responsible = State()


class ExtendFlow(StatesGroup):
    entering_custom_datetime = State()


class EditFlow(StatesGroup):
    editing_description = State()
    editing_datetime = State()
    choosing_bots_multi = State()
