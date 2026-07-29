import asyncio
import logging
from typing import Dict, List, Optional

from aiogram import Bot, Dispatcher, Router, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
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

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("FoggyPalaceMystery")

router = Router()

# =========================================================
#  IN-MEMORY USER STATE
#  user_id -> {"node": str, "evidence": set[str], "chapter": int}
# =========================================================
user_data: Dict[int, Dict] = {}


def get_user(user_id: int) -> Dict:
    if user_id not in user_data:
        user_data[user_id] = {"node": "start", "evidence": set(), "chapter": 0}
    return user_data[user_id]


# =========================================================
#  STORY DATA
#  Each node: text, chapter number, list of options.
#  Each option: (button_text, next_node_id, evidence_key_or_None)
# =========================================================
STORY: Dict[str, Dict] = {
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
            ("🚪 Enter Grand Hall", "grand_hall", None),
            ("🔍 Inspect the Gate", "inspect_gate", "rusty_key"),
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
        "options": [
            ("🚪 Enter Grand Hall", "grand_hall", None),
        ],
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
            ("📜 Read Old Diary", "read_diary", "diary_page"),
            ("🖼 Examine the Portrait", "examine_portrait", "hidden_lever"),
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
            ("🖼 Examine the Portrait", "examine_portrait", "hidden_lever"),
            ("⬆️ Go Upstairs", "chapter2_start", None),
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
            ("🚶 Step Into the Passage", "chapter2_start", None),
            ("⬆️ Go Upstairs Instead", "chapter2_start", None),
        ],
    },
    # -----------------------------------------------------
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
            ("📖 Check the Ledger", "check_ledger", "ledger_entry"),
            ("🔥 Search the Fireplace", "search_fireplace", "burnt_letter"),
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
            ("🔥 Search the Fireplace", "search_fireplace", "burnt_letter"),
            ("👤 Confront the Footsteps", "confront_shadow", None),
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
            ("📖 Check the Ledger", "check_ledger", "ledger_entry"),
            ("👤 Confront the Footsteps", "confront_shadow", None),
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
        "options": [
            ("🗼 Go to the Tower", "chapter3_start", None),
        ],
    },
    # -----------------------------------------------------
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
            ("🗣 Demand the Truth", "demand_truth", None),
            ("🔍 Present Your Evidence", "present_evidence", None),
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
        "options": [
            ("🔁 Restart the Quest", "start", None),
        ],
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
        "options": [
            ("🔁 Restart the Quest", "start", None),
        ],
    },
}


# =========================================================
#  KEYBOARDS
# =========================================================
def main_menu_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🏰 Start Quest"), KeyboardButton(text="🔍 Examine Evidence")],
            [KeyboardButton(text="📜 Story Progress"), KeyboardButton(text="❓ Help & Rules")],
        ],
        resize_keyboard=True,
    )


def story_inline_keyboard(node_id: str) -> InlineKeyboardMarkup:
    node = STORY[node_id]
    buttons: List[List[InlineKeyboardButton]] = []
    for option_text, next_node, _evidence in node["options"]:
        buttons.append(
            [InlineKeyboardButton(text=option_text, callback_data=f"story:{next_node}")]
        )
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# =========================================================
#  HELPERS
# =========================================================
def evidence_display_name(key: str) -> str:
    names = {
        "rusty_key": "🗝 A Rusty Key",
        "diary_page": "📜 A Torn Diary Page",
        "hidden_lever": "🖼 A Hidden Lever's Secret",
        "ledger_entry": "📖 A Suspicious Ledger Entry",
        "burnt_letter": "🔥 A Burnt Letter",
        "glove": "🧤 A Mysterious Glove",
    }
    return names.get(key, key)


async def send_story_node(target_message: Message, user_id: int, node_id: str):
    state = get_user(user_id)
    state["node"] = node_id
    state["chapter"] = STORY[node_id]["chapter"]

    node = STORY[node_id]
    await target_message.answer(
        node["text"],
        reply_markup=story_inline_keyboard(node_id),
    )


