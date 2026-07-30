import asyncio
import logging
import os
import random
import traceback
import aiohttp
from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    Message,
    CallbackQuery,
    ErrorEvent,
)

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# =========================================================
# XAVFSIZLIK ESLATMASI:
# Tokenlarni to'g'ridan-to'g'ri kodga yozmang!
# Railway -> Variables bo'limida BOT_TOKEN va OPENAI_API_KEY
# nomli muhit o'zgaruvchilarini kiritish tavsiya etiladi.
# =========================================================
BOT_TOKEN = os.getenv("BOT_TOKEN", "8641817546:AAE9g0L8f-msCuYs5wh4nzyPwgyRNf80Rps")
ADMIN_ID = 8425304206

# Diqqat: bu format standart OpenAI kaliti (odatda "sk-" bilan boshlanadi) ko'rinishida emas.
# Agar chaqiruvlar ishlamasa, bot avtomatik ravishda tayyor javoblar rejimiga o'tadi.
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "c481286c6ad12e968ffd702dae30e7ce9a9535e77033b0ec303afd91b1200161")
OPENAI_API_URL = "https://api.openai.com/v1/chat/completions"
OPENAI_MODEL = "gpt-4o-mini"

# Xotira va Bazalar
user_languages = {}
user_active_project = {}
admin_temp_data = {}
player_temp_data = {}
PROJECTS = {}
user_stats = {}
investigation_sessions = {}

CANCEL_TEXT = "❌ Bekor qilish"
DONE_PHOTOS_TEXT = "✅ Rasmlarni yuklab bo'ldim"
BACK_TEXT = "🔙 Ortga"

DIFFICULTY_POINTS = {"oson": 60, "orta": 120, "qiyin": 220}
DIFFICULTY_LABELS = {"oson": "🟢 Oson", "orta": "🟡 O'rta", "qiyin": "🔴 Qiyin"}

FALLBACK_RESPONSES = [
    "Bu haqda hech narsa demoqchi emasman.",
    "Eslay olmayapman, juda ko'p vaqt o'tib ketdi.",
    "Nega bunday so'ramoqdasiz? Menga aloqasi yo'q buning!",
    "Advokatim bilan gaplashmaguncha javob bermayman.",
    "Bilmayman, o'sha kuni boshqa ishlar bilan band edim.",
    "Bu savolga javob berishga hojat yo'q deb o'ylayman.",
]


# FSM Holatlari
class AdminAddState(StatesGroup):
    waiting_for_title = State()
    waiting_for_evidence_photos = State()
    waiting_for_difficulty = State()
    waiting_for_suspect_count = State()
    waiting_for_suspect_photo = State()
    waiting_for_suspect_info = State()
    waiting_for_suspect_dialog = State()
    waiting_for_suspect_guilt = State()


class PlayerState(StatesGroup):
    waiting_for_free_question = State()


# TILLAR VA MATNLAR
TEXTS = {
    "uz": {
        "choose_lang": "Iltimos, muloqot tilini tanlang:",
        "lang_selected": "✅ O'zbek tili tanlandi!",
        "select_project": "📁 **Mavjud loyihalar ro'yxati:**\n\nDavom etish uchun biror loyihani ustiga bosing:",
        "btn_suspects": "👥 Gumondorlar va So'roq",
        "btn_evidence": "🔍 Dalillar",
        "btn_projects": "📁 Loyihalar bo'limi",
        "btn_lang": "🌐 Tilni o'zgartirish",
        "btn_add_project": "➕ Yangi loyiha yuklash",
        "btn_delete_project": "🗑 Loyihani o'chirish",
        "btn_accuse": "🔍 Ayblov e'lon qilish",
        "btn_hint": "💡 Maslahat",
        "btn_leaderboard": "🏆 Reyting",
        "btn_stats": "👤 Mening natijalarim",
        "no_projects": "Hozircha hech qanday loyiha mavjud emas.",
        "interrogate_title": "❓ Tergovchi sifatida bermoqchi bo'lgan savol tugmasini bosing, yoki AI orqali erkin savol bering:",
        "cancelled": "🚫 Jarayon bekor qilindi.",
        "send_photo_only": "⚠️ Iltimos, rasmni albatta 'Photo' sifatida yuboring, fayl (document) sifatida emas.",
        "send_text_only": "⚠️ Iltimos, matn ko'rinishida javob yuboring.",
        "no_active_project": "⚠️ Avval loyihani tanlang!",
    },
    "ru": {
        "choose_lang": "Пожалуйста, выберите язык:",
        "lang_selected": "✅ Выбран русский язык!",
        "select_project": "📁 **Список доступных проектов:**\n\nВыберите проект:",
        "btn_suspects": "👥 Подозреваемые и Допрос",
        "btn_evidence": "🔍 Улики",
        "btn_projects": "📁 Раздел проектов",
        "btn_lang": "🌐 Сменить язык",
        "btn_add_project": "➕ Добавить проект",
        "btn_delete_project": "🗑 Удалить проект",
        "btn_accuse": "🔍 Предъявить обвинение",
        "btn_hint": "💡 Подсказка",
        "btn_leaderboard": "🏆 Рейтинг",
        "btn_stats": "👤 Мои результаты",
        "no_projects": "Проектов пока нет.",
        "interrogate_title": "❓ Выберите вопрос допроса или задайте свободный вопрос через AI:",
        "cancelled": "🚫 Процесс отменён.",
        "send_photo_only": "⚠️ Пожалуйста, отправьте фото как 'Photo', а не как файл.",
        "send_text_only": "⚠️ Пожалуйста, отправьте ответ текстом.",
        "no_active_project": "⚠️ Сначала выберите проект!",
    },
    "en": {
        "choose_lang": "Please select a language:",
        "lang_selected": "✅ English language selected!",
        "select_project": "📁 **Available projects list:**\n\nSelect a project:",
        "btn_suspects": "👥 Suspects & Interrogation",
        "btn_evidence": "🔍 Evidence",
        "btn_projects": "📁 Projects Section",
        "btn_lang": "🌐 Change Language",
        "btn_add_project": "➕ Add Project",
        "btn_delete_project": "🗑 Delete Project",
        "btn_accuse": "🔍 Make Accusation",
        "btn_hint": "💡 Hint",
        "btn_leaderboard": "🏆 Leaderboard",
        "btn_stats": "👤 My Stats",
        "no_projects": "No projects available yet.",
        "interrogate_title": "❓ Click a preset question or ask a free question via AI:",
        "cancelled": "🚫 Process cancelled.",
        "send_photo_only": "⚠️ Please send the image as a 'Photo', not as a document.",
        "send_text_only": "⚠️ Please reply with text.",
        "no_active_project": "⚠️ Please select a project first!",
    }
}


