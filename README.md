# SMM Bot

**SMM Bot** is a Telegram assistant for SMM specialists and small businesses. It keeps everyday content work in one place: client notes, post ideas, post drafts, and content plans. Its OpenAI-powered workflow turns one short marketing brief into a practical seven-day Telegram content plan.

**OpenAI Build Week 2026 track:** Work and Productivity

## Problem

Small teams and independent SMM specialists often manage content across chats, notes, and spreadsheets. Turning a short business brief into a balanced weekly plan requires defining a goal for every day, choosing varied formats, keeping the messaging consistent, and ending each post with a useful call to action.

Doing this manually is repetitive and time-consuming. The planning work must be repeated for every client, campaign, or new business goal before any post is written.

## Current features

- Manage clients: add, view, search, edit, delete, and open a client card.
- Store post ideas: add, list, search, edit, delete, and select a random idea.
- Create and save template-based posts with a selected client, topic or idea, and writing style; view, search, and delete saved posts.
- Create, view, search, edit, and delete content plans.
- Generate a structured seven-day content plan with OpenAI.

## What was built during OpenAI Build Week 2026

SMM Bot existed before the competition as a file-based Telegram MVP. During Build Week, one focused and complete AI feature was added to the existing content-plan section:

- one short free-form SMM brief as the input;
- a GPT-5.6 request through the Responses API;
- Structured Outputs validated with a Pydantic schema;
- exactly seven days, each with a goal, topic, format, key message, and CTA;
- output formatted for a single Telegram message;
- persistence only after a complete, correctly structured result is returned;
- clear handling for authentication, rate-limit, timeout, connection, service, and validation errors;
- five offline tests that do not call the OpenAI API.

The implementation and offline verification are complete. On July 19, 2026, the user manually completed a live Telegram smoke test with a real SMM brief. GPT-5.6 returned a complete seven-day plan, the bot formatted and saved it, and the saved result was successfully found under `📋 Мои контент-планы`. This was a user-performed manual check, not an automated API test.

## Before and after evidence

