import json
import subprocess
from pathlib import Path
from datetime import datetime

from telegram import (
    Update,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)

from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    ConversationHandler,
    filters,
)


# =========================================================
# ПУТИ
# =========================================================

BASE_DIR = Path(__file__).resolve().parent

CONFIG_FILE = BASE_DIR / "schedule_config.json"
SCHEDULE_FILE = BASE_DIR / "daily_schedule.json"
TOKEN_FILE = BASE_DIR / ".telegram_token"


# =========================================================
# СОСТОЯНИЯ ДИАЛОГА
# =========================================================

ASK_COUNT, ASK_START, ASK_END, CONFIRM = range(4)


# =========================================================
# ПРОЦЕСС RUNNER
# =========================================================

runner_process = None


# =========================================================
# КЛАВИАТУРЫ
# =========================================================

MAIN_KEYBOARD = ReplyKeyboardMarkup(
    [
        ["🆕 Новая смена"],
        ["📊 Статус"],
        ["▶️ Запустить", "⏹ Остановить"],
        ["❓ Помощь"],
    ],
    resize_keyboard=True,
)


CONFIRM_KEYBOARD = ReplyKeyboardMarkup(
    [
        ["✅ Создать", "❌ Отмена"],
    ],
    resize_keyboard=True,
)


CANCEL_KEYBOARD = ReplyKeyboardMarkup(
    [
        ["❌ Отмена"],
    ],
    resize_keyboard=True,
)


# =========================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# =========================================================

def load_token():
    if not TOKEN_FILE.exists():
        raise FileNotFoundError(
            "Не найден файл .telegram_token"
        )

    token = TOKEN_FILE.read_text(
        encoding="utf-8"
    ).strip()

    if not token:
        raise RuntimeError(
            "Файл .telegram_token пустой"
        )

    return token


def load_json(path):
    with open(
        path,
        "r",
        encoding="utf-8"
    ) as file:
        return json.load(file)


def save_json(path, data):
    with open(
        path,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            data,
            file,
            ensure_ascii=False,
            indent=2
        )


def valid_time(value):
    try:
        datetime.strptime(
            value,
            "%H:%M"
        )

        return True

    except ValueError:
        return False


# =========================================================
# /START
# =========================================================

async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    text = (
        "Привет 👋\n\n"
        "Я помогаю управлять расписанием.\n\n"
        "Для начала нажми:\n"
        "🆕 Новая смена\n\n"
        "Дальше я сам задам все вопросы."
    )

    await update.message.reply_text(
        text,
        reply_markup=MAIN_KEYBOARD
    )


# =========================================================
# НОВАЯ СМЕНА
# =========================================================

