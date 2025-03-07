import asyncio
from aiogram import Bot, Dispatcher
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    Message, ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
)
from config.config import logger, configs
from database.database import (
    add_user,
    get_user,
    update_user_registration,
    delete_user,
    add_document_link,
    get_document_link,
    get_document_links,
    delete_document_link
)

# Глобальное состояние для процесса добавления ссылок
add_link_state = {}  # admin_id -> выбранная категория (строка)

# Отображение ключей (для команд) в название категорий
CATEGORY_MAPPING = {
    "schedule": "Расписание",
    "changes": "Изменения в расписании",
    "attendance": "Посещаемость и питание",
    "fgis": 'ФГИС "Моя школа"'
}

# ------------------ Главное меню для обычных пользователей ------------------
def main_menu_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Расписание")],
            [KeyboardButton(text="Изменения в расписании")],
            [KeyboardButton(text="Посещаемость и питание")],
            [KeyboardButton(text='ФГИС "Моя школа"')]
        ],
        resize_keyboard=True
    )

# ------------------ Inline-клавиатуры ------------------

def registration_inline_keyboard(user_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Принять", callback_data=f"reg_accept_{user_id}"),
            InlineKeyboardButton(text="Отклонить", callback_data=f"reg_decline_{user_id}")
        ]
    ])

def addlink_category_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для выбора категории добавления ссылки с кнопкой 'Применить'."""
    buttons = []
    for key, cat in CATEGORY_MAPPING.items():
        buttons.append(InlineKeyboardButton(text=cat, callback_data=f"addlink_cat_{key}"))
    buttons.append(InlineKeyboardButton(text="Применить", callback_data="addlink_apply"))
    # Располагаем кнопки в столбик
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[btn] for btn in buttons])
    return keyboard

def dellink_category_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для выбора категории удаления ссылок."""
    buttons = []
    for key, cat in CATEGORY_MAPPING.items():
        buttons.append(InlineKeyboardButton(text=cat, callback_data=f"dellink_cat_{key}"))
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[btn] for btn in buttons])
    return keyboard

def dellink_links_keyboard(links: list) -> InlineKeyboardMarkup:
    """Создает клавиатуру, где каждая кнопка соответствует ссылке для удаления.
    Callback data: dellink_del_<link_id>
    """
    keyboard_buttons = []
    for i, link in enumerate(links, start=1):
        button = InlineKeyboardButton(text=str(i), callback_data=f"dellink_del_{link['id']}")
        keyboard_buttons.append([button])
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    return keyboard

# ------------------ Проверка доступа пользователя ------------------
def user_has_access(user_id: int) -> bool:
    if user_id in configs["ADMIN_IDS"]:
        return True
    user = get_user(user_id)
    if user and user["is_registered"] == 1:
        return True
    return False

# ------------------ Обработчик команды /start ------------------
async def cmd_start(message: Message, bot: Bot):
    user_id = message.from_user.id
    logger.info(f"User {user_id} called /start")
    user = get_user(user_id)
    if user:
        if user["is_registered"] == 1 or user_id in configs["ADMIN_IDS"]:
            await message.answer("Привет! Выберите действие:", reply_markup=main_menu_keyboard())
        else:
            await message.answer("Ваша заявка на регистрацию отправлена. Ожидайте подтверждения администратора.")
    else:
        username = message.from_user.username or ""
        add_user(user_id, username, is_registered=False)
        await message.answer("Ваша заявка на регистрацию отправлена. Ожидайте подтверждения администратора.")
        admin_info = f"(@{username})" if username else "без username"
        for admin_id in configs["ADMIN_IDS"]:
            inline_kb = registration_inline_keyboard(user_id)
            await bot.send_message(
                admin_id,
                f"Новый запрос на регистрацию: {admin_info} (ID: {user_id}).",
                reply_markup=inline_kb
            )
        logger.info(f"User {user_id} {admin_info} sent a registration request.")

# ------------------ Callback для подтверждения регистрации ------------------
async def registration_callback_handler(callback: CallbackQuery):
    data = callback.data
    if data.startswith("reg_accept_"):
        try:
            target_id = int(data.replace("reg_accept_", ""))
        except ValueError:
            await callback.answer("Ошибка данных.", show_alert=True)
            return
        update_user_registration(target_id, True)
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.answer("Пользователь одобрен.")
        try:
            await callback.bot.send_message(target_id, "Ваша регистрация одобрена! Теперь вы можете пользоваться ботом.")
        except Exception as e:
            logger.warning(f"Could not notify user {target_id}: {e}")
        logger.info(f"User {target_id} approved via inline button.")
    elif data.startswith("reg_decline_"):
        try:
            target_id = int(data.replace("reg_decline_", ""))
        except ValueError:
            await callback.answer("Ошибка данных.", show_alert=True)
            return
        delete_user(target_id)
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.answer("Пользователь отклонён.")
        try:
            await callback.bot.send_message(target_id, "Ваша регистрация отклонена. Обратитесь к администратору.")
        except Exception as e:
            logger.warning(f"Could not notify user {target_id}: {e}")
        logger.info(f"User {target_id} declined via inline button.")