def t(lang: str, key: str) -> str:
    """Til lug'atidan matn olish, mavjud bo'lmasa uz tiliga qaytadi."""
    return TEXTS.get(lang, TEXTS["uz"]).get(key, TEXTS["uz"].get(key, key))


# ---------------------------------------------------------
# YORDAMCHI FUNKSIYALAR: statistika va sessiya
# ---------------------------------------------------------
def get_stats(user_id: int, name: str = "Noma'lum"):
    if user_id not in user_stats:
        user_stats[user_id] = {"score": 0, "solved": 0, "failed": 0, "name": name}
    else:
        user_stats[user_id]["name"] = name
    return user_stats[user_id]


def get_session(user_id: int, proj_key: str):
    key = (user_id, proj_key)
    if key not in investigation_sessions:
        investigation_sessions[key] = {"questions_asked": 0, "hints_used": 0, "hinted": set()}
    return investigation_sessions[key]


def get_rank_title(score: int) -> str:
    if score < 100:
        return "🆕 Stajyor"
    if score < 300:
        return "🕵️ Tergovchi"
    if score < 600:
        return "🕶 Tajribali Tergovchi"
    return "🏆 Bosh Detektiv"


async def ask_suspect_ai(suspect: dict, case_title: str, question: str) -> str | None:
    """OpenAI orqali gumondor xarakteriga mos javob generatsiya qilish. Xato bo'lsa None qaytaradi."""
    system_prompt = (
        f"Sen '{suspect['name']}' ismli gumondorsan va tergov ostidasan. "
        f"Yoshing: {suspect.get('age')}, jinsing: {suspect.get('gender')}, "
        f"oilaviy ahvoling: {suspect.get('family')}, sudlanganliging: {suspect.get('criminal_record')}. "
        f"Ish nomi: '{case_title}'. "
    )
    if suspect.get("is_guilty"):
        system_prompt += (
            "SEN HAQIQATDA AYBDORSAN, lekin buni hech qachon ochiq tan olmaysiz. "
            "Savollarga ishonarli, lekin ozgina qarama-qarshiliklar va bahonalar bilan javob ber. "
            "Javobing 2-3 gapdan oshmasin."
        )
    else:
        system_prompt += (
            "SEN AYBDOR EMASSAN. Savollarga tinch va halol javob ber, lekin tergov ostida "
            "bo'lganing uchun biroz asabiylashgan bo'lishing mumkin. Javobing 2-3 gapdan oshmasin."
        )
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                OPENAI_API_URL,
                headers={
                    "Authorization": f"Bearer {OPENAI_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": OPENAI_MODEL,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": question},
                    ],
                    "max_tokens": 150,
                    "temperature": 0.9,
                },
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                data = await resp.json()
                if resp.status == 200:
                    return data["choices"][0]["message"]["content"].strip()
                logger.warning("OpenAI xatosi (status=%s): %s", resp.status, data)
                return None
    except Exception as e:
        logger.warning("OpenAI so'rovida xatolik: %s", e)
        return None


# TUGMALAR
def language_inline_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🇺🇿 O'zbekcha", callback_data="set_lang_uz"),
             InlineKeyboardButton(text="🇷🇺 Русский", callback_data="set_lang_ru")],
            [InlineKeyboardButton(text="🇬🇧 English", callback_data="set_lang_en")]
        ]
    )


