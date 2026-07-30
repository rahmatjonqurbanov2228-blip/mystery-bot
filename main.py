import asyncio
import logging
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
    CallbackQuery
)

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Config
BOT_TOKEN = "8678002733:AAGaG9W2Jf4ZvVA2FSPzL7rFHB9ZyxC3SpI"
ADMIN_ID = 8425304206

# Xotira va Bazalar
user_languages = {}
user_active_project = {}
admin_temp_data = {}
PROJECTS = {}

# FSM Holatlari
class AdminAddState(StatesGroup):
    waiting_for_title = State()
    waiting_for_evidence_photos = State()
    waiting_for_suspect_count = State()
    waiting_for_suspect_photo = State()
    waiting_for_suspect_info = State()
    waiting_for_suspect_dialog = State()

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
        "no_projects": "Hozircha hech qanday loyiha mavjud emas.",
        "interrogate_title": "❓ Tergovchi sifatida bermoqchi bo'lgan savol tugmasini bosing:"
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
        "no_projects": "Проектов пока нет.",
        "interrogate_title": "❓ Выберите вопрос допроса:"
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
        "no_projects": "No projects available yet.",
        "interrogate_title": "❓ Click a button to ask a question as an interrogator:"
    }
}

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
    t = TEXTS.get(lang, TEXTS["uz"])
    buttons = [
        [KeyboardButton(text=t["btn_suspects"]), KeyboardButton(text=t["btn_evidence"])],
        [KeyboardButton(text=t["btn_projects"]), KeyboardButton(text=t["btn_lang"])]
    ]
    if user_id == ADMIN_ID:
        buttons.append([KeyboardButton(text=t["btn_add_project"]), KeyboardButton(text=t["btn_delete_project"])])
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

def projects_inline_keyboard():
    kb = []
    for key, p in PROJECTS.items():
        kb.append([InlineKeyboardButton(text=f"📂 {p['title']}", callback_data=f"select_proj_{key}")])
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
    return InlineKeyboardMarkup(inline_keyboard=kb)

router = Router()

@router.message(F.text == "/start")
async def cmd_start(message: Message):
    user_languages[message.from_user.id] = "uz"
    await message.answer(TEXTS['uz']['choose_lang'], reply_markup=language_inline_keyboard())

@router.callback_query(F.data.startswith("set_lang_"))
async def process_language_choice(callback: CallbackQuery):
    lang_code = callback.data.split("_")[-1]
    user_id = callback.from_user.id
    user_languages[user_id] = lang_code
    t = TEXTS[lang_code]
    
    await callback.message.delete()
    await callback.message.answer(t["lang_selected"], reply_markup=main_menu_keyboard(lang_code, user_id))
    
    if PROJECTS:
        await callback.message.answer(t["select_project"], reply_markup=projects_inline_keyboard(), parse_mode=ParseMode.MARKDOWN)
    else:
        await callback.message.answer(t["no_projects"])
    await callback.answer()

@router.message(F.text.in_(["📁 Loyihalar bo'limi", "📁 Раздел проектов", "📁 Projects Section"]))
async def show_projects_menu(message: Message):
    lang = user_languages.get(message.from_user.id, "uz")
    if PROJECTS:
        await message.answer(TEXTS[lang]["select_project"], reply_markup=projects_inline_keyboard(), parse_mode=ParseMode.MARKDOWN)
    else:
        await message.answer(TEXTS[lang]["no_projects"])

@router.callback_query(F.data.startswith("select_proj_"))
async def choose_project(callback: CallbackQuery):
    proj_key = callback.data.replace("select_proj_", "")
    user_active_project[callback.from_user.id] = proj_key
    
    if proj_key in PROJECTS:
        proj = PROJECTS[proj_key]
        await callback.message.answer(
            f"✅ **{proj['title']}** loyihasi tanlandi!\n\n"
            "Endi pastdagi **👥 Gumondorlar va So'roq** yoki **🔍 Dalillar** tugmalarini bosing.",
            parse_mode=ParseMode.MARKDOWN
        )
    else:
        await callback.message.answer("⚠️ Bunday loyiha topilmadi.")
    await callback.answer()

@router.message(F.text.in_(["🔍 Dalillar", "🔍 Улики", "🔍 Evidence"]))
async def show_evidences(message: Message):
    proj_key = user_active_project.get(message.from_user.id)
    if not proj_key or proj_key not in PROJECTS:
        await message.answer("⚠️ Avval loyihani tanlang!", parse_mode=ParseMode.MARKDOWN)
        return
    evidences = PROJECTS[proj_key].get("evidences", [])
    if not evidences:
        await message.answer("🔍 Bu loyihada dalillar yo'q.")
        return
    for photo_id in evidences:
        await message.answer_photo(photo=photo_id)

@router.message(F.text.in_(["👥 Gumondorlar va So'roq", "👥 Подозреваемые и Допрос", "👥 Suspects & Interrogation"]))
async def show_suspects_list(message: Message):
    proj_key = user_active_project.get(message.from_user.id)
    if not proj_key or proj_key not in PROJECTS:
        await message.answer("⚠️ Avval loyihani tanlang!", parse_mode=ParseMode.MARKDOWN)
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
    await callback.message.answer(TEXTS[lang]["interrogate_title"], reply_markup=dialog_questions_keyboard(proj_key, s_idx))
    await callback.answer()

