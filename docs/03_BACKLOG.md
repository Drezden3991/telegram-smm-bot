# BACKLOG — SMM Bot / SMM Platform

Дата обновления: 22.08.2026

---

# 1. Назначение BACKLOG

BACKLOG используется для хранения:

- будущих продуктовых идей;
- технического долга;
- известных некритических ошибок;
- продуктовых гипотез;
- AI-экспериментов;
- compliance-задач;
- идей, которые могут улучшить продукт, но сейчас не входят в текущий scope;
- задач, необходимость которых должна подтвердиться реальной работой пользователей.

BACKLOG НЕ является ROADMAP.

Порядок разработки определяется:

`docs/PROJECT_ROADMAP.md`

---

# 2. Текущий статус проекта

Завершено:

- ✅ Stage 1 — основной MVP;
- ✅ Stage 2 — интеграция разделов;
- ✅ Stage 3 — архитектура v2.5;
- ✅ Stage 4 — AI;
- ✅ Stage 5 — коммерческая подготовка.

Текущий параллельный этап:

- 🟡 Stage 6 — тестирование заказчицей и стабилизация.

Следующий этап активной разработки:

- ⬜ Stage 7 — Brand Voice.

Дальнейшая последовательность определяется ROADMAP.

---

# 3. Текущий технический baseline

На 22.08.2026 проект уже имеет:

- SQLite;
- миграции;
- multi-user isolation;
- `telegram_user_id`;
- RedisStorage для FSM;
- OpenAI;
- Gemini;
- Groq;
- AI Content Plan;
- AI Write Post;
- AI Post Ideas;
- Structured Outputs там, где требуется структура;
- Pydantic validation;
- domain-specific AI errors;
- production logging;
- backup databases;
- health check;
- deployment documentation;
- systemd examples;
- no-AI mode;
- legacy migration tools;
- 375 автоматических тестов.

Реальные API smoke-тесты успешно выполнены для всех 9 AI-сценариев:

- OpenAI Content Plan;
- Gemini Content Plan;
- Groq Content Plan;
- OpenAI Write Post;
- Gemini Write Post;
- Groq Write Post;
- OpenAI Post Ideas;
- Gemini Post Ideas;
- Groq Post Ideas.

---

# 4. Обратная связь заказчицы

Статус: 🟡 Активно во время Stage 6

Во время пользовательского тестирования фиксировать все замечания.

Каждое замечание классифицировать как:

- 🐞 Bug;
- 🎨 UX issue;
- 💡 Feature request;
- 🤖 AI quality problem;
- ⚙️ Technical issue;
- ❓ непонятное поведение;
- 📝 личное предпочтение;
- 🔁 повторяющаяся рабочая проблема.

Не реализовывать автоматически каждое пожелание.

Перед добавлением в ROADMAP проверить:

- проблема повторяется?
- экономит ли решение время?
- улучшает ли качество?
- убирает ли рутину?
- усиливает ли существующие функции?
- нужна ли функция нескольким пользователям?
- можно ли решить проблему проще?

---

# 5. Реальные AI-проблемы как regression cases

Статус: 💡 BACKLOG

Приоритет: Средний

Сохранять реальные проблемные AI-примеры, обнаруженные заказчицей или разработчиком.

Типы:

- выдуманные акции;
- выдуманные скидки;
- выдуманные услуги;
- выдуманные товары;
- выдуманные контакты;
- выдуманный адрес;
- выдуманные часы работы;
- выдуманные отзывы;
- выдуманные награды;
- выдуманная статистика;
- мягкие галлюцинации;
- нарушение Brand Voice;
- неправильный JSON;
- нарушение структуры;
- дубли идей;
- плохое следование prompt.

Использовать такие случаи при:

- изменении AI-contract;
- изменении prompt;
- обновлении модели;
- смене provider;
- обновлении SDK;
- изменении Structured Output schema.

Не создавать пока большой AI evaluation framework.

Начать с небольшого набора реальных regression cases.

---

# 6. AI hallucination protection

Статус: ⏸ Не внедрять без новых данных

Ранее исследовался детерминированный AI safety validator.

Эксперимент показал:

- ложные срабатывания;
- пропуск мягких галлюцинаций;
- быстро растущую сложность;
- невозможность надёжно определять семантическую истинность простыми правилами.

Решение:

НЕ использовать такой validator в runtime сейчас.

