import asyncio
import json
import logging
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from aiogram import Bot, Dispatcher, Router, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    Message,
    CallbackQuery,
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

# =========================================================
#  CONFIG
# =========================================================
BOT_TOKEN = "8678002733:AAGaG9W2Jf4ZvVA2FSPzL7rFHB9ZyxC3SpI"

# ⚠️ IMPORTANT: replace this with YOUR real Telegram numeric user ID.
# You can get your ID by messaging @userinfobot on Telegram.
ADMIN_IDS = {8425304206}

PROJECTS_DIR = Path(__file__).parent / "projects"
PROJECTS_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("FoggyPalaceMystery")

router = Router()


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


# =========================================================
#  FSM STATES (admin project upload flow)
# =========================================================
class AdminStates(StatesGroup):
    waiting_for_file = State()


# =========================================================
#  IN-MEMORY USER STATE
#  user_id -> {"project": str|None, "node": str|None,
#              "evidence_by_project": {project_id: set(evidence_keys)}, "chapter": int}
# =========================================================
user_data: Dict[int, Dict] = {}


def get_user(user_id: int) -> Dict:
    if user_id not in user_data:
        user_data[user_id] = {
            "project": None,
            "node": None,
            "evidence_by_project": {},
            "chapter": 0,
        }
    return user_data[user_id]


