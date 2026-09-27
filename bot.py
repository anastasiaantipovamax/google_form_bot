from playwright.sync_api import sync_playwright
import random
import json
import os
import re


# =====================================================
# НАСТРОЙКИ
# =====================================================

# Ссылка на Google-форму
FORM_URL = "https://docs.google.com/forms/d/e/1FAIpQLSd3l-DSwfxQsKsjP3rL-twMUN3OZME1h6FpyTy6hpzihkm1Sg/viewform"

# Используем уже установленный на Mac Google Chrome
CHROME_PATH = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

# Сколько анкет отправить за один запуск
NUMBER_OF_RESPONSES = 1

# Папка, где лежит bot.py
BASE_DIR = os.path.dirname(os.path.abspath(__file__))


# =====================================================
# ВОПРОС 1
# Бар
# =====================================================

BAR = "РВ_МСК_МОЖ"


# =====================================================
# ВОПРОС 2
# Откуда вы о нас узнали?
# =====================================================

SOURCE_WEIGHTS = {
    "От друзей / знакомых": 40,
    "Соцсети (Instagram, VK и др.)": 25,
    "Онлайн-карты / поиск": 15,
    "Реклама (баннер, флаер, промо)": 5,
    "Проходил(а) мимо / вывеска": 5,
    "Уже был(а) раньше": 5,
    "Мероприятие (концерт, стендап, квиз)": 5,
}


# =====================================================
# ВОПРОС 3
# Как часто к нам ходите?
# =====================================================

FREQUENCY_WEIGHTS = {
    "Частый посетитель": 20,
    "Редкий гость": 30,
    "В первый раз": 10,
    "Периодически": 40,
}


# =====================================================
# ВОПРОС 4
# Общая оценка
# =====================================================

RATING_WEIGHTS = {
    "1": 1,
    "2": 1,
    "3": 8,
    "4": 50,
    "5": 70,
}


# =====================================================
# ВОПРОС 5
# Любимое заведение
# =====================================================

PLACES_FILE = os.path.join(
    BASE_DIR,
    "places_moscow_150.json"
)

PLACES_HISTORY_FILE = os.path.join(
    BASE_DIR,
    "places_history.json"
)

# Сколько последних анкет считаем "недавними"
RECENT_PLACES_LIMIT = 50

# 0.02 = 2% = примерно 1 повтор из последних 50 на 50 анкет
PLACE_REPEAT_PROBABILITY = 0.02


# =====================================================
# ВОПРОС 11
# Комментарий
# =====================================================

COMMENTS_FILE = os.path.join(
    BASE_DIR,
    "comments.json"
)


# =====================================================
# ВОПРОС 12
# Цены
# =====================================================

PRICE_WEIGHTS = {
    "Высокие": 0,
    "Адекватные": 100,
}


# =====================================================
# ВОПРОС 13
# Район / метро / улица
# =====================================================

AREAS_FILE = os.path.join(
    BASE_DIR,
    "areas_moscow.json"
)

# Иногда человек просто пишет "местный"
LOCAL_ONLY_PROBABILITY = 0.10

# Очень редко просто "приезжий"
VISITOR_ONLY_PROBABILITY = 0.01

# Примерно 14% — более дальняя часть Москвы
FAR_AREA_PROBABILITY = 0.14

# Если выпал дальний ответ:
# 35% улица, 65% район
FAR_STREET_PROBABILITY = 0.35


# =====================================================
# ВОПРОС 15
# Способ прохождения
# =====================================================

PASSAGE_WEIGHTS = {
    "Прошел сам через QR-код": 0,
    "Подошел сотрудник с опросом": 100,
}


# =====================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# =====================================================

def weighted_choice(options):
    """
    Выбирает один вариант ответа
    с учётом указанных вероятностей.
    """
    return random.choices(
        population=list(options.keys()),
        weights=list(options.values()),
        k=1
    )[0]


def choose_radio(question, answer):
    """
    Внутри конкретного вопроса
    находит radio-кнопку и нажимает её.
    """
    question.get_by_role(
        "radio",
        name=answer,
        exact=True
    ).click()


def load_json_list(path):
    """
    Загружает JSON-список.
    Если файла нет, возвращает пустой список.
    """
    if not os.path.exists(path):
        return []

    with open(
        path,
        "r",
        encoding="utf-8"
    ) as file:
        data = json.load(file)

    if not isinstance(data, list):
        raise ValueError(
            f"Файл {path} должен содержать JSON-список."
        )

    return data


