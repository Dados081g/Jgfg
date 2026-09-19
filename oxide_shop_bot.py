import asyncio
import logging
import sqlite3
from datetime import datetime

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
    FSInputFile,
    KeyboardButton,
    ReplyKeyboardMarkup,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    MessageEntity,
)

logging.basicConfig(level=logging.INFO)

# ======================= НАСТРОЙКИ (заполните перед запуском) =======================

BOT_TOKEN = "8342142309:AAHnGHfqM5M0_PI1WjJkfscvRk-yZemM8Ic"          # токен от @BotFather
ADMIN_ID = 123456789                    # ваш user_id (узнать у @userinfobot)
ADMIN_PASSWORD = "maksumtop1"           # пароль входа в /admin

BANNER_PATH = "banner.png"              # баннер "ГЛАВНОЕ МЕНЮ", должен лежать рядом со скриптом

CHANNEL_LINK = "https://t.me/your_channel"      # ссылка на "Наш канал"
REVIEWS_LINK = "https://t.me/your_reviews"      # ссылка на "Отзывы"
SUPPORT_USERNAME = "@your_support"              # юзернейм поддержки

# Реквизиты СБП — впишите свои
SBP_PHONE = "+7 900 000-00-00"
SBP_BANK = "Тинькофф"
SBP_RECEIVER = "Имя Ф."

DB_PATH = "shop.db"

# ======================= ID ПРЕМИУМ-ЭМОДЗИ =======================
# Каждая константа привязана к тому месту, где стоял обычный эмодзи в вашем ТЗ.

# Экран приветствия (подпись к баннеру)
EMOJI_WELCOME_DIAMOND = "5280475364865381482"   # 💎 Добро пожаловать!
EMOJI_WELCOME_CART = "5258024802010026053"      # 🛒 Каталог — весь ассортимент
EMOJI_WELCOME_WALLET = "5886285355279193209"    # 👛 Профиль — баланс, заказы, промокоды
EMOJI_WELCOME_MIC = "5983580310292402968"       # 🎙 Поддержка — если что-то пошло не так
EMOJI_WELCOME_POINTUP = "5766994197705921104"   # ☝️ Перед покупкой ознакомьтесь...

# Кнопки главного меню
EMOJI_BTN_CATALOG = "5229064374403998351"       # кнопка "Каталог" (красная)
EMOJI_BTN_PROFILE = "5904630315946611415"       # кнопка "Мой профиль" (синяя)

# Экран "Выберите вашу игру"
EMOJI_GAME_CART = "5258024802010026053"         # 🛒 Выберите вашу игру
EMOJI_GAME_POINTUP = "5280475364865381482"      # ☝️ Все разделы магазина — на кнопках ниже

# Экран "OXIDE" (после нажатия Oxide)
EMOJI_OXIDE_GAMEPAD = "5258508428212445001"     # 🎮 OXIDE
EMOJI_OXIDE_INBOX = "5258514780469075716"       # 📥 Выберите ваше устройство
EMOJI_BTN_ANDROID_NOROOT = "5258514780469075716"  # кнопка "Android Non Root" (красная, тот же id)

# Экран "OXIDE · Android • NROOT" (после нажатия Android Non Root)
EMOJI_DEVICE_DESKTOP = "5942734685976138521"    # 🖥 OXIDE · Android • NROOT
EMOJI_DEVICE_MAGNIFIER = "5280640845660330048"  # 🔎 Ознакомьтесь с тарифами...
EMOJI_BTN_CRY4ME_1D = "5399986364634641475"     # кнопка "Cry4me 1D 160 руб" (красная)

# Экран тарифа (после нажатия Cry4me 1D 160 руб)
EMOJI_TARIFF_CLOCK = "5775896410780079073"      # 🕓 Срок: 1 день
EMOJI_TARIFF_MONEY = "5231449120635370684"      # 💸 Цена: 160 ₽
EMOJI_BTN_BUY = "5258024802010026053"           # кнопка "Купить за 160Р" (зелёная, тот же id, что и 🛒)

# После нажатия "Купить"
EMOJI_BTN_PAY_SBP = "5280973778640211229"       # кнопка "Оплатить по СБП" (зелёная)


def emoji_entity(text: str, placeholder: str, emoji_id: str) -> MessageEntity:
    """MessageEntity для показа премиум-эмодзи вместо обычного символа placeholder в тексте.
    Пользователям без Telegram Premium вместо анимированного эмодзи покажется placeholder."""
    offset = text.index(placeholder)
    return MessageEntity(
        type="custom_emoji",
        offset=offset,
        length=len(placeholder),
        custom_emoji_id=emoji_id,
    )