def main_menu_keyboard(lang: str, user_id: int):
    buttons = [
        [KeyboardButton(text=t(lang, "btn_suspects")), KeyboardButton(text=t(lang, "btn_evidence"))],
        [KeyboardButton(text=t(lang, "btn_accuse")), KeyboardButton(text=t(lang, "btn_hint"))],
        [KeyboardButton(text=t(lang, "btn_projects")), KeyboardButton(text=t(lang, "btn_lang"))],
        [KeyboardButton(text=t(lang, "btn_leaderboard")), KeyboardButton(text=t(lang, "btn_stats"))],
    ]
    if user_id == ADMIN_ID:
        buttons.append([KeyboardButton(text=t(lang, "btn_add_project")), KeyboardButton(text=t(lang, "btn_delete_project"))])
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


def evidence_upload_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=DONE_PHOTOS_TEXT)], [KeyboardButton(text=CANCEL_TEXT)]],
        resize_keyboard=True,
    )


def cancel_only_keyboard():
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text=CANCEL_TEXT)]], resize_keyboard=True)


def back_only_keyboard():
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text=BACK_TEXT)]], resize_keyboard=True)


def projects_inline_keyboard():
    kb = []
    for key, p in PROJECTS.items():
        label = DIFFICULTY_LABELS.get(p.get("difficulty", "orta"), "")
        kb.append([InlineKeyboardButton(text=f"📂 {p['title']} {label}", callback_data=f"select_proj_{key}")])
    return InlineKeyboardMarkup(inline_keyboard=kb)


def delete_projects_inline_keyboard():
    kb = []
    for key, p in PROJECTS.items():
        kb.append([InlineKeyboardButton(text=f"❌ {p['title']}", callback_data=f"confirm_delete_{key}")])
    return InlineKeyboardMarkup(inline_keyboard=kb)


def suspects_inline_keyboard(proj_key: str):
    kb = []
    for idx, s in enumerate(PROJECTS[proj_key]["suspects"]):
        kb.append([InlineKeyboardButton(text=f"👤 {s['name']}", callback_data=f"view_suspect_{proj_key}_{idx}")])
    return InlineKeyboardMarkup(inline_keyboard=kb)


def dialog_questions_keyboard(proj_key: str, suspect_idx: int):
    kb = []
    for idx, d in enumerate(PROJECTS[proj_key]["suspects"][suspect_idx]["dialogs"]):
        kb.append([InlineKeyboardButton(text=f"❓ {d['question']}", callback_data=f"ans_{proj_key}_{suspect_idx}_{idx}")])
    kb.append([InlineKeyboardButton(text="💬 Erkin savol berish (AI)", callback_data=f"freeq_{proj_key}_{suspect_idx}")])
    return InlineKeyboardMarkup(inline_keyboard=kb)


def accuse_inline_keyboard(proj_key: str):
    kb = []
    for idx, s in enumerate(PROJECTS[proj_key]["suspects"]):
        kb.append([InlineKeyboardButton(text=f"⚖️ {s['name']}", callback_data=f"accuse_{proj_key}_{idx}")])
    return InlineKeyboardMarkup(inline_keyboard=kb)


router = Router()


# ---------------------------------------------------------
# ASOSIY BUYRUQLAR
# ---------------------------------------------------------
@router.message(F.text == "/start")
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    user_languages[message.from_user.id] = "uz"
    await message.answer(TEXTS['uz']['choose_lang'], reply_markup=language_inline_keyboard())


@router.callback_query(F.data.startswith("set_lang_"))
async def process_language_choice(callback: CallbackQuery):
    lang_code = callback.data.split("_")[-1]
    user_id = callback.from_user.id
    user_languages[user_id] = lang_code

    await callback.message.delete()
    await callback.message.answer(t(lang_code, "lang_selected"), reply_markup=main_menu_keyboard(lang_code, user_id))

    if PROJECTS:
        await callback.message.answer(t(lang_code, "select_project"), reply_markup=projects_inline_keyboard(), parse_mode=ParseMode.MARKDOWN)
    else:
        await callback.message.answer(t(lang_code, "no_projects"))
    await callback.answer()


# ---------------------------------------------------------
# BEKOR QILISH — admin qo'shish jarayonining har bir bosqichida
# ---------------------------------------------------------
@router.message(AdminAddState.waiting_for_title, F.text == CANCEL_TEXT)
@router.message(AdminAddState.waiting_for_evidence_photos, F.text == CANCEL_TEXT)
@router.message(AdminAddState.waiting_for_difficulty, F.text == CANCEL_TEXT)
@router.message(AdminAddState.waiting_for_suspect_count, F.text == CANCEL_TEXT)
@router.message(AdminAddState.waiting_for_suspect_photo, F.text == CANCEL_TEXT)
@router.message(AdminAddState.waiting_for_suspect_info, F.text == CANCEL_TEXT)
@router.message(AdminAddState.waiting_for_suspect_dialog, F.text == CANCEL_TEXT)
@router.message(AdminAddState.waiting_for_suspect_guilt, F.text == CANCEL_TEXT)
async def admin_cancel_add(message: Message, state: FSMContext):
    user_id = message.from_user.id
    lang = user_languages.get(user_id, "uz")
    admin_temp_data.pop(user_id, None)
    await state.clear()
    await message.answer(t(lang, "cancelled"), reply_markup=main_menu_keyboard(lang, user_id))