# =========================================================
#  HANDLERS: COMMANDS & MAIN MENU
# =========================================================
@router.message(CommandStart())
async def cmd_start(message: Message):
    user_id = message.from_user.id
    user_data[user_id] = {"node": "start", "evidence": set(), "chapter": 0}

    await message.answer(
        "🏰 <b>Welcome to The Foggy Palace Mystery!</b> 🕵️‍♂️\n\n"
        "A murder has taken place inside a fog-covered palace, and you are the "
        "detective sent to uncover the truth. Explore rooms, gather evidence, "
        "and unmask the killer before the trail goes cold.\n\n"
        "Use the menu below to begin your investigation.",
        reply_markup=main_menu_keyboard(),
    )


@router.message(F.text == "🏰 Start Quest")
async def start_quest(message: Message):
    user_id = message.from_user.id
    user_data[user_id] = {"node": "start", "evidence": set(), "chapter": 1}
    await send_story_node(message, user_id, "start")


@router.message(F.text == "🔍 Examine Evidence")
async def examine_evidence(message: Message):
    user_id = message.from_user.id
    state = get_user(user_id)

    if not state["evidence"]:
        await message.answer(
            "🔍 <b>Evidence Collected:</b>\n\n"
            "You haven't found any clues yet. Start your quest and explore "
            "the palace carefully — clues are often hidden in plain sight!"
        )
        return

    lines = "\n".join(f"• {evidence_display_name(e)}" for e in sorted(state["evidence"]))
    await message.answer(f"🔍 <b>Evidence Collected:</b>\n\n{lines}")


@router.message(F.text == "📜 Story Progress")
async def story_progress(message: Message):
    user_id = message.from_user.id
    state = get_user(user_id)

    if state["chapter"] == 0:
        await message.answer(
            "📜 <b>Story Progress:</b>\n\n"
            "You haven't started your investigation yet. Tap 🏰 Start Quest to begin!"
        )
        return

    node = STORY.get(state["node"], STORY["start"])
    await message.answer(
        "📜 <b>Story Progress:</b>\n\n"
        f"Current chapter: <b>{node['title']}</b>\n"
        f"Clues gathered: <b>{len(state['evidence'])}</b>\n\n"
        "Continue your investigation using the buttons in your last message, "
        "or tap 🏰 Start Quest to begin a new investigation."
    )


@router.message(F.text == "❓ Help & Rules")
async def help_rules(message: Message):
    await message.answer(
        "❓ <b>Help & Rules</b>\n\n"
        "🏰 <b>Start Quest</b> — begin or restart your investigation.\n"
        "🔍 <b>Examine Evidence</b> — review all clues you've collected.\n"
        "📜 <b>Story Progress</b> — check your current chapter.\n\n"
        "🕵️‍♂️ During the story, use the inline buttons under each message to "
        "make choices. Your decisions affect which clues you find and how the "
        "mystery unfolds. Explore carefully, gather every clue, and present "
        "solid evidence to solve the case!"
    )


# =========================================================
#  HANDLERS: INLINE STORY BUTTONS
# =========================================================
@router.callback_query(F.data.startswith("story:"))
async def handle_story_choice(callback: CallbackQuery):
    user_id = callback.from_user.id
    next_node_id = callback.data.split(":", 1)[1]

    if next_node_id not in STORY:
        await callback.answer("This path seems to be lost in the fog...", show_alert=True)
        return

    state = get_user(user_id)
    current_node_id = state.get("node", "start")
    current_node = STORY.get(current_node_id)

    # Record evidence tied to the option that led to this next node
    if current_node:
        for _text, target, evidence_key in current_node["options"]:
            if target == next_node_id and evidence_key:
                state["evidence"].add(evidence_key)

    await callback.answer()

    if callback.message:
        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass
        await send_story_node(callback.message, user_id, next_node_id)


# =========================================================
#  FALLBACK HANDLER
# =========================================================
@router.message()
async def fallback_handler(message: Message):
    await message.answer(
        "🕵️‍♂️ I don't understand that command. Please use the menu buttons below.",
        reply_markup=main_menu_keyboard(),
    )


# =========================================================
#  MAIN ENTRY POINT
# =========================================================
async def main():
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()
    dp.include_router(router)

    logger.info("Starting The Foggy Palace Mystery bot...")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped.")