def save_json_list(path, data):
    """
    Сохраняет список в JSON.
    """
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


def load_comments_data():
    """
    Загружает комментарии из comments.json.
    """
    if not os.path.exists(COMMENTS_FILE):
        raise FileNotFoundError(
            "Не найден файл comments.json. "
            "Положи его рядом с bot.py."
        )

    with open(
        COMMENTS_FILE,
        "r",
        encoding="utf-8"
    ) as file:
        data = json.load(file)

    required_sections = [
        "atmosphere",
        "bar",
        "kitchen",
        "staff",
        "comfort",
        "general",
        "positive",
    ]

    for section in required_sections:
        if section not in data:
            raise ValueError(
                f"В comments.json отсутствует раздел: {section}"
            )

        if not isinstance(data[section], list) or not data[section]:
            raise ValueError(
                f"Раздел {section} в comments.json должен быть непустым списком."
            )

    return data


def load_areas_data():
    """
    Загружает районы и улицы Москвы
    из отдельного JSON-файла.
    """
    if not os.path.exists(AREAS_FILE):
        raise FileNotFoundError(
            "Не найден файл areas_moscow.json. "
            "Положи его рядом с bot.py."
        )

    with open(
        AREAS_FILE,
        "r",
        encoding="utf-8"
    ) as file:
        data = json.load(file)

    required_sections = [
        "nearby",
        "all_districts",
        "far_streets",
        "nearby_official_districts",
    ]

    for section in required_sections:
        if section not in data:
            raise ValueError(
                f"В areas_moscow.json отсутствует раздел: {section}"
            )

    return data


def generate_area_answer():
    """
    Генерирует ответ на вопрос
    район / метро / улица / местный / приезжий.

    Вероятности:
    1%  — "приезжий"
    10% — "местный"
    14% — дальний район/улица
    75% — ближайший район/метро/улица
    """
    data = load_areas_data()

    nearby = data["nearby"]
    all_districts = data["all_districts"]
    far_streets = data["far_streets"]

    nearby_official = set(
        data["nearby_official_districts"]
    )

    roll = random.random()

    # 1% — просто "приезжий"
    if roll < VISITOR_ONLY_PROBABILITY:
        print("🌍 Ответ: приезжий")
        return "приезжий"

    # Следующие 10% — просто "местный"
    if roll < (
        VISITOR_ONLY_PROBABILITY
        + LOCAL_ONLY_PROBABILITY
    ):
        print("⌂ Ответ: местный")
        return "местный"

    # Следующие 14% — дальний район или улица
    if roll < (
        VISITOR_ONLY_PROBABILITY
        + LOCAL_ONLY_PROBABILITY
        + FAR_AREA_PROBABILITY
    ):
        # Внутри дальних ответов:
        # 35% улица, 65% район
        if random.random() < FAR_STREET_PROBABILITY:
            answer = random.choice(
                far_streets
            )
            print("↗ Дальний ответ: улица")
            return answer

        far_districts = [
            district
            for district in all_districts
            if district not in nearby_official
        ]

        answer = random.choice(
            far_districts
        )

        print("↗ Дальний ответ: район")
        return answer

    # Остальные 75% — ближайшие варианты.
    texts = [
        item["text"]
        for item in nearby
    ]

    weights = [
        item["weight"]
        for item in nearby
    ]

    return random.choices(
        population=texts,
        weights=weights,
        k=1
    )[0]


def get_favorite_place():
    """
    Выбирает заведение из places_moscow_150.json.

    В 98% случаев не берёт заведение из последних 50 анкет.
    Примерно в 2% случаев допускает повтор одного
    из последних 50 заведений.
    """
    if not os.path.exists(PLACES_FILE):
        raise FileNotFoundError(
            "Не найден файл places_moscow_150.json. "
            "Положи его рядом с bot.py."
        )

    all_places = load_json_list(
        PLACES_FILE
    )

    if not all_places:
        raise ValueError(
            "Файл places_moscow_150.json пуст."
        )

    history = load_json_list(
        PLACES_HISTORY_FILE
    )

    recent_places = history[
        -RECENT_PLACES_LIMIT:
    ]

    should_repeat = (
        bool(recent_places)
        and random.random() < PLACE_REPEAT_PROBABILITY
    )

    if should_repeat:
        selected_place = random.choice(
            recent_places
        )

        print(
            "↻ Допущен редкий повтор заведения"
        )

    else:
        available_places = [
            place
            for place in all_places
            if place not in recent_places
        ]

        if not available_places:
            available_places = all_places.copy()

        selected_place = random.choice(
            available_places
        )

    return selected_place