@router.message(F.text.in_(["📁 Loyihalar bo'limi", "📁 Раздел проектов", "📁 Projects Section"]))
async def show_projects_menu(message: Message):
    lang = user_languages.get(message.from_user.id, "uz")
    if PROJECTS:
        await message.answer(t(lang, "select_project"), reply_markup=projects_inline_keyboard(), parse_mode=ParseMode.MARKDOWN)
    else:
        await message.answer(t(lang, "no_projects"))


@router.callback_query(F.data.startswith("select_proj_"))
async def choose_project(callback: CallbackQuery):
    proj_key = callback.data.replace("select_proj_", "")
    user_active_project[callback.from_user.id] = proj_key

    if proj_key in PROJECTS:
        proj = PROJECTS[proj_key]
        diff_label = DIFFICULTY_LABELS.get(proj.get("difficulty", "orta"), "")
        await callback.message.answer(
            f"✅ **{proj['title']}** loyihasi tanlandi! {diff_label}\n\n"
            "Endi pastdagi **👥 Gumondorlar va So'roq** yoki **🔍 Dalillar** tugmalarini bosing.\n"
            "Tergovni yakunlagach, **🔍 Ayblov e'lon qilish** orqali xulosangizni bildiring.",
            parse_mode=ParseMode.MARKDOWN
        )
    else:
        await callback.message.answer("⚠️ Bunday loyiha topilmadi.")
    await callback.answer()


@router.message(F.text.in_(["🔍 Dalillar", "🔍 Улики", "🔍 Evidence"]))
async def show_evidences(message: Message):
    lang = user_languages.get(message.from_user.id, "uz")
    proj_key = user_active_project.get(message.from_user.id)
    if not proj_key or proj_key not in PROJECTS:
        await message.answer(t(lang, "no_active_project"))
        return
    evidences = PROJECTS[proj_key].get("evidences", [])
    if not evidences:
        await message.answer("🔍 Bu loyihada dalillar yo'q.")
        return
    for photo_id in evidences:
        await message.answer_photo(photo=photo_id)


@router.message(F.text.in_(["👥 Gumondorlar va So'roq", "👥 Подозреваемые и Допрос", "👥 Suspects & Interrogation"]))
async def show_suspects_list(message: Message):
    lang = user_languages.get(message.from_user.id, "uz")
    proj_key = user_active_project.get(message.from_user.id)
    if not proj_key or proj_key not in PROJECTS:
        await message.answer(t(lang, "no_active_project"))
        return
    await message.answer("🕵️‍♂️ **Gumondorni tanlang:**", reply_markup=suspects_inline_keyboard(proj_key), parse_mode=ParseMode.MARKDOWN)


@router.callback_query(F.data.startswith("view_suspect_"))
async def view_suspect_profile(callback: CallbackQuery):
    parts = callback.data.split("_")
    proj_key, s_idx = parts[2], int(parts[3])
    s = PROJECTS[proj_key]["suspects"][s_idx]
    lang = user_languages.get(callback.from_user.id, "uz")

    caption = f"📋 **{s['name']}**\n\n👤 Yoshi: {s['age']}\n🚻 Jinsi: {s['gender']}\n💍 Oilaviy: {s['family']}\n⚖️ Sudlangan: {s['criminal_record']}"
    await callback.message.answer_photo(photo=s["photo"], caption=caption, parse_mode=ParseMode.MARKDOWN)
    await callback.message.answer(t(lang, "interrogate_title"), reply_markup=dialog_questions_keyboard(proj_key, s_idx))
    await callback.answer()


@router.callback_query(F.data.startswith("ans_"))
async def process_question_click(callback: CallbackQuery):
    parts = callback.data.split("_")
    proj_key, s_idx, d_idx = parts[1], int(parts[2]), int(parts[3])
    s = PROJECTS[proj_key]["suspects"][s_idx]
    d = s["dialogs"][d_idx]

    session = get_session(callback.from_user.id, proj_key)
    session["questions_asked"] += 1

    await callback.message.answer(f"🕵️‍♂️ **Tergovchi:** {d['question']}\n\n🗣 **{s['name']}:** {d['answer']}", parse_mode=ParseMode.MARKDOWN)
    await callback.answer()


# ---------------------------------------------------------
# ERKIN SAVOL (AI) — gumondorga istalgan savol berish
# ---------------------------------------------------------
@router.callback_query(F.data.startswith("freeq_"))
async def start_free_question(callback: CallbackQuery, state: FSMContext):
    _, proj_key, s_idx = callback.data.split("_")
    s_idx = int(s_idx)
    user_id = callback.from_user.id
    player_temp_data[user_id] = {"proj_key": proj_key, "suspect_idx": s_idx}
    await state.set_state(PlayerState.waiting_for_free_question)
    suspect_name = PROJECTS[proj_key]["suspects"][s_idx]["name"]
    await callback.message.answer(
        f"💬 {suspect_name}ga savolingizni yozib yuboring:",
        reply_markup=back_only_keyboard(),
    )
    await callback.answer()


