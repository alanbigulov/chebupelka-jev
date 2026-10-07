# Паспорт учебного снимка v0.1.2

В v0.1.2 организована совместная очередь разработки и обучения в GitHub. Выпуск добавляет правила трекинга, подробный урок и обновлённые метаданные версии. Логика агента, зависимости и два существующих локальных теста сохранены.

| Поле | Значение снимка |
|---|---|
| Проект | `chebupelkajev`, репозиторий `alanbigulov/chebupelka-jev` |
| Версия Python-проекта | `0.1.2` |
| Git-тег выпуска | `v0.1.2` |
| Полный SHA коммита | После создания тега получить командой `git rev-parse 'v0.1.2^{}'` |
| Исходник агента | `agent/chebupelkajev.py` |
| Требования и версия | `agent/pyproject.toml` |
| Зафиксированные зависимости | `agent/uv.lock` |
| Минимальный Python | `requires-python = ">=3.10"` |
| Выбранная ветка Python | `3.14` в `agent/.python-version` |
| Проверенный интерпретатор | CPython `3.14.7` в `agent/.venv/` |
| Requests в lock-файле | `2.34.2`, версия зависимости не изменена |
| Каталог Python-команд | `agent/` |
| Локальное окружение | `agent/.venv/`, исключено из Git |
| Модель в исходнике | `deepseek-flash` |
| Ключ агента | `DEEPSEEK_API_KEY` в окружении процесса; значение не входит в снимок |
| Основной трекер | [Публичный GitHub Project № 4](https://github.com/users/alanbigulov/projects/4) и issues репозитория |

## Файлы рабочей копии и выпуска

Локальные ссылки открывают текущие файлы. Ссылки по тегу открывают снимок v0.1.2 после публикации тега. Для привязки к конкретному коммиту разреши тег в SHA и замени `v0.1.2` в URL этим SHA.

| Файл | Рабочая копия | Снимок v0.1.2 |
|---|---|---|
| Исходник | [chebupelkajev.py](../../agent/chebupelkajev.py) | [По тегу](https://github.com/alanbigulov/chebupelka-jev/blob/v0.1.2/agent/chebupelkajev.py) |
| Метаданные | [pyproject.toml](../../agent/pyproject.toml) | [По тегу](https://github.com/alanbigulov/chebupelka-jev/blob/v0.1.2/agent/pyproject.toml) |
| Зависимости | [uv.lock](../../agent/uv.lock) | [По тегу](https://github.com/alanbigulov/chebupelka-jev/blob/v0.1.2/agent/uv.lock) |
| Ветка Python | [.python-version](../../agent/.python-version) | [По тегу](https://github.com/alanbigulov/chebupelka-jev/blob/v0.1.2/agent/.python-version) |
| Проверки | [test_agent.py](../../agent/tests/test_agent.py) | [По тегу](https://github.com/alanbigulov/chebupelka-jev/blob/v0.1.2/agent/tests/test_agent.py) |
| Правила трекинга | [project-tracking.md](../project-tracking.md) | [По тегу](https://github.com/alanbigulov/chebupelka-jev/blob/v0.1.2/coding-agent-developement/project-tracking.md) |
| Урок | [01-github-project-tracking.md](01-github-project-tracking.md) | [По тегу](https://github.com/alanbigulov/chebupelka-jev/blob/v0.1.2/coding-agent-developement/lessons-v0.1.2/01-github-project-tracking.md) |

Паспорт не содержит собственный будущий SHA. Если вписать SHA коммита в файл этого же коммита, содержимое изменится и Git вычислит другой SHA.

## Проверка снимка

После публикации тега выполни из корня репозитория:

```bash
git rev-parse 'v0.1.2^{}'
git show v0.1.2:agent/pyproject.toml
git show v0.1.2:agent/.python-version
git diff v0.1.1 v0.1.2 -- agent/chebupelkajev.py agent/tests
```

Последняя команда должна дать пустой diff: выпуск не меняет программу и существующие тесты. Изменения версии в `pyproject.toml` и записи локального проекта в `uv.lock` проверяются отдельно от версий зависимостей.

Для подготовки окружения и локальных проверок начни из корня, затем перейди в `agent/`:

```bash
cd agent
uv sync --locked
uv run --locked python --version
uv run --locked python -c 'import requests; print(requests.__version__)'
uv run --locked python -m unittest discover -s tests -v
```

`3.14` в настройке выбирает ветку интерпретатора. Фактический патч показывает `python --version`; для выбора проверенного патча можно использовать `uv sync --locked --python 3.14.7`. При восстановлении выпуска не обновляй lock-файл.

## Что проверено и что осталось открытым

| Проверка | Граница результата |
|---|---|
| Project, связь с репозиторием, поля и представления | Конфигурация прочитана через GitHub API; визуальная проверка в браузере не выполнялась |
| Первоначальная очередь | Созданы 14 issues и 14 соответствующих project items; три доски показывают одну очередь |
| Обычный ответ агента | Существующий тест с синтетическим HTTP-ответом проверяет завершение без инструмента |
| Один `pwd` и финальный ответ | Существующий тест проверяет результат команды и `tool_call_id` во втором запросе |
| Сохранность программы и тестов | Сравнение с v0.1.1 проверяет отсутствие изменений изучаемой реализации |

Тесты подменяют `requests.post` и не обращаются к DeepSeek. Во время этого выпуска облачные запросы не выполнялись и новые тестовые сценарии не добавлялись. Настройка GitHub обращается к GitHub API, что не является вызовом модели агента.

EDU-06 остаётся частично выполненной. Два базовых сценария существуют со времени v0.1.1; несколько инструментов, ошибки, некорректные аргументы и предел ходов ещё требуют отдельных проверок. EDU-01, EDU-02, EDU-03 и оставшаяся часть EDU-06 перенесены в предварительную v0.1.3.

## Что сохраняет тег

Тег фиксирует исходники, метаданные, урок и записанные правила трекинга. GitHub Issues, Project, их статусы и milestone остаются изменяемыми внешними объектами. Открыв старый урок, читатель видит историческое объяснение; актуальное состояние задачи следует читать в GitHub.

v0.1.2 включает учебную задачу [#13](https://github.com/alanbigulov/chebupelka-jev/issues/13) и приёмку [#14](https://github.com/alanbigulov/chebupelka-jev/issues/14). Порядок завершения описан в уроке: проверка материалов, публикация коммита и тега, сверка SHA, закрытие issues и синхронизация Status, затем закрытие milestone. Наличие паспорта само по себе не подтверждает выполнение этих шагов.

Старые теги v0.1.0 и v0.1.1 сохраняются. Отдельные локальные окружения и игнорируемый контекст передачи сессии не входят в Git-снимок. Имя облачной модели `deepseek-flash` не фиксирует её внутреннюю версию или ответы.

## Связанные материалы

- [Подробный урок о GitHub-трекинге](01-github-project-tracking.md).
- [Навигация обучения](../README.md), [учебный roadmap](../development-roadmap.md) и [карта структуры](../project-structure.md).
- [README проекта](../../README.md), [README агента](../../agent/README.md).
- [Правила версий](../../VERSIONING.md) и [история изменений](../../CHANGELOG.md).
- [Паспорт v0.1.0](../lessons-v0.1.0/version.md) и [паспорт v0.1.1](../lessons-v0.1.1/version.md).