def remember_favorite_place(place):
    """
    Записывает заведение в историю
    после отправки анкеты.
    """
    history = load_json_list(
        PLACES_HISTORY_FILE
    )

    history.append(place)

    save_json_list(
        PLACES_HISTORY_FILE,
        history
    )


def detail_rating(overall_rating):
    """
    Генерирует оценку -1 / 0 / 1
    в зависимости от общей оценки 1–5.

    Вероятности оставлены без изменений.
    """
    overall_rating = int(overall_rating)

    if overall_rating == 5:
        return weighted_choice({
            "1 (супер)": 85,
            "0 (норм)": 15,
        })

    elif overall_rating == 4:
        return weighted_choice({
            "1 (супер)": 80,
            "0 (норм)": 40,
            "-1 (отстой)": 1,
        })

    elif overall_rating == 3:
        return weighted_choice({
            "1 (супер)": 30,
            "0 (норм)": 60,
            "-1 (отстой)": 1,
        })

    elif overall_rating == 2:
        return weighted_choice({
            "0 (норм)": 50,
            "-1 (отстой)": 1,
        })

    else:
        return "-1 (отстой)"


def generate_comment(
    overall_rating,
    atmosphere,
    bar_rating,
    kitchen_rating,
    staff_rating,
    comfort_rating
):
    """
    Генерирует комментарий.
    Комментарий всегда заполнен.
    """
    comments = load_comments_data()

    bad_categories = []

    if atmosphere == "-1 (отстой)":
        bad_categories.append(
            comments["atmosphere"]
        )

    if bar_rating == "-1 (отстой)":
        bad_categories.append(
            comments["bar"]
        )

    if kitchen_rating == "-1 (отстой)":
        bad_categories.append(
            comments["kitchen"]
        )

    if staff_rating == "-1 (отстой)":
        bad_categories.append(
            comments["staff"]
        )

    if comfort_rating == "-1 (отстой)":
        bad_categories.append(
            comments["comfort"]
        )

    # Если есть плохая оценка —
    # комментарий связан именно с ней.
    if bad_categories:
        category = random.choice(
            bad_categories
        )

        return random.choice(
            category
        )

    # При общей оценке 1–3 —
    # нейтральный комментарий.
    if int(overall_rating) <= 3:
        return random.choice(
            comments["general"]
        )

    # При оценке 4–5 —
    # позитивный комментарий.
    return random.choice(
        comments["positive"]
    )


def validate_required_files():
    """
    Проверяет внешние файлы до запуска Chrome,
    чтобы ошибка была понятной сразу.
    """
    required_files = [
        PLACES_FILE,
        COMMENTS_FILE,
        AREAS_FILE,
    ]

    missing = [
        path
        for path in required_files
        if not os.path.exists(path)
    ]

    if missing:
        names = ", ".join(
            os.path.basename(path)
            for path in missing
        )

        raise FileNotFoundError(
            f"Не найдены обязательные файлы: {names}. "
            "Они должны лежать рядом с bot.py."
        )

    # Заодно проверяем структуру файлов.
    places = load_json_list(PLACES_FILE)

    if not places:
        raise ValueError(
            "places_moscow_150.json пуст."
        )

    load_comments_data()
    load_areas_data()


# =====================================================
# ПРОХОЖДЕНИЕ ОДНОЙ АНКЕТЫ
# =====================================================