# ------------------ Логика добавления ссылок ------------------
async def addlink_command(message: Message):
    user_id = message.from_user.id
    if user_id not in configs["ADMIN_IDS"]:
        await message.answer("У вас нет прав для выполнения этой команды.")
        return
    add_link_state[user_id] = None
    await message.answer("Выберите категорию для добавления ссылки:", reply_markup=addlink_category_keyboard())

async def addlink_callback_handler(callback: CallbackQuery):
    data = callback.data
    admin_id = callback.from_user.id
    if data.startswith("addlink_cat_"):
        key = data.replace("addlink_cat_", "")
        if key not in CATEGORY_MAPPING:
            await callback.answer("Неверная категория.", show_alert=True)
            return
        category = CATEGORY_MAPPING[key]
        add_link_state[admin_id] = category
        await callback.answer(f"Выбрана категория: {category}", show_alert=True)
        await callback.bot.send_message(admin_id, f"Пришлите ссылку для категории '{category}', или нажмите 'Применить' для завершения.")
    elif data == "addlink_apply":
        # Можно добавить небольшую задержку, чтобы убедиться, что текст ссылки обработан до сброса состояния
        await asyncio.sleep(0.5)
        if admin_id in add_link_state:
            del add_link_state[admin_id]
        await callback.answer("Добавление ссылок завершено.", show_alert=True)
        await callback.message.edit_reply_markup(reply_markup=None)

async def addlink_text_handler(message: Message):
    admin_id = message.from_user.id
    logger.info(f"addlink_text_handler: Received text from {admin_id}: {message.text}")
    if admin_id in add_link_state and add_link_state[admin_id]:
        category = add_link_state[admin_id]
        url = message.text.strip()
        add_document_link(category, url, description=None)
        await message.answer(
            f"Ссылка для категории '{category}' добавлена.\nПришлите следующую ссылку или нажмите 'Применить' для завершения."
        )
        logger.info(f"Admin {admin_id} added link for category '{category}': {url}")
    else:
        logger.info(f"Admin {admin_id} attempted to add link, but no category selected.")

# ------------------ Логика удаления ссылок ------------------
async def dellink_command(message: Message, bot: Bot):
    user_id = message.from_user.id
    if user_id not in configs["ADMIN_IDS"]:
        await message.answer("У вас нет прав для выполнения этой команды.")
        return
    await message.answer("Выберите категорию для удаления ссылок:", reply_markup=dellink_category_keyboard())

async def dellink_callback_handler(callback: CallbackQuery):
    data = callback.data
    admin_id = callback.from_user.id
    if data.startswith("dellink_cat_"):
        key = data.replace("dellink_cat_", "")
        if key not in CATEGORY_MAPPING:
            await callback.answer("Неверная категория.", show_alert=True)
            return
        category = CATEGORY_MAPPING[key]
        links = get_document_links(category)
        if not links:
            await callback.answer(f"В категории '{category}' нет ссылок.", show_alert=True)
            return
        text = f"Ссылки для категории '{category}':\n"
        for i, link in enumerate(links, start=1):
            text += f"{i}. {link['url']}\n"
        keyboard = dellink_links_keyboard(links)
        await callback.message.edit_text(text, reply_markup=keyboard)
        await callback.answer()
    elif data.startswith("dellink_del_"):
        try:
            link_id = int(data.replace("dellink_del_", ""))
        except ValueError:
            await callback.answer("Ошибка данных.", show_alert=True)
            return
        delete_document_link(link_id)
        await callback.answer("Ссылка удалена.")
        await callback.message.delete()
        await callback.bot.send_message(admin_id, "Ссылка удалена. Для удаления других ссылок снова выберите категорию.")

# ------------------ Обработчик запроса ссылок пользователем ------------------
async def send_document_links(message: Message, doc_name: str):
    """
    Вспомогательная функция для отправки ссылок по заданной категории.
    """
    user_id = message.from_user.id
    if not user_has_access(user_id):
        await message.answer("Вы не зарегистрированы. Обратитесь к администратору.")
        return
    links = get_document_links(doc_name)
    logger.info(f"send_document_links: for doc_name '{doc_name}', found {len(links)} links: {[link['url'] for link in links]}")
    if links:
        text = f"Ссылки для \"{doc_name}\":\n"
        for link in links:
            text += f"- {link['url']}\n"
        await message.answer(text)
    else:
        await message.answer(f"Документы с именем \"{doc_name}\" не найдены.")
    logger.info(f"User {user_id} requested document links for '{doc_name}'.")