# ======================= БАЗА ДАННЫХ =======================

def db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = db()
    conn.execute(
        """CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            balance INTEGER NOT NULL DEFAULT 0
        )"""
    )
    conn.execute(
        """CREATE TABLE IF NOT EXISTS keys (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT NOT NULL,
            key_value TEXT NOT NULL,
            used INTEGER NOT NULL DEFAULT 0
        )"""
    )
    conn.execute(
        """CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            category TEXT NOT NULL,
            price TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            receipt_file_id TEXT,
            created_at TEXT NOT NULL
        )"""
    )
    conn.execute(
        """CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )"""
    )
    conn.commit()
    conn.close()


PRODUCT_CATEGORY = "oxide_android_nroot_cry4me_1d"
DEFAULT_PRICE = "160"


def get_price() -> str:
    conn = db()
    row = conn.execute("SELECT value FROM settings WHERE key = 'price'").fetchone()
    conn.close()
    return row["value"] if row else DEFAULT_PRICE


def set_price(value: str):
    conn = db()
    conn.execute(
        "INSERT INTO settings (key, value) VALUES ('price', ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (value,),
    )
    conn.commit()
    conn.close()


def add_keys(raw_text: str) -> int:
    lines = [ln.strip() for ln in raw_text.splitlines() if ln.strip()]
    conn = db()
    for ln in lines:
        conn.execute("INSERT INTO keys (category, key_value) VALUES (?, ?)", (PRODUCT_CATEGORY, ln))
    conn.commit()
    conn.close()
    return len(lines)


def keys_left() -> int:
    conn = db()
    n = conn.execute(
        "SELECT COUNT(*) as c FROM keys WHERE category = ? AND used = 0", (PRODUCT_CATEGORY,)
    ).fetchone()["c"]
    conn.close()
    return n


def take_key() -> str | None:
    conn = db()
    row = conn.execute(
        "SELECT id, key_value FROM keys WHERE category = ? AND used = 0 LIMIT 1", (PRODUCT_CATEGORY,)
    ).fetchone()
    if not row:
        conn.close()
        return None
    conn.execute("UPDATE keys SET used = 1 WHERE id = ?", (row["id"],))
    conn.commit()
    conn.close()
    return row["key_value"]


# ======================= КЛАВИАТУРЫ =======================

MAIN_KB = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="Каталог", icon_custom_emoji_id=EMOJI_BTN_CATALOG, style="danger"),
            KeyboardButton(text="Мой профиль", icon_custom_emoji_id=EMOJI_BTN_PROFILE, style="primary"),
        ],
        [
            KeyboardButton(text="Наш канал"),
            KeyboardButton(text="Поддержка"),
        ],
        [KeyboardButton(text="Отзывы")],
    ],
    resize_keyboard=True,
)
# "Наш канал", "Поддержка" и "Отзывы" — добавлены по образцу вашего скриншота.
# Премиум-эмодзи для них вы не присылали, поэтому иконок на них нет — пришлите
# ID, если нужно их тоже проставить.

CATALOG_KB = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Oxide", style="danger")],
        [KeyboardButton(text="⬅️ Назад")],
    ],
    resize_keyboard=True,
)
# Для кнопки "Oxide" премиум-эмодзи не присылали — оставлена без иконки.

OXIDE_KB = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Android Non Root", icon_custom_emoji_id=EMOJI_BTN_ANDROID_NOROOT, style="danger")],
        [KeyboardButton(text="⬅️ Назад")],
    ],
    resize_keyboard=True,
)


def build_tariff_kb() -> ReplyKeyboardMarkup:
    price = get_price()
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=f"Cry4me 1D {price} руб", icon_custom_emoji_id=EMOJI_BTN_CRY4ME_1D, style="danger")],
            [KeyboardButton(text="⬅️ Назад")],
        ],
        resize_keyboard=True,
    )


def build_buy_kb() -> ReplyKeyboardMarkup:
    price = get_price()
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=f"Купить за {price}Р", icon_custom_emoji_id=EMOJI_BTN_BUY, style="success")],
            [KeyboardButton(text="⬅️ Назад")],
        ],
        resize_keyboard=True,
    )


