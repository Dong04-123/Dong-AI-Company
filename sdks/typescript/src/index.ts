// ---------------------------------------------------------------------------
// Dong AI SDK — TypeScript client for the Dong AI Company API
// ---------------------------------------------------------------------------

import {
  DongAiError,
  NetworkError,
  RateLimitError,
  fromError,
} from './errors.js';
import type { RateLimitInfo } from './errors.js';

// ---------------------------------------------------------------------------
// Types — all public interfaces the SDK exposes
// ---------------------------------------------------------------------------

/** A single chat message in OpenAI-compatible format. */
export interface ChatMessage {
  /** The role of the message author. */
  role: 'system' | 'user' | 'assistant' | 'tool';
  /** The text content of the message. */
  content: string;
  /** An optional name for the participant (for distinguishing multiple users/tools). */
  name?: string;
  /** Tool call ID this message is responding to (for tool role messages). */
  tool_call_id?: string;
}

/**
 * Optional parameters for chat and chatStream requests.
 *
 * Supports all standard OpenAI parameters plus any additional parameters
 * accepted by the upstream provider.
 */
export interface ChatOptions {
  /** Model identifier (e.g. `"gpt-4"`, `"claude-3-opus"`). */
  model?: string;
  /** Sampling temperature (0 to 2, default provider-dependent). */
  temperature?: number;
  /** Nucleus sampling top-p (0 to 1). */
  top_p?: number;
  /** Maximum number of tokens to generate. */
  max_tokens?: number;
  /** Sequence(s) where generation should stop. */
  stop?: string | string[];
  /** Penalizes tokens based on their presence so far (−2 to 2). */
  presence_penalty?: number;
  /** Penalizes tokens based on their frequency so far (−2 to 2). */
  frequency_penalty?: number;
  /** A unique identifier representing the end user (for monitoring). */
  user?: string;
  /** Additional provider-specific options. */
  [key: string]: unknown;
}

/** A single chat completion choice returned by a non-streaming response. */
export interface ChatChoice {
  /** The index of this choice in the list of choices. */
  index: number;
  /** The chat message produced by the model. */
  message: ChatMessage;
  /** The reason the model stopped generating. */
  finish_reason: 'stop' | 'length' | 'content_filter' | 'tool_calls' | null;
}

/** Token usage statistics returned by the API. */
export interface Usage {
  /** Number of tokens in the prompt. */
  prompt_tokens: number;
  /** Number of tokens in the completion. */
  completion_tokens: number;
  /** Total tokens used (prompt + completion). */
  total_tokens: number;
}

/** Full response from a non-streaming chat completion request. */
export interface ChatResponse {
  /** Unique completion identifier. */
  id: string;
  /** Object type — always `'chat.completion'`. */
  object: 'chat.completion';
  /** Unix timestamp (seconds) when the completion was created. */
  created: number;
  /** The model used to generate the completion. */
  model: string;
  /** List of completion choices (typically 1). */
  choices: ChatChoice[];
  /** Token usage statistics. */
  usage: Usage;
}

/** A single streaming chunk from a chat completion stream. */
export interface ChatChunk {
  /** Unique completion identifier (shared across all chunks). */
  id: string;
  /** Object type — always `'chat.completion.chunk'`. */
  object: 'chat.completion.chunk';
  /** Unix timestamp (seconds) when the completion was created. */
  created: number;
  /** The model used to generate the completion. */
  model: string;
  /** Choices with delta content for this chunk. */
  choices: {
    /** Choice index. */
    index: number;
    /** The incremental content delta. */
    delta: Partial<ChatMessage>;
    /** The reason the model stopped generating (only on final chunk). */
    finish_reason: 'stop' | 'length' | 'content_filter' | null;
  }[];
}

/** Request body for the `/v1/run` CEO project execution endpoint. */
export interface RunRequest {
  /** Project name or identifier (required). */
  project: string;
  /** Shell command to execute (required). */
  command: string;
  /** Additional arguments passed to the project runner. */
  args?: Record<string, unknown>;
  /** Maximum execution time in seconds. */
  timeout?: number;
  /** Environment variables to set for the execution. */
  environment?: Record<string, string>;
}

