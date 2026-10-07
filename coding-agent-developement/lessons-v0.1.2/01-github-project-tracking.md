# Урок v0.1.2: общая очередь разработки и обучения в GitHub

В v0.1.2 задачи агента, учебных материалов и выпусков получили общий публичный трекер. Урок разбирает создание Project, перенос задач из roadmap, настройку Kanban и проверку результата через API. Python-код агента сохранён, исправления запланированы отдельно.

Исходная база этого занятия: [v0.1.1](../lessons-v0.1.1/version.md). Снимок занятия: [паспорт v0.1.2](version.md). Первоначальная настройка трекера выполнена владельцем проекта и OpenAI Codex 7 октября 2026 года; организационный выпуск оформляется 8 октября. Репозиторий называется `chebupelka-jev`, программа и Python-проект называются `chebupelkajev`.

## 1. Почему понадобился общий трекер

После разделения каталогов появились две очереди: изменения `agent/` и развитие `coding-agent-developement/`. Их результаты связаны. Изменение протокола требует проверок и объяснения, а публикация требует согласованного кода, уроков и номера версии.

Roadmap уже объяснял учебные темы, но Markdown-таблица неудобна для обсуждения одного изменения, хранения результатов проверки и перемещения задач между этапами. Поэтому задачи перенесли в Issues, а общую очередь показали в одном Project.

```text
alanbigulov/chebupelka-jev
|-- agent/                        код, инструменты, тесты
|-- coding-agent-developement/     уроки, паспорта, учебный смысл
`-- общие документы               версии, структура, история
             |
             v
GitHub Issues: критерии и доказательства
             |
             v
Project 4: этап, приоритет, порядок
```

| Объект | Что в нём хранится | Пример |
|---|---|---|
| Issue | Одна задача, критерии, обсуждение и результаты | [EDU-01, #1](https://github.com/alanbigulov/chebupelka-jev/issues/1) |
| Project item | Участие issue в очереди, значения полей Project | Карточка #1 с полем Status |
| View | Способ показать те же items | Доска кода с фильтром labels |
| Milestone issue | Целевой выпуск задачи | `v0.1.2` |
| Label issue | Область, тип или частичное выполнение | `area:learning`, `status:partial` |
| Git-тег | Зафиксированное дерево кода и документов | `v0.1.2` |

Issue и project item имеют разные ID. Номер `#1` принадлежит issue в репозитории. Номер `4` принадлежит Project пользователя. Их нельзя подставлять вместо GraphQL ID.

## 2. Перед созданием читаем существующие объекты

Для работы использовали GitHub CLI `gh`, его команды `project` и доступ к REST/GraphQL API. Авторизация CLI должна разрешать запись в репозиторий и Project. Проверка авторизации не требует публиковать токен в уроке.

Команды чтения ниже можно выполнить для существующего проекта из корня репозитория:

```bash
gh auth status
gh project list --owner alanbigulov --limit 100 --format json
gh api 'repos/alanbigulov/chebupelka-jev/labels?per_page=100'
gh api 'repos/alanbigulov/chebupelka-jev/milestones?state=all&per_page=100'
gh api 'repos/alanbigulov/chebupelka-jev/issues?state=all&per_page=100'
```

Проверяли открытые и закрытые задачи: закрытый issue с тем же EDU-ID тоже является существующей задачей. REST-список issues может включать pull requests, поэтому скрипт исключал записи с ключом `pull_request`.

Создание ниже объясняет выполненную настройку. Не запускай команды создания повторно против готового Project 4. Для нового проекта сначала выполни поиск совпадений; при нескольких совпадениях остановись и выясни, какое из них использовать. Лимита 100 хватило для этой очереди; большой репозиторий требует пагинации.

## 3. Создание, публичность и связь с репозиторием

Скрипт искал Project по точному названию `chebupelkajev — Разработка и обучение`. Если совпадение было одно, использовал его; если ни одного, создавал Project. После каждого существенного шага сохранял полученные ID для продолжения настройки.

```bash
# Пример первоначального создания, уже выполненного для Project 4.
gh project create --owner alanbigulov \
  --title 'chebupelkajev — Разработка и обучение' --format json
gh project link 4 --owner alanbigulov \
  --repo alanbigulov/chebupelka-jev
```

