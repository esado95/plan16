# -*- coding: utf-8 -*-
"""
Собирает личный файл plan16-data.json из markdown-документов plan-16.

Публикуется только движок (index.html и прочее). Этот файл и то, что он
производит, в репозиторий не попадают: см. .gitignore.

Запуск:  python build_data.py
"""

import json
import os
import re
import unicodedata
from datetime import date
from pathlib import Path

import markdown

# где лежат исходные заметки; путь можно переопределить переменной окружения
SRC = Path(os.environ.get("PLAN16_SRC", Path(__file__).resolve().parent.parent / "plan-16"))
COURSE = Path(os.environ.get("PLAN16_COURSE", Path(__file__).resolve().parent.parent / "Cours_RU"))
COURSE_FR = Path(os.environ.get("PLAN16_COURSE_FR", COURSE.parent / "Cours"))
OUT = Path(__file__).parent / "plan16-data.json"

# Темы повторения: модули курса, сгруппированные по смыслу, порядок курса сохранён.
# Из программы убраны экзамены REA (17, 21, 23, 35), проект (01), английский (07, 14, 19, 32)
# и мастерская CV (13) — повторяется только теория.
THEMES = [
    ("Матчасть, модель OSI и виртуализация", [2, 3, 4]),
    ("IPv4, CIDR и маршрутизация", [5, 6]),
    ("DHCP: Windows Server и Cisco", [8, 9]),
    ("DHCP на нескольких роутерах, DNS, Web и FTP", [10, 11]),
    ("VLSM и защита Cisco: SSH и ACL", [12]),
    ("Active Directory: установка, права, AGDLP", [15]),
    ("Групповые политики GPO", [16]),
    ("Развёртывание постов WDS и анализ трафика", [18, 20]),
    ("NAT и PAT: Windows и Cisco", [22, 24]),
    ("Debian: установка, сеть и SSH", [25, 26]),
    ("Debian: пользователи, права, пакеты и systemd", [27, 28]),
    ("Debian: DHCP-сервер, Samba и TP «Цитадель»", [29, 30]),
    ("Защита Debian и кластеры Windows и Proxmox", [31, 33, 34]),
]

YEAR = 2026
MONTHS = {
    "января": 1, "февраля": 2, "марта": 3, "апреля": 4, "мая": 5, "июня": 6,
    "июля": 7, "августа": 8, "сентября": 9, "октября": 10, "ноября": 11, "декабря": 12,
}

MD = markdown.Markdown(extensions=["tables", "nl2br", "sane_lists"])


def html(text):
    """markdown → html. Пустой текст даёт пустую строку, а не <p></p>."""
    text = text.strip()
    # хвостовой разделитель разделов в <hr> превращать незачем
    text = re.sub(r"\n-{3,}\s*$", "", text).strip()
    # прочерки для заполнения от руки: markdown принял бы их за выделение
    text = re.sub(r"_{3,}", '<span class="blank"></span>', text)
    if not text:
        return ""
    MD.reset()
    return MD.convert(text)


def slug(text):
    """Заголовок → идентификатор из латиницы и цифр."""
    text = unicodedata.normalize("NFKD", text.lower())
    text = "".join(c for c in text if not unicodedata.combining(c))
    ru = {
        "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e",
        "ж": "zh", "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m",
        "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
        "ф": "f", "х": "h", "ц": "c", "ч": "ch", "ш": "sh", "щ": "sch",
        "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
    }
    text = "".join(ru.get(c, c) for c in text)
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text or "x"


def split_headings(text, level):
    """Режет текст по заголовкам заданного уровня.

    Возвращает (текст до первого заголовка, [(заголовок, тело), ...]).
    Заголовки внутри блоков кода тут не встречаются, поэтому проверки на них нет.
    """
    pattern = re.compile(r"^%s (.+)$" % ("#" * level), re.M)
    marks = list(pattern.finditer(text))
    if not marks:
        return text, []
    head = text[: marks[0].start()]
    parts = []
    for i, m in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(text)
        parts.append((m.group(1).strip(), text[m.end():end]))
    return head, parts