@router.message(PlayerState.waiting_for_free_question, F.text == BACK_TEXT)
async def stop_free_question(message: Message, state: FSMContext):
    user_id = message.from_user.id
    player_temp_data.pop(user_id, None)
    lang = user_languages.get(user_id, "uz")
    await state.clear()
    await message.answer("🔙 Bosh menyuga qaytdingiz.", reply_markup=main_menu_keyboard(lang, user_id))


@router.message(PlayerState.waiting_for_free_question, F.text)
async def handle_free_question(message: Message, state: FSMContext):
    user_id = message.from_user.id
    ctx = player_temp_data.get(user_id)
    if not ctx:
        await state.clear()
        return
    proj_key, s_idx = ctx["proj_key"], ctx["suspect_idx"]
    if proj_key not in PROJECTS:
        await message.answer("⚠️ Bu loyiha endi mavjud emas.")
        player_temp_data.pop(user_id, None)
        await state.clear()
        return

    suspect = PROJECTS[proj_key]["suspects"][s_idx]
    case_title = PROJECTS[proj_key]["title"]

    await message.bot.send_chat_action(message.chat.id, "typing")
    answer = await ask_suspect_ai(suspect, case_title, message.text)
    if not answer:
        answer = random.choice(FALLBACK_RESPONSES)

    session = get_session(user_id, proj_key)
    session["questions_asked"] += 1

    await message.answer(f"🗣 **{suspect['name']}:** {answer}", parse_mode=ParseMode.MARKDOWN)


@router.message(PlayerState.waiting_for_free_question)
async def free_question_fallback(message: Message):
    await message.answer("💬 Iltimos, savolingizni matn ko'rinishida yozing.")


# ---------------------------------------------------------
# AYBLOV E'LON QILISH (VERDICT)
# ---------------------------------------------------------
@router.message(F.text.in_(["🔍 Ayblov e'lon qilish", "🔍 Предъявить обвинение", "🔍 Make Accusation"]))
async def start_accusation(message: Message):
    lang = user_languages.get(message.from_user.id, "uz")
    proj_key = user_active_project.get(message.from_user.id)
    if not proj_key or proj_key not in PROJECTS:
        await message.answer(t(lang, "no_active_project"))
        return
    await message.answer("⚖️ Kim aybdor deb o'ylaysiz? Tanlang:", reply_markup=accuse_inline_keyboard(proj_key))


@router.callback_query(F.data.startswith("accuse_"))
async def resolve_accusation(callback: CallbackQuery):
    _, proj_key, s_idx = callback.data.split("_")
    s_idx = int(s_idx)
    user_id = callback.from_user.id
    if proj_key not in PROJECTS:
        await callback.answer()
        return

    suspect = PROJECTS[proj_key]["suspects"][s_idx]
    session = get_session(user_id, proj_key)
    stats = get_stats(user_id, callback.from_user.full_name or "Noma'lum")
    points_base = PROJECTS[proj_key].get("points_base", 120)

    if suspect.get("is_guilty"):
        gained = max(points_base - session["questions_asked"] * 5 - session["hints_used"] * 15, 20)
        stats["score"] += gained
        stats["solved"] += 1
        text = (
            f"✅ **TO'G'RI!** {suspect['name']} haqiqatan ham aybdor edi!\n\n"
            f"🎯 Siz {session['questions_asked']} ta savol va {session['hints_used']} ta maslahatdan foydalandingiz.\n"
            f"⭐ +{gained} ball qo'lga kiritdingiz!\n"
            f"🏆 Jami balingiz: {stats['score']}"
        )
    else:
        stats["score"] = max(stats["score"] - 20, 0)
        stats["failed"] += 1
        real_culprit = next((x['name'] for x in PROJECTS[proj_key]["suspects"] if x.get("is_guilty")), "Noma'lum")
        text = (
            f"❌ **NOTO'G'RI!** {suspect['name']} aybdor emas edi.\n\n"
            f"🕵️ Haqiqiy aybdor: **{real_culprit}**\n"
            f"⭐ -20 ball.\n"
            f"🏆 Jami balingiz: {stats['score']}"
        )

    investigation_sessions.pop((user_id, proj_key), None)
    await callback.message.answer(text, parse_mode=ParseMode.MARKDOWN)
    await callback.answer()