@router.callback_query(F.data.startswith("ans_"))
async def process_question_click(callback: CallbackQuery):
    parts = callback.data.split("_")
    proj_key, s_idx, d_idx = parts[1], int(parts[2]), int(parts[3])
    s = PROJECTS[proj_key]["suspects"][s_idx]
    d = s["dialogs"][d_idx]
    
    await callback.message.answer(f"🕵️‍♂️ **Tergovchi:** {d['question']}\n\n🗣 **{s['name']}:** {d['answer']}", parse_mode=ParseMode.MARKDOWN)
    await callback.answer()

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

@router.message(F.text.in_(["➕ Yangi loyiha yuklash", "➕ Добавить проект", "➕ Add Project"]))
async def admin_start_add(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    admin_temp_data[message.from_user.id] = {"evidences": [], "suspects": []}
    await state.set_state(AdminAddState.waiting_for_title)
    await message.answer("📝 Loyiha nomini kiriting:", parse_mode=ParseMode.MARKDOWN)

@router.message(AdminAddState.waiting_for_title)
async def admin_get_title(message: Message, state: FSMContext):
    admin_temp_data[message.from_user.id]["title"] = message.text
    await state.set_state(AdminAddState.waiting_for_evidence_photos)
    done_kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="✅ Rasmlarni yuklab bo'ldim")]], resize_keyboard=True)
    await message.answer("🖼 Dalil rasmlarini yuboring va tugmani bosing:", reply_markup=done_kb)

@router.message(AdminAddState.waiting_for_evidence_photos, F.photo)
async def admin_get_evidence_photo(message: Message):
    admin_temp_data[message.from_user.id]["evidences"].append(message.photo[-1].file_id)
    await message.answer("📷 Rasm saqlandi.")

@router.message(AdminAddState.waiting_for_evidence_photos, F.text == "✅ Rasmlarni yuklab bo'ldim")
async def admin_finish_evidences(message: Message, state: FSMContext):
    await state.set_state(AdminAddState.waiting_for_suspect_count)
    await message.answer("🔢 Gumondorlar sonini raqamda kiriting:", reply_markup=main_menu_keyboard("uz", message.from_user.id))

@router.message(AdminAddState.waiting_for_suspect_count)
async def admin_get_suspect_count(message: Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("⚠️ Iltimos, faqat raqam kiriting (masalan: 2):")
        return
    admin_temp_data[message.from_user.id]["total_suspects"] = int(message.text)
    admin_temp_data[message.from_user.id]["current_suspect_index"] = 0
    
    await state.set_state(AdminAddState.waiting_for_suspect_photo)
    await message.answer("📸 **1-gumondor** rasmini yuboring:", parse_mode=ParseMode.MARKDOWN)

@router.message(AdminAddState.waiting_for_suspect_photo, F.photo)
async def admin_get_suspect_photo(message: Message, state: FSMContext):
    user_id = message.from_user.id
    idx = admin_temp_data[user_id]["current_suspect_index"] + 1
    admin_temp_data[user_id]["current_photo"] = message.photo[-1].file_id
    
    await state.set_state(AdminAddState.waiting_for_suspect_info)
    await message.answer(
        f"📋 **{idx}-gumondor** ma'lumotlarini quyidagi tartibda kiriting:\n\n"
        "Ismi: ...\nYoshi: ...\nJinsi: ...\nOilaviy ahvoli: ...\nSudlanganligi: ...",
        parse_mode=ParseMode.MARKDOWN
    )

@router.message(AdminAddState.waiting_for_suspect_info)
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
        f"🗣 **{idx}-gumondor** uchun tergov savol-javoblarini kiriting:\n\n"
        "Tergovchi: ...\nGumondor: ...",
        parse_mode=ParseMode.MARKDOWN
    )

@router.message(AdminAddState.waiting_for_suspect_dialog)
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

    temp["suspects"].append({
        **temp["current_info"], 
        "photo": temp["current_photo"], 
        "dialogs": parsed_dialogs
    })
    
    temp["current_suspect_index"] += 1
    
    if temp["current_suspect_index"] < temp["total_suspects"]:
        next_idx = temp["current_suspect_index"] + 1
        await state.set_state(AdminAddState.waiting_for_suspect_photo)
        await message.answer(f"📸 Keyingi (**{next_idx}-gumondor**) rasmini yuboring:")
    else:
        proj_id = f"proj_{len(PROJECTS) + 1}"
        PROJECTS[proj_id] = {
            "title": temp["title"], 
            "evidences": temp["evidences"], 
            "suspects": temp["suspects"]
        }
        await state.clear()
        await message.answer("🎉 Barcha gumondorlar qo'shildi va loyiha muvaffaqiyatli saqlandi!", reply_markup=main_menu_keyboard("uz", user_id))

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