def read(name):
    return (SRC / name).read_text(encoding="utf-8")


# ─────────────────────────── распорядок ───────────────────────────

def parse_schedule(body):
    """Строки вида «**06:30** Подъём…» → [{t, s}]."""
    out = []
    for line in body.splitlines():
        m = re.match(r"\*\*(\d{1,2}:\d{2})\*\*\s*(.+)", line.strip())
        if m:
            out.append({"t": m.group(1), "s": html(m.group(2)).replace("<p>", "").replace("</p>", "")})
    return out


def parse_day(title, body):
    """«День 1 · понедельник, 3 августа» + шапка с залом, темой и едой."""
    n = int(re.search(r"День\s+(\d+)", title).group(1))
    weekday = ""
    iso = ""
    m = re.search(r"·\s*([а-яё]+),\s*(\d{1,2})\s+([а-яё]+)", title)
    if m:
        weekday = m.group(1)
        iso = date(YEAR, MONTHS[m.group(3)], int(m.group(2))).isoformat()

    lines = body.strip().splitlines()
    meta_line = lines[0] if lines else ""
    rest = "\n".join(lines[1:])

    def grab(label):
        # «**Зал: кардио**» и «Тема: **DNS**» — обе формы встречаются в шапке
        for pattern in (r"\*\*%s:\s*(.+?)\*\*", r"%s:\s*\*\*(.+?)\*\*"):
            m = re.search(pattern % label, meta_line)
            if m:
                return m.group(1).strip()
        return ""

    gym = grab("Зал")
    topic = grab("Тема")
    study = bool(topic)   # в очередь повторения идут только настоящие темы
    if not topic:
        # дни 14 и 15 вместо темы несут одиночную пометку: **Самоэкзамен**, **Финал**
        for chunk in re.findall(r"\*\*(.+?)\*\*", meta_line):
            if not re.match(r"(Зал|Тема|Обед|Ужин):", chunk):
                topic = chunk.strip()
                break

    return {
        "n": n,
        "date": iso,
        "weekday": weekday,
        "gym": gym,
        "topic": topic,
        "study": study,
        "lunch": grab("Обед"),
        "dinner": grab("Ужин"),
        "html": html(strip_old_topics(rest)),
    }


# ─────────────────────────── программа курса ───────────────────────────

# абзацы, привязанные к прежним темам плана: их место занимает программа курса
DROP = re.compile(r"^\*\*(Возврат|Тема|Заход 2|Французский|21:00 · 15 минут)|Слабое место №")


def strip_old_topics(body):
    blocks = re.split(r"\n\s*\n", body.strip())
    return "\n\n".join(b for b in blocks if not DROP.match(b.strip()))


def read_module(path):
    """Заметка курса → номер, код, название и список разделов для проверки вслух."""
    text = path.read_text(encoding="utf-8")
    m = re.match(r"(\d+)_(.+?)_(?:\d|RU)", path.stem)
    n = int(m.group(1)) if m else 0
    code = m.group(2).replace("_", " ") if m else path.stem

    title = ""
    head = re.search(r"^#\s+(.+)$", text, re.M)
    if head:
        title = re.sub(r"\s*-\s*\d{2}\.\d{2}\.\d{4}.*$", "", head.group(1)).strip()
        title = re.sub(r"^[A-Z0-9 ]+\s*-\s*", "", title).strip() or title

    points = re.findall(r"^##\s+(.+)$", text, re.M)
    points = [re.sub(r"\s*\(.*?\)\s*$", "", p).strip() for p in points]

    mod = {"n": n, "code": code, "title": title, "note": path.name, "points": points[:14]}

    # французские формулировки той же темы — для вечернего блока на диктофон
    fr = sorted(COURSE_FR.glob("%02d_*.md" % n)) if COURSE_FR.exists() else []
    if fr:
        text_fr = fr[0].read_text(encoding="utf-8")
        head_fr = re.search(r"^#\s+(.+)$", text_fr, re.M)
        mod["fr"] = re.sub(r"\s*-\s*\d{2}\.\d{2}\.\d{4}.*$", "", head_fr.group(1)).strip() if head_fr else ""
        mod["frPoints"] = [re.sub(r"\s*\(.*?\)\s*$", "", p).strip()
                           for p in re.findall(r"^##\s+(.+)$", text_fr, re.M)][:8]
    return mod


