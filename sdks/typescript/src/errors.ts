// ---------------------------------------------------------------------------
// Dong AI SDK — Error class hierarchy
// ---------------------------------------------------------------------------

import type { ApiErrorResponse } from './index.js';

// ---------------------------------------------------------------------------
// Rate limit info parsed from response headers
// ---------------------------------------------------------------------------

/**
 * Rate limit information parsed from response headers.
 *
 * Returned by the API in `X-RateLimit-Limit`, `X-RateLimit-Remaining`,
 * and `X-RateLimit-Reset` headers.
 */
export interface RateLimitInfo {
  /** Maximum requests allowed in the current window. */
  limit: number;
  /** Number of requests remaining in the current window. */
  remaining: number;
  /** Unix timestamp (seconds) when the rate limit window resets. */
  reset: number;
}

// ---------------------------------------------------------------------------
// DongAiError — base class
// ---------------------------------------------------------------------------

/**
 * Base error class for all Dong AI SDK errors.
 *
 * Extends `Error` with HTTP status, error code, error type, and response
 * headers for programmatic handling.
 */
export class DongAiError extends Error {
  /** HTTP status code returned by the API. */
  public status: number;

  /** Machine-readable error code (e.g. `'unauthorized'`, `'rate_limited'`). */
  public code?: string;

  /** High-level error type (e.g. `'invalid_request_error'`). */
  public type?: string;

  /** Response headers from the API call. May contain rate-limit info. */
  public headers?: globalThis.Headers;

  constructor(
    status: number,
    body: ApiErrorResponse | string,
    headers?: globalThis.Headers,
  ) {
    const msg = typeof body === 'string' ? body : body.error?.message ?? 'Unknown error';
    super(`Dong AI API error ${status}: ${msg}`);
    this.name = 'DongAiError';
    this.status = status;
    this.headers = headers;
    if (typeof body !== 'string') {
      this.code = body.error?.code;
      this.type = body.error?.type;
    }
  }
}

// ---------------------------------------------------------------------------
// AuthError — 401 Unauthorized
// ---------------------------------------------------------------------------

/**
 * Thrown when the API returns HTTP 401 (Unauthorized).
 *
 * Typically means the API key is missing, invalid, or expired.
 */
export class AuthError extends DongAiError {
  constructor(body: ApiErrorResponse | string, headers?: globalThis.Headers) {
    super(401, body, headers);
    this.name = 'AuthError';
    this.code = 'unauthorized';
  }
}

// ---------------------------------------------------------------------------
// RateLimitError — 429 Too Many Requests
// ---------------------------------------------------------------------------

/**
 * Thrown when the API returns HTTP 429 (Too Many Requests).
 *
 * Contains parsed rate-limit information and a `retryAfter` property
 * indicating how many seconds to wait before retrying.
 */
export class RateLimitError extends DongAiError {
  /** Number of seconds to wait before retrying, parsed from `Retry-After` header. */
  public readonly retryAfter: number;

  constructor(body: ApiErrorResponse | string, headers?: globalThis.Headers) {
    super(429, body, headers);
    this.name = 'RateLimitError';
    this.code = 'rate_limited';

    // Parse Retry-After header (seconds or HTTP-date)
    const retryAfterRaw = headers?.get('retry-after') ?? '';
    if (/^\d+$/.test(retryAfterRaw)) {
      this.retryAfter = parseInt(retryAfterRaw, 10);
    } else if (retryAfterRaw) {
      // HTTP-date format — compute seconds from now
      const retryDate = new Date(retryAfterRaw).getTime();
      const now = Date.now();
      this.retryAfter = Math.max(0, Math.ceil((retryDate - now) / 1000));
    } else {
      this.retryAfter = 1; // sensible default
    }
  }