# =========================================================
#  BUILT-IN STORY: "The Foggy Palace Mystery"
#  (options use dict format so it shares the same engine as
#   admin-uploaded JSON projects)
# =========================================================
BUILTIN_NODES: Dict[str, Dict] = {
    "start": {
        "chapter": 1,
        "title": "Chapter 1: The Gates of Foggy Palace",
        "text": (
            "🏰 <b>Chapter 1: The Gates of Foggy Palace</b>\n\n"
            "The carriage stops before a massive iron gate, half swallowed by rolling fog. "
            "Somewhere behind these walls, Lord Ashworth was found dead last night — "
            "and you, detective, are the only one who can uncover the truth.\n\n"
            "🕵️‍♂️ The gate creaks open on its own. What will you do?"
        ),
        "options": [
            {"text": "🚪 Enter Grand Hall", "next": "grand_hall"},
            {"text": "🔍 Inspect the Gate", "next": "inspect_gate", "evidence": "rusty_key"},
        ],
    },
    "inspect_gate": {
        "chapter": 1,
        "title": "Chapter 1: The Gates of Foggy Palace",
        "text": (
            "🔍 You run your fingers along the cold iron bars. Wedged between two rusted "
            "links, you find a small, tarnished key.\n\n"
            "🗝 <b>Evidence found:</b> A Rusty Key\n\n"
            "The fog thickens. It's time to go inside."
        ),
        "options": [{"text": "🚪 Enter Grand Hall", "next": "grand_hall"}],
    },
    "grand_hall": {
        "chapter": 1,
        "title": "Chapter 1: The Gates of Foggy Palace",
        "text": (
            "🏰 The Grand Hall is dim, lit only by a dying fireplace. Dust covers "
            "everything except for a single object on the table.\n\n"
            "📜 A leather diary lies open, and a portrait of Lord Ashworth stares "
            "down at you from the wall.\n\n"
            "🕵️‍♂️ Where do you focus your attention?"
        ),
        "options": [
            {"text": "📜 Read Old Diary", "next": "read_diary", "evidence": "diary_page"},
            {"text": "🖼 Examine the Portrait", "next": "examine_portrait", "evidence": "hidden_lever"},
        ],
    },
    "read_diary": {
        "chapter": 1,
        "title": "Chapter 1: The Gates of Foggy Palace",
        "text": (
            "📜 The diary's last entry, written in shaky handwriting, reads:\n"
            "<i>\"...someone in this house wants me gone. I heard whispers near "
            "the library at midnight...\"</i>\n\n"
            "🗝 <b>Evidence found:</b> A torn Diary Page\n\n"
            "⏱ The clock in the hall strikes twelve. A door creaks somewhere upstairs."
        ),
        "options": [
            {"text": "🖼 Examine the Portrait", "next": "examine_portrait", "evidence": "hidden_lever"},
            {"text": "⬆️ Go Upstairs", "next": "chapter2_start"},
        ],
    },
    "examine_portrait": {
        "chapter": 1,
        "title": "Chapter 1: The Gates of Foggy Palace",
        "text": (
            "🖼 Behind the portrait's frame, your fingers brush against a small "
            "hidden lever. With a click, a narrow passage opens in the wall.\n\n"
            "🗝 <b>Evidence found:</b> A Hidden Lever's Secret\n\n"
            "🕵️‍♂️ A cold draft flows from the passage. Do you dare go further?"
        ),
        "options": [
            {"text": "🚶 Step Into the Passage", "next": "chapter2_start"},
            {"text": "⬆️ Go Upstairs Instead", "next": "chapter2_start"},
        ],
    },
    "chapter2_start": {
        "chapter": 2,
        "title": "Chapter 2: Whispers in the Library",
        "text": (
            "📜 <b>Chapter 2: Whispers in the Library</b>\n\n"
            "You arrive at the library. Shelves tower into the darkness above, and "
            "a faint smell of burnt paper lingers in the air.\n\n"
            "🕵️‍♂️ Two things catch your eye: an open ledger on the desk, and a "
            "fireplace still warm with ash.\n\nWhat do you investigate?"
        ),
        "options": [
            {"text": "📖 Check the Ledger", "next": "check_ledger", "evidence": "ledger_entry"},
            {"text": "🔥 Search the Fireplace", "next": "search_fireplace", "evidence": "burnt_letter"},
        ],
    },
    "check_ledger": {
        "chapter": 2,
        "title": "Chapter 2: Whispers in the Library",
        "text": (
            "📖 The ledger shows a large sum of money paid to someone named "
            "\"<b>V. Marsh</b>\" just three days before the murder.\n\n"
            "🗝 <b>Evidence found:</b> A Suspicious Ledger Entry\n\n"
            "🕵️‍♂️ Footsteps echo behind the bookshelf. Someone is watching you."
        ),
        "options": [
            {"text": "🔥 Search the Fireplace", "next": "search_fireplace", "evidence": "burnt_letter"},
            {"text": "👤 Confront the Footsteps", "next": "confront_shadow"},
        ],
    },
    "search_fireplace": {
        "chapter": 2,
        "title": "Chapter 2: Whispers in the Library",
        "text": (
            "🔥 Among the ashes, a half-burnt letter survives. You can still make "
            "out the words: <i>\"...meet me at the tower, midnight, tell no one...\"</i>\n\n"
            "🗝 <b>Evidence found:</b> A Burnt Letter\n\n"
            "🕵️‍♂️ You hear a faint creak — someone else is in this room."
        ),
        "options": [
            {"text": "📖 Check the Ledger", "next": "check_ledger", "evidence": "ledger_entry"},
            {"text": "👤 Confront the Footsteps", "next": "confront_shadow"},
        ],
    },
    "confront_shadow": {
        "chapter": 2,
        "title": "Chapter 2: Whispers in the Library",
        "text": (
            "👤 You spin around and catch a glimpse of a cloaked figure vanishing "
            "through a side door, dropping a glove as they flee.\n\n"
            "🗝 <b>Evidence found:</b> A Mysterious Glove\n\n"
            "⏱ The night is running out. It's time to head to the tower."
        ),
        "options": [{"text": "🗼 Go to the Tower", "next": "chapter3_start", "evidence": "glove"}],
    },
    "chapter3_start": {
        "chapter": 3,
        "title": "Chapter 3: The Tower of Truth",
        "text": (
            "🗝 <b>Chapter 3: The Tower of Truth</b>\n\n"
            "The winding stairs lead you to the top of the old tower, where the "
            "fog is thinner and the moon casts long shadows.\n\n"
            "🕵️‍♂️ A figure stands at the edge, waiting. It's time for answers.\n\n"
            "How do you approach?"
        ),
        "options": [
            {"text": "🗣 Demand the Truth", "next": "demand_truth"},
            {"text": "🔍 Present Your Evidence", "next": "present_evidence"},
        ],
    },
    "demand_truth": {
        "chapter": 3,
        "title": "Chapter 3: The Tower of Truth",
        "text": (
            "🗣 You shout your accusations into the wind, but without proof, the "
            "figure only smiles coldly and slips away into the fog.\n\n"
            "🕵️‍♂️ You've lost your only chance — the truth vanishes with them.\n\n"
            "🔚 <b>Ending: The Truth Escapes</b>\n"
            "The case remains unsolved. Foggy Palace keeps its secrets... for now."
        ),
        "options": [{"text": "🔁 Restart the Quest", "next": "start"}],
    },
    "present_evidence": {
        "chapter": 3,
        "title": "Chapter 3: The Tower of Truth",
        "text": (
            "🔍 One by one, you lay out the diary page, the ledger entry, the "
            "burnt letter, and the glove. The figure's smile fades to fear.\n\n"
            "🕵️‍♂️ Cornered by the truth, they finally confess: it was <b>V. Marsh</b>, "
            "the estate's steward, driven by debt and betrayal.\n\n"
            "🔚 <b>Ending: The Case is Solved!</b>\n"
            "🏆 Congratulations, Detective! You have uncovered the Foggy Palace Mystery."
        ),
        "options": [{"text": "🔁 Restart the Quest", "next": "start"}],
    },
}