def build_curriculum():
    if not COURSE.exists():
        print("  ! папка курса не найдена: %s" % COURSE)
        return []
    modules = {}
    for path in sorted(COURSE.glob("*.md")):
        mod = read_module(path)
        if mod["n"]:
            modules[mod["n"]] = mod

    out = []
    for i, (title, nums) in enumerate(THEMES, 1):
        picked = [modules[n] for n in nums if n in modules]
        missing = [n for n in nums if n not in modules]
        if missing:
            print("  ! в теме «%s» нет модулей: %s" % (title, missing))
        out.append({"i": i, "title": title, "modules": picked})
    return out


def build_sprint():
    text = read("РАСПОРЯДОК.md")
    intro, h1 = split_headings(text, 1)
    sec = {t: b for t, b in h1}

    skeleton_intro, skeleton_parts = split_headings(sec["Скелет дня"], 2)
    schedule = []
    skeleton_html = [html(skeleton_intro)]
    for title, body in skeleton_parts:
        if title == "Расписание":
            schedule = parse_schedule(body)
            continue
        skeleton_html.append("<h3>%s</h3>%s" % (title, html(body)))

    _, day_parts = split_headings(sec["Дни"], 2)
    days = [parse_day(t, b) for t, b in day_parts]

    # темы дней берутся из программы курса, а не из плана: порядок курсовой
    curriculum = build_curriculum()
    study = [d for d in days if d["study"]]
    if len(study) != len(curriculum):
        print("  ! учебных дней %d, тем %d — часть останется без темы" % (len(study), len(curriculum)))
    for d, theme in zip(study, curriculum):
        d["topic"] = theme["title"]
        d["theme"] = theme["i"]

    checklist = re.findall(r"^- \[ \]\s*(.+)$", sec["Чек-лист дня"], re.M)

    extras = []
    for key, title in [
        ("Если что-то пошло не так", "Если что-то пошло не так"),
        ("До завтра", "Подготовка"),
    ]:
        if key in sec:
            extras.append({"id": slug(key), "title": title, "html": html(sec[key])})

    first = next((d["date"] for d in days if d["date"]), "")
    last = next((d["date"] for d in reversed(days) if d["date"]), "")

    return {
        "id": "sprint-2026-08",
        "title": "Рывок · 3–17 августа",
        "short": "Рывок",
        "kind": "plan",
        "start": first,
        "end": last,
        "note": html(intro.split("\n", 1)[1] if "\n" in intro else ""),
        "skeletonHtml": "".join(x for x in skeleton_html if x),
        "schedule": schedule,
        "checklist": checklist,
        "days": days,
        "extras": extras,
        "curriculum": curriculum,
    }


# ─────────────────────────── рацион и гарниры ───────────────────────────

# Гарниры на выбор: Б / Ж / У / ккал на 100 г сухого или сырого продукта.
# Справочные значения (порядок CIQUAL), отклонение от марки к марке ±5 %.
SIDES = [
    ("Lentilles",        "чечевица",            25.0,  1.0, 50.0, 320),
    ("Riz blanc",        "рис",                  7.0,  0.6, 78.0, 350),
    ("Riz complet",      "рис нешлифованный",    8.0,  2.8, 72.0, 350),
    ("Pâtes",            "макароны",            12.0,  1.5, 72.0, 355),
    ("Semoule couscous", "кускус",              12.0,  1.0, 72.0, 350),
    ("Boulgour",         "булгур",              12.0,  1.5, 76.0, 350),
    ("Sarrasin",         "гречка",              13.0,  3.4, 72.0, 343),
    ("Quinoa",           "киноа",               14.0,  6.0, 64.0, 368),
    ("Pois chiches",     "нут",                 19.0,  6.0, 61.0, 364),
    ("Haricots rouges",  "красная фасоль",      22.0,  1.5, 60.0, 333),
    ("Pommes de terre",  "картофель, сырой",     2.0,  0.1, 17.0,  77),
    ("Patate douce",     "батат, сырой",         1.6,  0.1, 20.0,  86),
]