PAY_KB = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Оплатить по СБП", icon_custom_emoji_id=EMOJI_BTN_PAY_SBP, style="success")],
        [KeyboardButton(text="⬅️ Назад")],
    ],
    resize_keyboard=True,
)


def receipt_review_kb(order_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"approve_{order_id}"),
                InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_{order_id}"),
            ]
        ]
    )


# ======================= FSM (админка) =======================

class AdminAuth(StatesGroup):
    waiting_password = State()


class AdminActions(StatesGroup):
    waiting_keys = State()
    waiting_broadcast = State()
    waiting_price = State()


def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID


ADMIN_KB = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить ключи", callback_data="admin_add_keys")],
        [InlineKeyboardButton(text="📦 Заказы", callback_data="admin_orders")],
        [InlineKeyboardButton(text="💰 Изменить цену", callback_data="admin_price")],
        [InlineKeyboardButton(text="📢 Рассылка", callback_data="admin_broadcast")],
    ]
)


# ======================= РОУТЕР: ПОЛЬЗОВАТЕЛЬ =======================

router = Router()


def welcome_text_and_entities():
    text = (
        "💎 Добро пожаловать!\n\n"
        "Вы попали в магазин игровых утилит. Здесь можно пополнить баланс и купить "
        "нужный товар в пару нажатий.\n\n"
        "🛒 Каталог — весь ассортимент\n"
        "👛 Профиль — баланс, заказы, промокоды\n"
        "🎙 Поддержка — если что-то пошло не так\n\n"
        "☝️ Перед покупкой ознакомьтесь с правилами и политикой конфиденциальности "
        "— они в разделе «Профиль»."
    )
    entities = [
        emoji_entity(text, "💎", EMOJI_WELCOME_DIAMOND),
        emoji_entity(text, "🛒", EMOJI_WELCOME_CART),
        emoji_entity(text, "👛", EMOJI_WELCOME_WALLET),
        emoji_entity(text, "🎙", EMOJI_WELCOME_MIC),
        emoji_entity(text, "☝️", EMOJI_WELCOME_POINTUP),
    ]
    return text, entities


@router.message(CommandStart())
async def cmd_start(message: Message):
    conn = db()
    conn.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (message.from_user.id,))
    conn.commit()
    conn.close()

    text, entities = welcome_text_and_entities()
    photo = FSInputFile(BANNER_PATH)
    await message.answer_photo(photo=photo, caption=text, caption_entities=entities, reply_markup=MAIN_KB)


@router.message(F.text == "⬅️ Назад")
async def go_back(message: Message):
    await message.answer("Главное меню:", reply_markup=MAIN_KB)


@router.message(F.text == "Каталог")
async def catalog(message: Message):
    text = "🛒 Выберите вашу игру\n\n☝️ Все разделы магазина — на кнопках ниже."
    entities = [
        emoji_entity(text, "🛒", EMOJI_GAME_CART),
        emoji_entity(text, "☝️", EMOJI_GAME_POINTUP),
    ]
    await message.answer(text, entities=entities, reply_markup=CATALOG_KB)


@router.message(F.text == "Oxide")
async def oxide(message: Message):
    text = "🎮 OXIDE\n➖➖➖➖➖➖➖➖➖➖➖➖\n📥 Выберите ваше устройство:"
    entities = [
        emoji_entity(text, "🎮", EMOJI_OXIDE_GAMEPAD),
        emoji_entity(text, "📥", EMOJI_OXIDE_INBOX),
    ]
    await message.answer(text, entities=entities, reply_markup=OXIDE_KB)


@router.message(F.text == "Android Non Root")
async def android_non_root(message: Message):
    text = (
        "🖥 OXIDE · Android • NROOT\n"
        "➖➖➖➖➖➖➖➖➖➖➖➖\n"
        "🔎 Ознакомьтесь с тарифами — у каждого свой функционал и срок."
    )
    entities = [
        emoji_entity(text, "🖥", EMOJI_DEVICE_DESKTOP),
        emoji_entity(text, "🔎", EMOJI_DEVICE_MAGNIFIER),
    ]
    await message.answer(text, entities=entities, reply_markup=build_tariff_kb())


@router.message(F.text.startswith("Cry4me 1D"))
async def cry4me_1d_tariff(message: Message):
    price = get_price()
    text = f"OXIDE ANDROID\n➖➖➖➖➖➖➖➖➖➖➖➖\n🕓 Срок: 1 день\n💸 Цена: {price} ₽"
    entities = [
        emoji_entity(text, "🕓", EMOJI_TARIFF_CLOCK),
        emoji_entity(text, "💸", EMOJI_TARIFF_MONEY),
    ]
    await message.answer(text, entities=entities, reply_markup=build_buy_kb())


