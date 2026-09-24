import json
import os
import random
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


BASE_DIR = os.path.dirname(os.path.abspath(__file__))

CONFIG_FILE = os.path.join(
    BASE_DIR,
    "schedule_config.json"
)

SCHEDULE_FILE = os.path.join(
    BASE_DIR,
    "daily_schedule.json"
)

WEEKDAY_NAMES = [
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
]


def load_config():
    if not os.path.exists(CONFIG_FILE):
        raise FileNotFoundError(
            "Не найден schedule_config.json. "
            "Положи его рядом с scheduler.py."
        )

    with open(
        CONFIG_FILE,
        "r",
        encoding="utf-8"
    ) as file:
        config = json.load(file)

    required = [
        "responses_per_day",
        "start_time",
        "end_time",
        "minimum_gap_minutes",
        "active_weekdays",
        "timezone",
    ]

    for key in required:
        if key not in config:
            raise ValueError(
                f"В schedule_config.json отсутствует поле: {key}"
            )

    return config


def parse_hhmm(value):
    return datetime.strptime(
        value,
        "%H:%M"
    ).time()


def get_next_active_date(config):
    timezone = ZoneInfo(
        config["timezone"]
    )

    today = datetime.now(
        timezone
    ).date()

    active_weekdays = set(
        config["active_weekdays"]
    )

    if not active_weekdays:
        raise ValueError(
            "active_weekdays не может быть пустым."
        )

    for days_ahead in range(8):
        candidate = today + timedelta(
            days=days_ahead
        )

        weekday_name = WEEKDAY_NAMES[
            candidate.weekday()
        ]

        if weekday_name in active_weekdays:
            return candidate

    raise RuntimeError(
        "Не удалось найти активный день."
    )


def build_period(config, start_date):
    timezone = ZoneInfo(
        config["timezone"]
    )

    start_clock = parse_hhmm(
        config["start_time"]
    )

    end_clock = parse_hhmm(
        config["end_time"]
    )

    start_dt = datetime.combine(
        start_date,
        start_clock,
        tzinfo=timezone
    )

    end_date = start_date

    if end_clock <= start_clock:
        end_date = start_date + timedelta(
            days=1
        )

    end_dt = datetime.combine(
        end_date,
        end_clock,
        tzinfo=timezone
    )

    return start_dt, end_dt


def generate_times(
    start_dt,
    end_dt,
    count,
    minimum_gap_minutes
):
    if count <= 0:
        raise ValueError(
            "responses_per_day должен быть больше 0."
        )

    if minimum_gap_minutes < 0:
        raise ValueError(
            "minimum_gap_minutes не может быть отрицательным."
        )

    total_minutes = int(
        (end_dt - start_dt).total_seconds()
        // 60
    )

    if total_minutes <= 0:
        raise ValueError(
            "Временной период должен быть больше 0 минут."
        )

    available_minutes = total_minutes

    minimum_required = (
        (count - 1)
        * minimum_gap_minutes
        + 1
    )

    if minimum_required > available_minutes:
        raise ValueError(
            "В заданный период нельзя поместить "
            f"{count} запусков с минимальным интервалом "
            f"{minimum_gap_minutes} минут."
        )

    compression = (
        (count - 1)
        * (minimum_gap_minutes - 1)
    )

    compressed_size = (
        available_minutes
        - compression
    )

    raw_positions = sorted(
        random.sample(
            range(compressed_size),
            count
        )
    )

    minute_positions = []

    for index, raw_position in enumerate(
        raw_positions
    ):
        actual_position = (
            raw_position
            + index
            * (minimum_gap_minutes - 1)
        )

        minute_positions.append(
            actual_position
        )

    schedule = [
        start_dt + timedelta(
            minutes=position
        )
        for position in minute_positions
    ]

    return schedule


def save_schedule(
    config,
    start_date,
    start_dt,
    end_dt,
    schedule
):
    data = {
        "period_start_date": str(start_date),
        "timezone": config["timezone"],
        "window_start": start_dt.isoformat(),
        "window_end": end_dt.isoformat(),
        "responses_planned": len(schedule),
        "minimum_gap_minutes": config[
            "minimum_gap_minutes"
        ],
        "times": [
            dt.isoformat()
            for dt in schedule
        ],
        "completed": [],
    }

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


def print_schedule(
    start_dt,
    end_dt,
    schedule
):
    print()
    print("======================================")
    print("ПРЕДВАРИТЕЛЬНОЕ РАСПИСАНИЕ")
    print("======================================")

    print(
        "Период:",
        start_dt.strftime("%d.%m.%Y %H:%M"),
        "→",
        end_dt.strftime("%d.%m.%Y %H:%M")
    )

    print(
        f"Количество запусков: {len(schedule)}"
    )

    print()

    previous = None

    for number, dt in enumerate(
        schedule,
        start=1
    ):
        if previous is None:
            gap_text = ""
        else:
            gap = int(
                (dt - previous).total_seconds()
                // 60
            )

            gap_text = (
                f"   (+{gap} мин)"
            )

        print(
            f"{number:02d}. "
            f"{dt.strftime('%d.%m %H:%M')}"
            f"{gap_text}"
        )

        previous = dt

    print()
    print(
        "Расписание сохранено в:"
    )
    print(
        SCHEDULE_FILE
    )

    print()
    print(
        "ВАЖНО: сейчас scheduler.py "
        "ТОЛЬКО создаёт расписание."
    )

    print(
        "bot.py он пока НЕ запускает."
    )


def main():
    config = load_config()

    start_date = get_next_active_date(
        config
    )

    start_dt, end_dt = build_period(
        config,
        start_date
    )

    schedule = generate_times(
        start_dt=start_dt,
        end_dt=end_dt,
        count=config["responses_per_day"],
        minimum_gap_minutes=config[
            "minimum_gap_minutes"
        ],
    )

    save_schedule(
        config=config,
        start_date=start_date,
        start_dt=start_dt,
        end_dt=end_dt,
        schedule=schedule,
    )

    print_schedule(
        start_dt,
        end_dt,
        schedule
    )


if __name__ == "__main__":
    main()