# Чем добирать белок, если гарнир его недодаёт: белок и калории на порцию.
PROTEIN_FIX = [
    ("банка тунца au naturel, 112 г", 24, 100),
    ("3 яйца", 19, 234),
    ("200 г fromage blanc 0%", 16, 94),
    ("100 г blanc de poulet", 23, 113),
]

# Добавки сверх двух приёмов: то, что он решает съесть по ходу дня.
# Б / Ж / У / ккал на порцию.
EXTRAS = [
    ("pain",   "Ломтик хлеба, 40 г",          3,  1, 19, 100),
    ("fruit",  "Порция фруктов, ~180 г",      1,  0, 16,  70),
    ("thon",   "Банка тунца, 112 г",         24,  1,  0, 100),
    ("oeufs2", "Два яйца",                   13, 11,  1, 156),
    ("fb200",  "Fromage blanc 0%, 200 г",    16,  0,  8,  94),
    ("salade", "Салат с лёгким соусом",       2,  1,  8,  60),
]


def parse_table(text):
    """Строки markdown-таблицы без разделителя и без звёздочек."""
    rows = []
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        cells = [c.strip().strip("*").strip() for c in line.strip("|").split("|")]
        if all(set(c) <= set("-: ") for c in cells):
            continue
        rows.append(cells)
    return rows


def num_or(text, default=0.0):
    m = re.search(r"-?\d+(?:[.,]\d+)?", str(text))
    return float(m.group(0).replace(",", ".")) if m else default


def build_nutrition():
    """Норма дня и два приёма пищи из Рацион.md плюс список гарниров на замену."""
    text = read("Рацион.md")
    sections = {}
    _, h1 = split_headings(text, 1)
    for _, body in h1:
        _, h2 = split_headings(body, 2)
        for title, sub in h2:
            sections[title] = sub

    norm = {}
    for row in parse_table(sections.get("Норма дня", "")):
        key = row[0].lower()
        if "калори" in key:
            norm["kcal"] = row[1]
        elif "белок" in key:
            norm["p"] = row[1]
        elif "жир" in key:
            norm["f"] = row[1]
        elif "углевод" in key:
            norm["c"] = row[1]

    meals = []
    for title in sorted(t for t in sections if t.startswith("Приём")):
        items, total = [], None
        for row in parse_table(sections[title])[1:]:
            entry = {
                "name": row[0], "weight": row[1],
                "p": num_or(row[2]), "f": num_or(row[3]),
                "c": num_or(row[4]), "kcal": num_or(row[5]),
            }
            if row[0].lower().startswith("итого"):
                total = entry
            else:
                items.append(entry)
        meals.append({
            "title": re.sub(r"\s*·.*$", "", title),
            "items": items,
            "total": total,
        })

    side = None
    for meal in meals:
        for i, item in enumerate(meal["items"]):
            if "lentille" in item["name"].lower():
                side = dict(item, meal=meal["title"], idx=i)

    return {
        "norm": norm,
        "meals": meals,
        "side": side,
        "sides": [{"name": n, "ru": ru, "p": p, "f": f, "c": c, "kcal": k} for n, ru, p, f, c, k in SIDES],
        "proteinFix": [{"what": w, "p": p, "kcal": k} for w, p, k in PROTEIN_FIX],
        "extras": [{"id": i, "name": n, "p": p, "f": f, "c": c, "kcal": k}
                   for i, n, p, f, c, k in EXTRAS],
    }


# ─────────────────────────── кухня и справка ───────────────────────────