/** Response from the `/v1/run` CEO project execution endpoint. */
export interface RunResponse {
  /** Unique run identifier. */
  id: string;
  /** Current execution status. */
  status: 'queued' | 'running' | 'completed' | 'failed' | 'cancelled';
  /** Command output (stdout + stderr). */
  output: string;
  /** Error message if the run failed. */
  error?: string;
  /** Process exit code. */
  exit_code?: number;
  /** ISO 8601 timestamp when execution started. */
  started_at?: string;
  /** ISO 8601 timestamp when execution completed. */
  completed_at?: string;
}

/** A single model descriptor from `/v1/models`. */
export interface Model {
  /** Model identifier. */
  id: string;
  /** Object type — always `'model'`. */
  object: 'model';
  /** Unix timestamp (seconds) when the model was created. */
  created: number;
  /** The provider or organisation that owns the model. */
  owned_by: string;
  /** Permissions associated with the model. */
  permission?: unknown[];
  /** Root model identifier (for fine-tuned models). */
  root?: string;
  /** Parent model identifier (for fine-tuned models). */
  parent?: string | null;
}

/** Response from `GET /v1/models`. */
export interface ListModelsResponse {
  /** Object type — always `'list'`. */
  object: 'list';
  /** Array of available models. */
  data: Model[];
}

/** Response from `GET /health`. */
export interface HealthResponse {
  /** Service health status. */
  status: 'ok' | 'degraded' | 'down';
  /** Server software version. */
  version: string;
  /** Tenant identifier. */
  tenant: string;
  /** Server uptime in seconds. */
  uptime_seconds: number;
}

/** Generic API error shape returned by the server. */
export interface ApiErrorResponse {
  /** Error details. */
  error: {
    /** Human-readable error message. */
    message: string;
    /** High-level error type (e.g. `'invalid_request_error'`). */
    type?: string;
    /** Machine-readable error code (e.g. `'rate_limited'`). */
    code?: string;
    /** Parameter that caused the error, if applicable. */
    param?: string;
  };
}

/** Configuration options for the DongAI client. */
export interface ClientOptions {
  /** Request timeout in milliseconds. Defaults vary by method. */
  timeout?: number;
  /** Maximum number of automatic retries for retryable errors. Default: 3. */
  maxRetries?: number;
}

// ---------------------------------------------------------------------------
// SDK Client
// ---------------------------------------------------------------------------

/**
 * DongAI — TypeScript SDK for the Dong AI Company API.
 *
 * Zero runtime dependencies. Uses native `fetch` (Node 18+).
 * Supports streaming chat, project execution, model listing, health checks,
 * and Prometheus metrics retrieval.
 *
 * @example
 * ```ts
 * import { DongAI } from '@dong-ai/sdk';
 *
 * const client = new DongAI('sk-...');
 * const models = await client.listModels();
 * console.log(models);
 * ```
 *
 * @example
 * ```ts
 * // Streaming chat
 * for await (const delta of client.chatStream([
 *   { role: 'user', content: 'Hello!' },
 * ])) {
 *   process.stdout.write(delta);
 * }
 * ```
 */
export class DongAI {
  private readonly apiKey: string;
  private readonly baseUrl: string;
  private readonly maxRetries: number;
  private readonly defaultTimeout: number;

  /**
   * Rate limit information from the most recent API response.
   *
   * Updated after every request that includes `X-RateLimit-*` headers.
   * Returns `null` if no rate-limit headers have been received yet.
   */
  public rateLimit: RateLimitInfo | null = null;

