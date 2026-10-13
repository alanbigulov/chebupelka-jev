# EDU-08. Работа с режимом рассуждений DeepSeek

| Поле | Значение |
|---|---|
| ID | EDU-08 |
| Учебная тема | Полный ответ API |
| Область и тип | area:agent, type:feature |
| Место изменения | `call_llm()` и история |
| Исходная база | v0.1.1 |
| Целевая версия в трекере владельца | v0.2.0 |
| Issue в трекере владельца | [#8](https://github.com/alanbigulov/chebupelka-jev/issues/8) |

## Критерии готовности

- [ ] `reasoning_content` сохраняется согласно протоколу.
- [ ] Цикл инструмента проверен с thinking enabled.
- [ ] Необходимые локальные проверки результата проходят без реального API.
- [ ] Ссылки на изменения и результаты проверки записаны в трекере: в issue или в снимке `.handoff/`.
- [ ] Учебное объяснение изменения записано и связано с версией, в которую изменение входит.

## Источники

- [Код исходной базы](https://github.com/alanbigulov/chebupelka-jev/blob/v0.1.1/agent/chebupelkajev.py).
- [Существующие локальные проверки](https://github.com/alanbigulov/chebupelka-jev/blob/v0.1.1/agent/tests/test_agent.py).
- [Учебный roadmap](../development-roadmap.md).
- [Паспорта уроков](../README.md).
