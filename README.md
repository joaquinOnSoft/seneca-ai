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

## Project Structure

```
seneca-ai/
├── main.py                  # Entry point
├── config/
│   └── settings.py          # UI constants & layout values
├── src/
│   └── seneca/
│       ├── core/
│       │   ├── agent.py         # LangChain AI agent (streaming)
│       │   ├── conversation.py  # Domain models (Message, Conversation)
│       │   └── storage.py       # JSON persistence (~/.seneca/)
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

| `LLM_PROVIDER` | Required env vars |
|---|---|
| `openai` (default) | `OPENAI_API_KEY`, `OPENAI_MODEL` |
| `ollama` | `OLLAMA_BASE_URL`, `OLLAMA_MODEL` |
| `anthropic` | `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL` |

### 4. Run

```bash
python main.py
```

---

## Running Tests

```bash
# Unit tests only (no credentials needed)
pytest tests/unit/

# All tests including integration (requires LLM credentials)
pytest

# With coverage report
pytest --cov=seneca tests/unit/
```

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
