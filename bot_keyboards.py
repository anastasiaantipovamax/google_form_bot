from telegram import (
    ReplyKeyboardMarkup,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)


def main_keyboard(
    role="manager"
):
    rows = []

    if role in (
        "admin",
        "manager"
    ):
        rows.append(
            ["🆕 Новая смена"]
        )

    rows.append([
        "📊 Текущая смена",
        "📋 История"
    ])

    if role in (
        "admin",
        "manager"
    ):
        rows.append([
            "⏸ Пауза",
            "▶️ Продолжить"
        ])

        rows.append([
            "⏹ Завершить смену"
        ])

        rows.append([
            "🔁 Повторить прошлую"
        ])

    if role == "admin":
        rows.append([
            "👥 Пользователи",
            "⚙️ Настройки"
        ])

    rows.append([
        "❓ Помощь"
    ])

    return ReplyKeyboardMarkup(
        rows,
        resize_keyboard=True
    )


CANCEL_KEYBOARD = ReplyKeyboardMarkup(
    [
        ["❌ Отмена"]
    ],
    resize_keyboard=True
)


CONFIRM_KEYBOARD = ReplyKeyboardMarkup(
    [
        ["✅ Создать и запустить"],
        ["📅 Только создать"],
        ["❌ Отмена"],
    ],
    resize_keyboard=True
)


def finish_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "⏹ Да, завершить",
                callback_data="finish_yes"
            )
        ],
        [
            InlineKeyboardButton(
                "↩️ Не завершать",
                callback_data="finish_no"
            )
        ]
    ])


def access_keyboard(
    telegram_id
):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "✅ Разрешить",
                callback_data=
                f"access_yes:{telegram_id}"
            ),
            InlineKeyboardButton(
                "❌ Отклонить",
                callback_data=
                f"access_no:{telegram_id}"
            )
        ]
    ])


def role_keyboard(
    telegram_id
):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "👤 Менеджер",
                callback_data=
                f"role:manager:{telegram_id}"
            )
        ],
        [
            InlineKeyboardButton(
                "👀 Только просмотр",
                callback_data=
                f"role:viewer:{telegram_id}"
            )
        ],
        [
            InlineKeyboardButton(
                "👑 Администратор",
                callback_data=
                f"role:admin:{telegram_id}"
            )
        ]
    ])