# =========================================================
#  PROJECT REGISTRY
#  project_id -> {"title", "description", "start", "nodes", "builtin"}
# =========================================================
PROJECTS: Dict[str, Dict] = {}


def register_builtin_project():
    PROJECTS["foggy_palace"] = {
        "title": "🏰 The Foggy Palace Mystery",
        "description": "The original detective quest bundled with this bot.",
        "start": "start",
        "nodes": BUILTIN_NODES,
        "builtin": True,
    }


def sanitize_id(raw: str) -> str:
    base = raw.rsplit(".", 1)[0].strip().lower()
    base = re.sub(r"[^a-z0-9_]+", "_", base).strip("_")
    return base or "project"


def validate_and_build_project(data: dict, source_name: str) -> Tuple[str, Dict]:
    if not isinstance(data, dict):
        raise ValueError("The JSON root must be an object.")

    title = data.get("title")
    if not title or not isinstance(title, str):
        raise ValueError("Missing or invalid 'title' field.")

    start = data.get("start")
    if not start or not isinstance(start, str):
        raise ValueError("Missing or invalid 'start' field (must be a node id).")

    nodes = data.get("nodes")
    if not isinstance(nodes, dict) or not nodes:
        raise ValueError("Missing or empty 'nodes' object.")

    if start not in nodes:
        raise ValueError(f"'start' node '{start}' was not found inside 'nodes'.")

    for node_id, node in nodes.items():
        if not isinstance(node, dict):
            raise ValueError(f"Node '{node_id}' must be an object.")
        if "text" not in node or not isinstance(node["text"], str):
            raise ValueError(f"Node '{node_id}' is missing a valid 'text' field.")
        options = node.get("options", [])
        if not isinstance(options, list):
            raise ValueError(f"Node '{node_id}' field 'options' must be a list.")
        for opt in options:
            if not isinstance(opt, dict) or "text" not in opt or "next" not in opt:
                raise ValueError(f"Node '{node_id}' has an invalid option (needs 'text' and 'next').")
            if opt["next"] not in nodes:
                raise ValueError(
                    f"Node '{node_id}' has an option pointing to missing node '{opt['next']}'."
                )

    project_id = sanitize_id(str(data.get("id") or source_name))
    project = {
        "title": title,
        "description": data.get("description", ""),
        "start": start,
        "nodes": nodes,
        "builtin": False,
    }
    return project_id, project


def load_projects_from_disk():
    for file_path in PROJECTS_DIR.glob("*.json"):
        try:
            raw = file_path.read_text(encoding="utf-8")
            data = json.loads(raw)
            project_id, project = validate_and_build_project(data, file_path.name)
            PROJECTS[project_id] = project
            logger.info("Loaded project '%s' from %s", project_id, file_path.name)
        except Exception as exc:
            logger.warning("Skipped invalid project file %s: %s", file_path.name, exc)