# Ключи нарочно длинные и проверяются по порядку: коротким «omelette»
# блюдо 25 забрало бы фото блюда 3, а «vinaigrette» — фото соуса у салата из эндивия.
PHOTOS = [
    ("poulet-basquaise", "01-poulet-basquaise"),
    ("piperade", "02-piperade"),
    ("fines-herbes", "03-omelette-fines-herbes"),
    ("ratatouille", "04-ratatouille"),
    ("saumon", "05-saumon-papillote"),
    ("crevettes", "06-crevettes-ail-persil"),
    ("salade-de-lentilles", "07-salade-lentilles"),
    ("escalope", "08-escalope-moutarde"),
    ("vinaigrette-maison", "09-vinaigrette-maison"),
    ("poulet-roti", "10-poulet-roti"),
    ("pot-au-feu", "11-pot-au-feu"),
    ("blanquette", "12-blanquette-dinde"),
    ("hachis", "13-hachis-parmentier"),
    ("cabillaud", "14-cabillaud-provencale"),
    ("poulet-au-citron", "15-poulet-citron-olives"),
    ("truite", "16-truite-amandes"),
    ("salade-nicoise", "17-salade-nicoise"),
    ("oignon", "18-soupe-oignon"),
    ("potage-parmentier", "19-potage-parmentier"),
    ("pistou", "20-soupe-pistou"),
    ("cocotte", "21-oeufs-cocotte"),
    ("quiche", "22-quiche-poireaux"),
    ("chou-fleur", "23-gratin-chou-fleur"),
    ("tian", "24-tian-legumes"),
    ("champignons", "25-omelette-champignons"),
]


def photo_for(title):
    s = slug(title)
    for key, name in PHOTOS:
        if key in s:
            return name
    return ""


# Категории кухни. Дневная потребность стоит на категории, а не на продукте:
# план требует 400 г белкового в обед и 800 г овощей за день, а чем именно
# их закрыть — курицей или лососем, помидорами или кабачками — решает человек.
CATEGORIES = [
    ("meat",  "Мясо и рыба",     "г",  400),
    ("dairy", "Молочное и яйца", "",     0),
    ("grain", "Крупы и гарниры", "г",  100),
    ("veg",   "Овощи",           "г",  800),
    ("fruit", "Фрукты",          "г",  180),
    ("bread", "Хлеб и бакалея",  "",     0),
    ("fat",   "Масло",           "мл",  30),
    ("drink", "Напитки",         "",     0),
]

