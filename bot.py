import asyncio
import logging
import os
from pathlib import Path

from aiogram import Bot, Dispatcher, F, Router
from aiogram.enums import ChatType, MessageEntityType
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import SimpleEventIsolation
from aiogram.types import BufferedInputFile, Message
from dotenv import dotenv_values

from database import add_task, export_tasks_csv, get_tasks, init_db

router = Router()
router.message.filter(F.chat.type == ChatType.PRIVATE, F.from_user)


class AddTask(StatesGroup):
    waiting_for_text = State()


# Приветствует пользователя, показывает команды и сбрасывает ожидание текста.
@router.message(CommandStart())
async def start(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(
        "Привет! Я помогу сохранить твои задачи.\n\n"
        "/add — добавить задачу\n"
        "/list — показать все твои задачи\n"
        "/list_csv — скачать задачи в CSV"
    )


# Добавляет задачу из аргумента команды или запрашивает её текст.
@router.message(Command("add"))
async def begin_add(message: Message, command: CommandObject, state: FSMContext) -> None:
    task_text = (command.args or "").strip()
    if not task_text:
        await state.set_state(AddTask.waiting_for_text)
        await message.answer("Отправь текст задачи следующим сообщением.")
        return

    await save_task(message, state, task_text)


# Записывает задачу в SQLite и подтверждает сохранение.
async def save_task(message: Message, state: FSMContext, task_text: str) -> None:
    task_id = await asyncio.to_thread(add_task, message.from_user.id, task_text)
    await state.clear()
    await message.answer(f"Задача №{task_id} добавлена.")


# Показывает задачи владельца, разбивая длинный список на сообщения.
@router.message(Command("list"))
async def list_tasks(message: Message) -> None:
    tasks = await asyncio.to_thread(get_tasks, message.from_user.id)
    if not tasks:
        await message.answer("У тебя пока нет задач. Чтобы добавить задачу, отправь /add.")
        return

    listing = "\n\n".join(
        f"№{task_id} · {created_at} UTC\n{task_text}"
        for task_id, task_text, _, created_at in tasks
    )
    # 2000 символов Python занимают не более 4000 единиц UTF-16.
    for offset in range(0, len(listing), 2000):
        page = listing[offset : offset + 2000]
        if page.strip():
            await message.answer(page)


# Отправляет задачи владельца файлом CSV прямо в чат.
@router.message(Command("list_csv"))
async def list_csv(message: Message) -> None:
    content = await asyncio.to_thread(export_tasks_csv, message.from_user.id)
    await message.answer_document(BufferedInputFile(content, filename="tasks.csv"))


# Принимает текст задачи после /add и сохраняет его.
@router.message(AddTask.waiting_for_text)
async def receive_task(message: Message, state: FSMContext) -> None:
    task_text = (message.text or "").strip()
    is_command = any(
        entity.type == MessageEntityType.BOT_COMMAND and entity.offset == 0
        for entity in message.entities or ()
    )
    if not task_text or is_command:
        await message.answer("Отправь непустой текст задачи.")
        return

    await save_task(message, state, task_text)


# Проверяет настройки, подготавливает SQLite и запускает опрос Telegram.
async def main() -> None:
    settings = dotenv_values(Path(__file__).resolve().with_name(".env"), encoding="utf-8-sig")
    token = (settings.get("BOT_TOKEN") or "").strip()
    token = token or os.environ.get("BOT_TOKEN", "").strip()
    if not token:
        raise SystemExit("Впиши токен Telegram-бота в строку BOT_TOKEN= файла .env.")

    await asyncio.to_thread(init_db)
    dispatcher = Dispatcher(events_isolation=SimpleEventIsolation())
    dispatcher.include_router(router)
    await dispatcher.start_polling(Bot(token))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
