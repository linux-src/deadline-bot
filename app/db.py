"""Слой доступа к SQLite: сотрудники и временные изменения."""
from __future__ import annotations

import json
import os
from typing import Any

import aiosqlite

import config
from app import utils

SCHEMA = """
CREATE TABLE IF NOT EXISTS employees (
    tg_id INTEGER PRIMARY KEY,
    username TEXT,
    full_name TEXT,
    last_seen TEXT
);

CREATE TABLE IF NOT EXISTS changes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    change_type TEXT NOT NULL,
    description TEXT NOT NULL,
    bots TEXT NOT NULL,            -- JSON-список кодов ботов
    bots_done TEXT NOT NULL,       -- JSON-словарь код бота -> bool
    all_bots INTEGER NOT NULL DEFAULT 0,
    has_deadline INTEGER NOT NULL, -- 1 = точный срок удаления, 0 = только срок проверки
    target_at TEXT NOT NULL,       -- срок удаления либо срок следующей проверки (ISO)
    created_by_id INTEGER NOT NULL,
    created_by_username TEXT,
    created_by_name TEXT,
    responsible_id INTEGER NOT NULL,
    responsible_username TEXT,
    responsible_name TEXT,
    status TEXT NOT NULL DEFAULT 'active',
    created_at TEXT NOT NULL,
    removed_at TEXT,
    confirmed_by_username TEXT,
    card_chat_id INTEGER,
    card_message_id INTEGER,
    reminder_sent INTEGER NOT NULL DEFAULT 0,
    last_notice_at TEXT
);
"""

_db: aiosqlite.Connection | None = None


async def init_db() -> None:
    global _db
    os.makedirs(os.path.dirname(config.DB_PATH) or ".", exist_ok=True)
    _db = await aiosqlite.connect(config.DB_PATH)
    _db.row_factory = aiosqlite.Row
    await _db.executescript(SCHEMA)
    await _db.commit()


def conn() -> aiosqlite.Connection:
    if _db is None:
        raise RuntimeError("База данных ещё не инициализирована — вызови init_db()")
    return _db


async def close_db() -> None:
    if _db is not None:
        await _db.close()


# ---------------------------------------------------------------- employees

async def upsert_employee(tg_id: int, username: str | None, full_name: str | None) -> None:
    await conn().execute(
        """
        INSERT INTO employees (tg_id, username, full_name, last_seen)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(tg_id) DO UPDATE SET
            username = excluded.username,
            full_name = excluded.full_name,
            last_seen = excluded.last_seen
        """,
        (tg_id, username, full_name, utils.to_iso(utils.now())),
    )
    await conn().commit()


async def list_employees(limit: int = 50) -> list[aiosqlite.Row]:
    cur = await conn().execute(
        "SELECT * FROM employees ORDER BY last_seen DESC LIMIT ?", (limit,)
    )
    return await cur.fetchall()


async def get_employee(tg_id: int) -> aiosqlite.Row | None:
    cur = await conn().execute("SELECT * FROM employees WHERE tg_id = ?", (tg_id,))
    return await cur.fetchone()


# ------------------------------------------------------------------ changes

def _row_to_dict(row: aiosqlite.Row) -> dict[str, Any]:
    d = dict(row)
    d["bots"] = json.loads(d["bots"])
    d["bots_done"] = json.loads(d["bots_done"])
    return d


async def create_change(
    *,
    change_type: str,
    description: str,
    bots: list[str],
    all_bots: bool,
    has_deadline: bool,
    target_at,
    created_by_id: int,
    created_by_username: str | None,
    created_by_name: str | None,
    responsible_id: int,
    responsible_username: str | None,
    responsible_name: str | None,
) -> int:
    bots_done = {b: False for b in bots}
    cur = await conn().execute(
        """
        INSERT INTO changes (
            change_type, description, bots, bots_done, all_bots, has_deadline,
            target_at, created_by_id, created_by_username, created_by_name,
            responsible_id, responsible_username, responsible_name,
            status, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', ?)
        """,
        (
            change_type,
            description,
            json.dumps(bots, ensure_ascii=False),
            json.dumps(bots_done, ensure_ascii=False),
            int(all_bots),
            int(has_deadline),
            utils.to_iso(target_at),
            created_by_id,
            created_by_username,
            created_by_name,
            responsible_id,
            responsible_username,
            responsible_name,
            utils.to_iso(utils.now()),
        ),
    )
    await conn().commit()
    return cur.lastrowid


async def get_change(change_id: int) -> dict[str, Any] | None:
    cur = await conn().execute("SELECT * FROM changes WHERE id = ?", (change_id,))
    row = await cur.fetchone()
    return _row_to_dict(row) if row else None


async def update_change(change_id: int, **fields: Any) -> None:
    if not fields:
        return
    if "bots" in fields:
        fields["bots"] = json.dumps(fields["bots"], ensure_ascii=False)
    if "bots_done" in fields:
        fields["bots_done"] = json.dumps(fields["bots_done"], ensure_ascii=False)
    for key in ("target_at", "removed_at", "last_notice_at"):
        if key in fields and fields[key] is not None and not isinstance(fields[key], str):
            fields[key] = utils.to_iso(fields[key])
    columns = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + [change_id]
    await conn().execute(f"UPDATE changes SET {columns} WHERE id = ?", values)
    await conn().commit()


async def set_card_message(change_id: int, chat_id: int, message_id: int) -> None:
    await update_change(change_id, card_chat_id=chat_id, card_message_id=message_id)


async def list_open_changes() -> list[dict[str, Any]]:
    """Все изменения, которые ещё не завершены (для /active и планировщика)."""
    cur = await conn().execute(
        "SELECT * FROM changes WHERE status != 'completed' ORDER BY target_at ASC"
    )
    rows = await cur.fetchall()
    return [_row_to_dict(r) for r in rows]


async def list_all_changes() -> list[dict[str, Any]]:
    cur = await conn().execute("SELECT * FROM changes ORDER BY id DESC")
    rows = await cur.fetchall()
    return [_row_to_dict(r) for r in rows]