# Продукты: категория, единица, дневной расход там, где он однозначен,
# и ключевые слова, по которым строка списка покупок ложится в нужный продукт.
PRODUCTS = [
    ("poulet",     "Курица, грудка",      "meat",  "г",  0, ["blanc de poulet", "курин", "курица"]),
    ("boeuf",      "Говядина",            "meat",  "г",  0, ["boeuf", "говядин"]),
    ("dinde",      "Индейка",             "meat",  "г",  0, ["dinde", "индейк"]),
    ("saumon",     "Лосось",              "meat",  "г",  0, ["saumon", "лосось"]),
    ("cabillaud",  "Треска, хек",         "meat",  "г",  0, ["cabillaud", "colin", "треск"]),
    ("crevettes",  "Креветки",            "meat",  "г",  0, ["crevette", "креветк"]),
    ("thon",       "Тунец в банке",       "meat",  "шт", 0, ["thon", "тунец"]),

    ("oeufs",      "Яйца",                "dairy", "шт", 6, ["oeuf", "œuf", "яйц"]),
    ("fromage",    "Fromage blanc 0%",    "dairy", "г",  500, ["fromage blanc"]),
    ("skyr",       "Скир",                "dairy", "г",  0, ["skyr", "скир"]),

    ("lentilles",  "Чечевица",            "grain", "г",  0, ["lentille", "чечевиц"]),
    ("riz",        "Рис",                 "grain", "г",  0, ["riz", "рис"]),
    ("pates",      "Макароны",            "grain", "г",  0, ["pates", "макарон"]),
    ("semoule",    "Кускус",              "grain", "г",  0, ["semoule", "кускус"]),
    ("sarrasin",   "Гречка",              "grain", "г",  0, ["sarrasin", "гречк"]),
    ("boulgour",   "Булгур",              "grain", "г",  0, ["boulgour", "булгур"]),

    ("surgeles",   "Овощи замороженные",  "veg",   "г",  0, ["surgel", "заморож"]),
    ("tomates",    "Помидоры",            "veg",   "г",  0, ["помидор", "tomate"]),
    ("poivrons",   "Перец",               "veg",   "г",  0, ["перец", "poivron"]),
    ("oignons",    "Лук",                 "veg",   "г",  0, ["лук", "oignon"]),
    ("ail",        "Чеснок",              "veg",   "шт", 0, ["чеснок"]),
    ("carottes",   "Морковь",             "veg",   "г",  0, ["морков", "carotte"]),
    ("courgettes", "Кабачки",             "veg",   "г",  0, ["кабач", "courgette"]),
    ("aubergine",  "Баклажан",            "veg",   "шт", 0, ["баклажан", "aubergine"]),
    ("chou",       "Капуста",             "veg",   "шт", 0, ["капуст", "chou"]),
    ("concombre",  "Огурцы",              "veg",   "г",  0, ["огурц", "concombre"]),
    ("salade",     "Салат зелёный",       "veg",   "шт", 0, ["салат зел"]),
    ("haricots",   "Haricots verts",      "veg",   "г",  0, ["haricots verts", "фасоль"]),

    ("pasteque",   "Арбуз",               "fruit", "г",  0, ["арбуз"]),
    ("abricots",   "Абрикосы",            "fruit", "г",  0, ["абрикос", "abricot"]),
    ("prunes",     "Сливы",               "fruit", "г",  0, ["слив", "prune"]),
    ("peches",     "Персики, нектарины",  "fruit", "г",  0, ["персик", "нектарин"]),
    ("pommes",     "Яблоки",              "fruit", "г",  0, ["яблок", "pomme"]),
    ("fruits",     "Фрукты, без разбора", "fruit", "г",  0, ["фрукт"]),

    ("pain",       "Хлеб цельнозерновой", "bread", "г",  0, ["pain complet", "хлеб"]),
    ("epices",     "Специи",              "bread", "",   0, ["специи"]),

    ("huile",      "Оливковое масло",     "fat",   "мл", 0, ["huile", "оливков", "масло"]),
    ("colza",      "Масло colza",         "fat",   "мл", 0, ["colza"]),

    ("eau",        "Вода",                "drink", "уп", 0, ["вода", "eau"]),
]

UNITS = {"кг": 1000, "г": 1, "л": 1000, "мл": 1, "шт": 1}


# В списке пишут «1 бутылка» и «1 буханка» — это привычнее, чем граммы.
PACKS = {"бутылк": 750, "буханк": 500}


def parse_qty(amount, name):
    """«4,25 кг» → 4250; «5 упаковок» при «Œufs ×20» в названии → 100; «1 буханка 500 г» → 500."""
    masses = re.findall(r"(\d+(?:[.,]\d+)?)\s*(кг|мл|г|л)\b", amount)
    if masses:
        value, unit = masses[-1]
        return num_or(value) * UNITS[unit], "масса"

    for word, size in PACKS.items():
        if word in amount.lower():
            m = re.match(r"\s*(\d+)", amount)
            return (int(m.group(1)) if m else 1) * size, "масса"

    count = re.match(r"\s*(\d+(?:[.,]\d+)?)", amount)
    if not count:
        return None, None
    pack = re.search(r"×\s*(\d+)", name)
    return num_or(count.group(1)) * (int(pack.group(1)) if pack else 1), "штуки"


def product_for(name):
    low = name.lower()
    for pid, _, _, _, _, keys in PRODUCTS:
        if any(k in low for k in keys):
            return pid
    return None


# Даты походам не назначаются: владелец сам решает, когда идти, и добавляет закуп в день.
TRIPS = ["Большой закуп", "Свежее", "Добор"]


