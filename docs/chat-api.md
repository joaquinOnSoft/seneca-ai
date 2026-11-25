# Chat API

The Seneca AI API server calls the LLM. Clients such as the desktop app send
the user's message and receive the reply as a stream of
[Server-Sent Events](https://html.spec.whatwg.org/multipage/server-sent-events.html)
(SSE). The server builds the prompt from the conversation stored in MongoDB and
stores both the message and the reply.

```
Desktop app ──POST /senecaai/v1/chat──► API (Flask) ──► LLM (Ollama / OpenAI / Anthropic)
            ◄──── SSE: token, token… ───    │
                                            └──► MongoDB (conversation + messages)
```

Authentication is the same as for the other endpoints: `X-SENECA-AI-API-KEY`
(plus the optional `X-SENECA-AI-USER-ID`), or `Authorization: Bearer <JWT>`.

With long-term memory enabled, the server also adds passages of the user's
other conversations to the prompt, and a summary of the oldest messages of
long conversations. See [memory.md](memory.md).

## Configuration (api container)

| Variable                    | Default                    | Description                                         |
|-----------------------------|----------------------------|-----------------------------------------------------|
| `LLM_PROVIDER`              | `ollama`                   | `ollama`, `openai` or `anthropic`                   |
| `OLLAMA_MODEL`              | `hadad/LFM2.5-1.2B:Q4_K_M` | Model served by the `ollama` container. An `OLLAMA_MODEL` exported in the shell that runs `docker compose` wins over `.env` |
| `OPENAI_API_KEY` / `OPENAI_MODEL`       | – / `gpt-4o-mini` | Only with `LLM_PROVIDER=openai`             |
| `ANTHROPIC_API_KEY` / `ANTHROPIC_MODEL` | – / `claude-3-haiku-20240307` | Only with `LLM_PROVIDER=anthropic` |
| `CHAT_HISTORY_MAX_MESSAGES` | `50`                       | Most recent stored messages sent to the LLM         |
| `API_THREADS`               | `16`                       | Server threads. Each streamed reply keeps one busy until it ends, so this bounds the concurrent replies |

`docker-compose.yaml` passes them from the host `.env` to the `api`
container. After changing them, run `docker compose up -d`.

Desktop app (`.env`): `CHAT_READ_TIMEOUT` (default `300`) is the number of
seconds it waits for the next chunk of a reply. The first chunk can take
long while Ollama loads the model.

## `GET /senecaai/v1/chat/capabilities`

```json
{"provider": "ollama", "model": "hadad/LFM2.5-1.2B:Q4_K_M", "tool_calling": true}
```

Clients only offer tools when `tool_calling` is `true`.

## `POST /senecaai/v1/chat`

Send **either** `content` (a new user message) **or** `tool_results` (to resume
a reply that is waiting for tools).

```json
{
  "conversation_id": "6553f1a2b3c4d5e6f7a8b9c0",
  "content": "¿Qué es el estoicismo?",
  "tools": [
    {
      "name": "save_text_to_file",
      "description": "Saves text to a file with UTF-8 encoding.",
      "parameters": {
        "type": "object",
        "properties": {"text": {"type": "string"}, "file_name": {"type": "string"}},
        "required": ["text", "file_name"]
      }
    }
  ]
}
```

| Field             | Description |
|-------------------|-------------|
| `conversation_id` | Existing conversation. Omit it to create a new one, titled after the message. |
| `content`         | The user's message (at most 32,000 characters). |
| `tools`           | Optional, at most 16. Tools the model may call; the **client** runs them. Names: 1-64 letters, digits, `_` or `-`. `parameters` is a JSON schema of type `object`. |
| `tool_results`    | `[{"tool_call_id", "content"}]`, one per call of the last `tool_calls` event. Requires `conversation_id`. |

Errors detected before the stream starts are returned as regular JSON errors:
`400` (invalid body, conversation ID or tool results), `401`, `403` (another
user's conversation), `404`, `409` (`tool_results` but no tool call is
waiting) and `503` (database unavailable).

Otherwise the response is `200` with `Content-Type: text/event-stream`.

### Events

Each event has a name and a JSON payload:

```
event: conversation
data: {"id": "6553f1a2b3c4d5e6f7a8b9c0", "title": "¿Qué es el estoicismo?", "created": true}

event: token
data: {"text": "Una escuela"}

event: token
data: {"text": " filosófica…"}

event: done
data: {"message": {"role": "assistant", "content": "Una escuela filosófica…", "timestamp": "2026-11-24T22:15:03.123456Z"}}
```

| Event          | Payload | Meaning |
|----------------|---------|---------|
| `conversation` | `{"id", "title", "created"}` | Always the first event. A new conversation's id arrives here. |
| `token`        | `{"text"}` | A chunk of the reply. |
| `tool_calls`   | `{"tool_calls": [{"id", "name", "args"}]}` | The model wants to run tools. The stream ends; run them and send `tool_results`. |
| `done`         | `{"message"}` | The reply is complete and stored. `message` is `null` if the reply was empty. |
| `error`        | `{"error"}` | The LLM failed. Any text already streamed is stored. The stream ends. |

### Tools run by the client

Tools such as "open the reply in Notepad" act on the user's computer, so the
server cannot run them:

```
client                                   server
  │ POST {content, tools}                  │
  │ ─────────────────────────────────────► │  stores the user message, calls the LLM
  │ ◄── conversation, token…, tool_calls ── │  stores the turn state (pending_turn)
  │  runs the tools locally                 │
  │ POST {conversation_id, tool_results,    │
  │       tools}                            │
  │ ─────────────────────────────────────► │  resumes the LLM with the results
  │ ◄── conversation, token…, done ──────── │  stores the reply
```

- The turn state is kept in the conversation document in MongoDB
  (`pending_turn`, never returned by the conversation endpoints). It does not
  depend on the server process or thread.
- A turn allows at most 5 tool rounds. After that, the reply ends with `done`.
- If the client sends a new `content` instead of the results, the waiting turn
  is closed: the text already shown is stored and the new message is processed.
- Report tool failures as results (for example `"Error executing tool: …"`),
  so the model can explain them.
- The stored reply is all the text streamed in the turn, across tool rounds.
  The intermediate tool calls and results are not stored.

### Cancelling

The client cancels a reply by closing the connection. The server notices it,
stops the LLM and stores the text generated so far. This uses waitress
`channel_request_lookahead`, so the API must run with
`python src/seneca/api/api.py`, as the container does.

### Example with curl

```bash
curl -N http://localhost:1414/senecaai/v1/chat \
  -H "X-SENECA-AI-API-KEY: $SENECA_AI_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"content": "Hola"}'
```

The Postman collection (`assets/api/Seneca AI.postman_collection.json`) has a
**Chat** folder with every case, including a tool round trip.