Текущая защита:

- AI-contract;
- подтверждённый клиентский контекст;
- Structured Outputs;
- Pydantic;
- Human Review.

Вернуться к дополнительной защите только если реальные пользовательские тесты покажут необходимость.

---

# 7. Human Review

Статус: 🎯 Постоянный продуктовый принцип

AI-результат считается черновиком.

Базовый workflow:

AI generates
→ user reviews
→ user edits if necessary
→ user confirms

До отдельного решения и compliance review не допускать полностью автоматическую публикацию AI-контента без участия пользователя.

---

# 8. AI Act / прозрачность AI-контента

Статус: 💡 Compliance BACKLOG

Приоритет:

До серьёзного коммерческого масштабирования.

Изучить применимость:

- EU AI Act Article 50;
- роли provider/deployer;
- AI-generated content;
- AI-manipulated content;
- machine-readable marking;
- transparency requirements.

Отдельно проверить требования для:

- текста;
- изображений;
- аудио;
- видео;
- deepfakes;
- материалов по вопросам общественного интереса.

Продумать хранение признаков:

- создано AI;
- изменено AI;
- отредактировано человеком;
- подтверждено человеком.

Изучить:

- Code of Practice on Transparency of AI-generated Content.

Перед крупным коммерческим масштабированием провести отдельный AI Act compliance review.

---

# 9. FSM — кнопки меню как пользовательский ввод

Статус: 🐞 Известная UX-проблема

Приоритет: Средний

Проблема:

Когда FSM ожидает свободный текст, обычная keyboard может оставаться доступной.

Пользователь может нажать другую кнопку меню, и её текст потенциально будет воспринят как ввод.

Пример:

1. пользователь выбирает добавление данных;
2. FSM ожидает текст;
3. пользователь нажимает другую кнопку;
4. название кнопки может попасть в данные.

Возможные решения:

- скрывать обычную клавиатуру;
- показывать только `Отмена`;
- перехватывать navigation buttons;
- создать единый FSM navigation pattern.

Не исправлять массово во время тестирования заказчицей без подтверждения проблемы.

Если заказчица столкнётся с этим — повысить приоритет.

---

# 10. Пагинация

Статус: 💡 Technical / UX BACKLOG

Сейчас небольшие списки допустимы.

Понадобится при росте количества:

- клиентов;
- идей;
- постов;
- контент-планов.

Возможные варианты:

- Previous / Next;
- page size;
- search-first UX.

Не внедрять пока реальные списки остаются небольшими.

---

# 11. Поиск и фильтрация

Статус: 💡 BACKLOG

По мере роста данных могут понадобиться:

- поиск по клиенту;
- поиск по статусу;
- поиск по платформе;
- поиск по дате;
- фильтрация Post Ideas;
- фильтрация Posts;
- фильтрация Content Plans.

Большая часть расширенной фильтрации вероятнее относится к будущему Web Content Workspace.

Не перегружать Telegram сложными фильтрами.

---

# 12. Универсальный AIProvider

Статус: ⏸ Не внедрять без необходимости

Сейчас существуют отдельные provider-модули:

- OpenAI;
- Gemini;
- Groq.

Для текущего размера проекта это нормально.

Не вводить заранее:

- interface;
- abstract provider;
- factory;
- adapter hierarchy;
- provider registry framework.

Вернуться к общей архитектуре только если:

- количество AI-провайдеров сильно увеличится;
- повторение действительно мешает;
- появляется сложное dynamic routing;
- возникает устойчивая общая логика.

---

# 13. Dynamic AI routing

Статус: 💡 Долгосрочная идея

В будущем система потенциально может выбирать AI автоматически на основе:

- стоимости;
- скорости;
- качества;
- типа задачи;
- тарифа пользователя;
- доступности provider.

Пример:

простая задача
→ дешёвая/быстрая модель

сложный Content Plan
→ более сильная модель

Не внедрять до накопления:

- реальной статистики качества;
- стоимости;
- latency;
- пользовательских предпочтений.

---

# 14. Учёт стоимости AI

Статус: 💡 BACKLOG

Нужно перед масштабированием.

Собирать:

- provider;
- model;
- тип операции;
- количество запросов;
- input/output tokens, если доступны;
- стоимость;
- среднюю стоимость пользователя;
- среднюю стоимость одной AI-функции.