@router.message(F.text.startswith("Купить за"))
async def buy(message: Message):
    await message.answer("Нажмите кнопку ниже, чтобы получить реквизиты для оплаты:", reply_markup=PAY_KB)


@router.message(F.text == "Оплатить по СБП")
async def pay_sbp(message: Message):
    price = get_price()
    conn = db()
    conn.execute(
        "INSERT INTO orders (user_id, category, price, status, created_at) VALUES (?, ?, ?, 'pending', ?)",
        (message.from_user.id, PRODUCT_CATEGORY, price, datetime.utcnow().isoformat()),
    )
    conn.commit()
    conn.close()

    text = (
        f"Переведите {price} ₽ по СБП на номер:\n\n"
        f"📱 {SBP_PHONE}\n"
        f"🏦 Банк: {SBP_BANK}\n"
        f"👤 Получатель: {SBP_RECEIVER}\n\n"
        f"После оплаты пришлите сюда чек (фото или файл)."
    )
    await message.answer(text, reply_markup=MAIN_KB)


@router.message(F.photo | F.document)
async def receive_receipt(message: Message):
    conn = db()
    order = conn.execute(
        "SELECT * FROM orders WHERE user_id = ? AND status = 'pending' ORDER BY id DESC LIMIT 1",
        (message.from_user.id,),
    ).fetchone()
    if not order:
        conn.close()
        await message.answer("Активных заказов не найдено. Сначала оформите покупку в «Каталоге».")
        return

    file_id = message.photo[-1].file_id if message.photo else message.document.file_id
    conn.execute("UPDATE orders SET receipt_file_id = ? WHERE id = ?", (file_id, order["id"]))
    conn.commit()
    conn.close()

    await message.answer("🧾 Чек получен, ожидайте подтверждения.")

    caption = (
        f"Новый чек по заказу #{order['id']}\n"
        f"Пользователь: {message.from_user.id} (@{message.from_user.username})\n"
        f"Категория: {order['category']}\n"
        f"Сумма: {order['price']} ₽"
    )
    if message.photo:
        await message.bot.send_photo(ADMIN_ID, file_id, caption=caption, reply_markup=receipt_review_kb(order["id"]))
    else:
        await message.bot.send_document(ADMIN_ID, file_id, caption=caption, reply_markup=receipt_review_kb(order["id"]))