# ---------------------------------------------------------
# MASLAHAT (HINT)
# ---------------------------------------------------------
@router.message(F.text.in_(["💡 Maslahat", "💡 Подсказка", "💡 Hint"]))
async def give_hint(message: Message):
    lang = user_languages.get(message.from_user.id, "uz")
    user_id = message.from_user.id
    proj_key = user_active_project.get(user_id)
    if not proj_key or proj_key not in PROJECTS:
        await message.answer(t(lang, "no_active_project"))
        return

    suspects = PROJECTS[proj_key]["suspects"]
    session = get_session(user_id, proj_key)
    remaining = [i for i in range(len(suspects)) if i not in session["hinted"]]
    if not remaining:
        await message.answer("💡 Barcha maslahatlar allaqachon ishlatilgan!")
        return

    idx = random.choice(remaining)
    session["hinted"].add(idx)
    session["hints_used"] += 1
    s = suspects[idx]
    status = "🔴 AYBDOR bo'lishi mumkin!" if s.get("is_guilty") else "🟢 aybdor emasga o'xshaydi."
    await message.answer(
        f"💡 Maslahat (bu {session['hints_used']}-maslahatingiz, ball kamayadi): **{s['name']}** — {status}",
        parse_mode=ParseMode.MARKDOWN,
    )


# ---------------------------------------------------------
# REYTING VA STATISTIKA
# ---------------------------------------------------------
@router.message(F.text.in_(["🏆 Reyting", "🏆 Рейтинг", "🏆 Leaderboard"]))
async def show_leaderboard(message: Message):
    if not user_stats:
        await message.answer("🏆 Hozircha reytingda hech kim yo'q.")
        return
    ranked = sorted(user_stats.values(), key=lambda x: x["score"], reverse=True)[:10]
    lines = ["🏆 **TOP DETEKTIVLAR:**\n"]
    medals = ["🥇", "🥈", "🥉"]
    for i, u in enumerate(ranked):
        medal = medals[i] if i < 3 else f"{i + 1}."
        lines.append(f"{medal} {u['name']} — {u['score']} ball ({u['solved']} ish yechilgan)")
    await message.answer("\n".join(lines), parse_mode=ParseMode.MARKDOWN)


@router.message(F.text.in_(["👤 Mening natijalarim", "👤 Мои результаты", "👤 My Stats"]))
async def show_my_stats(message: Message):
    stats = get_stats(message.from_user.id, message.from_user.full_name or "Noma'lum")
    rank = get_rank_title(stats["score"])
    text = (
        f"👤 **Sizning natijalaringiz:**\n\n"
        f"🏅 Daraja: {rank}\n"
        f"⭐ Ball: {stats['score']}\n"
        f"✅ Yechilgan ishlar: {stats['solved']}\n"
        f"❌ Muvaffaqiyatsiz: {stats['failed']}"
    )
    await message.answer(text, parse_mode=ParseMode.MARKDOWN)


# ---------------------------------------------------------
# LOYIHANI O'CHIRISH (ADMIN)
# ---------------------------------------------------------
@router.message(F.text.in_(["🗑 Loyihani o'chirish", "🗑 Удалить проект", "🗑 Delete Project"]))
async def admin_start_delete(message: Message):
    if message.from_user.id != ADMIN_ID or not PROJECTS:
        return
    await message.answer("🗑 O'chiriladigan loyihani tanlang:", reply_markup=delete_projects_inline_keyboard(), parse_mode=ParseMode.MARKDOWN)


@router.callback_query(F.data.startswith("confirm_delete_"))
async def admin_confirm_delete(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return
    proj_key = callback.data.replace("confirm_delete_", "")
    if proj_key in PROJECTS:
        del PROJECTS[proj_key]
        await callback.message.answer("🗑 Loyiha o'chirildi!", parse_mode=ParseMode.MARKDOWN)
    await callback.answer()


# ---------------------------------------------------------
# LOYIHA QO'SHISH JARAYONI (ADMIN)
# ---------------------------------------------------------
@router.message(F.text.in_(["➕ Yangi loyiha yuklash", "➕ Добавить проект", "➕ Add Project"]))
async def admin_start_add(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    admin_temp_data[message.from_user.id] = {"evidences": [], "suspects": []}
    await state.set_state(AdminAddState.waiting_for_title)
    await message.answer("📝 Loyiha nomini kiriting:", parse_mode=ParseMode.MARKDOWN, reply_markup=cancel_only_keyboard())


@router.message(AdminAddState.waiting_for_title, F.text)
async def admin_get_title(message: Message, state: FSMContext):
    admin_temp_data[message.from_user.id]["title"] = message.text
    await state.set_state(AdminAddState.waiting_for_evidence_photos)
    await message.answer(
        "🖼 Dalil rasmlarini yuboring va tugmani bosing:\n\n"
        "⚠️ Rasmni albatta 'Photo' sifatida yuboring (fayl/document emas).",
        reply_markup=evidence_upload_keyboard(),
    )


@router.message(AdminAddState.waiting_for_title)
async def admin_get_title_invalid(message: Message):
    lang = user_languages.get(message.from_user.id, "uz")
    await message.answer(t(lang, "send_text_only"))


@router.message(AdminAddState.waiting_for_evidence_photos, F.photo)
async def admin_get_evidence_photo(message: Message):
    admin_temp_data[message.from_user.id]["evidences"].append(message.photo[-1].file_id)
    await message.answer("📷 Rasm saqlandi.")


@router.message(AdminAddState.waiting_for_evidence_photos, F.text == DONE_PHOTOS_TEXT)
async def admin_finish_evidences(message: Message, state: FSMContext):
    await state.set_state(AdminAddState.waiting_for_difficulty)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🟢 Oson", callback_data="diff_oson")],
        [InlineKeyboardButton(text="🟡 O'rta", callback_data="diff_orta")],
        [InlineKeyboardButton(text="🔴 Qiyin", callback_data="diff_qiyin")],
    ])
    await message.answer("🎚 Ish qiyinlik darajasini tanlang:", reply_markup=kb)