| Evidence | Location | What it shows |
| --- | --- | --- |
| Version before AI | [`code_history/content_plan/content_plan_v1_0_before_v1_1_ai_generator.py`](code_history/content_plan/content_plan_v1_0_before_v1_1_ai_generator.py) | The last working static five-point content-plan implementation before the AI feature. |
| Current implementation | [`handlers/content_plan.py`](handlers/content_plan.py) | The GPT-5.6 integration, schema, validation, Telegram formatting, error handling, and save-on-success flow. |
| Offline tests | [`tests/test_content_plan.py`](tests/test_content_plan.py) | Five tests for the API contract, seven-day format, Telegram length, day ordering, and no-save-on-error behavior. |
| First published commit | [`578dc3a`](https://github.com/Drezden3991/telegram-smm-bot/commit/578dc3a) | The initial repository import containing the Build Week AI content-plan feature. |

Git was connected after the project and its local version archive already existed. The files under `code_history` are local snapshots preserved during development; they must not be interpreted as Git commits or as proof of a Git history predating repository initialization.

## How GPT-5.6 is used

The content-plan handler sends the user's brief to the OpenAI Responses API with:

- model: `gpt-5.6`;
- reasoning effort: `low`;
- Structured Outputs parsed directly into Pydantic models;
- a schema that requires exactly seven day objects and the fields `day`, `goal`, `topic`, `format`, `key_message`, and `cta`.

GPT-5.6 acts as the SMM strategist: it turns a compact description of the niche, audience, and promotion goal into a practical sequence that moves from introduction and value to trust, objections, and action. The application then validates the structure, checks that days are ordered from 1 to 7, formats the plan for Telegram, and only then saves it.

The current developer instruction asks GPT-5.6 to produce a concise content plan in Russian.

## How Codex accelerated development

Codex was used to:

- analyze the existing architecture and current user flows;
- choose the content-plan section as an isolated Build Week feature;
- implement the OpenAI Responses API integration;
- create the Pydantic schema for structured output;
- add user-facing API and validation error handling;
- create five offline tests;
- resolve OpenAI SDK input-type warnings with official SDK types;
- prepare a safe `.gitignore` for secrets and local data;
- initialize the Git repository and publish it to GitHub.

## Key engineering decisions

- **One free-form brief instead of a complex form.** A user can describe the niche, audience, and goal naturally in one Telegram message.
- **Exactly seven structured days.** Pydantic constraints and an explicit day-order check keep the output predictable.
- **Non-blocking bot flow.** `asyncio.to_thread` runs the synchronous OpenAI SDK request without blocking aiogram's event loop.
- **No persistence on failure.** A new or edited plan is written only after API parsing and application-level validation succeed.
- **Secrets only through `.env`.** Telegram and OpenAI credentials are loaded from environment variables and are excluded from Git.
- **Existing file storage retained.** The MVP keeps its established TXT/JSON-style local storage so the Build Week change stays small and reviewable.

## Installation

The project uses Python 3.13 and pinned dependencies. In Windows PowerShell, run each command from the directory where you want to keep the project.

Clone the repository:

```powershell
git clone https://github.com/Drezden3991/telegram-smm-bot.git
```

Enter the project directory:

```powershell
Set-Location telegram-smm-bot
```

Create a virtual environment:

```powershell
python -m venv .venv
```

Activate it:

```powershell
.\.venv\Scripts\Activate.ps1
```

Install the dependencies:

```powershell
python -m pip install -r requirements.txt
```

Create a local environment file from the safe template:

```powershell
Copy-Item .env.example .env
```

## Environment variables

Open the newly created local `.env` file and provide these variables:

| Variable | Purpose |
| --- | --- |
| `TELEGRAM_BOT_TOKEN` | Token used by aiogram to run the Telegram bot. |
| `OPENAI_API_KEY` | OpenAI API credential used only by the AI content-plan generator. |

Never commit `.env` or real credential values.

## Running the bot

With the virtual environment activated and both environment variables configured, start the long-polling bot:

```powershell
python main.py
```

Keep this Python process running while using the bot in Telegram.

## How to test

Run all five offline content-plan tests without making a real OpenAI API request:

```powershell
python -m unittest discover -s tests -p "test_content_plan.py" -v
```

For a manual Telegram test:

1. Start the bot with `python main.py`.
2. Open the bot in Telegram and send `/start`.
3. Select `📅 Контент-план` and then `📅 Создать контент-план`.
4. Send one short brief.
5. Confirm that the response contains days 1 through 7 and that every day has a goal, topic, format, key message, and CTA.
6. Open `📋 Мои контент-планы` to confirm that the validated plan was saved.

For the most representative manual check, use a Russian brief because the current AI developer instruction requests a Russian-language result.

Safe example brief:

> Продукт: Telegram-бот SMM Bot, который помогает вести клиентов, сохранять идеи, писать посты и создавать контент-планы. Аудитория: начинающие и работающие SMM-специалисты, фрилансеры и владельцы малого бизнеса. Цель: познакомить аудиторию с ботом, показать его практическую пользу и привлечь первых тестировщиков.

The manual scenario makes a real OpenAI API request and therefore requires a valid API key, network access, and available API quota.

## Data and security

- Real keys are loaded from `.env`, which is excluded from Git.
- Local client records, post ideas, saved posts, and content plans are excluded from Git.
- `.env.example` contains only the two supported variable names with empty values.
- API or validation failures do not create a new content plan or overwrite an existing one.

## Project structure

```text
telegram-smm-bot/
├── handlers/          # Telegram menus and workflows for clients, ideas, posts, and plans
├── tests/             # Five offline tests for the AI content-plan feature
├── docs/              # Project log, roadmap, rules, backlog, and supporting notes
├── code_history/      # Local archived versions and section changelogs
├── main.py            # aiogram router setup and long-polling entry point
├── requirements.txt   # Pinned Python dependencies
└── .env.example       # Empty environment-variable template
```

## Known limitations

- Data is stored in local files rather than a database.
- The Python process must remain running for the Telegram bot to work.
- AI content-plan generation requires access to the OpenAI API.
- There is no publicly deployed bot instance.

## Future improvements

- Replace local file storage with a database.
- Separate data by Telegram user or workspace.
- Add focused AI features for ideas, posts, and rewriting.
- Deploy a persistent bot service.

## OpenAI Build Week

This project is prepared for **OpenAI Build Week 2026** in the **Work and Productivity** track.

Learn more on the official [OpenAI Build Week](https://openai.com/build-week/) page.
