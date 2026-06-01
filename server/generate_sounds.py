"""
Generate all card game announcement audio files using edge-tts.

Generates files for each role (default/dad/mom/sister/brother) with
distinct voices. Runs concurrent generation for speed.

Usage: python -m server.generate_sounds

Output: client/public/sound/announcement/{role}/*.mp3
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

import edge_tts

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger("generate_sounds")

BASE_DIR = Path(__file__).resolve().parent.parent / "client" / "public" / "sound" / "announcement"

# ── Role → edge-tts voice mapping ──────────────────────────────────────
ROLES: dict[str, str] = {
    "default": "zh-CN-XiaoxiaoNeural",   # standard female
    "dad":     "zh-CN-YunxiNeural",      # male, mature
    "mom":     "zh-CN-XiaoxiaoNeural",   # female, standard
    "sister":  "zh-CN-XiaoyiNeural",     # female, lively/young
    "brother": "zh-CN-YunjianNeural",    # male, young
}

# Chinese rank names
RANK_CN: dict[str, str] = {
    "THREE": "三", "FOUR": "四", "FIVE": "五", "SIX": "六",
    "SEVEN": "七", "EIGHT": "八", "NINE": "九", "TEN": "十",
    "JACK": "勾", "QUEEN": "圈", "KING": "K",
    "ACE": "尖", "TWO": "二",
}


def build_entries() -> list[tuple[str, str]]:
    """(filename_stem, chinese_text) for every unique announcement."""
    entries: list[tuple[str, str]] = []
    for eng, cn in RANK_CN.items():
        entries.append((f"single_{eng}", cn))
        entries.append((f"pair_{eng}", f"对{cn}"))
        entries.append((f"triple_{eng}", f"三个{cn}"))
    entries.append(("four_with_three", "四带三"))
    entries.append(("pass", "过"))
    entries.append(("declare_yes", "包牌"))
    entries.append(("declare_no", "不包"))
    entries.append(("straight", "顺子"))
    entries.append(("consecutive_pairs", "连对"))
    entries.append(("airplane", "飞机带翅膀"))
    entries.append(("bomb", "炸弹"))
    entries.append(("ace_bomb", "A炸"))
    return entries


async def generate_one(stem: str, text: str, voice: str, out_path: Path) -> bool:
    """Generate a single MP3 file. Returns True on success."""
    try:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        communicate = edge_tts.Communicate(text=text, voice=voice)
        await communicate.save(str(out_path))
        return True
    except Exception as e:
        log.error("FAIL [%s] %s: %s", out_path.parent.name, stem, e)
        return False


async def generate_role(role: str, voice: str, entries: list[tuple[str, str]]) -> tuple[str, int, int]:
    """Generate all entries for one role. Returns (role, generated, skipped)."""
    role_dir = BASE_DIR / role
    role_dir.mkdir(parents=True, exist_ok=True)

    tasks: list[asyncio.Task] = []
    for stem, text in entries:
        out_path = role_dir / f"{stem}.mp3"
        if out_path.exists():
            continue
        tasks.append(asyncio.create_task(generate_one(stem, text, voice, out_path)))

    if tasks:
        results = await asyncio.gather(*tasks)
        generated = sum(1 for r in results if r)
        skipped = len(entries) - generated - (len(entries) - len(tasks))
        # More accurate: skipped = existing files
        skipped = len(entries) - len(tasks)
        log.info("[%s] %d generated, %d skipped", role, generated, skipped)
        return role, generated, skipped
    else:
        log.info("[%s] all %d files already exist, skipped", role, len(entries))
        return role, 0, len(entries)


async def main() -> None:
    entries = build_entries()
    log.info("Output base: %s", BASE_DIR)
    log.info("Total files per role: %d", len(entries))
    log.info("Total roles: %d → %s", len(ROLES), ", ".join(ROLES.keys()))
    log.info("Total across all roles: %d", len(entries) * len(ROLES))

    role_tasks = [
        asyncio.create_task(generate_role(role, voice, entries))
        for role, voice in ROLES.items()
    ]

    results = await asyncio.gather(*role_tasks)
    total_gen = sum(r[1] for r in results)
    total_skip = sum(r[2] for r in results)
    log.info("All done. %d generated, %d skipped across %d roles.",
             total_gen, total_skip, len(ROLES))


if __name__ == "__main__":
    asyncio.run(main())
