import asyncio
import json
import os
import signal
import subprocess
import sys

from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo


from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)


from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)


from bot_database import (
    init_db,
    register_user,
    get_user,
    list_users,
    get_admins,
    approve_user,
    reject_user,
    set_user_role,
    create_shift,
    get_active_shift,
    get_shift,
    update_shift_status,
    update_shift_progress,
    list_shifts,
    get_last_shift,
    get_setting,
    set_setting,
)


from bot_keyboards import (
    main_keyboard,
    CANCEL_KEYBOARD,
    CONFIRM_KEYBOARD,
    finish_keyboard,
    access_keyboard,
    role_keyboard,
)


# =========================================================
# PATHS
# =========================================================

BASE_DIR = (
    Path(__file__)
    .resolve()
    .parent
)

CONFIG_FILE = (
    BASE_DIR
    / "schedule_config.json"
)

SCHEDULE_FILE = (
    BASE_DIR
    / "daily_schedule.json"
)

TOKEN_FILE = (
    BASE_DIR
    / ".telegram_token"
)

RUNNER_LOG = (
    BASE_DIR
    / "runner.log"
)

PID_FILE = (
    BASE_DIR
    / ".runner_pid"
)


# =========================================================
# CONFIG
# =========================================================

TIMEZONE_NAME = (
    "Europe/Moscow"
)

TIMEZONE = ZoneInfo(
    TIMEZONE_NAME
)


# =========================================================
# CONVERSATION
# =========================================================

ASK_COUNT = 0
ASK_START = 1
ASK_END = 2
CONFIRM = 3


# =========================================================
# JSON
# =========================================================

def load_json(
    path
):
    with open(
        path,
        "r",
        encoding="utf-8"
    ) as file:

        return json.load(
            file
        )


def save_json(
    path,
    data
):
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


# =========================================================
# USERS
# =========================================================

def current_user(
    update
):
    return get_user(
        update.effective_user.id
    )


def user_can_manage(
    user
):
    return (
        user
        and user["approved"]
        and user["role"]
        in (
            "admin",
            "manager"
        )
    )


async def require_access(
    update
):
    user = current_user(
        update
    )

    if (
        not user
        or not user["approved"]
    ):

        await update.effective_message.reply_text(
            "⛔ У вас пока нет доступа."
        )

        return False

    return True


async def require_manager(
    update
):
    user = current_user(
        update
    )

    if not user_can_manage(
        user
    ):

        await update.effective_message.reply_text(
            "⛔ Для этого действия "
            "нужны права менеджера."
        )

        return False

    return True


# =========================================================
# PID / RUNNER
# =========================================================

def save_runner_pid(
    pid
):
    PID_FILE.write_text(
        str(pid),
        encoding="utf-8"
    )


def get_runner_pid():
    if not PID_FILE.exists():
        return None

    try:
        return int(
            PID_FILE
            .read_text(
                encoding="utf-8"
            )
            .strip()
        )

    except Exception:
        return None


def process_alive(
    pid
):
    if not pid:
        return False

    try:

        os.kill(
            pid,
            0
        )

        return True

    except (
        ProcessLookupError,
        PermissionError
    ):

        return False


def runner_is_running():
    pid = get_runner_pid()

    if not pid:
        return False

    if process_alive(
        pid
    ):
        return True

    try:
        PID_FILE.unlink()
    except Exception:
        pass

    return False


def stop_runner_process():
    pid = get_runner_pid()

    if not pid:
        return False

    try:

        os.killpg(
            os.getpgid(pid),
            signal.SIGTERM
        )

    except Exception:

        try:
            os.kill(
                pid,
                signal.SIGTERM
            )
        except Exception:
            pass

    try:
        PID_FILE.unlink()
    except Exception:
        pass

    return True


# =========================================================
# SCHEDULE PROGRESS
# =========================================================