@router.message(AdminAddState.waiting_for_evidence_photos, F.document)
async def admin_evidence_wrong_type(message: Message):
    lang = user_languages.get(message.from_user.id, "uz")
    await message.answer(t(lang, "send_photo_only"))


@router.message(AdminAddState.waiting_for_evidence_photos)
async def admin_evidence_fallback(message: Message):
    await message.answer("🖼 Iltimos, rasm yuboring yoki tugmalardan birini bosing.", reply_markup=evidence_upload_keyboard())


@router.callback_query(AdminAddState.waiting_for_difficulty, F.data.startswith("diff_"))
async def admin_set_difficulty(callback: CallbackQuery, state: FSMContext):
    diff = callback.data.replace("diff_", "")
    user_id = callback.from_user.id
    admin_temp_data[user_id]["difficulty"] = diff
    admin_temp_data[user_id]["points_base"] = DIFFICULTY_POINTS.get(diff, 120)
    await state.set_state(AdminAddState.waiting_for_suspect_count)
    await callback.message.answer(
        f"✅ Qiyinlik darajasi: {DIFFICULTY_LABELS.get(diff)}\n\n🔢 Gumondorlar sonini raqamda kiriting:",
        reply_markup=cancel_only_keyboard(),
    )
    await callback.answer()


@router.message(AdminAddState.waiting_for_difficulty)
async def admin_difficulty_fallback(message: Message):
    await message.answer("⚠️ Iltimos, yuqoridagi tugmalardan birini tanlang.")


@router.message(AdminAddState.waiting_for_suspect_count, F.text)
async def admin_get_suspect_count(message: Message, state: FSMContext):
    if not message.text.isdigit() or int(message.text) <= 0:
        await message.answer("⚠️ Iltimos, faqat musbat raqam kiriting (masalan: 2):")
        return
    admin_temp_data[message.from_user.id]["total_suspects"] = int(message.text)
    admin_temp_data[message.from_user.id]["current_suspect_index"] = 0

    await state.set_state(AdminAddState.waiting_for_suspect_photo)
    await message.answer(
        "📸 **1-gumondor** rasmini yuboring:\n\n⚠️ Rasmni albatta 'Photo' sifatida yuboring.",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=cancel_only_keyboard(),
    )


@router.message(AdminAddState.waiting_for_suspect_count)
async def admin_suspect_count_fallback(message: Message):
    await message.answer("⚠️ Iltimos, gumondorlar sonini raqamda kiriting (masalan: 2):")


@router.message(AdminAddState.waiting_for_suspect_photo, F.photo)
async def admin_get_suspect_photo(message: Message, state: FSMContext):
    user_id = message.from_user.id
    idx = admin_temp_data[user_id]["current_suspect_index"] + 1
    admin_temp_data[user_id]["current_photo"] = message.photo[-1].file_id

    await state.set_state(AdminAddState.waiting_for_suspect_info)
    await message.answer(
        f"📋 **{idx}-gumondor** ma'lumotlarini quyidagi tartibda kiriting:\n\n"
        "Ismi: ...\nYoshi: ...\nJinsi: ...\nOilaviy ahvoli: ...\nSudlanganligi: ...",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=cancel_only_keyboard(),
    )


@router.message(AdminAddState.waiting_for_suspect_photo, F.document)
async def admin_suspect_photo_wrong_type(message: Message):
    lang = user_languages.get(message.from_user.id, "uz")
    await message.answer(t(lang, "send_photo_only"))


@router.message(AdminAddState.waiting_for_suspect_photo)
async def admin_suspect_photo_fallback(message: Message):
    await message.answer("📸 Iltimos, gumondor rasmini 'Photo' sifatida yuboring.")


@router.message(AdminAddState.waiting_for_suspect_info, F.text)
async def admin_get_suspect_info(message: Message, state: FSMContext):
    user_id = message.from_user.id
    lines = message.text.strip().split("\n")
    info = {"name": "Noma'lum", "age": "Noma'lum", "gender": "Noma'lum", "family": "Noma'lum", "criminal_record": "Noma'lum"}

    for line in lines:
        if ":" in line:
            k, v = line.split(":", 1)
            k, v = k.strip().lower(), v.strip()
            if "ism" in k: info["name"] = v
            elif "yosh" in k: info["age"] = v
            elif "jins" in k: info["gender"] = v
            elif "oilaviy" in k: info["family"] = v
            elif "sudlan" in k: info["criminal_record"] = v

    admin_temp_data[user_id]["current_info"] = info
    idx = admin_temp_data[user_id]["current_suspect_index"] + 1

    await state.set_state(AdminAddState.waiting_for_suspect_dialog)
    await message.answer(
        f"🗣 **{idx}-gumondor** uchun tergov savol-javoblarini kiriting:\n\nTergovchi: ...\nGumondor: ...",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=cancel_only_keyboard(),
    )


