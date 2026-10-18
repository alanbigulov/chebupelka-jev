# Прогресс разработки chebu-tutor

Таблица хранит статус каждого этапа. Сессия разработки обновляет свою строку в конце работы по [порядку сессии](development-workflow.md). Статусы те же, что у тикетов в [project-tracking.md](../../coding-agent-developement/project-tracking.md): «Бэклог», «К выполнению», «В работе», «Проверка», «Заблокировано», «Готово».

| Этап | Файл | Статус | Доказательство | Дата UTC |
|---|---|---|---|---|
| 0. Пакет документации | [README.md](README.md) | Готово | [PR #29](https://github.com/alanbigulov/chebupelka-jev/pull/29) слит 2026-10-15T17:48:08Z, коммит `a434f00` в `main` | 2026-10-16 |
| 1. Пробный навык в шести рантаймах | [01-runtime-probe.md](stages/01-runtime-probe.md) | Готово | 18 строк [журнала проб](runtime-adapters.md#журнал-проб): все шесть рантаймов находят навык, текст вызова доходит без изменений. Решения D-12–D-14 в [журнале](architecture.md#журнал-решений). [PR #30](https://github.com/alanbigulov/chebupelka-jev/pull/30) слит 2026-10-16T15:56:13Z, коммит `7cb1b18` в `main` | 2026-10-16 |
| 2. Каркас | [02-scaffold.md](stages/02-scaffold.md) | Готово | [skill.json](../skill.json) совпадает с формой из [architecture.md](architecture.md#структуры-данных). Четыре теста [test_skill_json.py](../tests/test_skill_json.py) проходят; дефекты `version` `0.1` и `handoff_schema` 3 дают падение с именем поля. Запись в [CHANGELOG навыка](../CHANGELOG.md). [PR #31](https://github.com/alanbigulov/chebupelka-jev/pull/31) слит 2026-10-16T16:37:41Z, коммит `b1cabc3` в `main` | 2026-10-16 |
| 3. Канонический текст и проверка флага | [03-canonical-source.md](stages/03-canonical-source.md) | Готово | Ключ `--mode` у `handoff.py start` (D-16): 11 тестов `ModeTest` в [test_handoff.py](../../.handoff/test_handoff.py), всего 74 теста `.handoff` проходят. Дефект `--exec` дал падение `Tuples differ: (0, 'Рантайм: …') != (2, '')`. Канонический текст [source/SKILL.md](../source/SKILL.md) и 7 тестов [test_source.py](../tests/test_source.py), всего 11 тестов навыка проходят. Решения D-15–D-20 в [журнале](architecture.md#журнал-решений). [PR #32](https://github.com/alanbigulov/chebupelka-jev/pull/32) слит 2026-10-16T17:43:39Z, коммит `a2f2e32` в `main` | 2026-10-18 |
| 4. Генератор и проверка синхронизации | [04-sync.md](stages/04-sync.md) | Проверка | Генератор [sync.py](../tools/sync.py) и 21 тест [test_sync.py](../tests/test_sync.py), всего 32 теста навыка проходят, 74 теста `.handoff` проходят. Дефект «генератор пропускает метку версии» дал падение `AssertionError: '  version: "0.1.0"' not found in [..., 'metadata:', '  version: ']`. Ещё 20 внесённых дефектов из строк этапа 4 в [verification.md](verification.md) уронили назначенные им тесты. Блок `skill` в шести файлах `runtime-config/runtimes/`, файл [source/agents/openai.yaml](../source/agents/openai.yaml). Решения D-21–D-23 в [журнале](architecture.md#журнал-решений). Ветка `chebu-tutor/stage-04`; «Готово» ставит следующая сессия после слияния PR этапа | 2026-10-18 |
| 5. Адаптеры в рантаймах и документы проекта | [05-install.md](stages/05-install.md) | Бэклог | нет | |
| 6. Приёмка в шести рантаймах | [06-acceptance.md](stages/06-acceptance.md) | Бэклог | нет | |
| 7. Выпуск chebu-tutor-v0.1.0 | [07-release.md](stages/07-release.md) | Бэклог | нет | |

## Открытые решения владельца

| Решение | Нужно до этапа | Предложение |
|---|---|---|
| Два каталога адаптеров и флаг из сообщения вызова (D-10, D-11) | 3 | Закрыто пробой этапа 1: D-12 выбирает ссылку, D-13 добавляет `$ARGUMENTS` к сообщению вызова. Контракт, architecture.md, verification.md и этапы 3–5 исправлены в ветке этапа 1 |
| Поведение без флага (D-08) | 3 | Закрыто: владелец подтвердил предложение 2026-10-16, решение D-15 |
| Место кода проверки флага (D-09) | 3 | Закрыто: владелец выбрал ключ `--mode` у `handoff.py start` 2026-10-16, решение D-16 |
| Запрет неявного вызова в Codex (D-17) | 4 | Закрыто: владелец выбрал генерировать `agents/openai.yaml` с `policy.allow_implicit_invocation: false` 2026-10-18, решение D-22 |
| Разрешение на запуски рантаймов для пробы и приёмки | 6 | Владелец называет рантаймы и число запусков в сессии этапа. Для этапа 1 владелец разрешил 12 вызовов без интерфейса 2026-10-16, все израсходованы |
| Сессия Codex в worktree не может выполнить `save` (вопрос 7 пробы) | не блокирует этапы | `install()` в `handoff.py` перехватывает `PermissionError` и печатает понятное сообщение вместо трассировки. Протокол `.handoff/` велит попросить владельца выполнить `save` из worktree вне песочницы |
| Объём приёмки, если ячейка матрицы не проверена | 7 | Выпуск только при итоге «Проверено» во всех 54 ячейках |
