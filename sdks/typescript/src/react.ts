// ---------------------------------------------------------------------------
// Dong AI SDK — React hooks
// ---------------------------------------------------------------------------

import { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import { DongAI } from './index.js';
import type { ChatMessage, ChatOptions, HealthResponse, Model } from './index.js';

// ---------------------------------------------------------------------------
// useDongAI
// ---------------------------------------------------------------------------

/** Global singleton cache keyed by `apiKey|baseUrl`. */
const instances = new Map<string, DongAI>();

/**
 * Returns a singleton `DongAI` client instance for the given credentials.
 *
 * The instance is cached globally so that all components sharing the same
 * `apiKey` and `baseUrl` reuse the same client (and therefore the same
 * rate-limit tracking state).
 *
 * @param apiKey  Bearer token for authentication. Falls back to `process.env.DONG_API_KEY`.
 * @param baseUrl Base URL of the API server. Falls back to `process.env.DONG_BASE_URL`.
 *
 * @returns A `DongAI` client instance.
 *
 * @example
 * ```tsx
 * import { useDongAI } from '@dong-ai/sdk/react';
 *
 * function Chat() {
 *   const client = useDongAI();
 *   // use client.chat(), client.chatStream(), etc.
 * }
 * ```
 */
export function useDongAI(apiKey?: string, baseUrl?: string): DongAI {
  const key = `${apiKey ?? ''}|${baseUrl ?? ''}`;
  return useMemo(() => {
    if (instances.has(key)) {
      return instances.get(key)!;
    }
    const client = new DongAI(apiKey, baseUrl);
    instances.set(key, client);
    return client;
  }, [key]);
}

// ---------------------------------------------------------------------------
// useChatStream
// ---------------------------------------------------------------------------

/** A single message in the chat stream state. */
export interface StreamMessage {
  /** The role of the message author. */
  role: 'user' | 'assistant';
  /** The full text content accumulated so far. */
  content: string;
}

/** Return type of the `useChatStream` hook. */
export interface UseChatStreamReturn {
  /**
   * Send a message and begin streaming the assistant's reply.
   *
   * @param content  The user's message text.
   * @param options  Optional chat parameters (model, temperature, etc.).
   */
  send: (content: string, options?: ChatOptions) => Promise<void>;

  /** The accumulated conversation history. */
  messages: StreamMessage[];

  /** Whether a stream is currently in progress. */
  isStreaming: boolean;

  /** The last error that occurred, or `null`. */
  error: Error | null;

  /** Clear the conversation history. */
  reset: () => void;
}

/**
 * React hook for streaming chat completions.
 *
 * Manages conversation state, streaming status, and error handling.
 * Each call to `send()` appends the user message and streams the
 * assistant's reply token by token.
 *
 * @param apiKey   Optional API key. Falls back to `process.env.DONG_API_KEY`.
 * @param baseUrl  Optional base URL. Falls back to `process.env.DONG_BASE_URL`.
 *
 * @returns An object with `send`, `messages`, `isStreaming`, `error`, and `reset`.
 *
 * @example
 * ```tsx
 * function ChatBox() {
 *   const { send, messages, isStreaming, error } = useChatStream();
 *
 *   return (
 *     <div>
 *       {messages.map((m, i) => (
 *         <p key={i}><strong>{m.role}:</strong> {m.content}</p>
 *       ))}
 *       <button onClick={() => send('Hello!')} disabled={isStreaming}>
 *         Send
 *       </button>
 *       {error && <p style={{ color: 'red' }}>{error.message}</p>}
 *     </div>
 *   );
 * }
 * ```
 */
export function useChatStream(apiKey?: string, baseUrl?: string): UseChatStreamReturn {
  const client = useDongAI(apiKey, baseUrl);
  const [messages, setMessages] = useState<StreamMessage[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      abortRef.current?.abort();
    };
  }, []);

  const send = useCallback(
    async (content: string, options?: ChatOptions) => {
      if (!content.trim()) return;

      setError(null);
      setIsStreaming(true);

      // Cancel any in-flight stream
      abortRef.current?.abort();

      const userMessage: StreamMessage = { role: 'user', content };
      setMessages(prev => [...prev, userMessage]);

      // Accumulator for the assistant's reply
      const assistantMessage: StreamMessage = { role: 'assistant', content: '' };
      setMessages(prev => [...prev, assistantMessage]);

      try {
        // Build conversation history
        const history: ChatMessage[] = messages.map(m => ({
          role: m.role as 'user' | 'assistant',
          content: m.content,
        }));
        history.push({ role: 'user', content });

        for await (const delta of client.chatStream(history, options)) {
          assistantMessage.content += delta;
          // Trigger re-render with updated content
          setMessages(prev => {
            const updated = [...prev];
            updated[updated.length - 1] = { ...assistantMessage };
            return updated;
          });
        }
      } catch (err) {
        // Remove the empty assistant message on error
        setMessages(prev => prev.slice(0, -1));
        setError(err instanceof Error ? err : new Error(String(err)));
      } finally {
        setIsStreaming(false);
      }
    },
    [client, messages],
  );

  const reset = useCallback(() => {
    setMessages([]);
    setError(null);
    abortRef.current?.abort();
  }, []);

  return { send, messages, isStreaming, error, reset };
}

