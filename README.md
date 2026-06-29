# mail-service

> Self-contained mail microservice — receives SMTP, delivers directly to MX.
> No queue, no relay, no database.

---

## What it does

**mail-service** is a single-process Python application with two functions:

1. **SMTP server** — accepts inbound mail and stores messages in memory.
2. **Direct MX delivery** — resolves the recipient's mail server via DNS MX lookup and delivers the message without an intermediate relay.

It exposes a **REST API** (FastAPI) for listing received messages and triggering outbound sends.

Production use: powers mail delivery on **[Ответы@Live](https://otvet.live)** since early 2024 — over a year on the public internet without issues.

---

## Quick start

```bash
# 1. Clone and install
git clone https://github.com/your-org/mail-service
cd mail-service
pip install -r requirements.txt

# 2. Required: your sender domain
export SMTP_SENDER_DOMAIN=mail.example.com

# 3. Run
uvicorn main:app --host 0.0.0.0 --port 8000
```

Result:

| Port | Listening on |
|------|--------------|
| `8000` | REST API + Swagger UI at `/docs` |
| `25`   | SMTP server (inbound) |

---

## API

### `GET /message?skip=0&limit=100`

List received message summaries (no body content).

```json
[
  {
    "id": "f47ac10b-...",
    "from": "alice@wonderland.org",
    "to": "bob@example.com",
    "subject": "Tea party at 4?",
    "received_time": "2025-01-15T14:22:31Z"
  }
]
```

### `GET /message/{id}`

Full message including plain-text body.

```json
{
  "id": "f47ac10b-...",
  "from": "alice@wonderland.org",
  "to": "bob@example.com",
  "subject": "Tea party at 4?",
  "received_time": "2025-01-15T14:22:31Z",
  "content": "Don't be late this time."
}
```

### `POST /message?to=boss@their-company.com&from=admin`

Send a message. Request body (JSON):

```json
{
  "title": "Weekly report",
  "content": "Everything is on track.",
  "html_content": "<h1>Weekly report</h1><p>Everything is on track.</p>",
  "sender_alias": "Auto Reporter"
}
```

Response — step-by-step delivery log:

```json
{
  "success": true,
  "logs": [
    { "step_type": "DNS_LOOKUP",      "domain": "their-company.com",   "error": null },
    { "step_type": "START_TLS",       "domain": "mx.their-company.com","error": null },
    { "step_type": "SEND_FROM",       "domain": "mx.their-company.com","error": null },
    { "step_type": "SEND_TO",         "domain": "mx.their-company.com","error": null },
    { "step_type": "SEND_DATA",       "domain": "mx.their-company.com","error": null },
    { "step_type": "QUIT",            "domain": "mx.their-company.com","error": null }
  ]
}
```

Each step records the MX host and any error with a full Python traceback.

---

## Internals

### Receiving

```
SMTP client  ──►  aiosmtpd Controller
                      │
                      ▼
                 MailHandler.handle_message()
                      │
                      ├─ Decode RFC 2047 headers
                      ├─ Walk MIME tree → extract text/plain
                      ├─ Assign UUID
                      └─ Store MessageDetails in dict
```

- SMTP server: **[aiosmtpd](https://github.com/aio-libs/aiosmtpd)**.
- Parsing: Python `email` stdlib. Multipart messages are walked for the first `text/plain` part; single-part messages use the top-level body.
- Encoded headers (`=?UTF-8?B?...?=`) are decoded automatically.
- Storage: `dict<UUID, MessageDetails>`. A background task deletes entries older than 1 hour.

### Sending

```
POST /message
      │
      ▼
MailSender.send_mail(from, to, title, ...)
      │
      ├─ Extract domain from recipient address
      ├─ DNS MX lookup (Cloudflare 1.1.1.1, Google 8.8.8.8, Yandex 77.88.8.8)
      │
      ├─ For each MX host (priority order):
      │    ├─ Connect :25
      │    ├─ EHLO → STARTTLS (opportunistic)
      │    ├─ MAIL FROM → RCPT TO
      │    ├─ Build MIME message (multipart/alternative: text + HTML)
      │    ├─ DKIM-sign (if key configured)
      │    ├─ DATA
      │    └─ QUIT
      │
      ▼
MessageSendingResult { success, logs[] }
```

- **No relay.** MX lookup via **[aiodns](https://github.com/saghul/aiodns)**, direct connection to the recipient's mail server on port 25.
- **Opportunistic STARTTLS.** Upgrades if the remote MX advertises support. Falls back to plain text otherwise.
- **DKIM signing** (optional). Enabled when `SMTP_DKIM_PRIVATE_KEY` and `SMTP_DKIM_SELECTOR` are set.
- **Per-step error recording.** Each SMTP conversation step is logged individually. If a step fails, subsequent MX hosts are tried only when the current host accepted the recipient (`RCPT TO` succeeded but a later step failed); otherwise the next MX is attempted.

### Cleanup

An `asyncio.Task` runs every `SMTP_TTL` seconds (default 3600) and removes messages older than 1 hour. Cancelled on shutdown.

---

## Configuration

All settings via environment variables:

| Variable | Required | Default | Purpose |
|---|---|---|---|
| `SMTP_SENDER_DOMAIN` | **Yes** | — | Domain in `EHLO` and `From` address |
| `SMTP_HOST` | No | `127.0.0.1` | Inbound SMTP bind address |
| `SMTP_PORT` | No | `25` | Inbound SMTP port |
| `SMTP_TTL` | No | `3600` | Cleanup interval in seconds (lifetime is fixed at 1 hour) |
| `SMTP_LOG_LEVEL` | No | `info` | Python log level |
| `SMTP_CERT` | No | — | SSL certificate path (inbound TLS) |
| `SMTP_KEY` | No | — | SSL private key path |
| `SMTP_DKIM_SELECTOR` | No | — | DKIM selector |
| `SMTP_DKIM_PRIVATE_KEY` | No | — | DKIM private key PEM path |

---

## Strengths

- **Production-proven.** Used on **[Ответы@Live](https://otvet.live)**, a public Q&A platform, since early 2024.
- **Zero external mail infrastructure.** No MTA, no relay service required. DNS is the only dependency.
- **Fully async.** HTTP, SMTP server, SMTP client, DNS, file I/O — all on the asyncio event loop.
- **Detailed delivery logs.** Every outbound attempt produces a per-step trace with hostnames and full tracebacks on failure.
- **Swagger UI.** Available at `/docs`.
- **Small footprint.** 8 dependencies. No database, no message broker.
- **Typed configuration.** Env vars are parsed into a Pydantic model; misconfiguration fails at startup.

---

## Limitations

| Limitation | Details |
|---|---|
| **In-memory storage** | Messages are lost on restart. No persistence. |
| **No built-in authentication** | SMTP and HTTP endpoints have no auth. By design: authentication is delegated to an external reverse proxy (nginx, Caddy, etc.). Run without one only on a trusted network. |
| **Fixed 1-hour lifetime** | Cleanup deletes everything older than 1 hour. `SMTP_TTL` controls sweep frequency, not lifetime. |
| **Port 25 only (outbound)** | No support for submission (587) or SMTPS (465). |
| **Plain-text only (inbound)** | HTML parts of incoming messages are discarded. |
| **No retry** | Each MX host gets one attempt. No queue, no backoff. |
| **No rate limiting** | No built-in throttling. |
| **No address validation** | `to` and `from` are not validated. |
| **No SPF/DMARC** | DKIM signing is available; SPF/DMARC verification and policy enforcement are not. |
| **Sender local-part default** | `POST /message` takes `from` as a query parameter defaulting to `"admin"`. The domain is always `SMTP_SENDER_DOMAIN`. |

---

## Suitable for

- Dev/test mailboxes
- Internal microservice communication
- Automated alert delivery
- DKIM configuration testing
- Learning SMTP

## Not suitable for

- Production inbound mail for end users
- High-volume bulk sending
- Replacing a full MTA or transactional email service

---

## Project layout

```
mail-service/
├── main.py              # FastAPI app, lifespan, routes
├── mail_handler.py      # SMTP receive → parse → store → cleanup
├── mail_sender.py       # MX lookup → SMTP delivery → DKIM sign
├── environment.py       # Env var → typed config
├── logger_cfg.py        # Logging setup
├── requirements.txt
└── model/               # Pydantic models
    ├── message_summary.py
    ├── message_details.py
    ├── message_sending_request.py
    ├── message_sending_result.py
    ├── message_sending_log_entry.py
    ├── message_sending_step_error.py
    └── dkim_configuration.py
```

---

## License

This is free and unencumbered software released into the public domain — [The Unlicense](https://unlicense.org/).