Использовать данные для:

- тарифов;
- AI limits;
- выбора моделей;
- unit economics.

Не определять коммерческие тарифы только теоретически.

---

# 15. AI fallback

Статус: 💡 BACKLOG

В будущем можно рассмотреть сценарий:

OpenAI unavailable
→ предложить Gemini / Groq.

Или:

provider error
→ пользователь выбирает другой provider.

Автоматический fallback не должен:

- незаметно менять модель;
- создавать неожиданные расходы;
- скрывать ошибки.

Решать после накопления production experience.

---

# 16. Provider quality statistics

Статус: 💡 BACKLOG

После достаточного реального использования можно собирать:

- provider;
- generation type;
- latency;
- success/failure;
- user accepted result;
- user regenerated result;
- amount of manual editing.

Использовать для понимания:

- какой AI лучше для какой задачи;
- где модели чаще ошибаются;
- какая модель экономически выгоднее.

Не превращать это сейчас в сложную telemetry platform.

---

# 17. Brand Voice improvements

Статус: 💡 BACKLOG после базового Stage 7

Stage 7 создаёт первую простую версию Brand Voice.

После реального использования можно рассмотреть:

- несколько Brand Voice profiles;
- Brand Voice presets;
- автоматическое определение tone из примеров;
- импорт старых публикаций;
- positive examples;
- negative examples;
- platform-specific tone;
- campaign-specific voice.

Не включать всё это в первую версию Stage 7.

---

# 18. Client Knowledge / Project Memory

Статус: 💡 Будущая идея

Возможность хранить более широкий рабочий контекст клиента:

- факты;
- продукты;
- услуги;
- terminology;
- current campaigns;
- restrictions;
- decisions;
- previous successful content.

Цель:

AI не должен каждый раз получать всё заново вручную.

Не превращать Stage 7 Brand Voice сразу в полноценную RAG/knowledge-base систему.

Развивать только если простой Client + Brand Voice начинает реально ограничивать продукт.

---

# 19. Content Categories

Статус: 💡 BACKLOG

Возможные категории:

- экспертный;
- продающий;
- информационный;
- вовлекающий;
- развлекательный;
- репутационный;
- пользовательские категории.

Потенциальное использование:

- Content Plan;
- Analytics;
- filtering;
- AI recommendations.

Вернуться к функции, когда появятся реальные метрики и достаточно контента.

---

# 20. Content Library

Статус: 💡 BACKLOG

В будущем хранить reusable материалы:

- CTA;
- hashtags;
- links;
- templates;
- удачные формулировки;
- snippets;
- media;
- campaign assets.

Текстовая часть может появиться раньше.

Полноценная media library относится к Web roadmap.

---

# 21. Templates

Статус: 💡 BACKLOG

Сейчас существует базовый no-AI template mode.

В будущем возможны:

- пользовательские шаблоны;
- шаблоны агентства;
- шаблоны клиента;
- шаблоны типов постов;
- template variables.

Не создавать сложный template engine без подтверждённой необходимости.

---

# 22. Hashtag assistance

Статус: 💡 BACKLOG

Возможности:

- предложить hashtags;
- сохранить группы;
- client-specific hashtags;
- platform-specific groups;
- избегать повторения.

Рассматривать как небольшое усиление существующего Write Post, а не отдельный раздел.

---

# 23. CTA Library

Статус: 💡 BACKLOG

Хранить:

- CTA клиента;
- тип CTA;
- platform;
- campaign;
- performance later.

Можно интегрировать в Content Library.

Не делать отдельный крупный раздел.

---

# 24. Campaigns

Статус: 💡 Долгосрочная продуктовая идея

Возможность группировать контент вокруг кампании:

Campaign
→ Content Plan
→ Posts
→ Platforms
→ Publishing
→ Analytics

Может стать полезно после появления Web и Scheduling.

Не добавлять сейчас в Telegram.

---

# 25. Notifications

Статус: 💡 BACKLOG

Telegram особенно хорошо подходит для уведомлений.

Будущие события:

- контент требует согласования;
- клиент оставил комментарий;
- публикация запланирована;
- публикация успешно выполнена;
- публикация не удалась;
- отчёт готов;
- обнаружено важное упоминание.

Реализовывать вместе с соответствующим функциональным этапом, а не заранее.

---

# 26. Client Approval improvements

