import json
import os
import subprocess
import sys
import time
from datetime import datetime
from zoneinfo import ZoneInfo


# =====================================================
# ПУТИ
# =====================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

SCHEDULE_FILE = os.path.join(
    BASE_DIR,
    "daily_schedule.json"
)

BOT_FILE = os.path.join(
    BASE_DIR,
    "bot.py"
)


# =====================================================
# РАБОТА С РАСПИСАНИЕМ
# =====================================================

def load_schedule():
    if not os.path.exists(SCHEDULE_FILE):
        raise FileNotFoundError(
            "Не найден daily_schedule.json. "
            "Сначала запусти scheduler.py."
        )

    with open(
        SCHEDULE_FILE,
        "r",
        encoding="utf-8"
    ) as file:
        data = json.load(file)

    if "times" not in data:
        raise ValueError(
            "В daily_schedule.json отсутствует список times."
        )

    if "completed" not in data:
        data["completed"] = []

    if "skipped" not in data:
        data["skipped"] = []

    return data


def save_schedule(data):
    with open(
        SCHEDULE_FILE,
        "w",
        encoding="utf-8"
    ) as file:
        json.dump(
            data,
            file,
            ensure_ascii=False,
            indent=2
        )


def get_timezone(data):
    timezone_name = data.get(
        "timezone",
        "Europe/Moscow"
    )

    return ZoneInfo(
        timezone_name
    )


# =====================================================
# ЗАПУСК BOT.PY
# =====================================================

def run_bot():
    if not os.path.exists(BOT_FILE):
        raise FileNotFoundError(
            "Не найден bot.py рядом с runner.py."
        )

    print()
    print("--------------------------------------")
    print("Запускаю bot.py...")
    print("--------------------------------------")

    result = subprocess.run(
        [
            sys.executable,
            BOT_FILE,
        ],
        cwd=BASE_DIR
    )

    return result.returncode == 0


# =====================================================
# ОСНОВНАЯ ЛОГИКА
# =====================================================

def main():
    data = load_schedule()

    timezone = get_timezone(
        data
    )

    completed = set(
        data.get(
            "completed",
            []
        )
    )

    skipped = set(
        data.get(
            "skipped",
            []
        )
    )

    print()
    print("======================================")
    print("RUNNER ЗАПУЩЕН")
    print("======================================")

    print(
        f"Часовой пояс: {timezone.key}"
    )

    print(
        f"Запланировано: {len(data['times'])}"
    )

    print(
        f"Уже выполнено: {len(completed)}"
    )

    print()

    for scheduled_text in data["times"]:

        # Уже было выполнено
        if scheduled_text in completed:
            continue

        # Уже было пропущено
        if scheduled_text in skipped:
            continue

        scheduled_dt = datetime.fromisoformat(
            scheduled_text
        )

        now = datetime.now(
            timezone
        )

        # Если время уже прошло до запуска runner,
        # не отправляем несколько анкет подряд.
        if scheduled_dt <= now:

            print(
                "Пропущено прошедшее время:",
                scheduled_dt.strftime(
                    "%d.%m.%Y %H:%M"
                )
            )

            skipped.add(
                scheduled_text
            )

            data["skipped"] = sorted(
                skipped
            )

            save_schedule(
                data
            )

            continue

        wait_seconds = (
            scheduled_dt - now
        ).total_seconds()

        print(
            "Следующий запуск:",
            scheduled_dt.strftime(
                "%d.%m.%Y %H:%M"
            )
        )

        print(
            f"Ждать примерно "
            f"{wait_seconds / 60:.1f} мин."
        )

        # Ждём нужного момента
        time.sleep(
            wait_seconds
        )

        actual_start = datetime.now(
            timezone
        )

        print()
        print(
            "Наступило время:",
            actual_start.strftime(
                "%d.%m.%Y %H:%M:%S"
            )
        )

        success = run_bot()

        if success:

            completed.add(
                scheduled_text
            )

            data["completed"] = sorted(
                completed
            )

            save_schedule(
                data
            )

            print(
                "✓ Запуск отмечен как выполненный."
            )

        else:

            print(
                "✗ bot.py завершился с ошибкой."
            )

            print(
                "Этот запуск НЕ отмечен "
                "как выполненный."
            )

    print()
    print("======================================")
    print("РАСПИСАНИЕ ЗАВЕРШЕНО")
    print("======================================")

    print(
        f"Выполнено: {len(completed)}"
    )

    print(
        f"Пропущено: {len(skipped)}"
    )


if __name__ == "__main__":
    main()
