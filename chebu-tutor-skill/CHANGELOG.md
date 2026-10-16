# История изменений chebu-tutor

Здесь фиксируются существенные изменения навыка `chebu-tutor`. Номер версии хранит [skill.json](skill.json). Правила номеров, тегов и выпуска описаны в [versioning.md](chebu-tutor-docs/versioning.md). Изменения `chebu` ведёт [CHANGELOG.md](../CHANGELOG.md) проекта.

## [Unreleased]

### Каркас

- Добавлен [skill.json](skill.json): имя `chebu-tutor`, версия `0.1.0`, требования `handoff_schema` 2 и `chebu_min_version` `0.1.4`.
- Добавлены тесты [test_skill_json.py](tests/test_skill_json.py): имя навыка, формат версии, схема снимка из [шаблона](../.handoff/TEMPLATE.md) и формат минимальной версии `chebu`.
- Добавлен этот CHANGELOG.

Навык ещё нельзя вызвать: канонического текста, генератора и адаптеров нет.