Статус: 💡 После базового Stage 12

После первой простой версии можно рассмотреть:

- несколько approvers;
- approval deadline;
- reminders;
- approval history;
- approval links;
- guest approval;
- multi-step approval.

Не строить enterprise workflow в первой версии.

---

# 27. Version History improvements

Статус: 💡 После Stage 13

Возможные улучшения:

- сравнение версий;
- restore;
- author;
- timestamp;
- AI/user/client source;
- diff view в Web.

Telegram должен показывать только простые версии.

Полноценный diff лучше делать в Web.

---

# 28. Audio improvements

Статус: 💡 После Stage 14

После базового Audio → Content можно рассмотреть:

- speaker separation;
- long audio;
- meeting summaries;
- extraction of tasks;
- extraction of client facts;
- automatic brief generation.

Не включать это в первую audio-версию.

---

# 29. Images / AI images

Статус: 💡 Будущее исследование

Возможности:

- генерация изображений;
- изменение изображений;
- resize/crop;
- social platform formats;
- captions;
- alt text.

Перед реализацией оценить:

- реальную необходимость;
- стоимость;
- copyright;
- AI Act;
- platform policies.

Вероятнее относится к Web/Media Library этапам.

---

# 30. Video

Статус: 💡 Долгосрочная идея

Потенциально:

- transcription;
- captions;
- clip suggestions;
- post generation from video;
- short-form content ideas.

Не приоритет до завершения основной Content Platform.

---

# 31. Social publishing integrations

Статус: 💡 Research BACKLOG до соответствующего ROADMAP stage

Перед Stage 20 исследовать API конкретных сетей.

Проверить:

- Meta Graph API;
- Instagram;
- Facebook;
- LinkedIn;
- Telegram;
- Threads;
- TikTok;
- другие платформы по запросу пользователей.

Для каждой:

- OAuth;
- scopes;
- publishing API;
- limitations;
- review requirements;
- quotas;
- costs;
- account requirements.

Не пытаться одновременно подключить все сети.

---

# 32. Background jobs

Статус: 💡 Technical BACKLOG для Web/Publishing

Понадобятся для:

- scheduled publishing;
- retries;
- analytics import;
- reports;
- notifications;
- token refresh;
- social listening.

Не выбирать Celery/RQ/другую систему заранее.

Выбрать решение при появлении реальной задачи.

---

# 33. Analytics data model

Статус: 💡 Technical BACKLOG

До Stage Analytics определить структуру хранения:

- platform;
- account;
- publication;
- metrics snapshot;
- timestamp;
- engagement;
- audience metrics.

Важно учитывать, что разные соцсети предоставляют разные метрики.

Не проектировать универсальную огромную schema заранее.

---

# 34. Best Time algorithm

Статус: 💡 BACKLOG

Не использовать:

«лучшее время вообще для Instagram».

Использовать реальные данные конкретного:

- клиента;
- account;
- platform;
- content type.

Сначала накопить достаточно данных.

Только потом делать рекомендации.

---

# 35. AI Analytics

Статус: 💡 BACKLOG для соответствующего ROADMAP stage

AI может анализировать:

- лучшие темы;
- форматы;
- CTA;
- категории;
- posting times;
- engagement patterns.

AI должен опираться на реальные показатели.

Не выдавать догадки как статистический факт.

---

# 36. Reports improvements

Статус: 💡 BACKLOG

После базовых Reports возможны:

- PDF;
- branded reports;
- custom periods;
- scheduled reports;
- email delivery;
- client comments;
- custom metrics;
- agency templates.

Не включать всё в первую версию отчётов.

---

# 37. Unified Inbox — AI assistance

Статус: 💡 BACKLOG

После появления Inbox:

AI может:

- классифицировать сообщения;
- определить тему;
- предложить ответ;
- суммировать conversation;
- выделить срочные обращения.

Пользователь контролирует отправку.

Не разрешать AI самостоятельно отвечать клиентам по умолчанию.

---

# 38. Social Listening scope

Статус: 💡 Исследование

Перед реализацией выяснить:

- какие данные реально доступны через API;
- ограничения соцсетей;
- стоимость;
- legal/privacy вопросы;
- качество sentiment analysis.

Не строить собственный большой crawler без необходимости.

---

# 39. Competitor Analysis limitations

Статус: 💡 Исследование