@router.message(AdminAddState.waiting_for_suspect_info)
async def admin_suspect_info_fallback(message: Message):
    lang = user_languages.get(message.from_user.id, "uz")
    await message.answer(
        t(lang, "send_text_only") + "\n\nMasalan:\nIsmi: Alisher\nYoshi: 30\nJinsi: erkak\nOilaviy ahvoli: uylangan\nSudlanganligi: yo'q"
    )


@router.message(AdminAddState.waiting_for_suspect_dialog, F.text)
async def admin_get_suspect_dialog(message: Message, state: FSMContext):
    user_id = message.from_user.id
    if user_id not in admin_temp_data:
        await state.clear()
        return

    temp = admin_temp_data[user_id]
    lines = message.text.strip().split('\n')
    parsed_dialogs = []
    current_q = None

    for line in lines:
        line_lower = line.lower()
        if line_lower.startswith("tergovchi:"):
            current_q = line.split(":", 1)[1].strip()
        elif line_lower.startswith("gumondor:") and current_q:
            answer = line.split(":", 1)[1].strip()
            parsed_dialogs.append({"question": current_q, "answer": answer})
            current_q = None

    if not parsed_dialogs and message.text:
        parsed_dialogs.append({"question": "Savol", "answer": message.text.strip()})

    temp["current_dialogs"] = parsed_dialogs
    idx = temp["current_suspect_index"] + 1

    await state.set_state(AdminAddState.waiting_for_suspect_guilt)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔴 Ha, aybdor", callback_data="guilt_ha")],
        [InlineKeyboardButton(text="🟢 Yo'q, aybdor emas", callback_data="guilt_yoq")],
    ])
    await message.answer(f"⚖️ **{idx}-gumondor** haqiqatda aybdormi?", parse_mode=ParseMode.MARKDOWN, reply_markup=kb)


@router.message(AdminAddState.waiting_for_suspect_dialog)
async def admin_suspect_dialog_fallback(message: Message):
    lang = user_languages.get(message.from_user.id, "uz")
    await message.answer(t(lang, "send_text_only") + "\n\nMasalan:\nTergovchi: Kechasi qayerda edingiz?\nGumondor: Uyda edim.")


@router.callback_query(AdminAddState.waiting_for_suspect_guilt, F.data.startswith("guilt_"))
async def admin_set_guilt(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    is_guilty = callback.data == "guilt_ha"
    temp = admin_temp_data[user_id]

    temp["suspects"].append({
        **temp["current_info"],
        "photo": temp["current_photo"],
        "dialogs": temp["current_dialogs"],
        "is_guilty": is_guilty,
    })
    temp["current_suspect_index"] += 1
    lang = user_languages.get(user_id, "uz")

    if temp["current_suspect_index"] < temp["total_suspects"]:
        next_idx = temp["current_suspect_index"] + 1
        await state.set_state(AdminAddState.waiting_for_suspect_photo)
        await callback.message.answer(
            f"📸 Keyingi (**{next_idx}-gumondor**) rasmini yuboring:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=cancel_only_keyboard(),
        )
    else:
        proj_id = f"proj_{len(PROJECTS) + 1}"
        PROJECTS[proj_id] = {
            "title": temp["title"],
            "evidences": temp["evidences"],
            "suspects": temp["suspects"],
            "difficulty": temp.get("difficulty", "orta"),
            "points_base": temp.get("points_base", 120),
        }
        guilty_count = sum(1 for s in temp["suspects"] if s.get("is_guilty"))
        admin_temp_data.pop(user_id, None)
        await state.clear()

        warn = "" if guilty_count > 0 else "\n\n⚠️ Diqqat: hech bir gumondor aybdor deb belgilanmadi!"
        await callback.message.answer(
            "🎉 Barcha gumondorlar qo'shildi va loyiha muvaffaqiyatli saqlandi!\n\n"
            f"🎚 Qiyinlik: {DIFFICULTY_LABELS.get(PROJECTS[proj_id]['difficulty'])}" + warn,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=main_menu_keyboard(lang, user_id),
        )
    await callback.answer()


@router.message(AdminAddState.waiting_for_suspect_guilt)
async def admin_guilt_fallback(message: Message):
    await message.answer("⚠️ Iltimos, yuqoridagi tugmalardan birini tanlang.")


# ---------------------------------------------------------
# GLOBAL XATOLIKLARNI USHLASH
# ---------------------------------------------------------
@router.errors()
async def global_error_handler(event: ErrorEvent):
    logger.error(
        "Update ishlashda xatolik yuz berdi: %s\n%s",
        event.exception,
        "".join(traceback.format_exception(type(event.exception), event.exception, event.exception.__traceback__)),
    )
    return True


async def main():
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)
    logger.info("Bot is running...")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped!")
