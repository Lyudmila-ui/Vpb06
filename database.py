import csv
import io
import sqlite3
from contextlib import closing
from pathlib import Path

DB_PATH = Path(__file__).resolve().with_name("tasks.sqlite3")


# Создаёт таблицу задач и индекс для поиска задач пользователя.
def init_db() -> None:
    with closing(sqlite3.connect(DB_PATH)) as connection, connection:
        connection.executescript("""
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY,
                text TEXT NOT NULL,
                user INTEGER NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_tasks_user_id ON tasks (user, id);
        """)


# Сохраняет задачу владельца и возвращает её номер.
def add_task(user_id: int, task_text: str) -> int:
    with closing(sqlite3.connect(DB_PATH)) as connection, connection:
        cursor = connection.execute(
            "INSERT INTO tasks (text, user) VALUES (?, ?)", (task_text, user_id)
        )
        return cursor.lastrowid


# Возвращает все задачи пользователя в порядке добавления.
def get_tasks(user_id: int) -> list[tuple[int, str, int, str]]:
    with closing(sqlite3.connect(DB_PATH)) as connection:
        return connection.execute(
            "SELECT id, text, user, created_at FROM tasks WHERE user = ? ORDER BY id",
            (user_id,),
        ).fetchall()


# Формирует CSV в памяти. BOM помогает Excel распознать кириллицу.
def export_tasks_csv(user_id: int) -> bytes:
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(("id", "text", "user", "created_at"))
    writer.writerows(get_tasks(user_id))
    return output.getvalue().encode("utf-8-sig")
