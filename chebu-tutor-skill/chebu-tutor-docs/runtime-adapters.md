# Рантаймы: где лежит навык и как его вызвать

Справочник собран 2026-10-15 без единого запроса к модели. Источники: справка установленных CLI, строки и код установленных пакетов, документация вендоров. Этап 1 проверяет главные факты пробным навыком и заменяет метки на `confirmed-local` с наблюдением.

| Метка | Значение |
|---|---|
| `confirmed-local` | Команда выполнена на машине владельца, или прочитан код установленного пакета. Указаны команда и результат |
| `confirmed-docs` | Факт взят из документации вендора. Указан URL |
| `unconfirmed` | Факт не проверен. Указана причина |

Голая строка в бинарнике подтверждает только то, что программа знает это имя. Код пакета и встроенная справка описывают поведение и получают метку `confirmed-local`. Что загрузчик действительно читает каталог в работающей сессии, подтверждает только проба этапа 1. Её итог записывается в [журнал проб](#журнал-проб), и итог «Проверено» в журнале переводит факт в `confirmed-local` с наблюдением.

## Версии CLI

`--version` выполнен 2026-10-15, `confirmed-local`. Две версии изменились после проверки, записанной в `runtime-config/`.

| Рантайм | id | Версия 2026-10-15 | В `runtime-config/runtimes/<id>.json` |
|---|---|---|---|
| Claude Code | `claude` | 2.1.300 | 2.1.296 |
| Codex | `codex` | 0.162.1 | 0.162.1 |
| Cursor | `cursor` | 2026.10.01-e373342 | 2026.10.01-e373342 |
| Devin | `devin` | 3000.11.3 | 3000.11.3 |
| Grok Build | `grok` | 1.0.52 | 1.0.52 |
| OpenCode | `opencode` | 2.0.29 | 2.0.27 |

## Кто какой каталог навыков читает

| Каталог проекта | `claude` | `codex` | `cursor` | `devin` | `grok` | `opencode` |
|---|---|---|---|---|---|---|
| `.claude/skills/` | да, `confirmed-docs` | нет, `unconfirmed`: docs его не называют | да, `confirmed-local`, код пакета | да, `confirmed-docs`, импорт | да, `confirmed-docs` | да, `confirmed-docs` |
| `.agents/skills/` | нет, `unconfirmed`: вывод из кода | да, `confirmed-docs` | да, `confirmed-local`, код пакета | да, `confirmed-local`, `devin skills paths` | да, `confirmed-local`, встроенная справка | да, `confirmed-docs` |
| `.claude/commands/` | да, `confirmed-docs` | нет, `unconfirmed`: docs называют только `~/.codex/prompts/` | да, `confirmed-local`, код пакета | да, `confirmed-docs`, как навыки | неизвестно, `unconfirmed`: только строка в бинарнике | нет, `unconfirmed`: данные на 2026-01 |

Ни один каталог не читают все шесть рантаймов. `.claude/skills/` не читает только Codex. `.agents/skills/` не читает только Claude Code. Пара каталогов `.claude/skills/chebu-tutor/` и `.agents/skills/chebu-tutor/` покрывает все шесть.

## Вызов и аргументы

| Рантайм | Вызов в интерфейсе | Аргументы в навыке | Вызов без интерфейса |
|---|---|---|---|
| `claude` | `/chebu-tutor --guide`, `confirmed-docs` | `$ARGUMENTS` раскрывается в строку как набрана. `$0` означает первый аргумент. Без плейсхолдера в конец дописывается `ARGUMENTS: <текст>`. `confirmed-docs` | `claude -p "/chebu-tutor --guide"`, `confirmed-docs` |
| `codex` | `$chebu-tutor --guide`, `confirmed-docs` | Подстановка не описана. Текст после имени, вероятно, остаётся в сообщении. `unconfirmed`: вызов не запускался | `codex exec '$chebu-tutor --guide'` в одинарных кавычках, `unconfirmed`: docs молчат |
| `cursor` | `/chebu-tutor --guide`, `confirmed-docs` и `confirmed-local`, код пакета | Подстановки нет. Навык прикрепляется к сообщению, а текст `--guide` остаётся в сообщении. `confirmed-local`, код пакета | `cursor-agent -p "/chebu-tutor --guide"`, `confirmed-local`, код пакета. Вызов не запускался |
| `devin` | `/chebu-tutor --guide`, `confirmed-docs` | `$ARGUMENTS` одной строкой, `$1` первый аргумент. Без плейсхолдера аргументы дописываются в конец. `confirmed-docs` | `devin -p "/chebu-tutor --guide"`, `unconfirmed`: docs не говорят о раскрытии навыка в `-p` |
| `grok` | `/chebu-tutor --guide`, `confirmed-docs` | Рядом с отрисовкой навыка в бинарнике стоят `$ARGUMENTS` и `**ARGUMENTS:**`. `unconfirmed`: только строки в бинарнике | `grok -p "/chebu-tutor --guide"`. Ключ `-p, --single` есть в справке, `confirmed-local`. Раскрытие навыка `unconfirmed` |
| `opencode` | `/chebu-tutor --guide`, `confirmed-docs`. В 2.0.18 вызов навыка через `/` был сломан, issue 51427, `unconfirmed` для 2.0.29 | Для навыков подстановка не описана, `unconfirmed`. В командах `.opencode/commands/` есть `$ARGUMENTS` и `$1`, `confirmed-docs` | `opencode run "/chebu-tutor --guide"`. Ключа `--command` в `opencode run --help` 2.0.29 нет, `confirmed-local`. Раскрытие навыка `unconfirmed` |

## Следствия для навыка

1. **Два адаптера с одним текстом.** Навык ставится в `.claude/skills/chebu-tutor/SKILL.md` и `.agents/skills/chebu-tutor/SKILL.md`. Оба каталога используют формат Agent Skills: обязательные `name` и `description`, имя равно имени папки. Второй адаптер может быть символической ссылкой на первый. Codex следует по ссылкам (docs), Cursor отбрасывает повтор с тем же realpath (код пакета). Как Devin, Grok и OpenCode ведут себя с копией и со ссылкой, проверяет этап 1. Grok дедуплицирует навыки по имени (встроенная справка).
2. **Флаг ищется в тексте вызова.** Позиционные подстановки несовместимы: у Claude Code первый аргумент `$0`, у Devin и OpenCode `$1`, у Cursor и Codex подстановки в навыке нет. Канонический текст не опирается на `$0` и `$1`. Он велит агенту найти флаги в сообщении, которым ученик вызвал навык. `$ARGUMENTS` можно оставить одной строкой: где он раскроется, агент увидит аргументы дважды, где нет, увидит буквальный текст и возьмёт флаг из сообщения.
3. **id рантайма называет агент.** Общий текст не может зашить `--runtime <id>`. AGENTS.md уже требует, чтобы агент назвал свой рантайм. У Devin переменной для распознавания нет, поэтому ключ `--runtime` обязателен.
4. **`handoff.py` запускает агент обычным вызовом shell.** Вставка вывода команды в текст навыка различается: у Claude Code `` !`cmd` `` требует правила allow, у Devin `$(cmd)` проходит права навыка, у OpenCode вставка есть только в командах. Канонический текст просит агента выполнить команду инструментом shell.
5. **Метка версии в `metadata`.** Поле `metadata` стандарта Agent Skills принимают Grok и OpenCode (docs), Devin и Cursor (код). Метка версии кладётся в `metadata.version`. Поведение Claude Code и Codex с этим полем проверяет этап 1.
6. **Навык вызывает только ученик.** Поле `user-invocable: false` скрывает навык из CLI Cursor (код пакета), поэтому его ставить нельзя. Запрет самостоятельного вызова агентом задают разные поля: `disable-model-invocation` у Claude Code и Grok, `triggers` у Devin, `agents/openai.yaml` у Codex. Выбор поля делает этап 3.

## Сведения по рантаймам

### Claude Code `claude`

- Навыки проекта лежат в `.claude/skills/<name>/SKILL.md`. Персональный навык с тем же именем перекрывает проектный. `confirmed-docs` https://code.claude.com/docs/en/skills.
- Изменения в проектном `.claude/skills/` подхватываются без перезапуска. `confirmed-docs`, там же.
- В бинарнике 2.1.300 есть строки `.claude/skills/`, `$ARGUMENTS`, `argument-hint`, `disable-model-invocation`, `${CLAUDE_SKILL_DIR}`. `confirmed-local`, `strings`.
- `.agents/skills/` в бинарнике стоит рядом с таблицей импорта из Cursor, а `claude import --help` называет импорт из codex, gemini и cursor. Вывод: каталог служит импорту, не поиску навыков. `unconfirmed`, загрузка не наблюдалась.
- `claude -p` раскрывает `/skill-name` в промпте. `confirmed-docs` https://code.claude.com/docs/en/headless.
- Claude Code загружает `CLAUDE.md`, строка `@AGENTS.md` подключает общие правила. Источник [claude.json](../../runtime-config/runtimes/claude.json).

### Codex `codex`

- Навыки проекта лежат в `.agents/skills/` в каждом каталоге от текущего до корня репозитория. `confirmed-docs` https://learn.chatgpt.com/docs/build-skills.
- Одноимённые навыки не сливаются и оба видны в выборе. Символические ссылки на папку навыка поддерживаются. `confirmed-docs`, там же.
- Вызов: `/skills` или `$` и имя навыка. `confirmed-docs`, там же.
- Пользовательские промпты устарели и живут только в `~/.codex/prompts/`. `confirmed-docs` https://learn.chatgpt.com/docs/custom-prompts.
- В режиме `workspace-write` каталоги `.agents` и `.codex` защищены от записи. Навык только читается, поэтому это ему не мешает. `confirmed-docs` https://learn.chatgpt.com/docs/agent-approvals-security.
- В эстафете 2026-10-13 песочница работала без сети. Источник [codex.json](../../runtime-config/runtimes/codex.json).

### Cursor `cursor`

- Код пакета задаёт каталоги навыков: `.cursor/skills`, `.claude/skills`, `.codex/skills`, `.grok/skills`, `.agents/skills`. Сторонние каталоги включены по умолчанию. `confirmed-local`, `~/.local/share/cursor-agent/versions/2026.10.01-e373342/9577.index.js`.
- Загрузчик держит одно множество realpath на все каталоги. `confirmed-local`, там же.
- Команды читаются из `.cursor/commands` и `.claude/commands`, подстановки `$ARGUMENTS` и `$1`…`$99`. В навыках подстановки нет. `confirmed-local`, там же.
- Режим `-p` разбирает ссылки `/name` на навыки. `confirmed-local`, `9969.index.js`. Вызов не запускался.
- Документация: https://cursor.com/docs/context/skills, `confirmed-docs`. Источник фактов о CLI [cursor.json](../../runtime-config/runtimes/cursor.json).

### Devin `devin`

- `devin skills paths` в корне репозитория печатает проектные каталоги `.devin/skills`, `.cognition/skills`, `.agents/skills`. `confirmed-local`.
- Импорт из Claude Code включён по умолчанию и берёт `.claude/skills` и `.claude/commands`. `confirmed-docs` https://docs.devin.ai/cli/reference/configuration/read-config-from.
- Навыки служат слэш-командами. Подстановки `$ARGUMENTS` и `$1`. `confirmed-docs` https://docs.devin.ai/cli/extensibility/skills/creating-skills.
- Режим прав `auto` по умолчанию одобряет только чтение. Запуск `python3 .handoff/handoff.py` спросит разрешение. `confirmed-local`, `devin --help`. Следствие для `allowed-tools` из документации, `unconfirmed`.
- Переменной окружения для распознавания нет. Источник [devin.json](../../runtime-config/runtimes/devin.json).

### Grok Build `grok`

- Навыки проекта лежат в `.grok/skills/` с подъёмом до корня репозитория. Grok читает навыки Claude Code. `confirmed-docs` https://docs.x.ai/build/features/skills-plugins-marketplaces.
- Встроенная справка в бинарнике: «Grok deduplicates skills by name ... Grok also scans `.agents/skills/` (and `commands/`) at each tier (alongside `.grok/`) and walks every directory between your working directory and the repo root». `confirmed-local`, `strings` по `~/.grok/downloads/grok-1.0.52-macos-aarch64`.
- В бинарнике есть строки `.claude/skills` (11 вхождений), `.agents/skills`, `.claude/commands`, `$ARGUMENTS`, `argument-hint`, `user-invocable`. `confirmed-local`, `strings`.
- `grok --help` описывает `-p, --single <PROMPT>`: однократный промпт с выводом в stdout. `confirmed-local`.
- Источник фактов о CLI [grok.json](../../runtime-config/runtimes/grok.json).

### OpenCode `opencode`

- Навыки проекта лежат в `.opencode/skills/`, `.claude/skills/` и `.agents/skills/` с подъёмом до корня git worktree. `confirmed-docs` https://opencode.ai/docs/skills/.
- Имя навыка совпадает с папкой и подходит под `^[a-z0-9]+(-[a-z0-9]+)*$`. Имя `chebu-tutor` подходит. `confirmed-docs`, там же.
- В 2.0.18 вызов навыка через `/` не работал. Исправлено ли это в 2.0.29, не проверено. `unconfirmed`, https://github.com/anomalyco/opencode/issues/51427.
- `opencode run --help` 2.0.29 показывает `opencode run [flags] [<message...>]` без ключа `--command`. `confirmed-local`.
- Подкоманды `opencode debug`: `agents`, `config`, `paths`. Списка навыков среди них нет. `confirmed-local`.
- Источник фактов о CLI [opencode.json](../../runtime-config/runtimes/opencode.json).

## Журнал проб

Этап 1 добавляет строку на каждый вызов пробного навыка. Прежние строки не меняются. Итог берётся из меток протокола: «Проверено», «Не проверено», «Частично», «Блокировано». После строки с итогом «Проверено» факт в разделах выше получает метку `confirmed-local` и ссылку на дату пробы.

| Дата UTC | Рантайм и версия CLI | Вариант: копия или ссылка | Кто запускал | Команда вызова | Строка вывода | Ответ на вопросы 1–7 | Итог |
|---|---|---|---|---|---|---|---|
| нет записей | | | | | | | |

## Открытые вопросы для этапа 1

1. Видят ли Devin, Grok и OpenCode один навык или два, если он лежит и в `.claude/skills/`, и в `.agents/skills/`: копией и символической ссылкой.
2. В каком виде доходит текст после имени навыка в каждом рантайме, сохраняются ли кавычки и остаётся ли `$HOME` текстом.
3. Работает ли вызов навыка в `codex exec`, `devin -p`, `grok -p` и `opencode run`.
4. Работает ли `/chebu-tutor` в OpenCode 2.0.29.
5. Принимают ли Claude Code и Codex поле `metadata.version` без ошибки.
6. Загружают ли Devin, Grok и Cursor `AGENTS.md` дважды: напрямую и через `@AGENTS.md` в `CLAUDE.md`.
7. Может ли Codex в режиме `workspace-write` записать состояние `.handoff/` основного клона, когда сессия идёт в git worktree.