def read_schedule_progress():

    if not SCHEDULE_FILE.exists():
        return {
            "planned": 0,
            "completed": 0,
            "skipped": 0,
            "remaining": 0,
            "next_time": None,
        }

    data = load_json(
        SCHEDULE_FILE
    )

    planned = data.get(
        "responses_planned",
        0
    )

    completed_items = data.get(
        "completed",
        []
    )

    skipped_items = data.get(
        "skipped",
        []
    )

    completed = len(
        completed_items
    )

    skipped = len(
        skipped_items
    )

    remaining = max(
        planned
        - completed
        - skipped,
        0
    )

    done = set(
        completed_items
        + skipped_items
    )

    now = datetime.now(
        TIMEZONE
    )

    next_time = None

    for value in data.get(
        "times",
        []
    ):

        if value in done:
            continue

        try:
            dt = datetime.fromisoformat(
                value
            )

            if dt >= now:
                next_time = dt
                break

        except Exception:
            continue

    return {
        "planned": planned,
        "completed": completed,
        "skipped": skipped,
        "remaining": remaining,
        "next_time": next_time,
    }


# =========================================================
# START
# =========================================================

async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    tg = update.effective_user

    old_user = get_user(
        tg.id
    )

    user = register_user(
        telegram_id=tg.id,
        username=tg.username,
        full_name=tg.full_name
    )

    if user["approved"]:

        await update.message.reply_text(
            "Привет 👋\n\n"
            "Бот готов к работе.",

            reply_markup=main_keyboard(
                user["role"]
            )
        )

        return

    await update.message.reply_text(
        "👋 Запрос на доступ отправлен.\n\n"

        "После подтверждения "
        "администратором бот станет доступен."
    )

    # Не отправляем администраторам
    # повторный запрос после каждого /start.
    if old_user:
        return

    admins = get_admins()

    username = (
        f"@{tg.username}"
        if tg.username
        else "username не указан"
    )

    for admin in admins:

        try:

            await context.bot.send_message(
                chat_id=admin[
                    "telegram_id"
                ],

                text=(
                    "👤 Новый запрос доступа\n\n"

                    f"Имя: {tg.full_name}\n"

                    f"Username: "
                    f"{username}\n"

                    f"Telegram ID: "
                    f"{tg.id}"
                ),

                reply_markup=
                access_keyboard(
                    tg.id
                )
            )

        except Exception as error:

            print(
                "Не удалось уведомить "
                "администратора:",

                error
            )


# =========================================================
# ACCESS CALLBACK
# =========================================================

async def access_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    query = update.callback_query
    await query.answer()

    admin = get_user(
        query.from_user.id
    )

    if (
        not admin
        or admin["role"] != "admin"
        or not admin["approved"]
    ):
        await query.answer(
            "Нет прав",
            show_alert=True
        )
        return

    action, raw_id = (
        query.data.split(
            ":",
            1
        )
    )

    telegram_id = int(
        raw_id
    )

    target = get_user(
        telegram_id
    )

    if not target:

        await query.edit_message_text(
            "Пользователь уже удалён."
        )
        return

    if action == "access_yes":

        approve_user(
            telegram_id,
            "manager"
        )

        await query.edit_message_text(
            f"✅ Доступ разрешён\n\n"
            f"{target['full_name']}\n"
            f"Роль: менеджер"
        )

        try:

            await context.bot.send_message(
                chat_id=telegram_id,

                text=(
                    "✅ Вам предоставлен "
                    "доступ к боту.\n\n"
                    "Отправьте /start."
                )
            )

        except Exception:
            pass

    else:

        reject_user(
            telegram_id
        )

        await query.edit_message_text(
            "❌ Запрос отклонён."
        )

        try:

            await context.bot.send_message(
                chat_id=telegram_id,

                text=(
                    "❌ Запрос на доступ "
                    "отклонён."
                )
            )

        except Exception:
            pass


# =========================================================
# NEW SHIFT
# =========================================================