async def schedule_handler(message: Message):
    await send_document_links(message, "Расписание")

async def changes_handler(message: Message):
    await send_document_links(message, "Изменения в расписании")

async def attendance_handler(message: Message):
    await send_document_links(message, "Посещаемость и питание")

async def fgis_handler(message: Message):
    await send_document_links(message, 'ФГИС "Моя школа"')

# ------------------ Команды для подтверждения/отклонения регистрации ------------------
async def approve_command(message: Message):
    admin_id = message.from_user.id
    if admin_id not in configs["ADMIN_IDS"]:
        await message.answer("У вас нет прав для выполнения этой команды.")
        return
    parts = message.text.split()
    if len(parts) != 2:
        await message.answer("Используйте: /approve <user_id>")
        return
    try:
        target_id = int(parts[1])
    except ValueError:
        await message.answer("Неверный ID пользователя.")
        return
    update_user_registration(target_id, True)
    await message.answer(f"Пользователь {target_id} одобрен.")
    try:
        await message.bot.send_message(target_id, "Ваша регистрация одобрена! Теперь вы можете пользоваться ботом.")
    except Exception as e:
        logger.warning(f"Could not notify user {target_id}: {e}")

async def deny_command(message: Message):
    admin_id = message.from_user.id
    if admin_id not in configs["ADMIN_IDS"]:
        await message.answer("У вас нет прав для выполнения этой команды.")
        return
    parts = message.text.split()
    if len(parts) != 2:
        await message.answer("Используйте: /deny <user_id>")
        return
    try:
        target_id = int(parts[1])
    except ValueError:
        await message.answer("Неверный ID пользователя.")
        return
    delete_user(target_id)
    await message.answer(f"Пользователь {target_id} отклонён.")
    try:
        await message.bot.send_message(target_id, "Ваша регистрация отклонена. Обратитесь к администратору.")
    except Exception as e:
        logger.warning(f"Could not notify user {target_id}: {e}")

# ------------------ Обработчик запроса ссылок для любых других документов ------------------
async def document_link_handler(message: Message):
    user_id = message.from_user.id
    if not user_has_access(user_id):
        await message.answer("Вы не зарегистрированы. Обратитесь к администратору.")
        return
    doc_name = message.text.strip()
    links = get_document_links(doc_name)
    if links:
        text = f"Ссылки для \"{doc_name}\":\n"
        for link in links:
            text += f"- {link['url']}\n"
        await message.answer(text)
    else:
        await message.answer(f"Документы с именем \"{doc_name}\" не найдены.")
    logger.info(f"User {user_id} requested document links for '{doc_name}'.")

# ------------------ Регистрация обработчиков ------------------
bot = Bot(token=configs["BOT_TOKEN"])
dp = Dispatcher()

# Команда /start
dp.message.register(cmd_start, CommandStart())

# Обработчики главного меню – теперь с лямбда-фильтрами для точного соответствия текста
dp.message.register(schedule_handler, lambda message: message.text.strip().lower() == "расписание")
dp.message.register(changes_handler, lambda message: message.text.strip().lower() == "изменения в расписании")
dp.message.register(attendance_handler, lambda message: message.text.strip().lower() == "посещаемость и питание")
dp.message.register(fgis_handler, lambda message: message.text.strip().lower() == 'фгис "моя школа"'.lower())

dp.message.register(approve_command, Command("approve"))
dp.message.register(deny_command, Command("deny"))
dp.message.register(addlink_command, Command("addlink"))
dp.message.register(dellink_command, Command("dellink"))

dp.callback_query.register(
    registration_callback_handler,
    lambda callback: callback.data.startswith("reg_accept_") or callback.data.startswith("reg_decline_")
)
dp.callback_query.register(
    addlink_callback_handler,
    lambda callback: callback.data.startswith("addlink_")
)
dp.callback_query.register(
    dellink_callback_handler,
    lambda callback: callback.data.startswith("dellink_")
)

# Обработчик для текстовых сообщений при добавлении ссылки
dp.message.register(addlink_text_handler, lambda message: hasattr(message, "from_user") and message.from_user.id in add_link_state)

# Общий обработчик для остальных текстовых сообщений (если текст не совпадает с главными пунктами)
dp.message.register(document_link_handler, lambda message: message.text.strip() not in [
    "Расписание", "Изменения в расписании", "Посещаемость и питание", 'ФГИС "Моя школа"'
])