def build_shopping():
    """Списки покупок: что взять и сколько чего это добавляет в запас."""
    by_id = {p[0]: p for p in PRODUCTS}
    out = []
    for title, body in split_headings(read("Закуп.md"), 1)[1]:
        if title not in TRIPS:
            continue

        items, names = [], []
        for row in parse_table(body):
            if len(row) < 2 or row[0].lower().startswith(("что", "итого")):
                continue
            names.append(row[0])
            pid = product_for(row[0])
            if not pid:
                continue
            qty, kind = parse_qty(row[1], row[0])
            unit = by_id[pid][3]
            if qty is None or (kind == "штуки") != (unit in ("шт", "уп")):
                print("  ! «%s | %s» не пересчитывается в %s, в запас не пойдёт" % (row[0], row[1], unit))
                continue
            items.append({"id": pid, "name": row[0], "amount": row[1], "product": pid, "qty": qty})

        out.append({"id": slug(title), "title": title, "html": html(body),
                    "items": items, "names": names})

    missing = [t for t in TRIPS if t not in [x["title"] for x in out]]
    if missing:
        print("  ! в Закуп.md нет разделов: %s" % ", ".join(missing))
    return out


def build_stock():
    return {
        "cats": [{"id": i, "name": n, "unit": u, "perDay": d} for i, n, u, d in CATEGORIES],
        # ключевые слова нужны и приложению: в плане продукт зовётся Œufs,
        # а в каталоге «Яйца», по названию их не сопоставить
        "items": [{"id": p, "name": n, "cat": c, "unit": u, "perDay": d, "keys": k}
                  for p, n, c, u, d, k in PRODUCTS],
    }


def build_doc(filename, doc_id, title, photos=False):
    """Документ → плоский список разделов в порядке текста.

    photos ставится только основному файлу кухни: фото есть у девяти его блюд,
    и без флага «Omelette aux champignons» из второго файла забрала бы чужую картинку.
    """
    text = read(filename)
    intro, h1 = split_headings(text, 1)
    sections = []
    for h1_title, h1_body in h1:
        h2_intro, h2_parts = split_headings(h1_body, 2)
        sections.append({
            "id": slug(h1_title),
            "level": 1,
            "title": h1_title,
            "html": html(h2_intro),
        })
        for h2_title, h2_body in h2_parts:
            sections.append({
                "id": slug(h1_title + "-" + h2_title),
                "level": 2,
                "title": h2_title,
                "html": html(h2_body),
                "photo": photo_for(h2_title) if photos else "",
            })
    return {"id": doc_id, "title": title, "html": html(intro), "sections": sections}


DISH = re.compile(r"^(\d+\s*·|Sauce\b|Gremolata|Déglaçage)", re.I)

# Главный овощ салата: по нему видно, собирается ли салат из того, что куплено.
SALAD_MAIN = [
    ("carottes-rapees",             "морковь",          ["морков"]),
    ("salade-verte",                "зелёный салат",    ["салат зел", "салат"]),
    ("concombres-au-fromage-blanc", "огурцы",           ["огурц"]),
    ("salade-de-tomates",           "помидоры",         ["помидор"]),
    ("haricots-verts-en-salade",    "зелёная фасоль",   ["haricots verts", "фасоль зел"]),
    ("salade-de-chou-blanc",        "белокочанная капуста", ["капуст"]),
    ("endives-a-la-vinaigrette",    "эндивий",          ["endive", "эндиви"]),
    ("salade-de-courgettes-crues",  "кабачки",          ["кабач"]),
]


def tag_salads(recipes, shopping):
    """Каждому салату — главный овощ и списки закупа, где он есть.

    Без этого салат выбирается вслепую: непонятно, собирается ли он
    из того, что куплено, или овощ надо ещё докупить.
    """
    by_id = {r["id"]: r for r in recipes}
    for sid, main, keys in SALAD_MAIN:
        r = by_id.get(sid)
        if not r:
            print("  ! салата %s нет среди рецептов, овощ не привязан" % sid)
            continue
        r["main"] = main
        r["trips"] = [
            t["id"] for t in shopping
            if any(any(k in name.lower() for k in keys) for name in t["names"])
        ]
        if not r["trips"]:
            print("  ! «%s»: %s не входит ни в один список закупа" % (r["title"], main))