async def new_shift(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not await require_manager(
        update
    ):
        return ConversationHandler.END

    active = get_active_shift()

    if active:

        await update.message.reply_text(
            "⚠️ Уже есть активная смена.\n\n"

            f"Смена #{active['id']}\n"

            f"Статус: "
            f"{active['status']}\n"

            f"План: "
            f"{active['responses_planned']}"
        )

        return ConversationHandler.END

    context.user_data.clear()

    await update.message.reply_text(
        "🆕 Новая смена\n\n"

        "Сколько запусков нужно сделать?\n\n"

        "Например:\n"
        "43",

        reply_markup=
        CANCEL_KEYBOARD
    )

    return ASK_COUNT


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

        count = int(
            text
        )

        if count <= 0:
            raise ValueError

    except ValueError:

        await update.message.reply_text(
            "Введите число.\n\n"
            "Например: 43"
        )

        return ASK_COUNT

    context.user_data[
        "count"
    ] = count

    await update.message.reply_text(
        f"Количество: {count} ✅\n\n"

        "Во сколько начать?\n\n"

        "Например:\n"
        "19:00"
    )

    return ASK_START


def valid_time(
    text
):
    try:

        datetime.strptime(
            text,
            "%H:%M"
        )

        return True

    except ValueError:

        return False


async def ask_start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    text = update.message.text.strip()

    if text == "❌ Отмена":
        return await cancel_shift(
            update,
            context
        )

    if not valid_time(
        text
    ):

        await update.message.reply_text(
            "Введите время "
            "в формате ЧЧ:ММ.\n\n"

            "Например: 19:00"
        )

        return ASK_START

    context.user_data[
        "start_time"
    ] = text

    await update.message.reply_text(
        f"Начало: {text} ✅\n\n"

        "Во сколько закончить?\n\n"

        "Например:\n"
        "06:00"
    )

    return ASK_END


async def ask_end(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    text = update.message.text.strip()

    if text == "❌ Отмена":
        return await cancel_shift(
            update,
            context
        )

    if not valid_time(
        text
    ):

        await update.message.reply_text(
            "Введите время "
            "в формате ЧЧ:ММ.\n\n"

            "Например: 06:00"
        )

        return ASK_END

    context.user_data[
        "end_time"
    ] = text

    count = context.user_data[
        "count"
    ]

    start_time = context.user_data[
        "start_time"
    ]

    gap = int(
        get_setting(
            "minimum_gap_minutes",
            6
        )
    )

    await update.message.reply_text(
        "Проверь настройки 👇\n\n"

        f"Количество: {count}\n"

        f"Начало: {start_time}\n"

        f"Окончание: {text}\n"

        f"Минимальный интервал: "
        f"{gap} мин.\n\n"

        "Что сделать?",

        reply_markup=
        CONFIRM_KEYBOARD
    )

    return CONFIRM


# =========================================================
# CREATE SCHEDULE
# =========================================================

def prepare_schedule(
    count,
    start_time,
    end_time
):
    config = load_json(
        CONFIG_FILE
    )

    gap = int(
        get_setting(
            "minimum_gap_minutes",
            config.get(
                "minimum_gap_minutes",
                6
            )
        )
    )

    config[
        "responses_per_day"
    ] = count

    config[
        "start_time"
    ] = start_time

    config[
        "end_time"
    ] = end_time

    config[
        "minimum_gap_minutes"
    ] = gap

    config[
        "timezone"
    ] = TIMEZONE_NAME

    # scheduler.py у тебя учитывает дни недели.
    today = datetime.now(
        TIMEZONE
    ).strftime(
        "%A"
    ).lower()

    config[
        "active_weekdays"
    ] = [
        today
    ]

    save_json(
        CONFIG_FILE,
        config
    )

    result = subprocess.run(
        [
            sys.executable,
            "scheduler.py"
        ],

        cwd=BASE_DIR,

        capture_output=True,

        text=True
    )

    return (
        result,
        gap
    )


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

    if text not in (
        "✅ Создать и запустить",
        "📅 Только создать"
    ):

        await update.message.reply_text(
            "Используйте кнопки ниже."
        )

        return CONFIRM

    count = context.user_data[
        "count"
    ]

    start_time = context.user_data[
        "start_time"
    ]

    end_time = context.user_data[
        "end_time"
    ]

    result, gap = prepare_schedule(
        count,
        start_time,
        end_time
    )

    if result.returncode != 0:

        error = (
            result.stderr
            or result.stdout
            or "Неизвестная ошибка"
        )

        await update.message.reply_text(
            "❌ Не удалось создать "
            "расписание.\n\n"

            + error[-2500:]
        )

        return ConversationHandler.END

    shift_id = create_shift(
        created_by=
        update.effective_user.id,

        count=count,

        start_time=start_time,

        end_time=end_time,

        minimum_gap_minutes=gap
    )

    context.user_data.clear()

    user = current_user(
        update
    )

    await update.message.reply_text(
        f"✅ Смена #{shift_id} создана.\n\n"

        f"Запусков: {count}\n"

        f"С {start_time} "
        f"до {end_time}",

        reply_markup=
        main_keyboard(
            user["role"]
        )
    )

    if text == "✅ Создать и запустить":

        await start_runner(
            update,
            context
        )

    return ConversationHandler.END


async def cancel_shift(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    context.user_data.clear()

    user = current_user(
        update
    )

    await update.message.reply_text(
        "Создание смены отменено.",

        reply_markup=
        main_keyboard(
            user["role"]
            if user
            else "manager"
        )
    )

    return ConversationHandler.END


# =========================================================
# RUNNER
# =========================================================

async def start_runner(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not await require_manager(
        update
    ):
        return

    shift = get_active_shift()

    if not shift:

        await update.effective_message.reply_text(
            "Нет активной смены."
        )

        return

    if runner_is_running():

        update_shift_status(
            shift["id"],
            "running"
        )

        await update.effective_message.reply_text(
            "🟢 Выполнение уже запущено."
        )

        return

    log_file = open(
        RUNNER_LOG,
        "a",
        encoding="utf-8"
    )

    process = subprocess.Popen(
        [
            sys.executable,
            "runner.py"
        ],

        cwd=BASE_DIR,

        stdout=log_file,

        stderr=log_file,

        start_new_session=True
    )

    save_runner_pid(
        process.pid
    )

    update_shift_status(
        shift["id"],
        "running"
    )

    await update.effective_message.reply_text(
        "▶️ Смена запущена."
    )


async def pause_runner(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not await require_manager(
        update
    ):
        return

    shift = get_active_shift()

    if not shift:

        await update.message.reply_text(
            "Нет активной смены."
        )
        return

    stop_runner_process()

    update_shift_status(
        shift["id"],
        "paused"
    )

    await update.message.reply_text(
        "⏸ Смена поставлена на паузу."
    )


async def resume_runner(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not await require_manager(
        update
    ):
        return

    shift = get_active_shift()

    if not shift:

        await update.message.reply_text(
            "Нет активной смены."
        )
        return

    if shift["status"] == "created":
        pass

    await start_runner(
        update,
        context
    )


# =========================================================
# FINISH
# =========================================================

async def finish_shift(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not await require_manager(
        update
    ):
        return

    shift = get_active_shift()

    if not shift:

        await update.message.reply_text(
            "Сейчас нет активной смены."
        )

        return

    await update.message.reply_text(
        f"⚠️ Завершить смену "
        f"#{shift['id']}?\n\n"

        "Оставшиеся запуски "
        "выполняться не будут.",

        reply_markup=
        finish_keyboard()
    )


async def finish_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    query = update.callback_query
    await query.answer()

    user = get_user(
        query.from_user.id
    )

    if not user_can_manage(
        user
    ):

        await query.answer(
            "Недостаточно прав",
            show_alert=True
        )

        return

    if query.data == "finish_no":

        await query.edit_message_text(
            "👌 Смена продолжает работать."
        )

        return

    shift = get_active_shift()

    if not shift:

        await query.edit_message_text(
            "Активной смены уже нет."
        )

        return

    stop_runner_process()

    progress = (
        read_schedule_progress()
    )

    update_shift_progress(
        shift["id"],
        progress["completed"],
        progress["skipped"]
    )

    update_shift_status(
        shift["id"],
        "cancelled"
    )

    await query.edit_message_text(
        f"⏹ Смена #{shift['id']} "
        "завершена вручную.\n\n"

        f"Выполнено: "
        f"{progress['completed']}\n"

        f"Пропущено: "
        f"{progress['skipped']}\n"

        f"План: "
        f"{shift['responses_planned']}"
    )


# =========================================================
# STATUS
# =========================================================

async def status(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not await require_access(
        update
    ):
        return

    shift = get_active_shift()

    if not shift:

        await update.message.reply_text(
            "Сейчас нет активной смены."
        )

        return

    progress = (
        read_schedule_progress()
    )

    completed = progress[
        "completed"
    ]

    skipped = progress[
        "skipped"
    ]

    planned = shift[
        "responses_planned"
    ]

    remaining = max(
        planned
        - completed
        - skipped,
        0
    )

    update_shift_progress(
        shift["id"],
        completed,
        skipped
    )

    if planned:

        percent = round(
            (
                completed
                / planned
            )
            * 100
        )

    else:
        percent = 0

    filled = min(
        10,
        round(
            percent / 10
        )
    )

    progress_bar = (
        "█" * filled
        + "░" * (
            10 - filled
        )
    )

    next_time = progress[
        "next_time"
    ]

    if next_time:

        next_text = (
            next_time.strftime(
                "%H:%M"
            )
        )

        now = datetime.now(
            TIMEZONE
        )

        minutes = max(
            0,
            int(
                (
                    next_time - now
                ).total_seconds()
                / 60
            )
        )

        next_text += (
            f" (примерно через "
            f"{minutes} мин.)"
        )

    else:

        next_text = "нет"

    status_text = {
        "created":
            "⚪️ создана",

        "running":
            "🟢 работает",

        "paused":
            "⏸ на паузе",
    }.get(
        shift["status"],
        shift["status"]
    )

    await update.message.reply_text(
        f"📊 Смена #{shift['id']}\n\n"

        f"{status_text}\n\n"

        f"{progress_bar} "
        f"{percent}%\n\n"

        f"Запланировано: "
        f"{planned}\n"

        f"Выполнено: "
        f"{completed}\n"

        f"Пропущено: "
        f"{skipped}\n"

        f"Осталось: "
        f"{remaining}\n\n"

        f"Следующий запуск: "
        f"{next_text}\n\n"

        f"Начало: "
        f"{shift['start_time']}\n"

        f"Окончание: "
        f"{shift['end_time']}\n\n"

        f"Процесс: "
        f"{'🟢 запущен' if runner_is_running() else '🔴 не запущен'}"
    )


# =========================================================
# HISTORY
# =========================================================

async def history(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not await require_access(
        update
    ):
        return

    shifts = list_shifts(
        10
    )

    if not shifts:

        await update.message.reply_text(
            "История пока пустая."
        )

        return

    icons = {
        "created": "⚪️",
        "running": "🟢",
        "paused": "⏸",
        "completed": "✅",
        "cancelled": "❌",
    }

    lines = [
        "📋 Последние смены\n"
    ]

    for shift in shifts:

        icon = icons.get(
            shift["status"],
            "•"
        )

        creator = (
            shift.get(
                "creator_name"
            )
            or "Неизвестно"
        )

        lines.append(
            f"{icon} #{shift['id']}\n"

            f"{shift['completed']} / "
            f"{shift['responses_planned']}\n"

            f"{shift['start_time']} → "
            f"{shift['end_time']}\n"

            f"Создал: {creator}\n"
        )

    await update.message.reply_text(
        "\n".join(
            lines
        )
    )


# =========================================================
# REPEAT LAST
# =========================================================

async def repeat_last(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not await require_manager(
        update
    ):
        return

    if get_active_shift():

        await update.message.reply_text(
            "Сначала завершите "
            "текущую смену."
        )

        return

    previous = get_last_shift()

    if not previous:

        await update.message.reply_text(
            "Предыдущих смен пока нет."
        )

        return

    context.user_data.clear()

    context.user_data[
        "count"
    ] = previous[
        "responses_planned"
    ]

    context.user_data[
        "start_time"
    ] = previous[
        "start_time"
    ]

    context.user_data[
        "end_time"
    ] = previous[
        "end_time"
    ]

    await update.message.reply_text(
        "🔁 Повторить прошлые настройки?\n\n"

        f"Количество: "
        f"{previous['responses_planned']}\n"

        f"Начало: "
        f"{previous['start_time']}\n"

        f"Окончание: "
        f"{previous['end_time']}",

        reply_markup=
        CONFIRM_KEYBOARD
    )

    return CONFIRM


# =========================================================
# USERS
# =========================================================

async def users(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    user = current_user(
        update
    )

    if (
        not user
        or user["role"] != "admin"
    ):

        await update.message.reply_text(
            "Функция доступна "
            "только администратору."
        )

        return

    people = list_users()

    if not people:

        await update.message.reply_text(
            "Пользователей нет."
        )

        return

    for person in people:

        username = (
            f"@{person['username']}"
            if person["username"]
            else "без username"
        )

        role_names = {
            "admin":
                "👑 Администратор",

            "manager":
                "👤 Менеджер",

            "viewer":
                "👀 Просмотр",

            "pending":
                "⏳ Ожидает",
        }

        role = role_names.get(
            person["role"],
            person["role"]
        )

        keyboard = None

        if person["approved"]:

            keyboard = role_keyboard(
                person[
                    "telegram_id"
                ]
            )

        await update.message.reply_text(
            f"{person['full_name']}\n"

            f"{username}\n"

            f"ID: "
            f"{person['telegram_id']}\n"

            f"Роль: {role}",

            reply_markup=keyboard
        )


async def role_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    query = update.callback_query
    await query.answer()

    admin = get_user(
        query.from_user.id
    )

    if (
        not admin
        or admin["role"] != "admin"
    ):
        return

    _, role, raw_id = (
        query.data.split(
            ":",
            2
        )
    )

    telegram_id = int(
        raw_id
    )

    # Не даём последнему администратору
    # случайно снять роль с самого себя.
    if (
        telegram_id
        == query.from_user.id
        and role != "admin"
    ):

        await query.answer(
            "Нельзя изменить "
            "собственную роль здесь.",
            show_alert=True
        )

        return

    set_user_role(
        telegram_id,
        role
    )

    role_names = {
        "manager":
            "Менеджер",

        "viewer":
            "Только просмотр",

        "admin":
            "Администратор",
    }

    await query.edit_message_text(
        "✅ Роль изменена:\n\n"
        f"{role_names[role]}"
    )

    try:

        await context.bot.send_message(
            chat_id=telegram_id,

            text=(
                "ℹ️ Ваша роль изменена:\n"
                f"{role_names[role]}\n\n"
                "Отправьте /start, "
                "чтобы обновить меню."
            )
        )

    except Exception:
        pass


# =========================================================
# SETTINGS
# =========================================================

async def settings(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    user = current_user(
        update
    )

    if (
        not user
        or user["role"] != "admin"
    ):

        return

    gap = get_setting(
        "minimum_gap_minutes",
        6
    )

    await update.message.reply_text(
        "⚙️ Настройки\n\n"

        f"Минимальный интервал: "
        f"{gap} минут\n\n"

        "Чтобы изменить:\n"
        "/gap 6"
    )


async def gap_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    user = current_user(
        update
    )

    if (
        not user
        or user["role"] != "admin"
    ):

        return

    if len(
        context.args
    ) != 1:

        await update.message.reply_text(
            "Например:\n"
            "/gap 6"
        )

        return

    try:

        gap = int(
            context.args[0]
        )

        if gap < 1:
            raise ValueError

    except ValueError:

        await update.message.reply_text(
            "Интервал должен быть "
            "целым числом минут."
        )

        return

    set_setting(
        "minimum_gap_minutes",
        gap
    )

    await update.message.reply_text(
        f"✅ Минимальный интервал: "
        f"{gap} минут."
    )


# =========================================================
# HELP
# =========================================================

async def help_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    await update.message.reply_text(
        "🆕 Новая смена\n"
        "Создать расписание.\n\n"

        "📊 Текущая смена\n"
        "Посмотреть состояние.\n\n"

        "⏸ Пауза\n"
        "Временно остановить работу.\n\n"

        "▶️ Продолжить\n"
        "Продолжить смену.\n\n"

        "⏹ Завершить смену\n"
        "Полностью завершить.\n\n"

        "📋 История\n"
        "Последние смены.\n\n"

        "🔁 Повторить прошлую\n"
        "Создать смену с теми же "
        "параметрами."
    )


# =========================================================
# MAIN BUTTONS
# =========================================================

async def main_buttons(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    text = update.message.text.strip()

    if text == "📊 Текущая смена":

        await status(
            update,
            context
        )

    elif text == "📋 История":

        await history(
            update,
            context
        )

    elif text == "⏸ Пауза":

        await pause_runner(
            update,
            context
        )

    elif text == "▶️ Продолжить":

        await resume_runner(
            update,
            context
        )

    elif text == "⏹ Завершить смену":

        await finish_shift(
            update,
            context
        )

    elif text == "👥 Пользователи":

        await users(
            update,
            context
        )

    elif text == "⚙️ Настройки":

        await settings(
            update,
            context
        )

    elif text == "❓ Помощь":

        await help_command(
            update,
            context
        )


# =========================================================
# MONITOR
# =========================================================

async def monitor_shift(
    application
):

    while True:

        try:

            shift = get_active_shift()

            if shift:

                progress = (
                    read_schedule_progress()
                )

                completed = progress[
                    "completed"
                ]

                skipped = progress[
                    "skipped"
                ]

                planned = shift[
                    "responses_planned"
                ]

                update_shift_progress(
                    shift["id"],
                    completed,
                    skipped
                )

                # -------------------------
                # NORMAL COMPLETION
                # -------------------------

                if (
                    planned > 0
                    and
                    completed + skipped
                    >= planned
                ):

                    stop_runner_process()

                    update_shift_status(
                        shift["id"],
                        "completed"
                    )

                    try:

                        await application.bot.send_message(
                            chat_id=
                            shift["created_by"],

                            text=(
                                "✅ Смена завершена\n\n"

                                f"Смена #{shift['id']}\n\n"

                                f"Запланировано: "
                                f"{planned}\n"

                                f"Выполнено: "
                                f"{completed}\n"

                                f"Пропущено: "
                                f"{skipped}"
                            )
                        )

                    except Exception as error:

                        print(
                            "Ошибка итогового "
                            "уведомления:",

                            error
                        )

                # -------------------------
                # RUNNER STOPPED EARLY
                # -------------------------

                elif (
                    shift["status"]
                    == "running"

                    and

                    not runner_is_running()
                ):

                    update_shift_status(
                        shift["id"],
                        "paused"
                    )

                    log_text = (
                        "Лог отсутствует."
                    )

                    if RUNNER_LOG.exists():

                        try:

                            log_text = (
                                RUNNER_LOG
                                .read_text(
                                    encoding="utf-8",
                                    errors="ignore"
                                )[-1800:]
                            )

                        except Exception:
                            pass

                    try:

                        await application.bot.send_message(
                            chat_id=
                            shift["created_by"],

                            text=(
                                "🚨 Выполнение неожиданно "
                                "остановилось\n\n"

                                f"Смена #{shift['id']} "
                                "поставлена на паузу.\n\n"

                                "Последние строки лога:\n\n"

                                f"{log_text}"
                            )
                        )

                    except Exception as error:

                        print(
                            "Ошибка уведомления:",

                            error
                        )

        except Exception as error:

            print(
                "Ошибка monitor_shift:",
                error
            )

        await asyncio.sleep(
            15
        )


async def post_init(
    application
):

    application.create_task(
        monitor_shift(
            application
        )
    )


# =========================================================
# MAIN
# =========================================================

def main():

    init_db()

    if not TOKEN_FILE.exists():

        raise FileNotFoundError(
            "Нет файла .telegram_token"
        )

    token = TOKEN_FILE.read_text(
        encoding="utf-8"
    ).strip()

    app = (
        Application
        .builder()
        .token(token)
        .post_init(post_init)
        .build()
    )

    conversation = ConversationHandler(

        entry_points=[

            MessageHandler(
                filters.Regex(
                    "^🆕 Новая смена$"
                ),
                new_shift
            ),

            MessageHandler(
                filters.Regex(
                    "^🔁 Повторить прошлую$"
                ),
                repeat_last
            ),
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
                    ask_start
                )
            ],

            ASK_END: [
                MessageHandler(
                    filters.TEXT
                    & ~filters.COMMAND,
                    ask_end
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
        ]
    )

    app.add_handler(
        CommandHandler(
            "start",
            start
        )
    )

    app.add_handler(
        CommandHandler(
            "gap",
            gap_command
        )
    )

    app.add_handler(
        conversation
    )

    app.add_handler(
        CallbackQueryHandler(
            finish_callback,
            pattern="^finish_"
        )
    )

    app.add_handler(
        CallbackQueryHandler(
            access_callback,
            pattern="^access_"
        )
    )

    app.add_handler(
        CallbackQueryHandler(
            role_callback,
            pattern="^role:"
        )
    )

    app.add_handler(
        MessageHandler(
            filters.TEXT
            & ~filters.COMMAND,
            main_buttons
        )
    )

    print(
        "Telegram control bot запущен..."
    )

    app.run_polling()


if __name__ == "__main__":
    main()