PROJECT_JSON_TEMPLATE = """{
  "title": "The Silent Manor",
  "description": "A short crime mystery about a missing heirloom.",
  "start": "start",
  "nodes": {
    "start": {
      "chapter": 1,
      "title": "Chapter 1: A Cold Welcome",
      "text": "🏚 You step into the manor. The air is cold. Where do you look first?",
      "options": [
        {"text": "🔍 Check the Study", "next": "study", "evidence": "torn_note"},
        {"text": "🚪 Go to the Kitchen", "next": "kitchen"}
      ]
    },
    "study": {
      "chapter": 1,
      "title": "Chapter 1: A Cold Welcome",
      "text": "📜 You find a torn note hidden in a drawer.",
      "options": [
        {"text": "🚪 Go to the Kitchen", "next": "kitchen"}
      ]
    },
    "kitchen": {
      "chapter": 1,
      "title": "Chapter 1: A Cold Welcome",
      "text": "🔚 <b>Ending:</b> To be continued...",
      "options": [
        {"text": "🔁 Restart", "next": "start"}
      ]
    }
  }
}"""


# =========================================================
#  KEYBOARDS
# =========================================================
def main_menu_keyboard(user_id: int) -> ReplyKeyboardMarkup:
    rows = [
        [KeyboardButton(text="🏰 Start Quest"), KeyboardButton(text="🔍 Examine Evidence")],
        [KeyboardButton(text="📜 Story Progress"), KeyboardButton(text="❓ Help & Rules")],
        [KeyboardButton(text="📂 Projects")],
    ]
    if is_admin(user_id):
        rows.append([KeyboardButton(text="➕ Add Project")])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