  /**
   * Creates a new DongAI client instance.
   *
   * All parameters are optional and fall back to environment variables.
   *
   * @param apiKey   Bearer token for authentication. Defaults to `process.env.DONG_API_KEY`.
   * @param baseUrl  Base URL of the API server. Defaults to `process.env.DONG_BASE_URL` or `http://localhost:8648`.
   * @param options  Additional client options (timeout, retry configuration).
   *
   * @example
   * ```ts
   * // Using environment variables
   * const client = new DongAI();
   *
   * // Explicit configuration
   * const client = new DongAI('sk-...', 'https://api.dong.ai', { timeout: 30000 });
   * ```
   */
  constructor(apiKey?: string, baseUrl?: string, options?: ClientOptions) {
    this.apiKey = apiKey ?? process.env.DONG_API_KEY ?? '';
    this.baseUrl = (baseUrl ?? process.env.DONG_BASE_URL ?? 'http://localhost:8648').replace(/\/+$/, '');
    this.maxRetries = options?.maxRetries ?? 3;
    this.defaultTimeout = options?.timeout ?? 0;
  }

  // -----------------------------------------------------------------------
  // Chat (non-streaming)
  // -----------------------------------------------------------------------

  /**
   * Send a chat completion request and receive a full response.
   *
   * Supports all OpenAI-compatible parameters via `ChatOptions`.
   *
   * @param messages  Array of chat messages in OpenAI format (`role` + `content`).
   * @param options   Optional parameters (model, temperature, max_tokens, etc.).
   * @param timeout   Request timeout in milliseconds. Defaults to 30000.
   *
   * @returns A `ChatResponse` with the model's reply and usage statistics.
   *
   * @throws {ValidationError} If the request payload is invalid.
   * @throws {AuthError}       If the API key is missing or invalid.
   * @throws {RateLimitError}  If rate-limited.
   * @throws {NotFoundError}   If the requested model does not exist.
   * @throws {UpstreamError}   If the upstream provider fails.
   * @throws {NetworkError}    If a network-level error occurs.
   *
   * @example
   * ```ts
   * const res = await client.chat(
   *   [{ role: 'user', content: 'What is TypeScript?' }],
   *   { model: 'gpt-4', temperature: 0.7 }
   * );
   * console.log(res.choices[0].message.content);
   * ```
   */
  async chat(
    messages: ChatMessage[],
    options?: ChatOptions,
    timeout?: number,
  ): Promise<ChatResponse> {
    const body = {
      messages,
      ...(options ?? {}),
      stream: false,
    };
    return this._post<ChatResponse>('/v1/chat/completions', body, timeout ?? 30000);
  }

  // -----------------------------------------------------------------------
  // Chat (streaming)
  // -----------------------------------------------------------------------

