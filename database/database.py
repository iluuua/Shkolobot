import sqlite3
from datetime import datetime
from config.config import logger

DATABASE_FILE = "database/db.sqlite"

def get_connection():
    """Возвращает подключение к базе данных с использованием sqlite3."""
    conn = sqlite3.connect(DATABASE_FILE)
    # Настраиваем вывод строк как словари для удобства доступа по именам столбцов
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Создает таблицы в базе данных, если они ещё не существуют."""
    conn = get_connection()
    cursor = conn.cursor()

    # Таблица пользователей
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER UNIQUE NOT NULL,
            username TEXT,
            registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_registered INTEGER DEFAULT 0
        )
    ''')

    # Таблица администраторов
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS admins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER UNIQUE NOT NULL,
            username TEXT,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Таблица ссылок на документы (без ограничения UNIQUE для возможности множественных записей)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS document_links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            url TEXT NOT NULL,
            description TEXT
        )
    ''')

    conn.commit()
    conn.close()

# ------------------ Функции для работы с пользователями ------------------

def add_user(telegram_id: int, username: str, is_registered: bool = False):
    """
    Добавляет нового пользователя в базу.
    Если пользователь с таким telegram_id уже существует, функция ничего не делает.
    """
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            'INSERT INTO users (telegram_id, username, is_registered) VALUES (?, ?, ?)',
            (telegram_id, username, int(is_registered))
        )
        conn.commit()
    except sqlite3.IntegrityError:
        # Пользователь уже существует
        pass
    conn.close()

def get_user(telegram_id: int):
    """Возвращает данные пользователя по telegram_id или None, если пользователь не найден."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE telegram_id = ?', (telegram_id,))
    row = cursor.fetchone()
    conn.close()
    return row

def update_user_registration(telegram_id: int, is_registered: bool):
    """Обновляет статус регистрации пользователя."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        'UPDATE users SET is_registered = ? WHERE telegram_id = ?',
        (int(is_registered), telegram_id)
    )
    conn.commit()
    conn.close()

def delete_user(telegram_id: int):
    """Удаляет пользователя из базы данных."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM users WHERE telegram_id = ?', (telegram_id,))
    conn.commit()
    conn.close()

# ------------------ Функции для работы с документами ------------------

def add_document_link(name: str, url: str, description: str = None):
    """
    Добавляет новую ссылку на документ в базу.
    Для возможности добавления нескольких ссылок для одной категории всегда выполняется INSERT.
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        'INSERT INTO document_links (name, url, description) VALUES (?, ?, ?)',
        (name, url, description)
    )
    logger.info("added")
    conn.commit()
    conn.close()


def delete_document_link(link_id: int):
    """
    Удаляет ссылку на документ по её id.
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM document_links WHERE id = ?', (link_id,))
    conn.commit()
    conn.close()


def get_document_link(name: str):
    """
    Возвращает URL документа по его имени.
    Если документ не найден, возвращает None.
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT url FROM document_links WHERE name = ?', (name,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return row["url"]
    return None

def get_document_links(name: str):
    """
    Возвращает список ссылок для заданной категории (имени).
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM document_links WHERE name = ?', (name,))
    rows = cursor.fetchall()
    conn.close()
    return rows

# ------------------ Функции для работы с администраторами ------------------

def add_admin(telegram_id: int, username: str):
    """
    Добавляет администратора в базу.
    Если администратор уже существует, функция ничего не делает.
    """
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            'INSERT INTO admins (telegram_id, username) VALUES (?, ?)',
            (telegram_id, username)
        )
        conn.commit()
    except sqlite3.IntegrityError:
        pass
    conn.close()