Функция должна использовать только легально доступные данные.

Не:

- обходить ограничения платформ;
- копировать чужой контент;
- выдавать приблизительные данные как точные.

Главная цель:

- выявление тем;
- тенденций;
- форматов;
- opportunities.

---

# 40. Team / Agency improvements

Статус: 💡 После базового Stage 25

В будущем возможны:

- organizations;
- workspaces;
- multiple teams;
- custom roles;
- permissions;
- audit log;
- agency branding;
- client portals;
- billing per workspace.

Не строить enterprise RBAC раньше реальных agency users.

---

# 41. Monetization

Статус: 💡 Product BACKLOG

Потенциальная модель:

- Free;
- Pro;
- Agency.

Возможные ограничения тарифа:

- количество клиентов;
- количество пользователей;
- AI requests;
- providers;
- analytics;
- reports;
- publishing accounts;
- storage.

Цены определять после получения данных о:

- использовании;
- AI cost;
- infrastructure cost;
- willingness to pay;
- типах пользователей.

---

# 42. AI credits / limits

Статус: 💡 BACKLOG

Возможный подход:

тариф
→ базовый AI allowance

дорогие дополнительные генерации
→ credits.

Не создавать систему кредитов до понимания unit economics.

---

# 43. Billing

Статус: 💡 Долгосрочная коммерческая задача

Понадобится после подтверждения платной модели.

Исследовать:

- Stripe;
- Paddle;
- другие варианты для EU;
- VAT;
- invoices;
- subscriptions;
- refunds.

Не реализовывать до реальной необходимости.

---

# 44. Privacy / GDPR

Статус: 💡 Compliance BACKLOG

Перед более широким коммерческим запуском проверить:

- какие персональные данные хранятся;
- зачем они хранятся;
- retention;
- deletion;
- export;
- subprocessors;
- AI providers;
- logs;
- backups;
- access rights.

Нужно предусмотреть:

- delete account/data;
- export;
- privacy notice;
- data retention rules.

---

# 45. Terms of Service

Статус: 💡 Compliance BACKLOG

Перед публичным коммерческим запуском подготовить:

- Terms of Service;
- Privacy Policy;
- AI disclaimer;
- acceptable use;
- limitation of liability;
- user responsibility за финальный публикуемый контент.

Не копировать шаблон без юридической проверки.

---

# 46. Security review

Статус: ⏸ Перед публичным Web/Commercial launch

Проверить:

- secrets;
- API keys;
- `.env`;
- authentication;
- authorization;
- user isolation;
- SQL queries;
- logging;
- backups;
- Redis;
- server configuration;
- HTTPS;
- session management;
- OAuth tokens;
- dependencies.

Добавить security regression tests там, где это оправдано.

---

# 47. Rate limiting

Статус: 💡 Technical BACKLOG

Понадобится при публичном использовании.

Защищать:

- AI endpoints;
- auth;
- public APIs;
- expensive operations.

Не внедрять сложную систему до появления публичного API/Web.

---

# 48. Abuse protection

Статус: 💡 Future BACKLOG

При публичном доступе оценить:

- spam;
- bot abuse;
- expensive AI abuse;
- credential attacks;
- excessive requests.

Решения определять по реальным угрозам.

---

# 49. Audit log

Статус: 💡 Future BACKLOG

Может понадобиться для:

- team;
- agency;
- approval;
- publishing;
- security.

Примеры:

- кто изменил Post;
- кто одобрил;
- кто запланировал;
- кто опубликовал.

Не нужен для текущего single-SMM workflow.

---

# 50. Observability

Статус: 💡 Technical BACKLOG

Сейчас есть logging и health check.

В будущем возможны:

- metrics;
- error tracking;
- uptime monitoring;
- alerts;
- request tracing.

Выбрать инструменты после реального server deployment.

---

# 51. Database evolution

Статус: 💡 Technical BACKLOG

SQLite подходит текущему масштабу.

Переход на PostgreSQL рассматривать только если появится реальная причина:

- Web;
- concurrency;
- larger user base;
- complex queries;
- analytics;
- background jobs.

Не мигрировать только потому, что PostgreSQL считается более production-oriented.

---

# 52. Redis evolution

Статус: 💡 Technical BACKLOG

Redis сейчас используется для FSM.

В будущем потенциально:

- cache;
- job coordination;
- rate limiting;
- temporary tokens.

