# @dong-ai/sdk

**TypeScript SDK for the Dong AI Company API** — a zero-dependency client for OpenAI-compatible endpoints.

> Uses native `fetch` (Node 18+). No `axios`, no `node-fetch`, no runtime dependencies.

---

## Installation

```bash
npm install @dong-ai/sdk
```

## Quickstart

```ts
import { DongAI } from '@dong-ai/sdk';

const client = new DongAI();

// List available models
const models = await client.listModels();
console.log(models);

// Chat (non-streaming)
const response = await client.chat([
  { role: 'user', content: 'Hello!' },
]);
console.log(response.choices[0].message.content);

// Chat (streaming)
for await (const delta of client.chatStream([
  { role: 'user', content: 'Tell me a story' },
])) {
  process.stdout.write(delta);
}
```

---

## Configuration

| Env variable      | Default                    | Description              |
|--------------------|----------------------------|--------------------------|
| `DONG_API_KEY`     | `""`                       | Bearer token for auth    |
| `DONG_BASE_URL`    | `http://localhost:8648`    | API server base URL      |

All options can also be passed to the `DongAI` constructor:

```ts
const client = new DongAI('sk-...', 'https://api.dong.ai');
```

---

## API Reference

### `new DongAI(apiKey?, baseUrl?)`

Creates a new SDK client. All parameters are optional and fall back to environment variables.

---

### `client.chat(messages, options?)`

**Non-streaming chat completion.** Returns a full `ChatResponse`.

```ts
const res = await client.chat(
  [{ role: 'user', content: 'Hello' }],
  { model: 'gpt-4', temperature: 0.7 }
);
```

**`ChatMessage`**
| Field     | Type                                     | Description          |
|-----------|------------------------------------------|----------------------|
| `role`    | `'system' \| 'user' \| 'assistant' \| 'tool'` | Message role |
| `content` | `string`                                 | Message content      |

**`ChatOptions`** — standard OpenAI parameters (model, temperature, top_p, max_tokens, stop, presence_penalty, frequency_penalty, user), plus any extras accepted by the server.

**`ChatResponse`**
| Field     | Type               | Description              |
|-----------|---------------------|--------------------------|
| `id`      | `string`            | Completion ID            |
| `object`  | `'chat.completion'` | Object type              |
| `created` | `number`            | Unix timestamp           |
| `model`   | `string`            | Model used               |
| `choices` | `ChatChoice[]`      | Completion choices       |
| `usage`   | `Usage`             | Token usage statistics   |

---

### `client.chatStream(messages, options?)`

**Streaming chat completion.** Returns an `AsyncIterable<string>` of content deltas.

```ts
for await (const delta of client.chatStream(
  [{ role: 'user', content: 'Hi!' }],
  { model: 'gpt-4' }
)) {
  process.stdout.write(delta);
}
```

Each iteration yields the `content` field of a streaming delta. The `[DONE]` signal and empty chunks are handled internally.

---

### `client.run(request)`

**CEO project execution.** Sends a command to be run in a project context.

```ts
const result = await client.run({
  project: 'my-app',
  command: 'npm test',
  timeout: 60,
});
```

**`RunRequest`**
| Field         | Type                          | Default  | Description                  |
|---------------|-------------------------------|----------|------------------------------|
| `project`     | `string`                      | —        | Project name **(required)**  |
| `command`     | `string`                      | —        | Shell command **(required)** |
| `args`        | `Record<string, unknown>`     | `{}`     | Additional arguments         |
| `timeout`     | `number`                      | —        | Max execution time (seconds) |
| `environment` | `Record<string, string>`      | —        | Environment variables        |

**`RunResponse`**
| Field          | Type                                                         | Description            |
|----------------|--------------------------------------------------------------|------------------------|
| `id`           | `string`                                                     | Run ID                 |
| `status`       | `'queued' \| 'running' \| 'completed' \| 'failed' \| 'cancelled'` | Execution status |
| `output`       | `string`                                                     | Command output         |
| `error`        | `string \| undefined`                                        | Error message          |
| `exit_code`    | `number \| undefined`                                        | Process exit code      |
| `started_at`   | `string \| undefined`                                        | ISO start timestamp    |
| `completed_at` | `string \| undefined`                                        | ISO completion timestamp |

---

### `client.listModels()`

List available AI models.

```ts
const models: Model[] = await client.listModels();
```

**`Model`**
| Field      | Type                | Description         |
|------------|---------------------|---------------------|
| `id`       | `string`            | Model identifier    |
| `object`   | `'model'`           | Object type         |
| `created`  | `number`            | Creation timestamp  |
| `owned_by` | `string`            | Owner / provider    |

---

### `client.health()`

Check API server health and retrieve tenant info.

```ts
const health = await client.health();
console.log(health.tenant); // tenant name
```

**`HealthResponse`**
| Field           | Type                                      | Description          |
|-----------------|-------------------------------------------|----------------------|
| `status`        | `'ok' \| 'degraded' \| 'down'`            | Service status       |
| `version`       | `string`                                  | Server version       |
| `tenant`        | `string`                                  | Tenant identifier    |
| `uptime_seconds`| `number`                                  | Server uptime        |

---

### `client.metrics()`

Fetch Prometheus-formatted metrics.

```ts
const metrics: string = await client.metrics();
console.log(metrics);
```

Returns a raw text string (Prometheus exposition format).

---

## CLI Usage

The package includes a `dongai` CLI tool.

```
dongai chat [message]           Send a chat message
  --stream, -s                  Stream the response

dongai run                      Execute a CEO project command
  --project, -p <name>          Project name (required)
  --command, -c <cmd>           Shell command (required)

dongai models                   List available models

dongai health                   Check API server health

dongai help                     Show help
```

### Examples

```bash
# Chat
dongai chat "What is the meaning of life?"
dongai chat --stream "Tell me a story"
echo "Hello" | dongai chat

# Run project
dongai run --project my-app --command "npm run build"

# List models
dongai models

# Health check
dongai health
```

---

## Error Handling

The SDK throws `DongAiError` on non-2xx responses. It extends `Error` with:

| Property | Type     | Description        |
|----------|----------|--------------------|
| `status` | `number` | HTTP status code   |
| `code`   | `string` | API error code     |
| `type`   | `string` | API error type     |

```ts
import { DongAI, DongAiError } from '@dong-ai/sdk';

try {
  await client.chat(messages);
} catch (err) {
  if (err instanceof DongAiError) {
    console.error(err.status, err.code, err.message);
  }
}
```

---

## Development

```bash
# Install dependencies
npm install

# Build
npm run build

# Type-check (no emit)
npm run typecheck

# Clean build artifacts
npm run clean
```

---

## Requirements

- **Node.js 18+** (native `fetch` support)
- TypeScript 5.4+ (optional — the compiled JS ships with type declarations)

---

## License

MIT
