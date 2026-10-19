# Рантаймы: где лежит навык и как его вызвать

Справочник собран 2026-10-15 без единого запроса к модели. Источники: справка установленных CLI, строки и код установленных пакетов, документация вендоров. Этап 1 проверяет главные факты пробным навыком и заменяет метки на `confirmed-local` с наблюдением. Проба этапа 1 прошла 2026-10-16: её итог записан в [журнал проб](#журнал-проб), а подтверждённые ею факты помечены «проба 2026-10-16».

| Метка | Значение |
|---|---|
| `confirmed-local` | Команда выполнена на машине владельца, или прочитан код установленного пакета. Указаны команда и результат |
| `confirmed-docs` | Факт взят из документации вендора. Указан URL |
| `unconfirmed` | Факт не проверен. Указана причина |

Голая строка в бинарнике подтверждает только то, что программа знает это имя. Код пакета и встроенная справка описывают поведение и получают метку `confirmed-local`. Что загрузчик действительно читает каталог в работающей сессии, подтверждает только проба этапа 1. Её итог записывается в [журнал проб](#журнал-проб), и итог «Проверено» в журнале переводит факт в `confirmed-local` с наблюдением.

## Версии CLI

`--version` выполнен 2026-10-15 и 2026-10-16, `confirmed-local`. За сутки обновились Claude Code и Codex. Cursor, Devin и Grok обновились сами во время пробы 2026-10-16, поэтому версию каждого наблюдения называет журнал проб.

| Рантайм | id | Версия 2026-10-15 | Версия 2026-10-16 | В `runtime-config/runtimes/<id>.json` |
|---|---|---|---|---|
| Claude Code | `claude` | 2.1.300 | 2.1.301 | 2.1.296 |
| Codex | `codex` | 0.162.1 | 0.163.0 | 0.162.1 |
| Cursor | `cursor` | 2026.10.01-e373342 | 2026.10.01-e373342, к концу пробы 2026.10.14-941492e | 2026.10.01-e373342 |
| Devin | `devin` | 3000.11.3 | 3000.11.3, к концу пробы 3000.11.92 | 3000.11.3 |
| Grok Build | `grok` | 1.0.52 | 1.0.52, к концу пробы 1.0.60 | 1.0.52 |
| OpenCode | `opencode` | 2.0.29 | 2.0.29 | 2.0.27 |

## Кто какой каталог навыков читает

| Каталог проекта | `claude` | `codex` | `cursor` | `devin` | `grok` | `opencode` |
|---|---|---|---|---|---|---|
| `.claude/skills/` | да, `confirmed-local`, проба 2026-10-16 | нет, `confirmed-local`: `codex debug prompt-input` не называет этот корень, проба 2026-10-16 | да, `confirmed-local`, код пакета | да, `confirmed-local`: `devin skills list`, проба 2026-10-16 | да, `confirmed-docs` | да, `confirmed-docs` |
| `.agents/skills/` | нет, `unconfirmed`: вывод из кода. Проба не различила «не читает» и дедупликацию по имени | да, `confirmed-local`, проба 2026-10-16 | да, `confirmed-local`, код пакета | да, `confirmed-local`: `devin skills paths` и `devin skills list` | да, `confirmed-local`, встроенная справка | да, `confirmed-docs` |
| `.claude/commands/` | да, `confirmed-docs` | нет, `unconfirmed`: docs называют только `~/.codex/prompts/` | да, `confirmed-local`, код пакета | да, `confirmed-docs`, как навыки | неизвестно, `unconfirmed`: только строка в бинарнике | нет, `unconfirmed`: данные на 2026-01 |

Ни один каталог не читают все шесть рантаймов. `.claude/skills/` не читает только Codex. `.agents/skills/` не читает только Claude Code. Пара каталогов `.claude/skills/chebu-tutor/` и `.agents/skills/chebu-tutor/` покрывает все шесть.

Проба 2026-10-16 положила навык в оба каталога. Claude Code, Codex, Cursor и Grok видят его один раз и с копией, и со ссылкой. Devin видит копию дважды, а ссылку один раз. В подсказке `/` OpenCode 2.0.29 навыков нет вовсе.

## Вызов и аргументы

| Рантайм | Вызов в интерфейсе | Аргументы в навыке | Вызов без интерфейса |
|---|---|---|---|
| `claude` | `/chebu-tutor --guide`, `confirmed-local`, проба 2026-10-16 | `$ARGUMENTS` раскрывается в строку как набрана: кавычки сохраняются, `$HOME` остаётся текстом, `confirmed-local`, проба 2026-10-16. `$0` означает первый аргумент. Без плейсхолдера в конец дописывается `ARGUMENTS: <текст>`. `confirmed-docs` | `claude -p "/chebu-tutor --guide"`, `confirmed-local`, проба 2026-10-16 |
| `codex` | `$chebu-tutor --guide`, `confirmed-local`, проба 2026-10-16 | Текст после имени остаётся в сообщении без изменений, `confirmed-local`, `codex debug prompt-input`. Как тело навыка попадает к модели, не наблюдалось: в `prompt-input` его нет, команды чтения файла в выводе `codex exec` тоже нет. Подставляет ли Codex `$ARGUMENTS`, не установлено: модель могла взять аргументы из сообщения, `unconfirmed` | `codex exec '$chebu-tutor --guide'` в одинарных кавычках, `confirmed-local`, проба 2026-10-16 |
| `cursor` | `/chebu-tutor --guide`, `confirmed-local`, проба 2026-10-16 | Подстановки нет. Навык прикрепляется к сообщению, а текст `--guide` остаётся в сообщении. `confirmed-local`, код пакета и проба 2026-10-16 | `cursor-agent -p "/chebu-tutor --guide"`, `confirmed-local`, проба 2026-10-16. В недоверенном каталоге завершается кодом 1 до вызова модели: `Workspace Trust Required` |
| `devin` | `/chebu-tutor --guide`, `confirmed-local`, проба 2026-10-16. Если навык лежит копией в двух каталогах, в подсказке два имени: `/agents:<имя>` и `/claude:<имя>` | Вместо сообщения вызова модель получает тело навыка с подставленным `$ARGUMENTS`. Аргументы доходят без изменений. `confirmed-local`, проба 2026-10-16, два наблюдения | `devin -p "/chebu-tutor --guide"`, `confirmed-local`, проба 2026-10-16. В недоверенном каталоге завершается кодом 1: `Refusing to run in an untrusted workspace` |
| `grok` | `/chebu-tutor --guide`, `confirmed-local`, проба 2026-10-16 | В интерфейсе `$ARGUMENTS` подставляется, `confirmed-local`, проба 2026-10-16 | `grok -p "/chebu-tutor --guide"`. В 1.0.52 команда не раскрылась: модель сама нашла навык, а `$ARGUMENTS` остался буквальным. В 1.0.60 вывод полный, аргументы подставлены. `confirmed-local`, проба 2026-10-16 |
| `opencode` | В 2.0.29 в подсказке `/` навыков нет. Сообщение `/chebu-tutor --guide` всё же работает: модель узнаёт имя и загружает навык инструментом Skill. `confirmed-local`, проба 2026-10-16. В CLI v2 навык показан командой `/id`, и выбор команды добавляет тело навыка к сессии, `confirmed-docs` https://dev.opencode.ai/v2/docs/skills/. В 2.0.32 навыка `chebu-tutor` в подсказке `/` нет, сообщение `/chebu-tutor …` уходит без вложения навыка, и модель навык не видит, `confirmed-local`, запуск владельца 2026-10-19 | Клиент не подставляет аргументы: значение `$ARGUMENTS` модель берёт из сообщения сама, `confirmed-local`, проба 2026-10-16. В 2.0.32 вложение навыка тоже содержит `$ARGUMENTS` буквально, `confirmed-local`, приёмка 2026-10-18. В командах `.opencode/commands/` есть `$ARGUMENTS` и `$1`, `confirmed-docs` | В 2.0.29 `opencode run -m <провайдер/модель> "/chebu-tutor --guide"`, `confirmed-local`, проба 2026-10-16: вывод `→ Skill "chebu-tutor-probe"`. В 2.0.32 та же команда навык не загружает, `confirmed-local`, приёмка 2026-10-18. Навык вызывает `session.prompt` с полем `skills` через API своего сервера, см. раздел OpenCode ниже. Ключа `--command` в `opencode run --help` нет, `confirmed-local` |

Запуск интерактивной сессии с вызовом навыка в первом сообщении владелец проверил 2026-10-19 из shell в корне основного клона, `confirmed-local`. Так выглядят команды продолжения, которые печатает `handoff.py save`. Пять рантаймов дали строку `Режим тьютора: execute, из снимка и флага`: `claude "/chebu-tutor --execute"` в 2.1.303, `codex '$chebu-tutor --execute'` в 0.163.0, `cursor-agent "/chebu-tutor --execute"` в 2026.10.16-e3cb207, `grok "/chebu-tutor --execute"` в 1.0.62 и `opencode --prompt "/chebu-tutor --execute"` в 2.0.32. Devin 3000.11.92 после `devin -- "/chebu-tutor --execute"` навык не подхватил: модель выполнила `start` без `--mode`, затем Devin завершил ход ошибкой «An internal error occurred». Запуск был один. Поэтому для Devin `save` печатает `devin` без сообщения и вызов навыка в комментарии.

## Следствия для навыка

1. **Два адаптера с одним текстом, второй ссылкой.** Навык ставится в `.claude/skills/chebu-tutor/SKILL.md`, а `.agents/skills/chebu-tutor` становится символической ссылкой на `../../.claude/skills/chebu-tutor` (D-12). Оба каталога используют формат Agent Skills: обязательные `name` и `description`, имя равно имени папки. С копией Devin показывает навык дважды, со ссылкой один раз. Codex идёт по ссылке, Cursor и Grok видят навык один раз в обоих вариантах, проба 2026-10-16.
2. **Флаг ищется в `$ARGUMENTS` и в тексте вызова.** Позиционные подстановки несовместимы: у Claude Code первый аргумент `$0`, у Devin и OpenCode `$1`, у Cursor и Codex подстановки в навыке нет. Канонический текст не опирается на `$0` и `$1`, но содержит `$ARGUMENTS` (D-13). Devin заменяет сообщение вызова телом навыка, поэтому там флаг виден только в подставленном `$ARGUMENTS`. Если плейсхолдер остался буквальным, как в Grok 1.0.52 с `-p`, флаг берётся из сообщения вызова.
3. **id рантайма называет агент.** Общий текст не может зашить `--runtime <id>`. AGENTS.md уже требует, чтобы агент назвал свой рантайм. У Devin переменной для распознавания нет, поэтому ключ `--runtime` обязателен.
4. **`handoff.py` запускает агент обычным вызовом shell.** Вставка вывода команды в текст навыка различается: у Claude Code `` !`cmd` `` требует правила allow, у Devin `$(cmd)` проходит права навыка, у OpenCode вставка есть только в командах. Канонический текст просит агента выполнить команду инструментом shell.
5. **Метка версии в `metadata`.** Поле `metadata` стандарта Agent Skills принимают Grok и OpenCode (docs), Devin и Cursor (код). Метка версии кладётся в `metadata.version`. Claude Code и Codex приняли поле без ошибки, проба 2026-10-16.
6. **Навык вызывает только ученик.** Поле `user-invocable: false` скрывает навык из CLI Cursor (код пакета), поэтому его ставить нельзя. Запрет самостоятельного вызова агентом задают разные поля: `disable-model-invocation` у Claude Code и Grok, `triggers` у Devin, `agents/openai.yaml` у Codex. Документация на 2026-10-16 уточняет, `confirmed-docs`. Cursor тоже принимает `disable-model-invocation: true` и тогда подключает навык только по `/имя` (https://cursor.com/docs/context/skills). У Devin значения `triggers` равны `user` и `model`, по умолчанию оба (https://docs.devin.ai/cli/extensibility/skills/creating-skills). Codex читает `policy.allow_implicit_invocation: false` из `agents/openai.yaml`, явный вызов `$имя` при этом работает (https://learn.chatgpt.com/docs/build-skills). OpenCode прячет навык от модели полем `metadata["opencode/autoinvoke"]: "false"` (https://opencode.ai/docs/skills/). Этап 3 выбрал `disable-model-invocation: true` и `triggers: [user]`, а OpenCode оставил без запрета (D-17). OpenCode 2.0.32 тоже учитывает `disable-model-invocation: true` и прячет навык от модели, приёмка 2026-10-18. Вложение `skills` в `session.prompt` делает только API (D-26), а в интерфейсе навык находит модель по строке AGENTS.md (D-27). Этап 4 добавил для Codex файл `source/agents/openai.yaml` с `policy.allow_implicit_invocation: false`, генератор кладёт его в папку адаптера (D-22). Документация Codex перечитана 2026-10-18: значение по умолчанию `true`, явный вызов `$имя` при `false` работает, по ссылке на папку навыка Codex проходит.
7. **Сессия Codex в worktree не сохраняет снимок сама.** В `workspace-write` основной клон лежит вне корней записи, и `handoff.py save` падает с `PermissionError`, проба 2026-10-16. Обход выбирает владелец, вопрос записан в [progress.md](progress.md).

## Сведения по рантаймам

### Claude Code `claude`

- Навыки проекта лежат в `.claude/skills/<name>/SKILL.md`. Персональный навык с тем же именем перекрывает проектный. `confirmed-docs` https://code.claude.com/docs/en/skills. Навык проекта виден в подсказке один раз, `confirmed-local`, проба 2026-10-16.
- Изменения в проектном `.claude/skills/` подхватываются без перезапуска. `confirmed-docs`, там же.
- В бинарнике 2.1.300 есть строки `.claude/skills/`, `$ARGUMENTS`, `argument-hint`, `disable-model-invocation`, `${CLAUDE_SKILL_DIR}`. `confirmed-local`, `strings`.
- `.agents/skills/` в бинарнике стоит рядом с таблицей импорта из Cursor, а `claude import --help` называет импорт из codex, gemini и cursor. Вывод: каталог служит импорту, не поиску навыков. `unconfirmed`, загрузка не наблюдалась. Проба 2026-10-16 этого не различила: при навыке в обоих каталогах Claude Code показал его один раз.
- `claude -p` раскрывает `/skill-name` в промпте. `confirmed-docs` https://code.claude.com/docs/en/headless. `confirmed-local`, проба 2026-10-16.
- Claude Code загружает `CLAUDE.md`, строка `@AGENTS.md` подключает общие правила. Источник [claude.json](../../runtime-config/runtimes/claude.json).

### Codex `codex`

- Навыки проекта лежат в `.agents/skills/` в каждом каталоге от текущего до корня репозитория. `confirmed-docs` https://learn.chatgpt.com/docs/build-skills. `confirmed-local`, проба 2026-10-16: `codex debug prompt-input` называет корень `.agents/skills` пробного клона и не называет `.claude/skills`.
- Одноимённые навыки не сливаются и оба видны в выборе. Символические ссылки на папку навыка поддерживаются. `confirmed-docs`, там же. Ссылка `.agents/skills/<имя>` на `../../.claude/skills/<имя>` работает, `confirmed-local`, проба 2026-10-16.
- Вызов: `/skills` или `$` и имя навыка. `confirmed-docs`, там же. `confirmed-local`, проба 2026-10-16.
- `codex debug prompt-input '<текст>'` печатает вход модели без запроса к ней: список навыков, блоки AGENTS.md, права песочницы. AGENTS.md проекта входит один раз. `confirmed-local`, проба 2026-10-16.
- Пользовательские промпты устарели и живут только в `~/.codex/prompts/`. `confirmed-docs` https://learn.chatgpt.com/docs/custom-prompts.
- В режиме `workspace-write` каталоги `.agents` и `.codex` защищены от записи. Навык только читается, поэтому это ему не мешает. `confirmed-docs` https://learn.chatgpt.com/docs/agent-approvals-security.
- Корни записи `workspace-write` по умолчанию: рабочая папка, `/tmp`, `$TMPDIR` и `writable_roots` из конфига. `/tmp` и `$TMPDIR` исключают ключи `-c sandbox_workspace_write.exclude_slash_tmp=true -c sandbox_workspace_write.exclude_tmpdir_env_var=true`. `confirmed-local`: заголовок `codex exec` и `codex debug prompt-input`, проба 2026-10-16.
- Из git worktree в режиме `workspace-write` Codex не записывает `.handoff/` основного клона, если клон лежит вне корней записи. `handoff.py save` завершается кодом 1 с `PermissionError`, `SESSION.md` не появляется, `SESSION.next.md` остаётся в worktree. `confirmed-local`, проба 2026-10-16, вопрос 7.
- В эстафете 2026-10-13 песочница работала без сети. Источник [codex.json](../../runtime-config/runtimes/codex.json).

### Cursor `cursor`

- Код пакета задаёт каталоги навыков: `.cursor/skills`, `.claude/skills`, `.codex/skills`, `.grok/skills`, `.agents/skills`. Сторонние каталоги включены по умолчанию. `confirmed-local`, `~/.local/share/cursor-agent/versions/2026.10.01-e373342/9577.index.js`.
- Загрузчик держит одно множество realpath на все каталоги. `confirmed-local`, там же. Навык в двух каталогах, копией или ссылкой, виден в подсказке один раз с пометкой `(project skill)`. `confirmed-local`, 2026.10.14-941492e, проба 2026-10-16.
- Команды читаются из `.cursor/commands` и `.claude/commands`, подстановки `$ARGUMENTS` и `$1`…`$99`. В навыках подстановки нет. `confirmed-local`, там же.
- Режим `-p` разбирает ссылки `/name` на навыки. `confirmed-local`, `9969.index.js`. Вызов выполнен, `confirmed-local`, проба 2026-10-16.
- Без интерфейса Cursor работает только в доверенном каталоге. Иначе `cursor-agent -p` печатает `Workspace Trust Required` и завершается кодом 1. Доверие дают ключ `--trust` или интерактивный запуск. `confirmed-local`, проба 2026-10-16.
- Документация: https://cursor.com/docs/context/skills, `confirmed-docs`. Источник фактов о CLI [cursor.json](../../runtime-config/runtimes/cursor.json).

### Devin `devin`

- `devin skills paths` в корне репозитория печатает проектные каталоги `.devin/skills`, `.cognition/skills`, `.agents/skills`. `confirmed-local`.
- Импорт из Claude Code включён по умолчанию и берёт `.claude/skills` и `.claude/commands`. `confirmed-docs` https://docs.devin.ai/cli/reference/configuration/read-config-from.
- `devin skills list` печатает навыки с путями. Копия в двух каталогах даёт две записи: `/agents:<имя>` из `.agents/skills` и `/claude:<имя>` из `.claude/skills`. Ссылка даёт одну запись `/<имя>` из `.claude/skills`. `confirmed-local`, 3000.11.92, проба 2026-10-16.
- Навыки служат слэш-командами. Подстановки `$ARGUMENTS` и `$1`. `confirmed-docs` https://docs.devin.ai/cli/extensibility/skills/creating-skills. `$ARGUMENTS` подставляется, а вместо сообщения вызова модель видит тело навыка. `confirmed-local`, проба 2026-10-16.
- `devin -p` работает только в доверенном каталоге. Иначе печатается `Refusing to run in an untrusted workspace` и код 1. Доверие даёт интерактивный запуск. `confirmed-local`, проба 2026-10-16.
- `devin rules list` показывает правила `AGENTS` и `CLAUDE` по два раза. `devin rules show` называет первую запись каждого имени: `AGENTS.md` проекта и глобальный `~/.claude/CLAUDE.md`. Раскрывается ли `@AGENTS.md` из `CLAUDE.md` проекта, вывод не показывает. `confirmed-local`, проба 2026-10-16.
- Режим прав `auto` по умолчанию одобряет только чтение. Запуск `python3 .handoff/handoff.py` спросит разрешение. `confirmed-local`, `devin --help`. Следствие для `allowed-tools` из документации, `unconfirmed`.
- Переменной окружения для распознавания нет. Источник [devin.json](../../runtime-config/runtimes/devin.json).
- `devin -- "<промпт>"` открывает интерактивную сессию с первым сообщением, `confirmed-local`, `devin --help`. Навык из такого сообщения 3000.11.92 не подхватил: модель выполнила `python3 .handoff/handoff.py start --runtime devin` без `--mode`. `confirmed-local`, запуск владельца 2026-10-19, один.

### Grok Build `grok`

- Навыки проекта лежат в `.grok/skills/` с подъёмом до корня репозитория. Grok читает навыки Claude Code. `confirmed-docs` https://docs.x.ai/build/features/skills-plugins-marketplaces.
- Встроенная справка в бинарнике: «Grok deduplicates skills by name ... Grok also scans `.agents/skills/` (and `commands/`) at each tier (alongside `.grok/`) and walks every directory between your working directory and the repo root». `confirmed-local`, `strings` по `~/.grok/downloads/grok-1.0.52-macos-aarch64`. Навык в двух каталогах `grok inspect` показывает один раз, `confirmed-local`, 1.0.60, проба 2026-10-16.
- `grok inspect` печатает без запроса к модели версию, найденные файлы инструкций и навыки. AGENTS.md проекта загружается один раз. `CLAUDE.md` проекта весит около 2 токенов: строка `@AGENTS.md` не раскрывается. `confirmed-local`, 1.0.60, проба 2026-10-16.
- В бинарнике есть строки `.claude/skills` (11 вхождений), `.agents/skills`, `.claude/commands`, `$ARGUMENTS`, `argument-hint`, `user-invocable`. `confirmed-local`, `strings`.
- `grok --help` описывает `-p, --single <PROMPT>`: однократный промпт с выводом в stdout. `confirmed-local`. Раскрытие навыка в `-p` различается по версиям, см. таблицу «Вызов и аргументы».
- Grok обновляется сам: за время пробы 2026-10-16 версия сменилась с 1.0.52 на 1.0.60. `confirmed-local`.
- Источник фактов о CLI [grok.json](../../runtime-config/runtimes/grok.json).

### OpenCode `opencode`

- Навыки проекта лежат в `.opencode/skills/`, `.claude/skills/` и `.agents/skills/` с подъёмом до корня git worktree. `confirmed-docs` https://opencode.ai/docs/skills/.
- Имя навыка совпадает с папкой и подходит под `^[a-z0-9]+(-[a-z0-9]+)*$`. Имя `chebu-tutor` подходит. `confirmed-docs`, там же.
- В 2.0.18 вызов навыка через `/` не работал. Исправлено ли это в 2.0.29, не проверено. `unconfirmed`, https://github.com/anomalyco/opencode/issues/51427. В 2.0.29 навыков нет в подсказке `/`, но сообщение `/<имя> …` приводит к загрузке навыка моделью через инструмент Skill. `confirmed-local`, проба 2026-10-16.
- `opencode run --help` 2.0.29 показывает `opencode run [flags] [<message...>]` без ключа `--command`. Модель задаёт ключ `--model, -m` в формате `provider/model#variant`. `confirmed-local`.
- `opencode run` без `-m` берёт модель по умолчанию из конфигурации. На машине владельца она завершилась `Error: User not found.`, а с `-m deepseek/deepseek-flash` вызов прошёл. `confirmed-local`, проба 2026-10-16.
- Подкоманды `opencode debug`: `agents`, `config`, `paths`. Списка навыков среди них нет. `confirmed-local`.
- Факты 2.0.32 наблюдались на приёмке 2026-10-18, `confirmed-local`, если не указано другое:
  - `opencode run` с сообщением из одного аргумента сохраняет его в кавычках и не раскрывает `/имя`. Модель получает текст `"/chebu-tutor …"`. Issue https://github.com/anomalyco/opencode/issues/49903 описывает то же для 2.0.8.
  - Навык с `disable-model-invocation: true` модель в списке навыков не видит: на `/chebu-tutor` она ответила, что такого навыка в списке нет, и навык не загрузила. Поле учитывается с 2.0.23 по сводке выпуска https://turboai.dev/blog/opencode-2-v2-0-23, `unconfirmed`: документация вендора называет только `metadata.opencode/autoinvoke`.
  - Навык вызывается через API своего сервера. `opencode serve --hostname 127.0.0.1 --port <порт>` требует пароль из `OPENCODE_PASSWORD`, клиент передаёт тот же. Затем `opencode api --server <url>` выполняет `session.create` с моделью, папкой и правами, `session.prompt` с текстом вызова и полем `skills: [{id, mention}]`, `experimental.session.wait` и `session.message.list` с `limit` не больше 200. Тело навыка приходит к модели блоком `<skill_content name="chebu-tutor">` из `.agents/skills/chebu-tutor`.
  - Права задаёт массив `permissions` из правил `action`, `resource`, `effect`. Действие `bash` называется `shell`, побеждает последнее подходящее правило, а без `--auto` неинтерактивный запуск отклоняет запрос прав. `confirmed-docs` https://dev.opencode.ai/v2/docs/permissions/. Встроенные правила агента `build` начинаются с `* * allow`, правила пользователя идут после них, это показывает `opencode debug agents`.
  - В TUI навыка `chebu-tutor` нет в подсказке `/`, а сообщение `/chebu-tutor …` уходит без поля `skills`: запуск владельца 2026-10-19, запись сессии в `opencode.db`. Вложение навыка делает только API, поэтому в интерфейсе навык находит модель по строке AGENTS.md (D-27). С этой строкой модель загружает навык инструментом `skill` по id или читает SKILL.md, запуски владельца 2026-10-19 на `bef8cc7`.
  - Фоновый сервис `opencode serve --service` не видит `OPENCODE_CONFIG_CONTENT` вызова. Сервер `opencode run --standalone` и собственный `opencode serve` видят: `get /api/config` называет встроенный конфиг отдельным источником.
- Источник фактов о CLI [opencode.json](../../runtime-config/runtimes/opencode.json).

## Журнал проб

Этап 1 добавляет строку на каждый вызов пробного навыка. Прежние строки не меняются. Итог берётся из меток протокола: «Проверено», «Не проверено», «Частично», «Блокировано». После строки с итогом «Проверено» факт в разделах выше получает метку `confirmed-local` и ссылку на дату пробы.

Проба 2026-10-16 шла в одноразовом клоне `/tmp/chebu-tutor-probe` с навыком `chebu-tutor-probe` и текстом `--guide тикет "EDU-02" $HOME`. Вызовы без интерфейса брали этот текст в одинарные кавычки, чтобы shell не раскрыл `$HOME`. Время интерактивных вызовов владельца взято из интерфейса рантайма, где оно показано.

| Дата UTC | Рантайм и версия CLI | Вариант: копия или ссылка | Кто запускал | Команда вызова | Строка вывода | Ответ на вопросы 1–7 | Итог |
|---|---|---|---|---|---|---|---|
| 2026-10-16T13:05:59Z | claude 2.1.301 | копия | агент | `claude -p '/chebu-tutor-probe …'` | `PROBE /chebu-tutor-probe --guide тикет "EDU-02" $HOME`; `ARGS --guide тикет "EDU-02" $HOME` | 2: текст как набран, `$ARGUMENTS` раскрыт. 3: да. 5: `metadata` без ошибки | Проверено |
| 2026-10-16T13:06:22Z | codex 0.163.0 | копия | агент | `codex exec '$chebu-tutor-probe …'` | `PROBE $chebu-tutor-probe --guide тикет "EDU-02" $HOME`; `ARGS --guide тикет "EDU-02" $HOME` | 2: текст как набран. 3: да. 5: `metadata` без ошибки | Проверено |
| 2026-10-16T13:06:42Z | cursor 2026.10.01-e373342 | копия | агент | `cursor-agent -p '/chebu-tutor-probe …'` | `Workspace Trust Required`, код 1 | 3: вызов не дошёл до модели, каталог не был доверенным | Блокировано |
| 2026-10-16T13:06:43Z | devin 3000.11.3 | копия | агент | `devin -p '/chebu-tutor-probe …'` | `Refusing to run in an untrusted workspace`, код 1 | 3: вызов не дошёл до модели, каталог не был доверенным | Блокировано |
| 2026-10-16T13:06:44Z | grok 1.0.52 | копия | агент | `grok -p '/chebu-tutor-probe …'` | `The workspace has a probe skill for this exact invocation. I'll read its instructions`; `PROBE /chebu-tutor-probe --guide тикет "EDU-02" $HOME`; `ARGS $ARGUMENTS` | 2: текст как набран. 3: частично, команда не раскрылась, модель нашла навык сама, `$ARGUMENTS` не подставлен | Частично |
| 2026-10-16T13:08:09Z | opencode 2.0.29 | копия | агент | `opencode run '/chebu-tutor-probe …'` | `build · meta/muse-spark-open`; `Error: User not found.`, код 1 | 3: вызов не дошёл до модели, ошибка учётной записи провайдера модели по умолчанию | Блокировано |
| 2026-10-16, около 13:48Z | claude 2.1.301 | копия | владелец | `/chebu-tutor-probe …` в интерфейсе | `PROBE /chebu-tutor-probe --guide тикет "EDU-02" $HOME`; `ARGS --guide тикет "EDU-02" $HOME` | 1: один раз в подсказке `/`. 2: текст как набран, `$ARGUMENTS` раскрыт | Проверено |
| 2026-10-16, около 13:49Z | codex 0.163.0 | копия | владелец | `$chebu-tutor-probe …` в интерфейсе | `Применяю навык chebu-tutor-probe.`; `PROBE $chebu-tutor-probe --guide тикет "EDU-02" $HOME`; `ARGS --guide тикет "EDU-02" $HOME` | 1: один раз в подсказке `$` с пометкой `[Skill]`; `codex debug prompt-input` даёт одну запись из `.agents/skills`. 2: текст как набран. 6: AGENTS.md проекта один раз (`prompt-input`) | Проверено |
| 2026-10-16 | cursor 2026.10.01-e373342 | копия | владелец | `/chebu-tutor-probe …` в интерфейсе после доверия каталогу | `PROBE /chebu-tutor-probe --guide тикет "EDU-02" $HOME`; `ARGS --guide тикет "EDU-02" $HOME` | 1: один раз, `(project skill)`, подсказка на 2026.10.14-941492e. 2: текст как набран. 6: не наблюдался | Проверено |
| 2026-10-16 | devin 3000.11.3 | копия | владелец | `/chebu-tutor-probe …` в интерфейсе после доверия каталогу | `Invoked skill chebu-tutor-probe`; после `PROBE` модель напечатала тело навыка с подставленным `--guide тикет "EDU-02" $HOME`; `ARGS --guide тикет "EDU-02" $HOME` | 1: два раза, `/agents:chebu-tutor-probe` и `/claude:chebu-tutor-probe`, подсказка и `devin skills list` на 3000.11.92. 2: модель получила тело навыка вместо сообщения вызова, аргументы без изменений. 6: частично, `devin rules list` | Проверено |
| 2026-10-16, около 13:53Z | grok, версия между 1.0.52 и 1.0.60 | копия | владелец | `/chebu-tutor-probe …` в интерфейсе | `PROBE /chebu-tutor-probe --guide тикет "EDU-02" $HOME ARGS --guide тикет "EDU-02" $HOME` | 1: один раз, подсказка и `grok inspect` на 1.0.60. 2: текст как набран, `$ARGUMENTS` подставлен. 6: AGENTS.md один раз, `@AGENTS.md` не раскрыт (`grok inspect`) | Проверено |
| 2026-10-16 | opencode 2.0.29, модель DeepSeek V4.1 Flash | копия | владелец | `/chebu-tutor-probe …` в интерфейсе | `→ Skill "chebu-tutor-probe"`; `PROBE / chebu-tutor-probe --guide тикет "EDU-02" $HOME`; `ARGS --guide тикет "EDU-02" $HOME` | 1: в подсказке `/` ноль раз. 2: текст как набран; пробел после `/` в копии экрана, вероятно, артефакт отрисовки. 4: команды в подсказке нет, навык загружает модель | Частично |
| 2026-10-16T14:06:40Z | codex 0.163.0 | ссылка | агент | `codex exec '$chebu-tutor-probe …'` | `PROBE $chebu-tutor-probe --guide тикет "EDU-02" $HOME`; `ARGS --guide тикет "EDU-02" $HOME` | 1: одна запись (`codex debug prompt-input`). 3: да. Код выхода не снят, вывод полный | Проверено |
| 2026-10-16T14:06:59Z | cursor 2026.10.14-941492e | ссылка | агент | `cursor-agent -p '/chebu-tutor-probe …'` | `PROBE /chebu-tutor-probe --guide тикет "EDU-02" $HOME`; `ARGS --guide тикет "EDU-02" $HOME` | 1: один раз в подсказке, наблюдение владельца. 3: да, после доверия каталогу | Проверено |
| 2026-10-16T14:07:28Z | devin 3000.11.92 | ссылка | агент | `devin -p '/chebu-tutor-probe …'` | После `PROBE` тело навыка с подставленными аргументами; `ARGS --guide тикет "EDU-02" $HOME` | 1: один раз, `/chebu-tutor-probe` из `.claude/skills` (`devin skills list`). 2: как в копии. 3: да | Проверено |
| 2026-10-16T14:08:06Z | grok 1.0.60 | ссылка | агент | `grok -p '/chebu-tutor-probe …'` | `PROBE /chebu-tutor-probe --guide тикет "EDU-02" $HOME`; `ARGS --guide тикет "EDU-02" $HOME` | 1: один раз (`grok inspect`). 3: да, аргументы подставлены | Проверено |
| 2026-10-16T14:08:22Z | opencode 2.0.29 | ссылка | агент | `opencode run -m deepseek/deepseek-flash '/chebu-tutor-probe …'` | `→ Skill "chebu-tutor-probe"`; `PROBE /chebu-tutor-probe --guide тикет "EDU-02" $HOME`; `ARGS --guide тикет "EDU-02" $HOME` | 1: в подсказке `/` ноль раз, наблюдение владельца. 3: да | Проверено |
| 2026-10-16T14:11:21Z | codex 0.163.0 | worktree `/tmp/chebu-tutor-probe-wt` | агент | `codex exec --sandbox workspace-write -c sandbox_workspace_write.exclude_slash_tmp=true -c sandbox_workspace_write.exclude_tmpdir_env_var=true -c approval_policy='"never"' '<выполни python3 .handoff/handoff.py save>'` | `PermissionError: [Errno 1] Operation not permitted: '/private/tmp/chebu-tutor-probe/.handoff/SESSION.md.12150.tmp'`, код 1 | 7: нет. `SESSION.md` основного клона не появился, `SESSION.next.md` остался в worktree | Проверено |

## Открытые вопросы для этапа 1

1. Видят ли Devin, Grok и OpenCode один навык или два, если он лежит и в `.claude/skills/`, и в `.agents/skills/`: копией и символической ссылкой.
2. В каком виде доходит текст после имени навыка в каждом рантайме, сохраняются ли кавычки и остаётся ли `$HOME` текстом.
3. Работает ли вызов навыка в `codex exec`, `devin -p`, `grok -p` и `opencode run`.
4. Работает ли `/chebu-tutor` в OpenCode 2.0.29.
5. Принимают ли Claude Code и Codex поле `metadata.version` без ошибки.
6. Загружают ли Devin, Grok и Cursor `AGENTS.md` дважды: напрямую и через `@AGENTS.md` в `CLAUDE.md`.
7. Может ли Codex в режиме `workspace-write` записать состояние `.handoff/` основного клона, когда сессия идёт в git worktree.

Итог пробы 2026-10-16 по журналу. Вопросы 2, 3, 5 и 7 закрыты. Вопрос 1 закрыт для всех шести рантаймов на уровне подсказки и списков CLI. Сколько раз навык виден модели OpenCode в списке инструмента Skill, не наблюдалось. Вопрос 4 закрыт частично: команды в подсказке нет, навык загружает модель. Вопрос 6 закрыт для Codex и Grok, для Devin частично, для Cursor не наблюдался. Остались открытыми: читает ли Claude Code `.agents/skills/` и подставляет ли Codex `$ARGUMENTS`.