def complete_form(page, number):
    print()
    print("======================================")
    print(
        f"ПРОХОЖДЕНИЕ "
        f"{number}/{NUMBER_OF_RESPONSES}"
    )
    print("======================================")

    print("Открываю форму...")

    # Каждый раз открываем новую чистую форму
    page.goto(
        FORM_URL,
        wait_until="domcontentloaded"
    )

    # Ждём, пока Google Forms загрузит ВСЕ 15 вопросов
    page.wait_for_function(
        """
        () => document.querySelectorAll(
            'div[role="listitem"]'
        ).length >= 15
        """,
        timeout=20000
    )

    questions = page.locator(
        'div[role="listitem"]'
    )

    question_count = questions.count()

    print(
        f"Найдено вопросов: {question_count}"
    )

    if question_count < 15:
        raise RuntimeError(
            f"Найдено только {question_count} вопросов. "
            f"Ожидалось минимум 15."
        )

    # =================================================
    # 1. Бар
    # =================================================

    choose_radio(
        questions.nth(0),
        BAR
    )

    print(
        f"✓ 1. Бар: {BAR}"
    )

    # =================================================
    # 2. Откуда узнали
    # =================================================

    source_answer = weighted_choice(
        SOURCE_WEIGHTS
    )

    choose_radio(
        questions.nth(1),
        source_answer
    )

    print(
        f"✓ 2. Откуда узнали: "
        f"{source_answer}"
    )

    # =================================================
    # 3. Частота посещения
    # =================================================

    frequency_answer = weighted_choice(
        FREQUENCY_WEIGHTS
    )

    choose_radio(
        questions.nth(2),
        frequency_answer
    )

    print(
        f"✓ 3. Частота: "
        f"{frequency_answer}"
    )

    # =================================================
    # 4. Общая оценка
    # =================================================

    rating_answer = weighted_choice(
        RATING_WEIGHTS
    )

    choose_radio(
        questions.nth(3),
        rating_answer
    )

    print(
        f"✓ 4. Общая оценка: "
        f"{rating_answer}"
    )

    # =================================================
    # 5. Любимое заведение
    # =================================================

    favorite_place = get_favorite_place()

    questions.nth(4).get_by_role(
        "textbox"
    ).fill(
        favorite_place
    )

    print(
        f"✓ 5. Любимое заведение: "
        f"{favorite_place}"
    )

    # =================================================
    # 6. Атмосфера
    # =================================================

    atmosphere = detail_rating(
        rating_answer
    )

    choose_radio(
        questions.nth(5),
        atmosphere
    )

    print(
        f"✓ 6. Атмосфера: "
        f"{atmosphere}"
    )

    # =================================================
    # 7. Бар
    # =================================================

    bar_rating = detail_rating(
        rating_answer
    )

    choose_radio(
        questions.nth(6),
        bar_rating
    )

    print(
        f"✓ 7. Бар: "
        f"{bar_rating}"
    )

    # =================================================
    # 8. Кухня
    # =================================================

    kitchen_rating = detail_rating(
        rating_answer
    )

    choose_radio(
        questions.nth(7),
        kitchen_rating
    )

    print(
        f"✓ 8. Кухня: "
        f"{kitchen_rating}"
    )

    # =================================================
    # 9. Персонал
    # =================================================

    staff_rating = detail_rating(
        rating_answer
    )

    choose_radio(
        questions.nth(8),
        staff_rating
    )

    print(
        f"✓ 9. Персонал: "
        f"{staff_rating}"
    )

    # =================================================
    # 10. Комфорт
    # =================================================

    comfort_rating = detail_rating(
        rating_answer
    )

    choose_radio(
        questions.nth(9),
        comfort_rating
    )

    print(
        f"✓ 10. Комфорт: "
        f"{comfort_rating}"
    )

    # =================================================
    # 11. Что не понравилось
    # =================================================

    comment = generate_comment(
        rating_answer,
        atmosphere,
        bar_rating,
        kitchen_rating,
        staff_rating,
        comfort_rating
    )

    questions.nth(10).get_by_role(
        "textbox"
    ).fill(
        comment
    )

    print(
        f"✓ 11. Комментарий: "
        f"{comment}"
    )

    # =================================================
    # 12. Цены
    # =================================================

    price_answer = weighted_choice(
        PRICE_WEIGHTS
    )

    choose_radio(
        questions.nth(11),
        price_answer
    )

    print(
        f"✓ 12. Цены: "
        f"{price_answer}"
    )

    # =================================================
    # 13. Район / метро / улица
    # =================================================

    area_answer = generate_area_answer()

    questions.nth(12).get_by_role(
        "textbox"
    ).fill(
        area_answer
    )

    print(
        f"✓ 13. Район: "
        f"{area_answer}"
    )

    # =================================================
    # 14. Рекомендация
    # =================================================

    if int(rating_answer) >= 4:
        recommendation = weighted_choice({
            "Да": 95,
            "Нет": 5,
        })

    elif int(rating_answer) == 3:
        recommendation = weighted_choice({
            "Да": 60,
            "Нет": 40,
        })

    else:
        recommendation = weighted_choice({
            "Да": 20,
            "Нет": 80,
        })

    choose_radio(
        questions.nth(13),
        recommendation
    )

    print(
        f"✓ 14. Рекомендация: "
        f"{recommendation}"
    )

    # =================================================
    # 15. Способ прохождения
    # =================================================

    passage_answer = weighted_choice(
        PASSAGE_WEIGHTS
    )

    choose_radio(
        questions.nth(14),
        passage_answer
    )

    print(
        f"✓ 15. Способ прохождения: "
        f"{passage_answer}"
    )

    # =================================================
    # ОТПРАВКА
    # =================================================

    print()
    print("Все вопросы заполнены.")

    page.wait_for_timeout(1000)

    print("Отправляю форму...")

    submit_pattern = re.compile(
        r"Отправить|Submit",
        re.IGNORECASE
    )

    # Ищем кнопку отправки
    submit_button = page.get_by_role(
        "button",
        name=submit_pattern
    )

    # Запасной вариант поиска
    if submit_button.count() == 0:
        submit_button = page.locator(
            '[role="button"]'
        ).filter(
            has_text=submit_pattern
        )

    # Если кнопку вообще не нашли
    if submit_button.count() == 0:

        print()
        print("Не удалось найти кнопку отправки.")
        print("Кнопки на странице:")

        buttons = page.locator(
            '[role="button"], button'
        )

        for i in range(buttons.count()):
            try:
                text = buttons.nth(i).inner_text().strip()

                if text:
                    print(
                        f"  Кнопка {i}: {text!r}"
                    )

            except Exception:
                pass

        raise RuntimeError(
            "Кнопка отправки Google Forms не найдена."
        )


    print(
        f"Кнопок отправки найдено: "
        f"{submit_button.count()}"
    )

    # Нажимаем кнопку РОВНО ОДИН РАЗ
    submit_button.last.click(
        timeout=15000
    )


    # Ждём реального подтверждения Google
    confirmation = page.get_by_text(
        re.compile(
            r"(Ответ записан|Your response has been recorded)",
            re.IGNORECASE
        )
    )

    confirmation.wait_for(
        state="visible",
        timeout=15000
    )

    print(
        "✓ Google подтвердил сохранение ответа"
    )


    # Только после подтверждения
    # записываем заведение в историю
    remember_favorite_place(
        favorite_place
    )

    print(
        f"✓ Прохождение {number} отправлено!"
    )