Фактический результат: [Project 4](https://github.com/users/alanbigulov/projects/4), GraphQL ID `PVT_kwHOC5I5Oc4BmHPp`. Публичность установили через `updateProjectV2`, связь с репозиторием через `gh project link`.

Для многострочных запросов скрипт передавал структурированный JSON через stdin. Следующий сокращённый помощник показывает тот же приём. Это учебный пример Python, который используется в примерах ниже; выполнение мутаций меняет GitHub.

```python
import json
import subprocess

def gh_json(*args, body=None):
    command = ["gh", *args]
    if body is not None:
        command += ["--input", "-"]
    result = subprocess.run(
        command, input=json.dumps(body, ensure_ascii=False) if body is not None else None,
        text=True, capture_output=True, check=True,
    )
    return json.loads(result.stdout) if result.stdout.strip() else None

def graphql(query, **variables):
    response = gh_json("api", "graphql", body={"query": query, "variables": variables})
    if response.get("errors"):
        raise RuntimeError(response["errors"])
    return response["data"]

projects = gh_json("project", "list", "--owner", "alanbigulov",
                   "--limit", "100", "--format", "json")["projects"]
title = "chebupelkajev — Разработка и обучение"
matches = [project for project in projects if project["title"] == title]
assert len(matches) <= 1, "Нужно проверить дублирующиеся Projects"
project = matches[0] if matches else gh_json(
    "project", "create", "--owner", "alanbigulov", "--title", title, "--format", "json",
)
graphql("""mutation($id: ID!) {
  updateProjectV2(input: {projectId: $id, public: true}) {
    projectV2 { id public }
  }
}""", id=project["id"])
```

JSON-сериализация сохраняет реальные переводы строк и кавычки. Здесь `subprocess.run` получает список аргументов, без оболочки. Это исключает ошибку, когда shell интерпретирует `$variable`, обратные кавычки или подстановку команды внутри тела запроса. Проверка `errors` нужна отдельно от кода выхода CLI.

В описании и README самого Project записали переходы Kanban, ссылки на представления и правила работы с issues. Эти тексты обновляли через `updateProjectV2`. После уточнения выпуска описание очереди также должно соответствовать согласованному составу.

## 4. Labels разделяют область и тип задачи

Создали девять меток. Проверка существующих имён перед `POST` предотвращала повторное создание.

| Метка | Назначение |
|---|---|
| `area:agent` | Исполняемый агент и его проверки |
| `area:learning` | Уроки и паспорта версий |
| `area:organization` | Приёмка и организация выпусков |
| `type:bug` | Исправление наблюдаемого поведения |
| `type:feature` | Новая возможность |
| `type:testing` | Проверки поведения |
| `type:documentation` | Документы и учебные материалы |
| `type:release` | Приёмка и публикация версии |
| `status:partial` | Выполнена и проверена часть критериев |

Область и тип отвечают на разные вопросы. Например, EDU-06 имеет `area:agent`, `type:testing` и `status:partial`. Учебный тикет #13 имеет `area:learning` и `type:documentation`, а выпускной #14 имеет `area:organization` и `type:release`.

```python
# Пример создания одной метки после проверки, что такого имени ещё нет.
gh_json("api", "repos/alanbigulov/chebupelka-jev/labels", "-X", "POST", body={
    "name": "area:agent", "color": "0052CC",
    "description": "Исполняемый агент и его проверки",
})
```

`status:partial` не заменяет Status доски. Она сохраняет факт о покрытии критериев даже тогда, когда задача ещё находится в Бэклоге.

## 5. Целевая версия является родным Milestone

Использовали milestone репозитория, который уже связан с issue и доступен как поле Project. Отдельное текстовое поле "Версия" создало бы вторую запись того же факта и потребовало бы синхронизации.

Изначально создали три milestone через REST. Позже согласованный состав ближайшего выпуска изменился, поэтому для оставшихся исправлений появилась предварительная v0.1.3.

| Milestone | Состав после решения о v0.1.2 |
|---|---|
| [v0.1.2](https://github.com/alanbigulov/chebupelka-jev/milestone/1) | Организация трекера, новый урок, паспорт и метаданные версии; #13 и #14 |
| [v0.1.3](https://github.com/alanbigulov/chebupelka-jev/milestone/4) | EDU-01, EDU-02, EDU-03 и оставшаяся часть EDU-06; план ещё не реализован |
| [v0.2.0](https://github.com/alanbigulov/chebupelka-jev/milestone/2) | Управление командами, конфигурация, рассуждения и ресурсы |
| [v0.3.0](https://github.com/alanbigulov/chebupelka-jev/milestone/3) | Дополнительные инструменты и сохранение сессий |

```python
# Пример первоначального создания; этот milestone уже существует.
gh_json("api", "repos/alanbigulov/chebupelka-jev/milestones", "-X", "POST", body={
    "title": "v0.1.2", "description": "Согласованный учебный выпуск",
})
```

При изменении состава исправили milestone существующих issues и критерии #13/#14. Новые копии EDU-тикетов не понадобились. Сроки не назначены, будущие номера остаются предварительными.

## 6. Status описывает движение работы

У Project уже было поле `Status` с вариантами `Todo`, `In Progress`, `Done`. Его сохранили и расширили до шести русских вариантов.

| Значение | Когда использовать | ID варианта в Project 4 |
|---|---|---|
| Бэклог | Задача записана, работа не начата | `f75ad846` |
| К выполнению | Конкретный объём и критерии согласованы | `59abc02c` |
| В работе | Человек или агент действительно выполняет задачу | `47fc9ee4` |
| Проверка | Результат подготовлен, проверяются критерии | `da1c1536` |
| Заблокировано | Записаны препятствие и условие продолжения | `cc39e2fa` |
| Готово | Критерии проверены, доказательства записаны, issue закрыт | `98236657` |

```text
Бэклог -> К выполнению -> В работе -> Проверка -> Готово
                              |         |
                              +---------+-> Заблокировано
                                              |
                         устранено препятствие +-> нужный этап
```

Переименование сохраняло ID старых вариантов: `Todo` стал Бэклогом, `In Progress` стал В работе, `Done` стал Готово. Это позволяет сохранить связь уже назначенных значений с вариантами. Для новых вариантов ID вернул GitHub.

Сначала прочитали `gh project field-list 4 --owner alanbigulov --format json`, затем передали полный набор вариантов в `updateProjectV2Field`. Пример тела одной опции: `{"id":"f75ad846","name":"Бэклог","color":"GRAY","description":"Записано, исполнение не начато"}`.

```graphql
mutation($id: ID!, $options: [ProjectV2SingleSelectFieldOptionInput!]!) {
  updateProjectV2Field(input: {fieldId: $id, singleSelectOptions: $options}) {
    projectV2Field {
      ... on ProjectV2SingleSelectField { id name options { id name } }
    }
  }
}
```

ID поля Status: `PVTSSF_lAHOC5I5Oc4BmHPpzhkxhbE`. ID поля, ID варианта и имя варианта являются разными данными. После изменения перечитали поле, чтобы получить фактический набор ID.

## 7. Приоритет и порядок являются отдельными полями

Приоритет показывает относительную важность, а Порядок задаёт рекомендуемую последовательность. Номер не является сроком и не запускает работу автоматически.

```bash
# Примеры первоначального создания, уже выполненного.
gh project field-create 4 --owner alanbigulov --name 'Приоритет' \
  --data-type SINGLE_SELECT --single-select-options 'Высокий,Средний,Низкий' \
  --format json
gh project field-create 4 --owner alanbigulov --name 'Порядок' \
  --data-type NUMBER --format json
gh project field-list 4 --owner alanbigulov --format json
```

| Поле | ID | Значения |
|---|---|---|
| Приоритет | `PVTSSF_lAHOC5I5Oc4BmHPpzhkxhho` | Высокий `aa62b70e`, Средний `5d801995`, Низкий `ee929bc8` |
| Порядок | `PVTF_lAHOC5I5Oc4BmHPpzhkxhio` | Число |

Перед созданием проверяли имена в списке полей. После создания перечитывали список, а не вычисляли ID самостоятельно. Сортировку по Порядку пользователь может выбрать в представлении; заполненное поле само по себе не доказывает настройку сортировки.

## 8. Roadmap превращается в проверяемые issues

Строки `EDU-01`...`EDU-12` стали issues #1...#12. Для каждой записали контекст, место в коде, критерии, границы работы, источники и порядок завершения. Скрипт искал совпадения по префиксу `[EDU-XX] ` среди всех issues.

Критерий должен описывать наблюдаемое поведение. Для EDU-01 это одна assistant-запись со всеми вызовами и отдельные результаты инструментов с правильными ID. Фраза "улучшить протокол" не позволяет проверить готовность.

Для EDU-06 сохранили два выполненных пункта v0.1.1 и открытые пункты про несколько инструментов, ошибки, аргументы и предел ходов. Поэтому issue остаётся открытым с `status:partial`.

```python
# Сокращённая форма фактического REST-создания; #1 уже существует.
# Переменная issue_body содержит подготовленный Markdown с критериями.
gh_json("api", "repos/alanbigulov/chebupelka-jev/issues", "-X", "POST", body={
    "title": "[EDU-01] Правильная история нескольких инструментов; протокол сообщений",
    "body": issue_body, "labels": ["area:agent", "type:bug"],
    "milestone": 1, "assignees": ["alanbigulov"],
})
```

Здесь `milestone: 1` описывает первоначальную привязку к v0.1.2. После уточнения выпуска EDU-01 перенесён в v0.1.3. Исторический пример не является инструкцией вернуть задачу в прежний milestone.

В CLI для длинного Markdown используй файл вместо сложного shell-экранирования. Пример редактирования существующего issue, выполняемый только после подготовки актуального текста:

```bash
gh issue edit 13 --repo alanbigulov/chebupelka-jev --body-file issue-body.md
```

Кроме EDU-задач создали [#13, LEARN-v0.1.2](https://github.com/alanbigulov/chebupelka-jev/issues/13) и [#14, RELEASE-v0.1.2](https://github.com/alanbigulov/chebupelka-jev/issues/14). Первый отвечает за урок и паспорт, второй за согласованную приёмку и публикацию.

## 9. Добавляем существующий issue, затем заполняем item

Сначала прочитали items и построили соответствие URL issue и item. Если URL уже находился в Project, использовали найденный item. Если нет, добавляли существующий issue через `item-add`, без отдельного draft item.

```bash
gh project item-list 4 --owner alanbigulov --limit 100 --format json
# Пример первоначального добавления: issue #1 уже находится в Project.
gh project item-add 4 --owner alanbigulov \
  --url https://github.com/alanbigulov/chebupelka-jev/issues/1 --format json
```

Для #1 API вернул issue ID `I_kwDOU_VSps8AAAABVsh4uA` и item ID `PVTI_lAHOC5I5Oc4BmHPpzg_Oo9Y`. Значения полей записываются во второй объект.

```python
# Пример первоначального назначения Бэклога карточке #1.
graphql("""mutation($project: ID!, $item: ID!, $field: ID!, $option: String!) {
  updateProjectV2ItemFieldValue(input: {
    projectId: $project, itemId: $item, fieldId: $field,
    value: {singleSelectOptionId: $option}
  }) { projectV2Item { id } }
}""", project="PVT_kwHOC5I5Oc4BmHPp", item="PVTI_lAHOC5I5Oc4BmHPpzg_Oo9Y",
    field="PVTSSF_lAHOC5I5Oc4BmHPpzhkxhbE", option="f75ad846")
```

Приоритет записывается тем же `singleSelectOptionId`, но с ID поля Приоритет и его варианта. Для числового Порядка используют `value: {number: $orderValue}` и переменную GraphQL типа `Float!`.

Первоначальная настройка помещала все 14 новых карточек в Бэклог. Скрипт задавал значения новым items или items без Status. Повторный запуск не должен сбрасывать этап существующей работы. Наличие issue не означает согласования реализации.

## 10. Три доски показывают одну очередь

| Представление | URL | Фильтр |
|---|---|---|
| Общая доска | [views/1](https://github.com/users/alanbigulov/projects/4/views/1) | Пустой, все 14 исходных задач |
| Код агента | [views/2](https://github.com/users/alanbigulov/projects/4/views/2) | `label:"area:agent"` |
| Учебные материалы | [views/3](https://github.com/users/alanbigulov/projects/4/views/3) | `label:"area:learning"` |

```text
Issue #13 -> один project item
                    |-- Общая доска: виден
                    |-- Код агента: отфильтрован
                    `-- Учебные материалы: виден
```

Представления создали через `createProjectV2View` с `layout: BOARD_LAYOUT`, затем уточнили имя и фильтр через `updateProjectV2View`. Уже существующее единственное представление использовали как Общую доску.

```graphql
mutation($project: ID!, $name: String!) {
  createProjectV2View(input: {projectId: $project, name: $name, layout: BOARD_LAYOUT}) {
    projectV2View { id name number }
  }
}
```

```graphql
mutation($id: ID!, $name: String!, $filter: String!) {
  updateProjectV2View(input: {
    viewId: $id, name: $name, layout: BOARD_LAYOUT, filter: $filter
  }) { projectV2View { id name layout filter } }
}
```

Это две отдельные операции, передаваемые по очереди. В Python значение фильтра записывается как `'label:"area:agent"'`; JSON-сериализация экранирует кавычки для транспорта. Кавычки являются частью синтаксиса фильтра GitHub, поскольку имя метки содержит двоеточие.

## 11. Поля карточки и колонки проверяются отдельно

Во всех трёх видах выбрали поля `Title`, `Assignees`, `Labels`, `Milestone`, `Приоритет`, `Порядок`. Их ID получили из `field-list`, затем передали через `configuration.visibleFieldIds`.

```graphql
mutation($id: ID!, $fields: [ID!]!) {
  updateProjectV2View(input: {
    viewId: $id, configuration: {visibleFieldIds: $fields}
  }) {
    projectV2View {
      id name
      fields(first: 20) { nodes {
        ... on ProjectV2Field { name }
        ... on ProjectV2SingleSelectField { name }
      } }
      verticalGroupByFields(first: 10) { nodes {
        ... on ProjectV2SingleSelectField { name }
      } }
    }
  }
}
```

У Board поле `verticalGroupByFields` описывает колонки. Проверка вернула `Status` для каждого представления. Оно уже было выбрано при создании Board; отдельная мутация колонок не потребовалась.

`groupByFields` описывает дополнительную горизонтальную группировку. Пустой список не означает отсутствие колонок. При настройке сначала проверили это поле, затем уточнили смысл по документации и запросили `verticalGroupByFields`.

Браузерное подключение было недоступно. Поэтому результат подтверждён чтением конфигурации API, без заявления о визуальной проверке расположения или внешнего вида карточек.

## 12. API-проверка должна читать итоговое состояние

Успешная мутация подтверждает приём запроса, но не заменяет итоговую сверку всех связанных объектов. Проверили публичность, связь с репозиторием, 14 issues/items, три Board-представления, фильтры, видимые поля, варианты Status, приоритеты, порядок и milestones.

```graphql
query {
  user(login: "alanbigulov") {
    projectV2(number: 4) {
      id public title
      repositories(first: 10) { nodes { nameWithOwner } }
      views(first: 20) { nodes {
        id name number layout filter
        fields(first: 20) { nodes {
          ... on ProjectV2Field { name }
          ... on ProjectV2SingleSelectField { name }
        } }
        verticalGroupByFields(first: 10) { nodes {
          ... on ProjectV2SingleSelectField { id name }
        } }
        groupByFields(first: 10) { nodes {
          ... on ProjectV2Field { name }
          ... on ProjectV2SingleSelectField { name }
        } }
      } }
      items(first: 100) { totalCount nodes {
        id
        content { ... on Issue {
          number title state url milestone { title }
          labels(first: 20) { nodes { name } }
        } }
        fieldValues(first: 20) { nodes {
          ... on ProjectV2ItemFieldSingleSelectValue {
            name field { ... on ProjectV2SingleSelectField { name } }
          }
          ... on ProjectV2ItemFieldNumberValue {
            number field { ... on ProjectV2Field { name } }
          }
        } }
      } }
    }
  }
}
```

Передай запрос через `gh api graphql --input -` в JSON с ключом `query`, как в помощнике из раздела 3. После изменения состава выпуска перечитай milestones и критерии #13/#14. Первоначальный результат, где EDU-01/02/03/06 ещё имели v0.1.2, описывает историю настройки.

При переносе задач наблюдалось расхождение: поля `open_issues` milestones ещё показывали 6 и 0, хотя issues и Project уже относили две задачи к v0.1.2 и четыре к v0.1.3. Причину расхождения не устанавливали. Фактический состав проверили отдельными списками issues с фильтром milestone:

```bash
gh api 'repos/alanbigulov/chebupelka-jev/issues?state=open&milestone=1&per_page=100' \
  --jq 'map({number, milestone: .milestone.title})'
gh api 'repos/alanbigulov/chebupelka-jev/issues?state=open&milestone=4&per_page=100' \
  --jq 'map({number, milestone: .milestone.title})'
```

Первая проверка дала #13/#14, вторая #1/#2/#3/#6. После закрытия выпускных задач список открытых issues milestone #1 должен стать пустым. Это проверка реальных задач, которая не подменяется одним агрегированным счётчиком.

При исследовании схемы GitHub ограничил один introspection-запрос максимум двумя полями `__type(...){inputFields...}`. Вместо одного большого запроса использовали несколько небольших. Например, так можно отдельно проверить тип настройки view:

```bash
gh api graphql -f query='query {
  __type(name: "UpdateProjectV2ViewInput") {
    inputFields { name type { kind name ofType { kind name } } }
  }
}'
```

Это ограничение наблюдалось при настройке данного проекта. Оно не является правилом языка GraphQL. Схему следует читать у сервиса, а не угадывать имя входного поля по названию элемента интерфейса.

## 13. Как работать с кодом, обучением и приёмкой

| Область | Исходные задачи | Где читать результат |
|---|---|---|
| Код агента | [#1](https://github.com/alanbigulov/chebupelka-jev/issues/1)...[#12](https://github.com/alanbigulov/chebupelka-jev/issues/12), EDU-01...EDU-12 | Issue, коммит/PR, локальные проверки, связанный урок |
| Учебный выпуск | [#13](https://github.com/alanbigulov/chebupelka-jev/issues/13), LEARN-v0.1.2 | Этот урок, паспорт, навигация и проверка ссылок |
| Приёмка | [#14](https://github.com/alanbigulov/chebupelka-jev/issues/14), RELEASE-v0.1.2 | Согласованный состав, результаты, тег и удалённые SHA |

Перед работой выбери issue и конкретные критерии. При реальном начале поставь В работе, после подготовки результата поставь Проверка. Запиши команды проверки, полученные результаты и оставшиеся ограничения. После выполнения всех согласованных критериев закрой issue и явно проверь Готово в Project.

Состояние issue `OPEN/CLOSED` и Status Project независимы. Закрытие issue не является доказательством автоматического перемещения карточки. При повторном открытии задачи также проверь её этап.

EDU-06 не следует закрывать из-за двух успешных существующих тестов. Проверены обычный ответ и один `pwd`; остальные пункты остаются открытыми. Тесты подменяют HTTP и не доказывают работу облачной модели.

Первоначально ближайший план включал EDU-06, EDU-01, EDU-02/03, уроки и выпуск. После решения владельца v0.1.2 ограничена трекером, уроком и метаданными. Эти EDU-задачи перенесены в v0.1.3, а учебный и выпускной тикеты уточнены под фактический состав. Код и тесты в v0.1.2 не менялись; новых запросов к DeepSeek не выполняли.

## 14. Документы сохраняют объяснение, GitHub хранит текущую работу

| Информация | Основной источник |
|---|---|
| Критерии задачи, обсуждение, доказательства | GitHub Issue |
| Текущий этап, приоритет, порядок | Project |
| Целевой выпуск | Milestone issue |
| Правила использования очереди | [project-tracking.md](../project-tracking.md) |
| Учебный смысл задач | [development-roadmap.md](../development-roadmap.md) |
| Решения о каталогах | [project-structure.md](../project-structure.md) |
| Реализованная история выпусков | [CHANGELOG.md](../../CHANGELOG.md) |
| Код и урок конкретного выпуска | Git-тег и его полный SHA |

Roadmap ссылается на issues и объясняет, чему учит изменение. Он не хранит независимую копию текущих этапов. Старые BASE-этапы остались историей; ретроспективные issues для уже завершённой подготовки не создавали.

Тег замораживает Markdown урока, но не внешние данные GitHub. Статус на доске сегодня может отличаться от первоначального статуса, описанного здесь. Ссылки на код урока закреплены за выпуском; ссылка на Project ведёт к актуальной очереди.

## 15. Локальная передача сохраняет незавершённый контекст

Для продолжения между агентами используется игнорируемая корневая `.handoff/`. Передача кратко фиксирует текущее состояние, выполненные проверки, согласованный объём и следующий шаг со ссылками на issues. Перед продолжением агент сверяет эти записи с Git и GitHub. Папка не входит в публикацию и не появляется при клонировании; публичные тикеты содержат проверяемые результаты работы.

## 16. Выпуск связывает проверку, тег и закрытие задач

Для v0.1.2 версия Python-проекта и запись локального проекта в lock-файле имеют `0.1.2`. Версии зависимостей сохранены. Полный процесс находится в [VERSIONING.md](../../VERSIONING.md); здесь приведены проверки этого состава.

```bash
# Из корня, до создания тега.
git diff --check
git diff v0.1.1 -- agent/chebupelkajev.py agent/tests
git status --short --branch
cd agent
uv lock --check --offline
uv run --locked python -m unittest discover -s tests -v
```

Пустой diff программы и тестов подтверждает сохранность файлов. Оба существующих теста должны пройти. Отдельно проверяют согласованность версии, ссылки урока, отсутствие приватных данных и подготовленный состав коммита. Из `agent/` перед Git-командами публикации вернись в корень через `cd ..`.

Последовательность приёмки и публикации, а не заявление, что все действия уже завершены:

1. Проверить урок и паспорт по критериям #13, записать доказательства.
2. Принять согласованный состав по #14, подготовить коммит и новый аннотированный тег `v0.1.2`.
3. Опубликовать `main` и тег, проверить удалённый коммит и целевой коммит тега.
4. Записать окончательные ссылки и результаты, закрыть #13/#14 и синхронизировать их Status с Готово.
5. Проверить, что все задачи milestone v0.1.2 приняты; только затем закрыть milestone.

```bash
# Проверка после публикации, из корня.
git rev-parse HEAD
git rev-parse 'v0.1.2^{}'
git ls-remote origin refs/heads/main refs/tags/v0.1.2 'refs/tags/v0.1.2^{}'
gh issue view 13 --repo alanbigulov/chebupelka-jev
gh issue view 14 --repo alanbigulov/chebupelka-jev
gh api repos/alanbigulov/chebupelka-jev/milestones/1
```

У аннотированного тега собственный объект. Удалённая строка `refs/tags/v0.1.2^{}` показывает коммит, который сравнивают с локальным разрешённым тегом. Старые v0.1.0 и v0.1.1 не передвигают. GitHub Release является отдельным объектом и не возникает от создания Git-тега.

## 17. Практическая проверка понимания

Без изменения GitHub открой общую доску, затем учебное представление и issue #13. Объясни, почему это одна задача в двух представлениях. Прочитай #6 и назови два подтверждённых сценария и оставшиеся пункты. Через API найди milestone #1 и Status соответствующего project item.

| Ошибка | Как проверить и исправить понимание |
|---|---|
| Создать draft item рядом с issue | Искать item по URL существующего issue |
| Принять пустой `groupByFields` за отсутствие колонок | Читать `verticalGroupByFields` |
| Назвать настройку API визуальным тестом | Разделять данные конфигурации и наблюдение в браузере |
| Отметить EDU-06 Готово после двух тестов | Сверить весь checklist, оставить `status:partial` |
| Хранить версию в milestone и текстовом поле | Использовать родной Milestone issue |
| Скопировать актуальные статусы в roadmap | Хранить этап в Project, в roadmap оставить учебный смысл |
| Повторить создание при продолжении настройки | Сначала прочитать объекты и сопоставить их ID/URL |

## Источники и дальнейшее чтение

- [GitHub Docs: About Projects](https://docs.github.com/en/issues/planning-and-tracking-with-projects/learning-about-projects/about-projects), [Using the API to manage Projects](https://docs.github.com/en/issues/planning-and-tracking-with-projects/automating-your-project/using-the-api-to-manage-projects).
- [GitHub Docs: Customizing the board layout](https://docs.github.com/en/issues/planning-and-tracking-with-projects/customizing-views-in-your-project/customizing-the-board-layout), [Filtering projects](https://docs.github.com/en/issues/planning-and-tracking-with-projects/customizing-views-in-your-project/filtering-projects).
- [GitHub CLI: gh project](https://cli.github.com/manual/gh_project), [gh api](https://cli.github.com/manual/gh_api), [gh issue edit](https://cli.github.com/manual/gh_issue_edit).
- [GraphQL mutations GitHub](https://docs.github.com/en/graphql/reference/mutations), [REST milestones](https://docs.github.com/en/rest/issues/milestones), [REST labels](https://docs.github.com/en/rest/issues/labels).
- [Project 4](https://github.com/users/alanbigulov/projects/4), [issues репозитория](https://github.com/alanbigulov/chebupelka-jev/issues), [правила трекинга](../project-tracking.md).
- [README проекта](../../README.md), [README обучения](../README.md), [VERSIONING.md](../../VERSIONING.md), [CHANGELOG.md](../../CHANGELOG.md), [паспорт этого урока](version.md).
