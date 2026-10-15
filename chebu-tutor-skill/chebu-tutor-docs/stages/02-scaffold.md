# Этап 2. Каркас

## Цель

Создать каркас, который нужен каждому следующему этапу: `chebu-tutor-skill/skill.json` с версией и требованиями, CHANGELOG навыка и каталог тестов с первым тестом. После этапа у навыка есть источник версии и команда тестов. Адаптеров и текста навыка ещё нет.

## Входные условия

| Условие | Команда | Ожидаемый результат |
|---|---|---|
| Этап 1 готов | Строка этапа 1 в [progress.md](../progress.md) | Статус «Готово» |
| Рабочее дерево чистое | `git status --short` | Пустой вывод |
| Протокол работает | `python3 -m unittest discover -s .handoff -p 'test_*.py'` | `OK`, 63 теста |
| Каркаса ещё нет | `ls chebu-tutor-skill/skill.json` | Ошибка: файла нет |

## Прочитать

- [architecture.md](../architecture.md), разделы «Структуры данных» и «Раскладка каталога».
- [versioning.md](../versioning.md), разделы «Источник номера» и «История изменений».
- [verification.md](../verification.md), строки этапа 2 в таблице дефектов.

## Шаги

1. Напиши тест до кода: `chebu-tutor-skill/tests/test_skill_json.py`, только стандартная библиотека и `unittest`. Тест читает `skill.json` и проверяет: `name` равно `chebu-tutor`, `version` соответствует `^\d+\.\d+\.\d+$`, `requires.handoff_schema` равно числу из строки «Схема» в [TEMPLATE.md](../../../.handoff/TEMPLATE.md), `requires.chebu_min_version` соответствует тому же формату.
2. Запусти `python3 -m unittest discover -s chebu-tutor-skill/tests -v`. Тест должен упасть, потому что `skill.json` нет. Процитируй сообщение об ошибке.
3. Создай `chebu-tutor-skill/skill.json` в форме из architecture.md с версией `0.1.0`. Запусти тесты. Все должны пройти.
4. Внеси дефекты по одному: версия `0.1`, затем `handoff_schema` равна 3. После каждого дефекта тест должен упасть и назвать поле. Процитируй оба сообщения и верни файл.
5. Создай `chebu-tutor-skill/CHANGELOG.md`: заголовок, ссылка на versioning.md, раздел `[Unreleased]` с записью о каркасе.
6. Обнови `chebu-tutor-skill/README.md`: статус «этап 2: каркас» и команду тестов навыка.
7. Добавь в раздел 4 [project-structure.md](../../../coding-agent-developement/project-structure.md) строки для `skill.json`, CHANGELOG навыка и тестов навыка.

## Критерий готовности

- `python3 -m unittest discover -s chebu-tutor-skill/tests -v` завершается `OK`, тестов не меньше четырёх.
- Оба внесённых дефекта дали падение с именем поля, сообщения процитированы в отчёте сессии.
- `python3 -m unittest discover -s .handoff -p 'test_*.py'` завершается `OK`, 63 теста.
- Каталогов `chebu-tutor-skill/source/` и `chebu-tutor-skill/tools/` нет.

## Что записать

- Строку этапа 2 в [progress.md](../progress.md).
- Запись в `[Unreleased]` CHANGELOG навыка.
- Строку журнала решений, если форма `skill.json` отличается от architecture.md.

## Границы

- Канонический текст, проверка флага, генератор и адаптеры на этом этапе не создаются.
- `handoff.py` не меняется.
- Версия остаётся `0.1.0`, тег не создаётся.
- Коммит, push и PR только по разрешению владельца в текущей сессии.