Не превращать Redis автоматически в универсальное хранилище.

---

# 53. Caching

Статус: 💡 Technical BACKLOG

Добавлять только для подтверждённых bottlenecks.

Потенциально:

- expensive external API calls;
- analytics;
- repeated static data.

Не оптимизировать заранее.

---

# 54. Project Memory Lite

Статус: 💡 Developer Experience BACKLOG

Идея:

хранить внутри проекта краткую историю важных технических решений.

Например:

- почему выбран SQLite;
- почему Redis;
- почему отказались от AI safety validator;
- почему нет Repository Pattern;
- почему Telegram остаётся частью продукта;
- почему Web начинается после определённой точки.

Цель:

разработчик и AI понимают причины решений без чтения всей истории чатов.

Не хранить все разговоры.

Возможный формат:

`docs/DECISIONS.md`

или ADR-lite.

---

# 55. AI Regression Kit

Статус: 💡 Developer Tool BACKLOG

Будущий небольшой reusable tool для проверки:

- OpenAI;
- Gemini;
- Groq;
- новых моделей;
- новых prompts.

Использовать реальные production examples.

Не превращать сейчас в отдельный большой проект.

---

# 56. Repo Doctor / maintenance-check

Статус: 💡 Developer Tool BACKLOG

После стабильного релиза можно автоматизировать проверку:

- dependencies;
- deprecated APIs;
- tests;
- docs;
- architecture;
- security basics;
- TODO;
- BACKLOG;
- ROADMAP;
- dead code.

Рассмотреть после обязательного maintenance-pass.

---

# 57. Automated dependency updates

Статус: 💡 BACKLOG

После стабильного server deployment рассмотреть:

- Dependabot;
- Renovate;
- аналогичный инструмент.

Обновления не должны автоматически попадать в production без тестов.

---

# 58. CI

Статус: 💡 Technical BACKLOG

Если ещё не появится раньше, рассмотреть GitHub Actions для:

- pytest;
- compile check;
- linting;
- migration checks.

Не усложнять pipeline раньше необходимости.

---

# 59. Formatting / linting

Статус: 💡 Developer Experience BACKLOG

В будущем рассмотреть:

- Ruff;
- formatter;
- import checking.

Добавлять только если это улучшает работу и не создаёт шум.

---

# 60. Type checking

Статус: 💡 Technical BACKLOG

В будущем можно рассмотреть:

- mypy;
- pyright.

Не требовать 100% strict typing от текущего проекта без реальной пользы.

---

# 61. Test strategy evolution

Статус: 💡 Technical BACKLOG

Сейчас:

375 automated tests.

Дальше тесты добавлять для:

- bugs;
- important business rules;
- multi-user isolation;
- migrations;
- AI integration contracts;
- security-sensitive behavior.

Не тестировать implementation details ради увеличения числа тестов.

Перед рискованными изменениями использовать characterization tests.

---

# 62. Load testing

Статус: 💡 Future BACKLOG

Не требуется на текущем этапе.

Понадобится после появления:

- публичного Web;
- большого числа пользователей;
- background jobs;
- publishing;
- analytics.

---

# 63. Data export

Статус: 💡 Product / GDPR BACKLOG

В будущем пользователь должен иметь возможность экспортировать:

- clients;
- posts;
- ideas;
- plans;
- metrics.

Форматы определить позже:

- JSON;
- CSV;
- ZIP.

---

# 64. Data deletion

Статус: 💡 Product / GDPR BACKLOG

Нужен понятный workflow:

- удалить клиента;
- удалить его связанные данные;
- удалить account;
- удалить все пользовательские данные.

Особенно важно после появления Web accounts.

---

# 65. Import

Статус: 💡 Product BACKLOG

Возможный импорт:

- existing clients;
- posts;
- CSV;
- old social content;
- Brand Voice examples.

Добавлять только если реальные пользователи сталкиваются с проблемой ручного переноса.

---

# 66. Onboarding

Статус: 💡 Product BACKLOG

При появлении новых пользователей понадобится первый сценарий:

1. создать клиента;
2. заполнить минимальный контекст;
3. создать идею;
4. создать Content Plan;
5. получить Post.

Не строить большой tutorial.

Лучше короткий guided workflow.

---

# 67. Demo data

Статус: 💡 Product BACKLOG

