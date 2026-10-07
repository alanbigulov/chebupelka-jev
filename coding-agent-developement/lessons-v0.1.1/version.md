# Паспорт учебного снимка v0.1.1

В v0.1.1 исполняемая часть проекта и её Python-окружение выделены в `agent/`. Исходник агента перенесён без изменения байтов. Выпуск добавляет структуру, сохранение исторических снимков и две локальные проверки поведения.

| Поле | Значение снимка |
|---|---|
| Проект | `chebupelkajev` |
| Версия Python-проекта | `0.1.1` |
| Git-тег выпуска | `v0.1.1` |
| Полный SHA коммита | Получить после создания тега командой `git rev-parse 'v0.1.1^{}'` |
| Исходный файл | `agent/chebupelkajev.py` |
| Требования проекта | `agent/pyproject.toml` |
| Зафиксированные зависимости | `agent/uv.lock` |
| Минимальный Python | `requires-python = ">=3.10"` |
| Выбранная ветка Python | `3.14` в `agent/.python-version` |
| Проверенный Python выпуска | CPython `3.14.7` в `agent/.venv/` |
| Requests в lock-файле | `2.34.2` |
| Рабочая директория команд | `agent/` |
| Локальное окружение | `agent/.venv/`, исключено из Git |
| Модель в исходнике | `deepseek-flash` |
| Ключ | `DEEPSEEK_API_KEY` в окружении процесса, значение в Git не хранится |

## Где смотреть файлы

Локальные ссылки открывают текущую рабочую копию. Ссылки выпуска открывают файлы тега v0.1.1 после его публикации. Для строгой привязки сначала разреши тег в полный SHA и используй этот SHA в Git или URL GitHub.

| Файл | Рабочая копия | Снимок v0.1.1 |
|---|---|---|
| Исходник | [chebupelkajev.py](../../agent/chebupelkajev.py) | [По тегу](https://github.com/alanbigulov/chebupelka-jev/blob/v0.1.1/agent/chebupelkajev.py) |
| Требования | [pyproject.toml](../../agent/pyproject.toml) | [По тегу](https://github.com/alanbigulov/chebupelka-jev/blob/v0.1.1/agent/pyproject.toml) |
| Зависимости | [uv.lock](../../agent/uv.lock) | [По тегу](https://github.com/alanbigulov/chebupelka-jev/blob/v0.1.1/agent/uv.lock) |
| Ветка Python | [.python-version](../../agent/.python-version) | [По тегу](https://github.com/alanbigulov/chebupelka-jev/blob/v0.1.1/agent/.python-version) |
| Проверки | [test_agent.py](../../agent/tests/test_agent.py) | [По тегу](https://github.com/alanbigulov/chebupelka-jev/blob/v0.1.1/agent/tests/test_agent.py) |

Полный SHA собственного коммита выпуска нельзя вписать в файл, который входит в этот же коммит. Изменение файла изменило бы сам SHA. Поэтому паспорт содержит тег и команду его разрешения.

## Проверка снимка и окружения

После создания тега выполняй из корня репозитория:

```bash
git rev-parse 'v0.1.1^{}'
git show v0.1.1:agent/pyproject.toml
git show v0.1.1:agent/.python-version
git show v0.1.1:agent/chebupelkajev.py
```

Для текущей рабочей копии начни из корня репозитория. Первая команда переходит в `agent/`; последующие команды выполняются там:

```bash
cd agent
uv sync --locked
uv run --locked python --version
uv run --locked python -c 'import sys, requests; print(sys.executable); print(requests.__version__)'
uv run --locked python -m unittest discover -s tests -v
```

Путь `sys.executable` должен указывать на `agent/.venv/`. Фактический патч Python показывает `python --version`; значение `3.14` в настройке не закрепляет конкретный патч. `--locked` требует согласованности `pyproject.toml` и `uv.lock`.

## Подтверждённое поведение и границы

| Проверка | Что проверяет |
|---|---|
| Сравнение исходников v0.1.0 и `agent/chebupelkajev.py` | Перенос сохранил байты программы |
| Обычный ответ | Агент принимает синтетический ответ и завершает цикл без инструмента |
| Один вызов `pwd` и финальный ответ | Результат команды и `tool_call_id` входят во второй запрос, затем агент завершает цикл |

Ответы API для тестов подготовлены вручную в `agent/tests/fixtures/`. Тесты подменяют `requests.post`; реальный DeepSeek не вызывается. Сценарий `pwd` допускает одну локальную команду через проверяющий перехватчик.

При подготовке выпуска оба локальных теста прошли в новом окружении. Соседний worktree v0.1.0 подготовлен через `uv sync --locked --offline` и отдельно проверен реальным `pwd` и двухходовым циклом с подставными HTTP-ответами. Его рабочие файлы остались чистыми. Это проверка восстановленного Python-кода, а не повторный облачный тест.

Покрытие ограничено этими двумя сценариями. Обработка нескольких инструментов, HTTP-ошибок, некорректного JSON и лимита ходов остаётся в [плане развития](../development-roadmap.md). Подготовка этого выпуска не повторяет облачную проверку первой сессии.

Для сравнения со старой версией используй [паспорт v0.1.0](../lessons-v0.1.0/version.md) и отдельный worktree. Ключи API не сохраняются в паспортах, fixtures или Git.

## Связанные материалы

- [Урок о структуре и снимках](01-structure-and-snapshots.md).
- [Карта проекта](../project-structure.md).
- [План развития](../development-roadmap.md).
- [Навигация обучения](../README.md).
- [Правила версий](../../VERSIONING.md).
