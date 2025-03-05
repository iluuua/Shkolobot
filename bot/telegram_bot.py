import asyncio
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from config.config import logger, configs
from database.database import (
    add_user,
    get_user,
    update_user_registration,
    delete_user,
    add_document_link,
    get_document_link
)


# ------------------ Главное меню ------------------
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


# ------------------ Проверка доступа пользователя ------------------
def user_has_access(user_id: int) -> bool:
    """
    Возвращает True, если пользователь зарегистрирован в базе.
    Администраторы всегда имеют доступ.
    """
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
            await message.answer("Ваша заявка на регистрацию уже отправлена. Ожидайте подтверждения администратора.")
    else:
        # Создаем новую запись пользователя с is_registered = 0 (не подтвержден)
        username = message.from_user.username or ""
        add_user(user_id, username, is_registered=False)
        await message.answer("Ваша заявка на регистрацию отправлена. Ожидайте подтверждения администратора.")

        # Уведомление администратора
        admin_info = f"(@{username})" if username else "без username"
        for admin_id in configs["ADMIN_IDS"]:
            await bot.send_message(
                admin_id,
                f"Попытка регистрации: {admin_info} (ID: {user_id}).\n"
                f"Для одобрения введите: /approve {user_id}\n"
                f"Для отклонения введите: /deny {user_id}"
            )
        logger.info(f"User {user_id} {admin_info} sent a registration request.")


# ------------------ Обработчики запросов ссылок на документы ------------------
async def schedule_handler(message: Message):
    user_id = message.from_user.id
    if user_has_access(user_id):
        url = get_document_link("Расписание")
        if url:
            await message.answer(f"Вот ссылка на расписание: {url}")
        else:
            await message.answer("Ссылка на расписание не задана.")
        logger.info(f"User {user_id} received the schedule link.")
    else:
        await message.answer("Вы не зарегистрированы. Обратитесь к администратору.")


async def changes_handler(message: Message):
    user_id = message.from_user.id
    if user_has_access(user_id):
        url = get_document_link("Изменения в расписании")
        if url:
            await message.answer(f"Вот ссылка на изменения в расписании: {url}")
        else:
            await message.answer("Ссылка на изменения в расписании не задана.")
        logger.info(f"User {user_id} received the changes link.")
    else:
        await message.answer("Вы не зарегистрированы. Обратитесь к администратору.")


async def attendance_handler(message: Message):
    user_id = message.from_user.id
    if user_has_access(user_id):
        url = get_document_link("Посещаемость и питание")
        if url:
            await message.answer(f"Вот ссылка на посещаемость и питание: {url}")
        else:
            await message.answer("Ссылка на посещаемость и питание не задана.")
        logger.info(f"User {user_id} received the attendance & meals link.")
    else:
        await message.answer("Вы не зарегистрированы. Обратитесь к администратору.")


async def fgis_handler(message: Message):
    user_id = message.from_user.id
    if user_has_access(user_id):
        url = get_document_link('ФГИС "Моя школа"')
        if url:
            await message.answer(f"Вот ссылка на ФГИС 'Моя школа': {url}")
        else:
            await message.answer("Ссылка на ФГИС 'Моя школа' не задана.")
        logger.info(f"User {user_id} received the FGIS link.")
    else:
        await message.answer("Вы не зарегистрированы. Обратитесь к администратору.")


# ------------------ Админ-команды ------------------
async def approve_command(message: Message, bot: Bot):
    user_id = message.from_user.id
    if user_id not in configs["ADMIN_IDS"]:
        await message.answer("У вас нет прав для выполнения этой команды.")
        return
    parts = message.text.split()
    if len(parts) != 2 or not parts[1].isdigit():
        await message.answer("Используйте формат: /approve <user_id>")
        return
    target_id = int(parts[1])
    user = get_user(target_id)
    if user:
        update_user_registration(target_id, True)
        await message.answer(f"Пользователь {target_id} одобрен.")
        await bot.send_message(target_id, "Ваша регистрация одобрена! Теперь вы можете пользоваться ботом.")
        logger.info(f"Admin {user_id} approved user {target_id}.")
    else:
        # Если пользователя нет, создаем его с подтвержденным статусом
        add_user(target_id, "", is_registered=True)
        await message.answer(f"Пользователь {target_id} создан и одобрен.")
        try:
            await bot.send_message(target_id, "Ваша регистрация одобрена! Теперь вы можете пользоваться ботом.")
        except Exception as e:
            logger.warning(f"Could not send message to user {target_id}: {e}")
        logger.info(f"Admin {user_id} created and approved user {target_id}.")