# =====================================================
# ЗАПУСК БОТА
# =====================================================

def main():
    print()
    print("======================================")
    print("GOOGLE FORM BOT")
    print("======================================")

    print(
        f"Количество прохождений: "
        f"{NUMBER_OF_RESPONSES}"
    )

    print(
        f"Бар: {BAR}"
    )

    # Проверяем JSON-файлы ещё до запуска браузера.
    validate_required_files()

    successful = 0

    with sync_playwright() as p:
        # Если бот запущен внутри GitHub Actions
        if os.getenv("GITHUB_ACTIONS") == "true":

            print("Запуск в GitHub Actions")

            browser = p.chromium.launch(
                headless=True,
                channel="chrome"
            )

        # Если запускаем на своём Mac
        else:

            print("Запуск на Mac")

            browser = p.chromium.launch(
                headless=True,
                executable_path=CHROME_PATH
            )


        page = browser.new_page()

        for number in range(
            1,
            NUMBER_OF_RESPONSES + 1
        ):
            try:
                complete_form(
                    page,
                    number
                )

                successful += 1

            except Exception as error:
                print()

                print(
                    f"✗ Ошибка на прохождении "
                    f"{number}"
                )

                print(error)

                screenshot_name = os.path.join(
                    BASE_DIR,
                    f"error_{number}.png"
                )

                try:
                    page.screenshot(
                        path=screenshot_name,
                        full_page=True
                    )

                    print(
                        f"Создан скриншот: "
                        f"{screenshot_name}"
                    )

                except Exception as screenshot_error:
                    print(
                        "Не удалось сделать скриншот:"
                    )
                    print(
                        screenshot_error
                    )

                break

        browser.close()

    # =================================================
    # ИТОГ
    # =================================================

    print()
    print("======================================")
    print("РАБОТА ЗАВЕРШЕНА")
    print("======================================")

    print(
        f"Успешно отправлено: "
        f"{successful}"
    )

    print(
        f"Запланировано: "
        f"{NUMBER_OF_RESPONSES}"
    )
    if successful != NUMBER_OF_RESPONSES:
        raise RuntimeError(
        f"Не все анкеты были отправлены. "
        f"Успешно: {successful}, "
        f"нужно: {NUMBER_OF_RESPONSES}"
    )


# =====================================================
# СТАРТ
# =====================================================

if __name__ == "__main__":
    main()