  /**
   * Send a chat completion request and stream back content deltas.
   *
   * Yields each content delta as it arrives from the server. The SSE stream
   * is parsed line-by-line; `[DONE]` signals and empty chunks are handled
   * automatically.
   *
   * @param messages  Array of chat messages in OpenAI format (`role` + `content`).
   * @param options   Optional parameters (model, temperature, max_tokens, etc.).
   * @param timeout   Request timeout in milliseconds. Defaults to 30000.
   *
   * @returns An `AsyncIterable` that yields content deltas (strings).
   *
   * @throws {ValidationError} If the request payload is invalid.
   * @throws {AuthError}       If the API key is missing or invalid.
   * @throws {RateLimitError}  If rate-limited.
   * @throws {NotFoundError}   If the requested model does not exist.
   * @throws {UpstreamError}   If the upstream provider fails.
   * @throws {NetworkError}    If a network-level error occurs.
   *
   * @example
   * ```ts
   * for await (const delta of client.chatStream(
   *   [{ role: 'user', content: 'Tell me a story' }],
   *   { model: 'gpt-4' }
   * )) {
   *   process.stdout.write(delta);
   * }
   * ```
   */
  async *chatStream(
    messages: ChatMessage[],
    options?: ChatOptions,
    timeout?: number,
  ): AsyncIterable<string> {
    const body = {
      messages,
      ...(options ?? {}),
      stream: true,
    };

    const response = await this._rawPost('/v1/chat/completions', body, timeout ?? 30000);

    const contentType = response.headers.get('content-type') ?? '';
    if (!contentType.includes('text/event-stream')) {
      // Fallback: return the single response body content
      const data = (await response.json()) as ChatResponse;
      if (data.choices?.[0]?.message?.content) {
        yield data.choices[0].message.content;
      }
      return;
    }

    const reader = response.body?.getReader();
    if (!reader) {
      throw new Error('Response body is null — cannot start stream');
    }

    const decoder = new TextDecoder();
    let buffer = '';

    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        // Keep the last (possibly incomplete) line in the buffer
        buffer = lines.pop() ?? '';

        for (const line of lines) {
          const trimmed = line.trim();

          // SSE event boundary — skip
          if (trimmed === '' || trimmed.startsWith(':')) continue;

          // "[DONE]" signal
          if (trimmed === 'data: [DONE]') return;

          if (trimmed.startsWith('data: ')) {
            const json = trimmed.slice(6);
            try {
              const chunk = JSON.parse(json) as ChatChunk;
              const delta = chunk.choices?.[0]?.delta?.content;
              if (delta != null) {
                yield delta;
              }
            } catch {
              // Malformed JSON chunk — skip silently
            }
          }
        }
      }
    } catch (err) {
      // Wrap fetch-level stream errors as NetworkError
      if (err instanceof DongAiError) throw err;
      throw new NetworkError(err instanceof Error ? err : new Error(String(err)));
    } finally {
      reader.releaseLock();
    }
  }

  // -----------------------------------------------------------------------
  // Run — CEO project execution
  // -----------------------------------------------------------------------

  /**
   * Execute a project command via the CEO `/v1/run` endpoint.
   *
   * Sends a command to be executed in an isolated project environment.
   *
   * @param request  The run request specifying project, command, and optional args.
   * @param timeout  Request timeout in milliseconds. Defaults to 60000.
   *
   * @returns A `RunResponse` with execution status, output, and timing.
   *
   * @throws {ValidationError} If the request payload is invalid.
   * @throws {AuthError}       If the API key is missing or invalid.
   * @throws {RateLimitError}  If rate-limited.
   * @throws {NetworkError}    If a network-level error occurs.
   *
   * @example
   * ```ts
   * const result = await client.run({
   *   project: 'my-app',
   *   command: 'npm test',
   *   timeout: 120,
   * });
   * console.log(result.output);
   * ```
   */
  async run(request: RunRequest, timeout?: number): Promise<RunResponse> {
    return this._post<RunResponse>('/v1/run', request, timeout ?? 60000);
  }

  // -----------------------------------------------------------------------
  // List models
  // -----------------------------------------------------------------------

  /**
   * Fetch the list of available AI models from `/v1/models`.
   *
   * @param timeout  Request timeout in milliseconds. Defaults to 30000.
   *
   * @returns An array of `Model` objects representing available models.
   *
   * @throws {AuthError}      If the API key is missing or invalid.
   * @throws {NetworkError}   If a network-level error occurs.
   *
   * @example
   * ```ts
   * const models = await client.listModels();
   * console.log(models.map(m => m.id));
   * ```
   */
  async listModels(timeout?: number): Promise<Model[]> {
    const res = await this._get<ListModelsResponse>('/v1/models', timeout ?? 30000);
    return res.data;
  }

  // -----------------------------------------------------------------------
  // Health
  // -----------------------------------------------------------------------

  /**
   * Fetch health and tenant information from `/health`.
   *
   * @param timeout  Request timeout in milliseconds. Defaults to 10000.
   *
   * @returns A `HealthResponse` with service status, version, and tenant.
   *
   * @throws {NetworkError} If a network-level error occurs.
   *
   * @example
   * ```ts
   * const health = await client.health();
   * console.log(`Status: ${health.status}, Tenant: ${health.tenant}`);
   * ```
   */
  async health(timeout?: number): Promise<HealthResponse> {
    return this._get<HealthResponse>('/health', timeout ?? 10000);
  }

  // -----------------------------------------------------------------------
  // Metrics
  // -----------------------------------------------------------------------

  /**
   * Fetch Prometheus-formatted metrics as a raw string from `/metrics`.
   *
   * @param timeout  Request timeout in milliseconds. Defaults to 10000.
   *
   * @returns A raw string in Prometheus exposition format.
   *
   * @throws {AuthError}    If the API key is missing or invalid.
   * @throws {NetworkError} If a network-level error occurs.
   *
   * @example
   * ```ts
   * const metrics = await client.metrics();
   * console.log(metrics);
   * ```
   */
  async metrics(timeout?: number): Promise<string> {
    const url = `${this.baseUrl}/metrics`;
    const headers = this._headers();
    const response = await this._fetchWithRetry(url, { method: 'GET', headers }, timeout ?? 10000);

    if (!response.ok) {
      throw fromError(response, await this._errorBody(response));
    }

    return response.text();
  }

  // -----------------------------------------------------------------------
  // Internal helpers
  // -----------------------------------------------------------------------

  /**
   * Build the default headers for every request.
   */
  private _headers(): Record<string, string> {
    const h: Record<string, string> = {
      'Content-Type': 'application/json',
    };
    if (this.apiKey) {
      h['Authorization'] = `Bearer ${this.apiKey}`;
    }
    return h;
  }

  /**
   * Parse rate-limit headers from a response and update `this.rateLimit`.
   */
  private _trackRateLimit(response: globalThis.Response): void {
    const limit = response.headers.get('x-ratelimit-limit');
    const remaining = response.headers.get('x-ratelimit-remaining');
    const reset = response.headers.get('x-ratelimit-reset');
    if (limit != null && remaining != null && reset != null) {
      this.rateLimit = {
        limit: parseInt(limit, 10),
        remaining: parseInt(remaining, 10),
        reset: parseInt(reset, 10),
      };
    }
  }

  /**
   * Determine whether a status code is retryable.
   */
  private _isRetryable(status: number): boolean {
    return status === 429 || status === 502 || status === 503;
  }

  /**
   * Determine whether an error is a retryable network error.
   */
  private _isRetryableError(err: Error): boolean {
    const msg = err.message.toLowerCase();
    return (
      msg.includes('dns') ||
      msg.includes('econnrefused') ||
      msg.includes('econnreset') ||
      msg.includes('enetunreach') ||
      msg.includes('timeout') ||
      msg.includes('abort') ||
      msg.includes('socket hang up') ||
      msg.includes('fetch failed')
    );
  }

  /**
   * Sleep for a given number of milliseconds.
   */
  private _sleep(ms: number): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  /**
   * Compute the delay before the next retry attempt.
   *
   * Uses exponential backoff with full jitter.
   *
   * @param attempt  The current retry attempt number (0-indexed).
   * @param baseMs   The base delay in milliseconds.
   * @param retryAfter  Optional explicit `Retry-After` value in seconds.
   */
  private _computeBackoff(attempt: number, baseMs: number, retryAfter?: number): number {
    if (retryAfter != null && retryAfter > 0) {
      // Honour the server's Retry-After header, with jitter
      return retryAfter * 1000 + Math.random() * 500;
    }
    const exponential = baseMs * Math.pow(2, attempt);
    // Full jitter: random between 0 and exponential
    return Math.random() * Math.min(exponential, 30000);
  }

  /**
   * Perform a fetch with automatic retry, timeout, and rate-limit tracking.
   *
   * Retries on HTTP 429, 502, 503 and certain network errors.
   * Uses exponential backoff with jitter. Respects `Retry-After` header.
   *
   * @param url       The URL to fetch.
   * @param init      The fetch options (method, headers, body, etc.).
   * @param timeoutMs Timeout in milliseconds.
   * @param attempt   Current retry attempt (internal, 0-indexed).
   *
   * @returns The fetch `Response` object.
   *
   * @throws {NetworkError} If all retries are exhausted on network errors.
   * @throws {DongAiError}  If the server returns a non-retryable error.
   */
  private async _fetchWithRetry(
    url: string,
    init: RequestInit,
    timeoutMs?: number,
    attempt = 0,
  ): Promise<globalThis.Response> {
    // Create abort controller for timeout
    const controller = new AbortController();
    const signal = controller.signal;

    let timeoutHandle: ReturnType<typeof setTimeout> | undefined;
    if (timeoutMs && timeoutMs > 0) {
      timeoutHandle = setTimeout(() => {
        controller.abort(new Error(`Request timed out after ${timeoutMs}ms`));
      }, timeoutMs);
    }

    try {
      const response = await fetch(url, { ...init, signal });

      // Track rate limit info regardless of status
      this._trackRateLimit(response);

      // If successful, return immediately
      if (response.ok) {
        return response;
      }

      // If retryable and we have retries left, back off and retry
      if (this._isRetryable(response.status) && attempt < this.maxRetries) {
        let retryAfter: number | undefined;

        // Parse Retry-After for 429 specifically
        if (response.status === 429) {
          const retryAfterRaw = response.headers.get('retry-after');
          if (retryAfterRaw && /^\d+$/.test(retryAfterRaw)) {
            retryAfter = parseInt(retryAfterRaw, 10);
          }
        }

        const delay = this._computeBackoff(attempt, 1000, retryAfter);
        await this._sleep(delay);

        return this._fetchWithRetry(url, init, timeoutMs, attempt + 1);
      }

      // Non-retryable status — throw typed error
      throw fromError(response, await this._errorBody(response));
    } catch (err) {
      // If this is already a DongAiError, re-throw
      if (err instanceof DongAiError) {
        throw err;
      }

      // Network-level errors: retry if retryable
      const error = err instanceof Error ? err : new Error(String(err));
      if (this._isRetryableError(error) && attempt < this.maxRetries) {
        const delay = this._computeBackoff(attempt, 1000);
        await this._sleep(delay);
        return this._fetchWithRetry(url, init, timeoutMs, attempt + 1);
      }

      // If it's an abort/timeout error, wrap as NetworkError
      if (
        error.name === 'AbortError' ||
        error.message.toLowerCase().includes('timed out') ||
        error.message.toLowerCase().includes('abort')
      ) {
        throw new NetworkError(error);
      }

      // Other network-level errors
      throw new NetworkError(error);
    } finally {
      if (timeoutHandle) {
        clearTimeout(timeoutHandle);
      }
    }
  }

  /**
   * Perform a GET request with retry and rate-limit tracking.
   */
  private async _get<T>(path: string, timeoutMs = 30000): Promise<T> {
    const url = `${this.baseUrl}${path}`;
    const response = await this._fetchWithRetry(url, {
      method: 'GET',
      headers: this._headers(),
    }, timeoutMs);
    return response.json() as Promise<T>;
  }

  /**
   * Perform a POST request with retry and rate-limit tracking.
   */
  private async _post<T>(path: string, body: unknown, timeoutMs = 30000): Promise<T> {
    const response = await this._rawPost(path, body, timeoutMs);
    return response.json() as Promise<T>;
  }

  /**
   * Send a raw POST request and return the Response.
   */
  private _rawPost(path: string, body: unknown, timeoutMs?: number): Promise<globalThis.Response> {
    const url = `${this.baseUrl}${path}`;
    return this._fetchWithRetry(url, {
      method: 'POST',
      headers: this._headers(),
      body: JSON.stringify(body),
    }, timeoutMs);
  }

  /**
   * Safely extract the error body from a non-OK response.
   */
  private async _errorBody(response: globalThis.Response): Promise<ApiErrorResponse | string> {
    try {
      return (await response.json()) as ApiErrorResponse;
    } catch {
      return response.statusText || `HTTP ${response.status}`;
    }
  }
}

// Re-export error types for convenience
export {
  DongAiError,
  AuthError,
  RateLimitError,
  NotFoundError,
  UpstreamError,
  NetworkError,
  ValidationError,
  fromError,
} from './errors.js';
export type { RateLimitInfo } from './errors.js';