async def new_shift(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    context.user_data.clear()

    await update.message.reply_text(
        "🆕 Создаём новую смену.\n\n"
        "Сколько запусков нужно сделать?\n\n"
        "Например:\n"
        "43",
        reply_markup=CANCEL_KEYBOARD
    )

    return ASK_COUNT


# =========================================================
# ВОПРОС 1 — КОЛИЧЕСТВО
# =========================================================

async def ask_count(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    text = update.message.text.strip()

    if text == "❌ Отмена":
        return await cancel_shift(
            update,
            context
        )

    try:
        count = int(text)

        if count <= 0:
            raise ValueError

    except ValueError:

        await update.message.reply_text(
            "Нужно написать обычное число.\n\n"
            "Например:\n"
            "43"
        )

        return ASK_COUNT

    context.user_data["count"] = count

    await update.message.reply_text(
        f"Количество: {count} ✅\n\n"
        "Во сколько начать?\n\n"
        "Напиши время в формате:\n"
        "19:00",
        reply_markup=CANCEL_KEYBOARD
    )

    return ASK_START


# =========================================================
# ВОПРОС 2 — ВРЕМЯ НАЧАЛА
# =========================================================

async def ask_start_time(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    text = update.message.text.strip()

    if text == "❌ Отмена":
        return await cancel_shift(
            update,
            context
        )

    if not valid_time(text):

        await update.message.reply_text(
            "Не понял время 😕\n\n"
            "Напиши так:\n"
            "19:00\n\n"
            "или:\n"
            "00:30"
        )

        return ASK_START

    context.user_data["start_time"] = text

    await update.message.reply_text(
        f"Начало: {text} ✅\n\n"
        "Во сколько закончить?\n\n"
        "Например:\n"
        "06:00",
        reply_markup=CANCEL_KEYBOARD
    )

    return ASK_END


# =========================================================
# ВОПРОС 3 — ВРЕМЯ ОКОНЧАНИЯ
# =========================================================

async def ask_end_time(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    text = update.message.text.strip()

    if text == "❌ Отмена":
        return await cancel_shift(
            update,
            context
        )

    if not valid_time(text):

        await update.message.reply_text(
            "Не понял время 😕\n\n"
            "Напиши, например:\n"
            "06:00"
        )

        return ASK_END

    context.user_data["end_time"] = text

    count = context.user_data["count"]
    start_time = context.user_data["start_time"]
    end_time = context.user_data["end_time"]

    message = (
        "Проверь настройки 👇\n\n"
        f"Количество: {count}\n"
        f"Начало: {start_time}\n"
        f"Окончание: {end_time}\n\n"
        "Всё правильно?"
    )

    await update.message.reply_text(
        message,
        reply_markup=CONFIRM_KEYBOARD
    )

    return CONFIRM


# =========================================================
# ПОДТВЕРЖДЕНИЕ
# =========================================================

async def confirm_shift(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    text = update.message.text.strip()

    if text == "❌ Отмена":

        return await cancel_shift(
            update,
            context
        )

    if text != "✅ Создать":

        await update.message.reply_text(
            "Нажми:\n"
            "✅ Создать\n"
            "или\n"
            "❌ Отмена"
        )

        return CONFIRM

    count = context.user_data["count"]
    start_time = context.user_data["start_time"]
    end_time = context.user_data["end_time"]

    try:
        config = load_json(
            CONFIG_FILE
        )

        config["responses_per_day"] = count
        config["start_time"] = start_time
        config["end_time"] = end_time

        save_json(
            CONFIG_FILE,
            config
        )

    except Exception as error:

        await update.message.reply_text(
            f"❌ Не удалось сохранить настройки:\n\n{error}",
            reply_markup=MAIN_KEYBOARD
        )

        return ConversationHandler.END

    await update.message.reply_text(
        "Настройки сохранены ✅\n\n"
        "Создаю расписание...",
        reply_markup=MAIN_KEYBOARD
    )

    # Запускаем scheduler.py

    result = subprocess.run(
        ["python", "scheduler.py"],
        cwd=BASE_DIR,
        capture_output=True,
        text=True
    )

    if result.returncode == 0:

        await update.message.reply_text(
            "✅ Смена создана.\n\n"
            f"Запусков: {count}\n"
            f"С {start_time} до {end_time}\n\n"
            "Теперь можно посмотреть 📊 Статус."
        )

    else:

        error_text = (
            result.stderr
            or result.stdout
            or "Неизвестная ошибка"
        )

        await update.message.reply_text(
            "❌ Не удалось создать расписание.\n\n"
            + error_text[-2000:]
        )

    context.user_data.clear()

    return ConversationHandler.END


# =========================================================
# ОТМЕНА
# =========================================================

async def cancel_shift(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    context.user_data.clear()

    await update.message.reply_text(
        "Создание смены отменено.",
        reply_markup=MAIN_KEYBOARD
    )

    return ConversationHandler.END


# =========================================================
# СТАТУС
# =========================================================

async def status(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not SCHEDULE_FILE.exists():

        await update.message.reply_text(
            "Расписание пока не создано."
        )

        return

    try:

        data = load_json(
            SCHEDULE_FILE
        )

    except Exception as error:

        await update.message.reply_text(
            f"Не удалось прочитать расписание:\n{error}"
        )

        return

    planned = data.get(
        "responses_planned",
        0
    )

    completed_list = data.get(
        "completed",
        []
    )

    skipped_list = data.get(
        "skipped",
        []
    )

    completed = len(
        completed_list
    )

    skipped = len(
        skipped_list
    )

    remaining = max(
        planned
        - completed
        - skipped,
        0
    )

    times = data.get(
        "times",
        []
    )

    completed_times = set(
        completed_list
    )

    skipped_times = set(
        skipped_list
    )

    next_time = None

    now = datetime.now().astimezone()

    for item in times:

        if (
            item not in completed_times
            and item not in skipped_times
        ):

            try:

                dt = datetime.fromisoformat(
                    item
                )

                if dt >= now:

                    next_time = dt
                    break

            except Exception:

                next_time = item
                break

    if isinstance(
        next_time,
        datetime
    ):

        next_text = next_time.strftime(
            "%d.%m %H:%M"
        )

    elif next_time:

        next_text = str(
            next_time
        )

    else:

        next_text = "нет"

    global runner_process

    if (
        runner_process
        and runner_process.poll() is None
    ):

        runner_status = "🟢 работает"

    else:

        runner_status = "🔴 остановлен"

    # Прогресс в процентах

    if planned > 0:

        percent = round(
            completed / planned * 100
        )

    else:

        percent = 0

    text = (
        "📊 Статус смены\n\n"
        f"Запланировано: {planned}\n"
        f"Выполнено: {completed}\n"
        f"Пропущено: {skipped}\n"
        f"Осталось: {remaining}\n\n"
        f"Прогресс: {percent}%\n\n"
        f"Следующий запуск:\n"
        f"{next_text}\n\n"
        f"Runner: {runner_status}"
    )

    await update.message.reply_text(
        text,
        reply_markup=MAIN_KEYBOARD
    )


# =========================================================
# ЗАПУСК RUNNER
# =========================================================

async def run_runner(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    global runner_process

    if (
        runner_process
        and runner_process.poll() is None
    ):

        await update.message.reply_text(
            "⚠️ Выполнение уже запущено."
        )

        return

    if not SCHEDULE_FILE.exists():

        await update.message.reply_text(
            "Сначала создай новую смену."
        )

        return

    runner_process = subprocess.Popen(
        ["python", "runner.py"],
        cwd=BASE_DIR
    )

    await update.message.reply_text(
        "▶️ Выполнение запущено.\n\n"
        "Пока проект работает локально, "
        "Mac должен оставаться включённым.",
        reply_markup=MAIN_KEYBOARD
    )


# =========================================================
# ОСТАНОВКА RUNNER
# =========================================================

async def stop_runner(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    global runner_process

    if (
        not runner_process
        or runner_process.poll() is not None
    ):

        await update.message.reply_text(
            "Сейчас ничего не запущено."
        )

        return

    runner_process.terminate()

    try:

        runner_process.wait(
            timeout=10
        )

    except subprocess.TimeoutExpired:

        runner_process.kill()

    runner_process = None

    await update.message.reply_text(
        "⏹ Выполнение остановлено.",
        reply_markup=MAIN_KEYBOARD
    )


# =========================================================
# ПОМОЩЬ
# =========================================================

async def help_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    text = (
        "Как пользоваться ботом:\n\n"

        "1️⃣ Нажми «🆕 Новая смена»\n"
        "2️⃣ Укажи количество\n"
        "3️⃣ Укажи время начала\n"
        "4️⃣ Укажи время окончания\n"
        "5️⃣ Подтверди\n\n"

        "После этого нажми:\n"
        "▶️ Запустить\n\n"

        "Кнопка 📊 Статус показывает "
        "текущий прогресс."
    )

    await update.message.reply_text(
        text,
        reply_markup=MAIN_KEYBOARD
    )


# =========================================================
# ОБРАБОТКА ГЛАВНЫХ КНОПОК
# =========================================================

async def handle_main_buttons(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    text = update.message.text.strip()

    if text == "📊 Статус":

        await status(
            update,
            context
        )

    elif text == "▶️ Запустить":

        await run_runner(
            update,
            context
        )

    elif text == "⏹ Остановить":

        await stop_runner(
            update,
            context
        )

    elif text == "❓ Помощь":

        await help_command(
            update,
            context
        )

    else:

        await update.message.reply_text(
            "Выбери действие кнопками ниже.",
            reply_markup=MAIN_KEYBOARD
        )


# =========================================================
# ОБРАБОТЧИК ОШИБОК
# =========================================================

async def error_handler(
    update: object,
    context: ContextTypes.DEFAULT_TYPE
):

    print(
        "Ошибка Telegram-бота:",
        context.error
    )


# =========================================================
# MAIN
# =========================================================

def main():

    token = load_token()

    app = (
        Application
        .builder()
        .token(token)
        .build()
    )

    # Пошаговый диалог создания смены

    conversation_handler = ConversationHandler(

        entry_points=[
            MessageHandler(
                filters.Regex(
                    "^🆕 Новая смена$"
                ),
                new_shift
            )
        ],

        states={

            ASK_COUNT: [
                MessageHandler(
                    filters.TEXT
                    & ~filters.COMMAND,
                    ask_count
                )
            ],

            ASK_START: [
                MessageHandler(
                    filters.TEXT
                    & ~filters.COMMAND,
                    ask_start_time
                )
            ],

            ASK_END: [
                MessageHandler(
                    filters.TEXT
                    & ~filters.COMMAND,
                    ask_end_time
                )
            ],

            CONFIRM: [
                MessageHandler(
                    filters.TEXT
                    & ~filters.COMMAND,
                    confirm_shift
                )
            ],
        },

        fallbacks=[
            CommandHandler(
                "cancel",
                cancel_shift
            )
        ],
    )

    app.add_handler(
        CommandHandler(
            "start",
            start
        )
    )

    app.add_handler(
        CommandHandler(
            "help",
            help_command
        )
    )

    app.add_handler(
        CommandHandler(
            "status",
            status
        )
    )

    app.add_handler(
        conversation_handler
    )

    # Основные кнопки должны идти
    # после ConversationHandler

    app.add_handler(
        MessageHandler(
            filters.TEXT
            & ~filters.COMMAND,
            handle_main_buttons
        )
    )

    app.add_error_handler(
        error_handler
    )

    print(
        "Telegram control bot запущен..."
    )

    app.run_polling()


if __name__ == "__main__":
    main()