"""Формирование текста карточек и уведомлений по временному изменению."""
from __future__ import annotations

from typing import Any

from app import keyboards, utils


def _bots_label(change: dict[str, Any]) -> str:
    if change["all_bots"]:
        return "Все боты"
    return ", ".join(change["bots"])


def _bots_status_block(change: dict[str, Any]) -> str:
    bots = change["bots"]
    if len(bots) <= 1:
        return ""
    done = change["bots_done"]
    lines = [f"{'✅' if done.get(b) else '🔴'} {b}" for b in bots]
    return "\n\n" + "\n".join(lines)


def deadline_field_label(change: dict[str, Any]) -> str:
    return "Убрать" if change["has_deadline"] else "Проверить"


def build_active_card(change: dict[str, Any]) -> str:
    status = change["status"]
    emoji = utils.STATUS_EMOJI[status]
    status_text = utils.STATUS_TEXT[status]
    created_at = utils.from_iso(change["created_at"])
    target_at = utils.from_iso(change["target_at"])

    lines = [
        "🔴 ВРЕМЕННОЕ ИЗМЕНЕНИЕ",
        "",
        "Что:",
        change["description"],
        "Где:",
        _bots_label(change),
        "Включено:",
        utils.fmt_abs(created_at),
        f"{deadline_field_label(change)}:",
        utils.fmt_abs(target_at),
        "Создал:",
        utils.display_name(change["created_by_username"], change["created_by_name"]),
        "Ответственный:",
        utils.display_name(change["responsible_username"], change["responsible_name"]),
        "",
        f"Статус: {emoji} {status_text}",
    ]
    text = "\n".join(lines)
    text += _bots_status_block(change)
    return text


def build_completed_card(change: dict[str, Any]) -> str:
    removed_at = utils.from_iso(change["removed_at"]) if change["removed_at"] else utils.now()
    lines = [
        "✅ ЗАВЕРШЕНО",
        "",
        change["description"],
        f"Убран: {removed_at.strftime('%H:%M')}",
        f"Подтвердил: {change['confirmed_by_username'] or '—'}",
    ]
    return "\n".join(lines)


def build_card_text(change: dict[str, Any]) -> str:
    if change["status"] == utils.STATUS_COMPLETED:
        return build_completed_card(change)
    return build_active_card(change)


def build_reminder_text(change: dict[str, Any]) -> str:
    label = "убрать" if change["has_deadline"] else "проверить"
    return (
        "⏰ Напоминание\n\n"
        f"Через {config_minutes_phrase()} нужно {label}:\n"
        f"{change['description']}\n"
        f"Боты: {_bots_label(change).lower() if change['all_bots'] else _bots_label(change)}."
    )


def config_minutes_phrase() -> str:
    import config

    minutes = config.REMINDER_MINUTES_BEFORE
    if minutes % 60 == 0:
        hours = minutes // 60
        return f"{hours} час" if hours == 1 else f"{hours} часа"
    return f"{minutes} минут"


def build_expired_text(change: dict[str, Any]) -> str:
    if change["has_deadline"]:
        return (
            "🔴 Срок временного изменения истёк\n\n"
            f"Нужно убрать:\n{change['description']}\n\n"
            f"Ответственный: {utils.display_name(change['responsible_username'], change['responsible_name'])}"
        )
    return (
        "🟠 Наступило время проверки\n\n"
        f"Нужно проверить, актуально ли:\n{change['description']}\n\n"
        f"Ответственный: {utils.display_name(change['responsible_username'], change['responsible_name'])}"
    )


async def refresh_card(bot, change: dict[str, Any]) -> None:
    """Перерисовывает исходную карточку изменения после любого действия."""
    if not change.get("card_chat_id") or not change.get("card_message_id"):
        return
    text = build_card_text(change)
    kb = None
    if change["status"] != utils.STATUS_COMPLETED:
        kb = keyboards.kb_card_active(change["id"])
    try:
        await bot.edit_message_text(
            chat_id=change["card_chat_id"],
            message_id=change["card_message_id"],
            text=text,
            reply_markup=kb,
        )
    except Exception:
        pass  # карточку могли удалить вручную — не критично


def build_overdue_text(change: dict[str, Any]) -> str:
    target_at = utils.from_iso(change["target_at"])
    if change["has_deadline"]:
        return (
            "⚠ ПРОСРОЧЕНО\n\n"
            f"{change['description']} должно было быть убрано в {target_at.strftime('%H:%M')}.\n\n"
            f"Ответственный: {utils.display_name(change['responsible_username'], change['responsible_name'])}"
        )
    return (
        "⚠ ТРЕБУЕТ ПРОВЕРКИ\n\n"
        f"{change['description']} нужно было проверить в {target_at.strftime('%H:%M')}.\n\n"
        f"Ответственный: {utils.display_name(change['responsible_username'], change['responsible_name'])}"
    )
