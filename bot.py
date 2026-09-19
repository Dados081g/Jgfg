import asyncio
import logging
import os
from pathlib import Path

from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import CommandStart
from aiogram.types import (
    CallbackQuery,
    FSInputFile,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputMediaPhoto,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
)

# ───────────────────────── НАСТРОЙКИ ─────────────────────────
BOT_TOKEN = os.getenv("BOT_TOKEN", "PASTE_YOUR_TOKEN_HERE")

BASE_DIR = Path(__file__).resolve().parent / "banners"
BANNERS = {
    "main": BASE_DIR / "main.png",        # Главное меню
    "games": BASE_DIR / "games.png",      # Выбор игры
    "devices": BASE_DIR / "devices.png",  # Выбор устройства
}

# Цвета кнопок: danger = красная, success = зелёная, primary = синяя
RED, GREEN, BLUE = "danger", "success", "primary"


def em(emoji_id: str, fallback: str) -> str:
    """Премиум-эмодзи в тексте сообщения."""
    return f'<tg-emoji emoji-id="{emoji_id}">{fallback}</tg-emoji>'


# ───────────────────────── ТЕКСТЫ ─────────────────────────
LINE = "➖➖➖➖➖➖➖➖➖➖➖➖"

WELCOME_TEXT = (
    f"{em('5280475364865381482', '💎')} Добро пожаловать!\n\n"
    "Вы попали в магазин игровых утилит. Здесь можно пополнить баланс "
    "и купить нужный товар в пару нажатий.\n\n"
    f"{em('5258024802010026053', '🛒')} Каталог — весь ассортимент\n"
    f"{em('5886285355279193209', '👛')} Профиль — баланс, заказы, промокоды\n"
    f"{em('5983580310292402968', '🎙')} Поддержка — если что-то пошло не так\n\n"
    f"{em('5766994197705921104', '☝️')} Перед покупкой ознакомьтесь с правилами "
    "и политикой конфиденциальности — они в разделе «Профиль»."
)

CATALOG_TEXT = (
    f"{em('5258024802010026053', '🛒')} Выберите вашу игру\n\n"
    f"{em('5280475364865381482', '☝️')} Все разделы магазина — на кнопках ниже."
)

DEVICES_TEXT = (
    f"{em('5258508428212445001', '🎮')} OXIDE\n"
    f"{LINE}\n"
    f"{em('5258514780469075716', '📥')} Выберите ваше устройство:"
)

TARIFFS_TEXT = (
    f"{em('5942734685976138521', '🖥')} OXIDE · Android • NROOT\n"
    f"{LINE}\n"
    f"{em('5280640845660330048', '🔎')} Ознакомьтесь с тарифами — "
    "у каждого свой функционал и срок."
)

CARD_TEXT = (
    "OXIDE ANDROID\n"
    f"{LINE}\n"
    f"{em('5775896410780079073', '🕓')} Срок: 1 день\n"
    f"{em('5231449120635370684', '💸')} Цена: 160 ₽"
)

PROFILE_TEXT = (
    f"{em('5886285355279193209', '👛')} Профиль\n\n"
    "ID: {user_id}\n"
    "Баланс: 0 ₽\n"
    "Заказов: 0\n\n"
    "Здесь же будут промокоды, правила и политика конфиденциальности."
)


# ───────────────────────── КЛАВИАТУРЫ ─────────────────────────
# Меню кнопок под сообщением (2 кнопки)
MAIN_KB = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(
                text="Каталог",
                icon_custom_emoji_id="5229064374403998351",
                style=RED,
            ),
            KeyboardButton(
                text="Мой профиль",
                icon_custom_emoji_id="5904630315946611415",
                style=BLUE,
            ),
        ]
    ],
    resize_keyboard=True,
)


def ib(text: str, data: str, emoji: str | None = None, style: str | None = None):
    return InlineKeyboardButton(
        text=text,
        callback_data=data,
        icon_custom_emoji_id=emoji,
        style=style,
    )


def kb(*rows) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[b] for b in rows])


CATALOG_KB = kb(ib("Oxide", "go:devices", style=RED))

DEVICES_KB = kb(
    ib("Android Non Root", "go:tariffs", emoji="5258514780469075716", style=RED),
    ib("Назад", "go:catalog"),
)

TARIFFS_KB = kb(
    ib("Cry4me 1D 160 руб", "go:card", emoji="5399986364634641475", style=RED),
    ib("Назад", "go:devices"),
)

CARD_KB = kb(
    ib("Купить за 160Р", "go:pay", emoji="5258024802010026053", style=GREEN),
    ib("Назад", "go:tariffs"),
)

PAY_KB = kb(
    ib("Оплатить по СБП", "pay:sbp", emoji="5280973778640211229", style=GREEN),
    ib("Назад", "go:card"),
)

# экран → (баннер, текст, клавиатура)
SCREENS = {
    "catalog": ("games", CATALOG_TEXT, CATALOG_KB),
    "devices": ("devices", DEVICES_TEXT, DEVICES_KB),
    "tariffs": ("devices", TARIFFS_TEXT, TARIFFS_KB),
    "card": ("devices", CARD_TEXT, CARD_KB),
    "pay": ("devices", CARD_TEXT, PAY_KB),
}

# ───────────────────────── ЛОГИКА ─────────────────────────
router = Router()
_file_ids: dict[str, str] = {}  # кэш file_id, чтобы не загружать баннеры каждый раз


def banner_input(name: str):
    return _file_ids.get(name) or FSInputFile(BANNERS[name])


def remember(name: str, msg) -> None:
    if isinstance(msg, Message) and msg.photo:
        _file_ids[name] = msg.photo[-1].file_id


@router.message(CommandStart())
async def cmd_start(message: Message):
    res = await message.answer_photo(
        photo=banner_input("main"),
        caption=WELCOME_TEXT,
        reply_markup=MAIN_KB,
    )
    remember("main", res)


@router.message(F.text == "Каталог")
async def open_catalog(message: Message):
    banner, text, markup = SCREENS["catalog"]
    res = await message.answer_photo(
        photo=banner_input(banner), caption=text, reply_markup=markup
    )
    remember(banner, res)


@router.message(F.text == "Мой профиль")
async def open_profile(message: Message):
    await message.answer(PROFILE_TEXT.format(user_id=message.from_user.id))


@router.callback_query(F.data.startswith("go:"))
async def navigate(cb: CallbackQuery):
    screen = cb.data.split(":", 1)[1]
    banner, text, markup = SCREENS[screen]
    try:
        res = await cb.message.edit_media(
            media=InputMediaPhoto(
                media=banner_input(banner),
                caption=text,
                parse_mode=ParseMode.HTML,
            ),
            reply_markup=markup,
        )
        remember(banner, res)
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            raise
    await cb.answer()


@router.callback_query(F.data == "pay:sbp")
async def pay_sbp(cb: CallbackQuery):
    # TODO: здесь создать платёж по СБП в вашей платёжной системе
    # и отправить пользователю ссылку/QR.
    await cb.answer("Оплата по СБП пока не подключена.", show_alert=True)


async def main():
    logging.basicConfig(level=logging.INFO)

    missing = [str(p) for p in BANNERS.values() if not p.is_file()]
    if missing:
        raise SystemExit(
            "Не найдены файлы баннеров:\n  " + "\n  ".join(missing) +
            "\nЗагрузите папку banners рядом с bot.py (main.png, games.png, devices.png)."
        )

    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()
    dp.include_router(router)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