// ---------------------------------------------------------------------------
// useHealth
// ---------------------------------------------------------------------------

/** Return type of the `useHealth` hook. */
export interface UseHealthReturn {
  /** The latest health check result, or `null` before the first fetch. */
  health: HealthResponse | null;

  /** Whether a health check is in progress. */
  loading: boolean;

  /** The last error that occurred, or `null`. */
  error: Error | null;

  /** Manually trigger a health check. */
  refetch: () => void;
}

/**
 * React hook for polling the Dong AI API health endpoint.
 *
 * Automatically fetches health on mount and provides a `refetch` function
 * for manual refreshes.
 *
 * @param apiKey   Optional API key. Falls back to `process.env.DONG_API_KEY`.
 * @param baseUrl  Optional base URL. Falls back to `process.env.DONG_BASE_URL`.
 *
 * @returns An object with `health`, `loading`, `error`, and `refetch`.
 *
 * @example
 * ```tsx
 * function HealthStatus() {
 *   const { health, loading, error } = useHealth();
 *   if (loading) return <p>Checking...</p>;
 *   if (error) return <p>Error: {error.message}</p>;
 *   return <p>Status: {health?.status}</p>;
 * }
 * ```
 */
export function useHealth(apiKey?: string, baseUrl?: string): UseHealthReturn {
  const client = useDongAI(apiKey, baseUrl);
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const fetchHealth = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await client.health();
      setHealth(result);
    } catch (err) {
      setError(err instanceof Error ? err : new Error(String(err)));
    } finally {
      setLoading(false);
    }
  }, [client]);

  useEffect(() => {
    fetchHealth();
  }, [fetchHealth]);

  return { health, loading, error, refetch: fetchHealth };
}

// ---------------------------------------------------------------------------
// useModels
// ---------------------------------------------------------------------------

/** Return type of the `useModels` hook. */
export interface UseModelsReturn {
  /** The list of available models, or `null` before the first fetch. */
  models: Model[] | null;

  /** Whether a model fetch is in progress. */
  loading: boolean;

  /** The last error that occurred, or `null`. */
  error: Error | null;

  /** Manually trigger a model list refresh. */
  refetch: () => void;
}

/**
 * React hook for fetching available AI models.
 *
 * Automatically fetches the model list on mount and provides a `refetch`
 * function for manual refreshes.
 *
 * @param apiKey   Optional API key. Falls back to `process.env.DONG_API_KEY`.
 * @param baseUrl  Optional base URL. Falls back to `process.env.DONG_BASE_URL`.
 *
 * @returns An object with `models`, `loading`, `error`, and `refetch`.
 *
 * @example
 * ```tsx
 * function ModelList() {
 *   const { models, loading, error } = useModels();
 *   if (loading) return <p>Loading models...</p>;
 *   if (error) return <p>Error: {error.message}</p>;
 *   return (
 *     <ul>
 *       {models?.map(m => <li key={m.id}>{m.id}</li>)}
 *     </ul>
 *   );
 * }
 * ```
 */
export function useModels(apiKey?: string, baseUrl?: string): UseModelsReturn {
  const client = useDongAI(apiKey, baseUrl);
  const [models, setModels] = useState<Model[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const fetchModels = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await client.listModels();
      setModels(result);
    } catch (err) {
      setError(err instanceof Error ? err : new Error(String(err)));
    } finally {
      setLoading(false);
    }
  }, [client]);

  useEffect(() => {
    fetchModels();
  }, [fetchModels]);

  return { models, loading, error, refetch: fetchModels };
}
