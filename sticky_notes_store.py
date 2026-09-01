"""便签本地持久化（内容 / 位置 / 尺寸 / 颜色 / 置顶）。"""

from __future__ import annotations

import json
import logging
import uuid
from pathlib import Path

from config import APP_DIR

logger = logging.getLogger("sticky_notes")

NOTES_FILE: Path = APP_DIR / "sticky_notes.json"


def new_note_id() -> str:
    return uuid.uuid4().hex


def load_notes() -> list[dict]:
    try:
        raw = NOTES_FILE.read_text(encoding="utf-8-sig")
        data = json.loads(raw)
    except (OSError, json.JSONDecodeError, TypeError):
        return []

    if isinstance(data, dict):
        items = data.get("notes", [])
    elif isinstance(data, list):
        items = data
    else:
        items = []

    notes: list[dict] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        text = str(item.get("text", "") or "")
        if not text.strip():
            continue
        nid = str(item.get("id") or "").strip() or new_note_id()
        notes.append(
            {
                "id": nid,
                "text": text,
                "x": int(item.get("x", 100)),
                "y": int(item.get("y", 100)),
                "width": int(item.get("width", 280)),
                "height": int(item.get("height", 220)),
                "content_color": str(item.get("content_color") or "#F0B6F0"),
                "header_color": str(item.get("header_color") or "#EFC1EF"),
                "pinned": bool(item.get("pinned", False)),
            }
        )
    return notes


def save_notes(notes: list[dict]) -> None:
    payload = {"notes": list(notes)}
    NOTES_FILE.parent.mkdir(parents=True, exist_ok=True)
    NOTES_FILE.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def upsert_note(record: dict) -> None:
    text = str(record.get("text", "") or "")
    if not text.strip():
        nid = str(record.get("id") or "").strip()
        if nid:
            delete_note(nid)
        return

    nid = str(record.get("id") or "").strip() or new_note_id()
    record = {**record, "id": nid, "text": text}
    notes = load_notes()
    replaced = False
    for i, item in enumerate(notes):
        if item.get("id") == nid:
            notes[i] = record
            replaced = True
            break
    if not replaced:
        notes.append(record)
    try:
        save_notes(notes)
    except OSError:
        logger.exception("保存便签失败 | id=%s", nid)


def delete_note(note_id: str) -> None:
    nid = str(note_id or "").strip()
    if not nid:
        return
    notes = [n for n in load_notes() if n.get("id") != nid]
    try:
        save_notes(notes)
    except OSError:
        logger.exception("删除便签失败 | id=%s", nid)
