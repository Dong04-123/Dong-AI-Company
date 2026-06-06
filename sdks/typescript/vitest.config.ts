// ---------------------------------------------------------------------------
// Vitest configuration for @dong-ai/sdk
// ---------------------------------------------------------------------------

import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    // Use node environment (no DOM needed)
    environment: 'node',
    // Global test utilities (describe, it, expect, vi)
    globals: true,
    // Include all test files matching these patterns
    include: ['tests/**/*.test.ts'],
    // Exclude node_modules and dist
    exclude: ['node_modules', 'dist'],
    // Timeout per test (10 seconds)
    testTimeout: 10_000,
    // Enable TypeScript support via vite
    deps: {
      inline: [],
    },
  },
});