@router.callback_query(F.data.startswith("approve_"))
async def approve_order(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Недостаточно прав", show_alert=True)
        return

    order_id = int(callback.data.split("_", 1)[1])
    conn = db()
    order = conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
    if not order or order["status"] != "pending":
        conn.close()
        await callback.answer("Заказ уже обработан", show_alert=True)
        return

    key = take_key()
    if not key:
        conn.close()
        await callback.answer("Нет свободных ключей! Добавьте ключи в /admin.", show_alert=True)
        return

    conn.execute("UPDATE orders SET status = 'completed' WHERE id = ?", (order_id,))
    conn.commit()
    conn.close()

    await callback.bot.send_message(
        order["user_id"], f"✅ Оплата подтверждена!\n\nВаш ключ: {key}", parse_mode=None
    )
    await callback.message.edit_caption(caption=callback.message.caption + "\n\n✅ ПОДТВЕРЖДЕНО")
    await callback.answer("Ключ выдан")


@router.callback_query(F.data.startswith("reject_"))
async def reject_order(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Недостаточно прав", show_alert=True)
        return

    order_id = int(callback.data.split("_", 1)[1])
    conn = db()
    order = conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
    if order and order["status"] == "pending":
        conn.execute("UPDATE orders SET status = 'rejected' WHERE id = ?", (order_id,))
        conn.commit()
    conn.close()

    if order:
        await callback.bot.send_message(order["user_id"], "❌ Чек не подтверждён. Свяжитесь с поддержкой " + SUPPORT_USERNAME)
    await callback.message.edit_caption(caption=callback.message.caption + "\n\n❌ ОТКЛОНЕНО")
    await callback.answer("Отклонено")


@router.message(F.text == "Мой профиль")
async def profile(message: Message):
    conn = db()
    row = conn.execute("SELECT balance FROM users WHERE user_id = ?", (message.from_user.id,)).fetchone()
    completed = conn.execute(
        "SELECT COUNT(*) as c FROM orders WHERE user_id = ? AND status = 'completed'",
        (message.from_user.id,),
    ).fetchone()["c"]
    conn.close()
    balance = row["balance"] if row else 0

    text = (
        f"👤 Ваш профиль\n\n"
        f"Баланс: {balance} ₽\n"
        f"Куплено товаров: {completed}\n\n"
        f"Правила и политика конфиденциальности: свяжитесь с поддержкой {SUPPORT_USERNAME}"
    )
    await message.answer(text)


@router.message(F.text == "Наш канал")
async def our_channel(message: Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Открыть канал", url=CHANNEL_LINK)]])
    await message.answer("Наш канал:", reply_markup=kb)


@router.message(F.text == "Поддержка")
async def support(message: Message):
    await message.answer(f"Если у вас возникла проблема — напишите нам {SUPPORT_USERNAME}")


@router.message(F.text == "Отзывы")
async def reviews(message: Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Открыть отзывы", url=REVIEWS_LINK)]])
    await message.answer("Отзывы наших покупателей:", reply_markup=kb)


# ======================= РОУТЕР: АДМИНКА =======================

admin_router = Router()


@admin_router.message(Command("admin"))
async def cmd_admin(message: Message, state: FSMContext):
    await message.answer("Введите пароль:")
    await state.set_state(AdminAuth.waiting_password)


@admin_router.message(AdminAuth.waiting_password)
async def check_password(message: Message, state: FSMContext):
    if message.text == ADMIN_PASSWORD:
        await state.clear()
        await message.answer("Админ-панель:", reply_markup=ADMIN_KB)
    else:
        await message.answer("Неверный пароль.")


@admin_router.callback_query(F.data == "admin_add_keys")
async def admin_add_keys_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("Недостаточно прав", show_alert=True)
        return
    await callback.message.answer(f"Пришлите ключи для «{PRODUCT_CATEGORY}» — по одному в строке.")
    await state.set_state(AdminActions.waiting_keys)
    await callback.answer()


@admin_router.message(AdminActions.waiting_keys)
async def admin_add_keys_finish(message: Message, state: FSMContext):
    n = add_keys(message.text)
    await state.clear()
    await message.answer(f"Добавлено ключей: {n}. Осталось свободных: {keys_left()}.")


@admin_router.callback_query(F.data == "admin_orders")
async def admin_orders(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Недостаточно прав", show_alert=True)
        return
    conn = db()
    rows = conn.execute(
        "SELECT * FROM orders ORDER BY id DESC LIMIT 20"
    ).fetchall()
    conn.close()
    if not rows:
        await callback.message.answer("Заказов пока нет.")
    else:
        lines = [f"#{r['id']} | {r['user_id']} | {r['price']} ₽ | {r['status']}" for r in rows]
        await callback.message.answer("Последние заказы:\n\n" + "\n".join(lines))
    await callback.answer()


@admin_router.callback_query(F.data == "admin_price")
async def admin_price_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("Недостаточно прав", show_alert=True)
        return
    await callback.message.answer(f"Текущая цена: {get_price()} ₽. Пришлите новую цену (число).")
    await state.set_state(AdminActions.waiting_price)
    await callback.answer()


@admin_router.message(AdminActions.waiting_price)
async def admin_price_finish(message: Message, state: FSMContext):
    set_price(message.text.strip())
    await state.clear()
    await message.answer(f"Цена обновлена: {get_price()} ₽")


@admin_router.callback_query(F.data == "admin_broadcast")
async def admin_broadcast_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("Недостаточно прав", show_alert=True)
        return
    await callback.message.answer("Пришлите текст объявления для рассылки всем пользователям.")
    await state.set_state(AdminActions.waiting_broadcast)
    await callback.answer()


@admin_router.message(AdminActions.waiting_broadcast)
async def admin_broadcast_finish(message: Message, state: FSMContext):
    conn = db()
    user_ids = [r["user_id"] for r in conn.execute("SELECT user_id FROM users").fetchall()]
    conn.close()
    await state.clear()

    sent, failed = 0, 0
    for uid in user_ids:
        try:
            await message.bot.send_message(uid, message.text, parse_mode=None)
            sent += 1
        except Exception:
            failed += 1
        await asyncio.sleep(0.05)

    await message.answer(f"Рассылка завершена. Отправлено: {sent}, ошибок: {failed}.")


# ======================= ЗАПУСК =======================

async def main():
    init_db()
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(admin_router)
    dp.include_router(router)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
