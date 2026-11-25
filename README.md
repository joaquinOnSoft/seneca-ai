# Seneca-AI

> *An open-source European generative AI assistant that supports and empowers humans — never replacing them.*

![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![License](https://img.shields.io/badge/license-Apache--2.0-green)
![Framework](https://img.shields.io/badge/UI-customtkinter-blueviolet)

---

## What is Seneca-AI?

Seneca is a **multi-purpose, cross-platform** AI assistant built on European open-source principles. It is designed to augment human capability — not automate it away.

- 🌍 European open-source values  
- 🔌 Multiple LLM backends (OpenAI, Ollama, Anthropic)  
- 🎤 Voice input via microphone  
- 💬 Persistent conversation history  
- 🌐 Internationalised (es, en, fr, de out of the box)  

---

## Installation

To install Seneca AI, follow the instructions in the tutorial for your operating system:

 - [Seneca AI: Linux installation (Ubuntu)](docs/installacion-linux.md)
 - [Seneca AI: Windows installation](docs/installacion-win.md)

Seneca AI relies on [Docker containers](docs/containers.md) to run all the services required to provide the service

## Project Structure

```
seneca-ai/
├── main.py                  # Entry point
├── config/
│   └── settings.py          # UI constants & layout values
├── src/
│   └── seneca/
│       ├── api/
│       │   ├── api.py           # Flask REST API (STT, auth, chat, conversations)
│       │   ├── chat.py          # Server-side chat: LLM providers, prompt, tool loop
│       │   ├── client.py        # Typed HTTP client for the REST API (incl. SSE chat)
│       │   └── database.py      # MongoDB access layer
│       ├── core/
│       │   ├── agent.py         # Desktop chat agent: streams replies from the API, runs tools
│       │   ├── conversation.py  # Domain models (Message, Conversation)
│       │   └── api_storage.py   # Conversation history (read/delete) through the REST API
│       ├── memory/              # Long-term memory (Qdrant index of past conversations)
│       │   ├── service.py       # Search + prompt block, used by the chat
│       │   ├── indexer.py       # MongoDB → Qdrant indexing and running summaries
│       │   └── worker.py        # memory-worker container entry point
│       ├── i18n/
│       │   └── locale.py        # Babel-backed i18n helper
│       ├── ui/
│       │   ├── main_window.py   # Root CTk window, event routing
│       │   ├── sidebar.py       # Collapsible lateral menu
│       │   ├── chat_area.py     # Scrollable bubble container
│       │   ├── input_bar.py     # Text input + mic + send/stop
│       │   └── bubble.py        # UserBubble / AssistantBubble widgets
│       └── utils/
│           ├── config.py        # python-dotenv config loader
│           └── audio.py         # SpeechRecognition wrapper
├── tests/
│   ├── unit/                # Pure logic tests (no LLM, no UI)
│   ├── seneca/api/          # REST API, HTTP client and MongoDB layer tests (mocked)
│   ├── seneca/core/         # API-backed conversation store tests (mocked)
│   ├── seneca/memory/       # Memory tests (in-process Qdrant, fake embedder)
│   └── integration/         # LLM integration tests (require credentials)
├── .env.example
├── requirements.txt
├── pyproject.toml
└── README.md
```

---

## Quick Start

### 1. Clone & create a virtual environment

```bash
git clone https://github.com/your-org/seneca-ai.git
cd seneca-ai
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt

# Optional – voice input (requires portaudio system library)
pip install pyaudio

# Optional – Anthropic backend
pip install langchain-anthropic
```
#### 2.1 Dependencies in Ubuntu

```bash

#  ALSA (Advanced Linux Sound Architecture) and JACK Audio Connection Kit.
sudo apt install alsa-utils alsa-oss alsa-tools

# To avoid errors when accessing the sound hardware (such as those you saw earlier),
# make sure your Linux user is a member of the api group. 
sudo usermod -a -G api $USER

# In Ubuntu, PyAudio requires the PortAudio development headers  
sudo apt install portaudio19-dev python3-all-dev
```

#### 2.2 Development tools in Ubuntu

[Antigravity: Download for Linux](https://antigravity.google/download/linux)

### 3. Configure environment

```bash
cp .env.example .env
# Edit .env and set your LLM_PROVIDER + credentials
```

#### Supported providers

The LLM is called by the **API server**, not by the desktop app: the
`api` container reads these variables from `.env` (apply changes with
`docker compose up -d`).

| `LLM_PROVIDER`     | Required env vars                      |
|--------------------|----------------------------------------|
| `openai`           | `OPENAI_API_KEY`, `OPENAI_MODEL`       |
| `ollama` (default) | `OLLAMA_BASE_URL`, `OLLAMA_MODEL`      |
| `anthropic`        | `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL` |

The installer stores the Ollama model in `OLLAMA_MODEL` in `.env`, using
`select_ollama_model.sh` (Linux) or `select_ollama_model.ps1` (Windows). It
keeps a value already in `.env`, otherwise it writes the `OLLAMA_MODEL`
environment variable. If neither is set, it suggests a model for the RAM tier
of the computer and whether it has a GPU, and writes the chosen one:

| Detected RAM | Tier  |
|--------------|-------|
| < 15 GB      | 8 GB  |
| 15 - 30 GB   | 16 GB |
| 31 - 62 GB   | 32 GB |
| >= 63 GB     | 64 GB |

Each tier starts 1 GB below its size, because the operating system reports a
bit less RAM than the installed RAM. The models suggested for each tier are
listed in [docs/containers.md](docs/containers.md#ollama-container).

### 4. Run

```bash
python main.py
```

---

## Chat and conversation storage

The desktop app is a thin client of the Seneca AI REST API:

1. It sends the user's message to `POST /senecaai/v1/chat`.
2. The API builds the prompt from the conversation stored in MongoDB, calls
   the LLM (`LLM_PROVIDER`) and streams the reply back as Server-Sent Events.
3. The API stores both the message and the reply. A cancelled reply ("stop"
   button) is stored up to the point where it was interrupted.

Tools such as "open in Notepad" act on the user's computer, so the app
runs them when the model asks for them and sends the results back. The
protocol is described in [docs/chat-api.md](docs/chat-api.md).

The desktop app authenticates with `SENECA_AI_API_KEY` and works on behalf
of `SENECA_USER_ID` (sent in the `X-SENECA-AI-USER-ID` header). If it is
empty, conversations are stored under the generic user `api_key_user`.

| Method   | Resource                                     | Description                                                       |
|----------|----------------------------------------------|-------------------------------------------------------------------|
| `POST`   | `/senecaai/v1/chat`                          | Send a message and stream the reply (SSE); creates the conversation if `conversation_id` is omitted |
| `GET`    | `/senecaai/v1/chat/capabilities`             | LLM provider, model and tool-calling support                      |
| `GET`    | `/senecaai/v1/conversations`                 | Paginated list, newest first (`convPerPage` ≤ 100, `numPage`). Messages only with `includeMessages=true` |
| `GET`    | `/senecaai/v1/conversations/{id}`            | One conversation with all its messages                            |
| `POST`   | `/senecaai/v1/conversations`                 | Create a conversation (`201` + `Location` header)                 |
| `PATCH`  | `/senecaai/v1/conversations/{id}`            | Change `title` and/or replace `messages`                          |
| `POST`   | `/senecaai/v1/conversations/{id}/messages`   | Append messages at the end of the conversation                    |
| `DELETE` | `/senecaai/v1/conversations/{id}`            | Delete a conversation (`204`)                                     |

The full Swagger documentation is served at `http://localhost:1414/apidocs`.

### Long-term memory

The API also remembers the user's other conversations: the `memory-worker`
container indexes them into [Qdrant](https://qdrant.tech/), and the chat adds the passages related to
the new message to the prompt. See [docs/memory.md](docs/memory.md).

> **Qdrant has no API key.** The `qdrant` container publishes no port: it is
> only reachable from the other containers in the internal `llm_net` Docker
> network (`api` and `memory-worker`), not from the host or the local network.
> A key would only protect against code
> already running inside that network, which can read the Docker secrets
> anyway. If you publish its port (e.g. `127.0.0.1:6333:6333` in
> `docker-compose.override.yaml` to use the dashboard), bind it to
> `127.0.0.1` only. If Qdrant ever has to be reachable from other machines,
> set `QDRANT__SERVICE__API_KEY` on the container as a Docker secret and the
> same value in `QDRANT_API_KEY` for `api` and `memory-worker` (the code
> already sends it when set).

---

## Running Tests

The tests use [pytest](https://docs.pytest.org/). `pyproject.toml` already
adds `src/` to the Python path, so no `PYTHONPATH` or `pip install -e .` is
needed. Run every command from the project root with the virtual environment
activated.

### Prerequisites

1. Install the dependencies (step 2 of the *Quick Start*).
2. Create the `.env` file (`cp .env.example .env`). `JWT_SECRET_KEY` must
   have a value: the configuration refuses to load without it.

The API, client, database and storage tests mock MongoDB, the Whisper model
and the HTTP calls: **no Docker container, database or API server is
needed**.

### Commands

```bash
# All the tests
# (tests/integration is skipped unless the API with the /chat endpoint is
#  running at SENECA_API_BASE_URL; it chats with the real LLM)
pytest

# Unit tests only (no credentials needed)
pytest tests/unit/

# REST API, HTTP client and MongoDB layer
pytest tests/seneca/api/

# Server-side chat (fake LLM, in-memory database)
pytest tests/seneca/api/test_chat.py

# Desktop chat agent and API-backed conversation store
pytest tests/seneca/core/

# Long-term memory (in-process Qdrant, fake embeddings)
pytest tests/seneca/memory/

# A single file, test or group of tests
pytest tests/seneca/api/test_api.py
pytest tests/seneca/api/test_api.py::test_delete_conversation_success
pytest -k conversation                 # tests whose name contains "conversation"

# Quieter output / stop at the first failure
pytest -q
pytest -x

# Coverage report (requires: pip install pytest-cov)
pytest --cov=seneca --cov-report=term-missing
```

On Windows, the same commands work in PowerShell once the virtual
environment is activated (`.venv\Scripts\activate`).

---

## UI Overview

| Element | Behaviour |
|---|---|
| **☰ Hamburger** | Toggles the sidebar |
| **Sidebar** | Shows history of last 20 conversations; "New conversation" resets context |
| **Chat area (top 85%)** | Scrollable; user bubbles right-aligned, Seneca bubbles left |
| **Input bar (bottom 15%)** | Type + Enter or Shift-Enter for newline |
| **🎤 Microphone** | Records speech and inserts transcription |
| **▶ Send** | Submits prompt; switches to **■ Stop** while Seneca streams |
| **■ Stop** | Cancels the in-flight request |

---

## Internationalisation

Set `APP_LOCALE` in `.env` to one of:

| Tag | Language |
|---|---|
| `es_ES` | Spanish (default) |
| `en_US` | English |
| `fr_FR` | French |
| `de_DE` | German |

To add a new locale, extend the `_CATALOGUE` dict in
`src/seneca/i18n/locale.py`.

---

---

## Contributing

Pull requests are welcome. Please follow PEP 8, add type hints, and
include tests for new behaviour. Run `ruff check .` and `mypy src/`
before opening a PR.

---

## License

Apache 2.0 — see [LICENSE](LICENSE).