async def deny_command(message: Message, bot: Bot):
    user_id = message.from_user.id
    if user_id not in configs["ADMIN_IDS"]:
        await message.answer("У вас нет прав для выполнения этой команды.")
        return
    parts = message.text.split()
    if len(parts) != 2 or not parts[1].isdigit():
        await message.answer("Используйте формат: /deny <user_id>")
        return
    target_id = int(parts[1])
    user = get_user(target_id)
    if user:
        delete_user(target_id)
        await message.answer(f"Пользователь {target_id} отклонён.")
        try:
            await bot.send_message(target_id, "Ваша регистрация отклонена. Обратитесь к администратору.")
        except Exception as e:
            logger.warning(f"Could not send message to user {target_id}: {e}")
        logger.info(f"Admin {user_id} denied user {target_id}.")
    else:
        await message.answer(f"Пользователь {target_id} не найден.")


# ------------------ Команда для установки ссылки на документ ------------------
async def set_link_command(message: Message, bot: Bot):
    """
    Команда для изменения ссылки на документ.
    Используйте формат:
    /setlink <doc_key> <ссылка> [описание]

    Допустимые значения doc_key:
      - schedule     – Расписание
      - changes      – Изменения в расписании
      - attendance   – Посещаемость и питание
      - fgis         – ФГИС "Моя школа"
    """
    user_id = message.from_user.id
    if user_id not in configs["ADMIN_IDS"]:
        await message.answer("У вас нет прав для выполнения этой команды.")
        return
    parts = message.text.split(maxsplit=3)
    if len(parts) < 3:
        await message.answer("Используйте формат: /setlink <doc_key> <ссылка> [описание]")
        return
    doc_key = parts[1].lower()
    url = parts[2]
    description = parts[3] if len(parts) == 4 else None
    allowed_keys = {
        "schedule": "Расписание",
        "changes": "Изменения в расписании",
        "attendance": "Посещаемость и питание",
        "fgis": 'ФГИС "Моя школа"'
    }
    if doc_key not in allowed_keys:
        await message.answer("Неверный ключ документа. Доступные ключи: schedule, changes, attendance, fgis")
        return
    doc_name = allowed_keys[doc_key]
    add_document_link(doc_name, url, description)
    await message.answer(f"Ссылка для '{doc_name}' обновлена.")
    logger.info(f"Admin {user_id} updated document link for '{doc_name}' to {url}.")


# ------------------ Обработчик запроса документа ------------------
async def document_link_handler(message: Message):
    user_id = message.from_user.id
    if not user_has_access(user_id):
        await message.answer("Вы не зарегистрированы. Обратитесь к администратору.")
        return
    doc_name = message.text.strip()
    url = get_document_link(doc_name)
    if url:
        await message.answer(f"Вот ссылка для \"{doc_name}\": {url}")
    else:
        await message.answer(f"Документ с именем \"{doc_name}\" не найден.")
    logger.info(f"User {user_id} requested document link for '{doc_name}'.")


# ------------------ Регистрация обработчиков ------------------
bot = Bot(token=configs["BOT_TOKEN"])
dp = Dispatcher()

dp.message.register(cmd_start, CommandStart())
dp.message.register(schedule_handler, F.text("Расписание"))
dp.message.register(changes_handler, F.text("Изменения в расписании"))
dp.message.register(attendance_handler, F.text("Посещаемость и питание"))
dp.message.register(fgis_handler, F.text('ФГИС "Моя школа"'))
dp.message.register(approve_command, Command("approve"))
dp.message.register(deny_command, Command("deny"))
dp.message.register(set_link_command, Command("setlink"))
# Регистрируем catch-all обработчик для запроса документов, исключая фиксированные тексты кнопок:
dp.message.register(
    document_link_handler,
    F.text().exclude(
        lambda text: text in ["Расписание", "Изменения в расписании", "Посещаемость и питание", 'ФГИС "Моя школа"'])
)