def story_inline_keyboard(project_id: str, node_id: str) -> InlineKeyboardMarkup:
    node = PROJECTS[project_id]["nodes"][node_id]
    buttons: List[List[InlineKeyboardButton]] = []
    for opt in node["options"]:
        buttons.append(
            [InlineKeyboardButton(text=opt["text"], callback_data=f"story:{project_id}:{opt['next']}")]
        )
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def projects_inline_keyboard() -> InlineKeyboardMarkup:
    buttons: List[List[InlineKeyboardButton]] = []
    for pid, project in PROJECTS.items():
        buttons.append([InlineKeyboardButton(text=project["title"], callback_data=f"project:{pid}")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# =========================================================
#  HELPERS
# =========================================================
def evidence_display_name(key: str) -> str:
    return "🗝 " + key.replace("_", " ").title()


async def send_story_node(target_message: Message, user_id: int, project_id: str, node_id: str):
    project = PROJECTS[project_id]
    node = project["nodes"][node_id]

    state = get_user(user_id)
    state["project"] = project_id
    state["node"] = node_id
    state["chapter"] = node.get("chapter", 1)

    await target_message.answer(node["text"], reply_markup=story_inline_keyboard(project_id, node_id))


# =========================================================
#  HANDLERS: COMMANDS & MAIN MENU
# =========================================================
@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    user_id = message.from_user.id
    user_data[user_id] = {
        "project": None,
        "node": None,
        "evidence_by_project": {},
        "chapter": 0,
    }

    await message.answer(
        "🏰 <b>Welcome to The Foggy Palace Mystery!</b> 🕵️‍♂️\n\n"
        "A murder has taken place inside a fog-covered palace, and you are the "
        "detective sent to uncover the truth. Explore rooms, gather evidence, "
        "and unmask the killer before the trail goes cold.\n\n"
        "Use the menu below to begin your investigation, or open 📂 Projects to "
        "explore other mystery cases.",
        reply_markup=main_menu_keyboard(user_id),
    )


@router.message(F.text == "🏰 Start Quest")
async def start_quest(message: Message):
    user_id = message.from_user.id
    user_data[user_id] = {
        "project": "foggy_palace",
        "node": "start",
        "evidence_by_project": {},
        "chapter": 1,
    }
    await send_story_node(message, user_id, "foggy_palace", "start")


@router.message(F.text == "📂 Projects")
async def show_projects(message: Message):
    if not PROJECTS:
        await message.answer("📂 There are no investigation cases available right now.")
        return

    lines = ["📂 <b>Available Cases:</b>\n"]
    for project in PROJECTS.values():
        desc = f" — {project['description']}" if project.get("description") else ""
        lines.append(f"• <b>{project['title']}</b>{desc}")

    await message.answer("\n".join(lines), reply_markup=projects_inline_keyboard())


@router.message(F.text == "🔍 Examine Evidence")
async def examine_evidence(message: Message):
    user_id = message.from_user.id
    state = get_user(user_id)
    evidence_by_project = state["evidence_by_project"]

    if not any(evidence_by_project.values()):
        await message.answer(
            "🔍 <b>Evidence Collected:</b>\n\n"
            "You haven't found any clues yet. Start a case and explore "
            "carefully — clues are often hidden in plain sight!"
        )
        return

    blocks = []
    for pid, evidence_set in evidence_by_project.items():
        if not evidence_set:
            continue
        title = PROJECTS.get(pid, {}).get("title", pid)
        lines = "\n".join(f"• {evidence_display_name(e)}" for e in sorted(evidence_set))
        blocks.append(f"<b>{title}</b>\n{lines}")

    await message.answer("🔍 <b>Evidence Collected:</b>\n\n" + "\n\n".join(blocks))


@router.message(F.text == "📜 Story Progress")
async def story_progress(message: Message):
    user_id = message.from_user.id
    state = get_user(user_id)

    if not state["project"] or state["project"] not in PROJECTS:
        await message.answer(
            "📜 <b>Story Progress:</b>\n\n"
            "You haven't started an investigation yet. Tap 🏰 Start Quest or "
            "open 📂 Projects to begin!"
        )
        return

    project = PROJECTS[state["project"]]
    node = project["nodes"].get(state["node"], {})
    evidence_count = len(state["evidence_by_project"].get(state["project"], set()))

    await message.answer(
        "📜 <b>Story Progress:</b>\n\n"
        f"Case: <b>{project['title']}</b>\n"
        f"Current chapter: <b>{node.get('title', 'Unknown')}</b>\n"
        f"Clues gathered: <b>{evidence_count}</b>\n\n"
        "Continue using the buttons in your last message, or open 📂 Projects "
        "to switch to a different case."
    )


@router.message(F.text == "❓ Help & Rules")
async def help_rules(message: Message):
    await message.answer(
        "❓ <b>Help & Rules</b>\n\n"
        "🏰 <b>Start Quest</b> — begin or restart the default investigation.\n"
        "📂 <b>Projects</b> — browse and play all available mystery cases.\n"
        "🔍 <b>Examine Evidence</b> — review all clues you've collected.\n"
        "📜 <b>Story Progress</b> — check your current case and chapter.\n\n"
        "🕵️‍♂️ During the story, use the inline buttons under each message to "
        "make choices. Your decisions affect which clues you find and how the "
        "mystery unfolds. Explore carefully, gather every clue, and present "
        "solid evidence to solve the case!"
    )


# =========================================================
#  HANDLERS: ADMIN — ADD NEW PROJECT
# =========================================================
@router.message(F.text == "➕ Add Project")
async def add_project_start(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return

    await state.set_state(AdminStates.waiting_for_file)
    await message.answer(
        "➕ <b>Add a New Mystery Case</b>\n\n"
        "Send me a <b>.json</b> file describing your story. It must follow this "
        "structure:\n\n"
        f"<pre>{PROJECT_JSON_TEMPLATE}</pre>\n\n"
        "Rules:\n"
        "• <code>title</code> — the case name shown in 📂 Projects.\n"
        "• <code>start</code> — the id of the first node.\n"
        "• <code>nodes</code> — an object of node id → node data.\n"
        "• Each node needs <code>text</code> and a list of <code>options</code> "
        "(each option needs <code>text</code> and <code>next</code>, and can "
        "optionally add <code>evidence</code>: \"some_key\").\n\n"
        "Send /cancel to stop."
    )


@router.message(AdminStates.waiting_for_file, Command("cancel"))
async def add_project_cancel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("❌ Cancelled adding a new project.", reply_markup=main_menu_keyboard(message.from_user.id))


@router.message(AdminStates.waiting_for_file, F.document)
async def add_project_receive_file(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await state.clear()
        return

    document = message.document
    if not document.file_name or not document.file_name.lower().endswith(".json"):
        await message.answer("❌ Please send a valid <b>.json</b> file, or /cancel.")
        return

    try:
        buffer = await message.bot.download(document)
        raw = buffer.read().decode("utf-8")
        data = json.loads(raw)
        project_id, project = validate_and_build_project(data, document.file_name)
    except json.JSONDecodeError as exc:
        await message.answer(f"❌ Invalid JSON syntax: {exc}\n\nPlease fix the file and try again, or /cancel.")
        return
    except Exception as exc:
        await message.answer(f"❌ Failed to load project: {exc}\n\nPlease fix the file and try again, or /cancel.")
        return

    file_path = PROJECTS_DIR / f"{project_id}.json"
    file_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    PROJECTS[project_id] = project
    await state.clear()

    await message.answer(
        f"✅ <b>Project added successfully!</b>\n\n"
        f"Title: <b>{project['title']}</b>\n"
        f"ID: <code>{project_id}</code>\n\n"
        "It is now visible to everyone in the 📂 Projects section.",
        reply_markup=main_menu_keyboard(message.from_user.id),
    )


@router.message(AdminStates.waiting_for_file)
async def add_project_wrong_content(message: Message):
    await message.answer("📎 Please send the story as a <b>.json file (document)</b>, or /cancel.")


# =========================================================
#  HANDLERS: INLINE BUTTONS
# =========================================================
@router.callback_query(F.data.startswith("project:"))
async def handle_project_selection(callback: CallbackQuery):
    user_id = callback.from_user.id
    project_id = callback.data.split(":", 1)[1]

    if project_id not in PROJECTS:
        await callback.answer("This case is no longer available.", show_alert=True)
        return

    project = PROJECTS[project_id]
    state = get_user(user_id)
    state["project"] = project_id
    state["node"] = project["start"]
    state["evidence_by_project"].setdefault(project_id, set())

    await callback.answer()
    if callback.message:
        await send_story_node(callback.message, user_id, project_id, project["start"])


@router.callback_query(F.data.startswith("story:"))
async def handle_story_choice(callback: CallbackQuery):
    user_id = callback.from_user.id
    try:
        _, project_id, next_node_id = callback.data.split(":", 2)
    except ValueError:
        await callback.answer("Something went wrong.", show_alert=True)
        return

    if project_id not in PROJECTS or next_node_id not in PROJECTS[project_id]["nodes"]:
        await callback.answer("This path seems to be lost in the fog...", show_alert=True)
        return

    state = get_user(user_id)
    current_project_id = state.get("project")
    current_node_id = state.get("node")

    if current_project_id == project_id and current_node_id in PROJECTS[project_id]["nodes"]:
        current_node = PROJECTS[project_id]["nodes"][current_node_id]
        for opt in current_node["options"]:
            if opt["next"] == next_node_id and opt.get("evidence"):
                state["evidence_by_project"].setdefault(project_id, set()).add(opt["evidence"])

    await callback.answer()

    if callback.message:
        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass
        await send_story_node(callback.message, user_id, project_id, next_node_id)


# =========================================================
#  FALLBACK HANDLER
# =========================================================
@router.message()
async def fallback_handler(message: Message):
    await message.answer(
        "🕵️‍♂️ I don't understand that command. Please use the menu buttons below.",
        reply_markup=main_menu_keyboard(message.from_user.id),
    )


# =========================================================
#  MAIN ENTRY POINT
# =========================================================
async def main():
    register_builtin_project()
    load_projects_from_disk()

    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)

    logger.info("Starting The Foggy Palace Mystery bot with %d project(s)...", len(PROJECTS))
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped.")