В Web можно рассмотреть demo workspace, чтобы пользователь сразу увидел:

- клиента;
- идеи;
- план;
- пост;
- workflow.

Не смешивать demo-data с реальными пользовательскими данными.

---

# 68. Product analytics

Статус: 💡 Future BACKLOG

После появления большего числа пользователей можно анонимно/корректно измерять:

- какие функции используются;
- где пользователи бросают workflow;
- сколько AI generations;
- сколько posts создаётся;
- какие функции почти не используются.

Учитывать privacy/GDPR.

---

# 69. Feature flags

Статус: 💡 Technical BACKLOG

Могут понадобиться для:

- beta features;
- AI providers;
- experiments;
- staged rollout.

Не внедрять раньше появления реальной необходимости.

---

# 70. Search across workspace

Статус: 💡 Web BACKLOG

В будущем единый поиск по:

- clients;
- posts;
- ideas;
- content plans;
- campaigns;
- assets.

Вероятнее полезен уже в Web.

---

# 71. Dashboard

Статус: 💡 Web BACKLOG

Возможные элементы:

- upcoming posts;
- awaiting approval;
- failed publications;
- recent activity;
- key metrics;
- AI recommendations.

Не превращать dashboard в свалку виджетов.

Показывать только actionable information.

---

# 72. Client portal

Статус: 💡 Future BACKLOG

Вместо полного интерфейса SMM клиент потенциально получает простой portal:

- посмотреть контент;
- оставить комментарий;
- approve/reject;
- посмотреть reports.

Вернуться после базовой Web/Approval системы.

---

# 73. Public share links

Статус: 💡 Future BACKLOG

Возможность поделиться:

- Post;
- Content Plan;
- Report;

через ограниченную ссылку без полноценного аккаунта.

Обязательно:

- access control;
- expiration;
- revocation.

---

# 74. Calendar integrations

Статус: 💡 Future BACKLOG

В будущем возможна интеграция с:

- Google Calendar;
- Outlook.

Польза должна быть подтверждена SMM workflow.

Не дублировать собственный Content Calendar без причины.

---

# 75. External storage integrations

Статус: 💡 Future BACKLOG

В будущем:

- Google Drive;
- Dropbox;
- OneDrive.

Особенно для Media Library.

Добавлять по реальному пользовательскому спросу.

---

# 76. Canva / design integrations

Статус: 💡 Future Research

Возможная интеграция с design workflows.

Исследовать:

- API;
- permissions;
- реальную пользу;
- возможности автоматизации.

Не делать просто потому, что Canva популярна.

---

# 77. Automation rules

Статус: 💡 Long-term BACKLOG

В будущем пользователь потенциально может создавать правила:

`Approved`
→ schedule

или

`Publication failed`
→ Telegram notification.

Не строить generic automation engine раньше реальной необходимости.

---

# 78. SMM Growth Loop

Статус: 🎯 Долгосрочное направление

Главный продуктовый цикл:

задача бизнеса
→ клиентский контекст
→ идеи
→ Content Plan
→ Posts
→ Approval
→ Publishing
→ Analytics
→ AI Insights
→ следующий Content Plan.

Любая новая функция должна оцениваться по вопросу:

**Помогает ли она этому циклу?**

---

# 79. Исследование рынка

Статус: 🟡 Периодически

Следить за:

- Buffer;
- Hootsuite;
- Sprout Social;
- Metricool;
- SocialBee;
- Planable;
- Later;
- Agorapulse;
- Loomly;
- Sendible;
- Publer;
- Vista Social;
- новыми AI-native SMM products.

Исследовать:

- новые workflows;
- pricing;
- AI;
- approvals;
- publishing;
- analytics;
- inbox;
- agency features.

Не копировать конкурентов автоматически.

Главный вопрос:

**Почему SMM-специалист должен использовать SMM Platform вместо обычного ChatGPT или существующего social media manager?**

---

# 80. Работа с SMM-специалистами

Статус: 💡 Product Research

После заказчицы желательно постепенно получить feedback других SMM-специалистов.

Спрашивать:

- что занимает больше всего времени;
- что приходится делать вручную;
- где чаще всего совершаются ошибки;
- что приходится переносить между разными сервисами;
- какие функции текущих продуктов раздражают;
- за что они готовы платить.

Ключевой вопрос:

**Какие 5 вещей больше всего облегчили бы твою ежедневную работу?**