def build_recipes(docs):
    """Индекс блюд: карточки, на которые ссылается день. Фото есть только у кухни."""
    out = []
    for doc in docs:
        if doc["id"] not in ("cuisine", "cuisine2", "salades"):
            continue
        group = ""
        for s in doc["sections"]:
            if s["level"] == 1:
                group = re.sub(r"^База\s*·\s*", "", s["title"]).strip()
                if "vinaigrette" in slug(s["title"]) and s["html"]:
                    out.append({
                        "id": slug(s["title"]), "title": group, "group": "База",
                        "doc": doc["id"], "sec": s["id"],
                        "photo": photo_for(s["title"]), "html": s["html"],
                    })
                continue
            if not DISH.match(s["title"]):
                continue
            name = re.sub(r"^\d+\s*·\s*", "", s["title"]).strip()
            out.append({
                "id": slug(name), "title": name, "group": group,
                "doc": doc["id"], "sec": s["id"],
                "photo": s["photo"],          # проставлен в build_doc только тем документам, у кого есть фото
                "html": s["html"],
            })
    return out


def main():
    docs = [
        # порядок = порядок в приложении; закуп первым, он нужен чаще всего
        build_doc("Закуп.md", "achats", "Закуп"),
        build_doc("Рацион.md", "racion", "Рацион"),
        build_doc("Французская_кухня.md", "cuisine", "Французская кухня", photos=True),
        build_doc("Французская_кухня_2.md", "cuisine2", "Ещё блюда", photos=True),
        build_doc("Салаты_и_соусы.md", "salades", "Салаты и соусы"),
        build_doc("Вкус.md", "gout", "Вкус"),
        build_doc("Что_это_значит.md", "glossaire", "Что это значит"),
    ]

    shopping = build_shopping()
    recipes = build_recipes(docs)
    tag_salads(recipes, shopping)
    sprint = build_sprint()
    curriculum = sprint.pop("curriculum")           # программа общая, а не свойство рывка

    data = {
        "v": 1,
        "generated": date.today().isoformat(),
        "periods": [sprint],
        "curriculum": curriculum,
        "nutrition": build_nutrition(),
        "stock": build_stock(),
        "shopping": shopping,
        "recipes": recipes,
        "docs": docs,
    }

    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")

    p = data["periods"][0]
    size = OUT.stat().st_size / 1024
    print("периодов: %d, дней: %d, чек-лист: %d пунктов, расписание: %d строк"
          % (len(data["periods"]), len(p["days"]), len(p["checklist"]), len(p["schedule"])))
    print("блюд: %d (с фото %d), документов: %d"
          % (len(data["recipes"]), sum(1 for r in data["recipes"] if r["photo"]), len(docs)))
    print("закуп: %s" % ", ".join("%s (%d позиций в запас)" % (x["title"], len(x["items"])) for x in data["shopping"]))

    n = data["nutrition"]
    print("рацион: норма %s ккал, приёмов %d, гарнир по плану %s, вариантов замены %d"
          % (n["norm"].get("kcal", "?"), len(n["meals"]),
             n["side"]["name"] if n["side"] else "не найден", len(n["sides"])))

    mods = sum(len(t["modules"]) for t in curriculum)
    print("программа: %d тем, %d модулей, %d пунктов для проверки"
          % (len(curriculum), mods, sum(len(m["points"]) for t in curriculum for m in t["modules"])))
    print("%s — %.1f КБ" % (OUT.name, size))
    for d in p["days"]:
        if not (d["date"] and d["gym"] and d["topic"]):
            print("  ! день %s разобран не полностью: %s" % (d["n"], d))


if __name__ == "__main__":
    main()