  /**
   * Convenience getter for rate-limit header information.
   * Returns `null` if the headers are not available or unparseable.
   */
  get rateLimit(): RateLimitInfo | null {
    if (!this.headers) return null;
    const limit = this.headers.get('x-ratelimit-limit');
    const remaining = this.headers.get('x-ratelimit-remaining');
    const reset = this.headers.get('x-ratelimit-reset');
    if (limit != null && remaining != null && reset != null) {
      return {
        limit: parseInt(limit, 10),
        remaining: parseInt(remaining, 10),
        reset: parseInt(reset, 10),
      };
    }
    return null;
  }
}

// ---------------------------------------------------------------------------
// NotFoundError — 404 Model Not Found
// ---------------------------------------------------------------------------

/**
 * Thrown when the API returns HTTP 404 (Not Found).
 *
 * Typically means the requested model does not exist or is not accessible.
 */
export class NotFoundError extends DongAiError {
  constructor(body: ApiErrorResponse | string, headers?: globalThis.Headers) {
    super(404, body, headers);
    this.name = 'NotFoundError';
    this.code = 'model_not_found';
  }
}

// ---------------------------------------------------------------------------
// UpstreamError — 502 Bad Gateway / upstream failure
// ---------------------------------------------------------------------------

/**
 * Thrown when the API returns HTTP 502 (Bad Gateway) or another upstream error.
 *
 * Indicates the API server received an invalid response from an upstream
 * provider. May be transient — retry is recommended.
 */
export class UpstreamError extends DongAiError {
  constructor(body: ApiErrorResponse | string, headers?: globalThis.Headers) {
    super(502, body, headers);
    this.name = 'UpstreamError';
    this.code = 'upstream_error';
  }
}

// ---------------------------------------------------------------------------
// ValidationError — 400 Bad Request
// ---------------------------------------------------------------------------

/**
 * Thrown when the API returns HTTP 400 (Bad Request).
 *
 * Indicates the request payload failed server-side validation.
 */
export class ValidationError extends DongAiError {
  constructor(body: ApiErrorResponse | string, headers?: globalThis.Headers) {
    super(400, body, headers);
    this.name = 'ValidationError';
    this.code = 'invalid_request';
  }
}

// ---------------------------------------------------------------------------
// NetworkError — Fetch-level failures (DNS, timeout, connection refused)
// ---------------------------------------------------------------------------

/**
 * Thrown when a network-level error prevents the request from reaching the API.
 *
 * Covers DNS resolution failures, connection refused, socket hang-up,
 * and timeout-induced abort errors. Not triggered by HTTP status codes.
 */
export class NetworkError extends DongAiError {
  /** The original error that caused the network failure. */
  public readonly cause: Error;

  constructor(cause: Error) {
    super(0, `Network error: ${cause.message}`);
    this.name = 'NetworkError';
    this.code = 'network_error';
    this.cause = cause;
  }
}

// ---------------------------------------------------------------------------
// fromError — factory function
// ---------------------------------------------------------------------------

/**
 * Create the most specific `DongAiError` subclass for a given HTTP response.
 *
 * Inspects the HTTP status code and returns the appropriate error type:
 * - 400 → `ValidationError`
 * - 401 → `AuthError`
 * - 404 → `NotFoundError`
 * - 429 → `RateLimitError`
 * - 502 → `UpstreamError`
 * - all others → `DongAiError` (base type)
 *
 * @param response The raw `Response` object from `fetch`.
 * @param body     The parsed JSON body (or a string fallback).
 * @returns An instance of the most specific error subclass.
 */
export function fromError(response: globalThis.Response, body: ApiErrorResponse | string): DongAiError {
  const headers = response.headers;
  switch (response.status) {
    case 400:
      return new ValidationError(body, headers);
    case 401:
      return new AuthError(body, headers);
    case 404:
      return new NotFoundError(body, headers);
    case 429:
      return new RateLimitError(body, headers);
    case 502:
      return new UpstreamError(body, headers);
    default:
      return new DongAiError(response.status, body, headers);
  }
}