---

# 81. Неактивные функции

Статус: 💡 Future Product Review

После накопления usage data проверять:

- что почти никто не использует;
- что дублирует другое;
- что создаёт поддержку без пользы.

Не бояться:

- упрощать;
- объединять;
- удалять малоценные функции.

---

# 82. Mobile App

Статус: ⏸ Не планировать до Stage 26

До этого:

- Telegram выполняет роль быстрого mobile interface;
- Web должен быть responsive;
- возможно использование PWA.

Native iOS/Android создавать только если реальные пользователи покажут, что:

- Telegram недостаточно;
- responsive Web недостаточно;
- PWA недостаточно.

---

# 83. Отдельные будущие проекты

Не относятся к текущему SMM Platform ROADMAP.

## Client Scope Assistant

Идея:

- требования клиента;
- scope changes;
- approvals;
- история договорённостей.

Рассматривать как отдельный продукт после SMM Platform.

---

## Learning OS

Идея:

- изученные темы;
- план обучения;
- реальные проекты;
- повторение;
- пробелы;
- прогресс.

Не начинать до завершения основных целей SMM Platform.

---

# 84. Maintenance Pass

Статус: ⏸ Обязательная техническая процедура

После первой стабильной версии провести полный технический обзор.

Проверить:

- Python;
- aiogram;
- OpenAI SDK;
- Gemini SDK;
- Groq SDK;
- Pydantic;
- Redis;
- SQLite;
- остальные dependencies;
- deprecated APIs;
- tests;
- migrations;
- architecture;
- logging;
- backups;
- deployment;
- `.env.example`;
- documentation;
- Git;
- security;
- ROADMAP;
- BACKLOG;
- technical debt.

После Web и крупных релизов повторять maintenance-pass периодически.

---

# 85. Правила оценки новой идеи

Перед добавлением новой задачи спросить:

1. Какую реальную проблему она решает?
2. Экономит ли время SMM-специалиста?
3. Улучшает ли качество работы?
4. Убирает ли рутину?
5. Усиливает ли существующие данные и функции?
6. Можно ли встроить её в существующий workflow?
7. Требуется ли она сейчас?
8. Подтверждена ли проблема пользователями?
9. Можно ли сделать значительно проще?
10. Не относится ли задача уже к будущему Web?

Если идея полезная, но не нужна текущему этапу:

→ BACKLOG.

Если задача стала необходимой частью последовательного развития:

→ ROADMAP.

---

# 86. Правила архитектурного BACKLOG

Не делать крупный refactoring ради:

- красоты;
- симметрии;
- модных patterns;
- возможного переиспользования когда-нибудь.

Архитектурное изменение оправдано, если текущая структура:

- реально мешает новой функции;
- создаёт ошибки;
- существенно усложняет тестирование;
- создаёт заметное дублирование;
- мешает нескольким интерфейсам использовать одну бизнес-логику.

---

# 87. Правила AI BACKLOG

Новая AI-функция должна отвечать на вопрос:

**Почему здесь AI лучше обычного детерминированного кода?**

Не использовать AI:

- ради самого факта наличия AI;
- для задач, которые проще и надёжнее решить кодом;
- как гарантированный источник бизнес-фактов.

Использовать AI там, где полезны:

- генерация;
- переработка;
- summarization;
- adaptation;
- classification;
- recommendations;
- analysis неструктурированного контекста.

---

# 88. Правила Web BACKLOG

Не переносить автоматически каждую Telegram-функцию на отдельную Web-страницу.

Web должен использовать преимущества интерфейса:

- большие таблицы;
- filters;
- calendar;
- drag-and-drop;
- media;
- dashboards;
- analytics;
- multi-client workspace.

Telegram сохранять там, где он удобнее:

- быстрый ввод;
- voice;
- notifications;
- approvals;
- быстрые AI-actions.

---

# 89. Правила работы с BACKLOG

Во время каждого нового Stage:

- не вытаскивать случайные задачи из BACKLOG;
- сначала завершить scope текущего ROADMAP Stage.

В конце Stage:

1. проверить новые идеи;
2. проверить feedback;
3. проверить technical debt;
4. обновить BACKLOG;
5. определить, нужно ли что-то переносить в ROADMAP.

BACKLOG может быть большим.

Текущий Stage должен оставаться маленьким и понятным.