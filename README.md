# Fish Zone — спиннинг-блог

SEO-блог для рыбаков-спиннингистов. Статический сайт на GitHub Pages, домен `www.fish-zone.ru`. Текст/SEO, без видео. Ориентир — Яндекс.

## Структура

```
fish-zone/
├── build.py            # сборщик Markdown → SEO-HTML
├── content/*.md        # статьи (frontmatter + Markdown)
├── templates/          # шаблоны страниц (blog-post, blog-index)
├── static/             # статика (favicon и т.п.) → копируется в output
├── output/             # собранный сайт → GitHub Pages
├── CNAME               # www.fish-zone.ru
└── requirements.txt
```

## Команды

```bash
python3 build.py                  # собрать все статьи
python3 build.py --check          # проверить статьи
python3 build.py --new "Заголовок" # создать новую статью
python3 build.py --watch          # dev-режим
```

## Категории

| slug | Рубрика |
|---|---|
| `tackle` | Снасти |
| `fish` | Виды рыб |
| `technique` | Техники ловли |
| `lure` | Приманки |
| `rig` | Оснастка и узлы |
| `season` | Сезон и места |
| `rating` | Выбор и рейтинги |

## Конвейер статьи

`IDEA → DRAFT → HUMANIZE → CRITIC → BUILD → DEPLOY`

- Гуманизатор/критик: переиспользуются из `/Users/igor/project/blog/`
- Деплой: `output/` → ветка Pages → https://www.fish-zone.ru

## Питфоллы

- НЕ использовать `build.py --deploy` (нет такого) — собираем в output, пушим ветку Pages
- Длинное тире (—) — AI-маркер, избегать
- Категории фиксированы в `build.py` (CATEGORY_NAMES)
