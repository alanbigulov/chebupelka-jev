# chebupelkajev

Учебный кодинговый агент на Python и курс по его устройству. Агент обращается к DeepSeek, выполняет запрошенные моделью команды и возвращает их результаты в историю сообщений.

Проект основан на [chebupelka Алексея Голобурдина](https://github.com/alexey-goloburdin/chebupelka). Исходная история Git сохранена. Репозиторий развивается самостоятельно под именем `chebupelkajev` для изучения и последовательного улучшения агентов.

Текущий выпуск: **v0.1.1**. Код и обучение разделены по каталогам; логика агента осталась прежней. Изменилось место запуска: теперь Python-команды выполняются из `agent/`.

## Выбери маршрут

| Цель | Документ |
|---|---|
| Установить и запустить текущего агента | [agent/README.md](agent/README.md) |
| Пройти обучение | [Учебная навигация](coding-agent-developement/README.md) |
| Понять структуру и причины решений | [project-structure.md](coding-agent-developement/project-structure.md) |
| Выбрать следующую доработку | [development-roadmap.md](coding-agent-developement/development-roadmap.md) |
| Восстановить конкретный выпуск | [VERSIONING.md](VERSIONING.md) |
| Посмотреть реализованные изменения | [CHANGELOG.md](CHANGELOG.md) |

## Быстрый старт

В новой директории:

```bash
git clone https://github.com/alanbigulov/chebupelka-jev.git
cd chebupelka-jev/agent
uv sync --locked
```

Нужен современный [uv](https://docs.astral.sh/uv/). Он выбирает Python 3.14 из `.python-version` и создаёт `agent/.venv`. На машине с двумя экземплярами `uv` используй проверенный `"$(brew --prefix)/bin/uv"` вместо обычного `uv`.

Ввод ключа DeepSeek в **zsh**:

```zsh
read -rs "DEEPSEEK_API_KEY?Вставь ключ DeepSeek и нажми Enter: "
printf '\n'
export DEEPSEEK_API_KEY
```

```bash
uv run python chebupelkajev.py "Вызови инструмент bash ровно один раз с командой pwd. Затем сообщи текущую директорию и заверши работу. Файлы не изменяй."
```

Ключ действует в текущей сессии терминала, не записывается в исходники и не читается из `.env` автоматически. Проверки без ключа и без обращения к API выполняются из `agent/`:

```bash
uv run python -m unittest discover -s tests -v
```

> [!WARNING]
> Агент выполняет shell-команды с правами пользователя, без подтверждения и изоляции. Учебный worktree не ограничивает эти права. Облачные запросы платные; текущий предел составляет 1000 ходов.

## Два модуля в одном репозитории

```text
chebupelka-jev/
├── README.md, VERSIONING.md, CHANGELOG.md    общие документы
├── agent/                                  исполняемый Python-проект
│   ├── chebupelkajev.py
│   ├── pyproject.toml, uv.lock, .python-version
│   ├── README.md
│   └── tests/fixtures/
└── coding-agent-developement/               учебные материалы
    ├── README.md, project-structure.md
    ├── development-roadmap.md
    ├── lessons-v0.1.0/
    └── lessons-v0.1.1/
```

Реализация: [agent/chebupelkajev.py](agent/chebupelkajev.py). Прямая зависимость: `requests`. Внутренние функции не разделялись на новые модули.

```text
Задача → agent_loop() → call_llm() → DeepSeek
              ^                         |
              |                  текст или tool_calls
              |                         |
              +── результат ← call_tool() → run_bash()
```

## Что изменилось в v0.1.1

- Python-файл, метаданные, lock-файл и выбранная версия Python перенесены в `agent/`.
- Создано отдельное окружение `agent/.venv`; прежнее корневое окружение сохранено локально для отката.
- Добавлены две локальные проверки с синтетическими ответами API: текстовый ответ и один `pwd` с последующим завершением.
- Уроки получили паспорта версий. Ссылки уроков v0.1.0 на код и настройки закреплены за прежним снимком.
- Добавлены журнал структуры и урок о разделении проекта, тегах и worktree.
- На машине создан отдельный worktree `../chebupelkajev-v0.1.0` с собственным окружением. Эта локальная папка не входит в Git-коммит.

## Развернуть старую версию

Из корня основного репозитория, если соседней папки ещё нет:

```bash
git worktree add --detach ../chebupelkajev-v0.1.0 v0.1.0
cd ../chebupelkajev-v0.1.0
uv sync --locked
```

В снимке v0.1.0 исходник находится в корне. В v0.1.1 он находится в `agent/`. Для уже созданной папки повторный `worktree add` не нужен: перейди в неё и следуй [паспорту v0.1.0](coding-agent-developement/lessons-v0.1.0/version.md).

Тег сохраняет код и зависимости, но не фиксирует облачную модель под именем `deepseek-flash`. Подробности восстановления и ограничений описаны в [уроке о снимках](coding-agent-developement/lessons-v0.1.1/01-structure-and-snapshots.md).

Продолжай с [исходных трёх уроков v0.1.0](coding-agent-developement/README.md) и затем с пакета v0.1.1. Исходное [видео автора](https://www.youtube.com/watch?v=H7FSTj4x4xQ) объясняет минимальную реализацию, от которой начался проект.
