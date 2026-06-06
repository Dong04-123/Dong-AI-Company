#!/usr/bin/env node

import { DongAI, type ChatMessage, type RunRequest } from './index.js';

// ---------------------------------------------------------------------------
// CLI entry point — parse subcommand and dispatch
// ---------------------------------------------------------------------------

async function main() {
  const [, , subcommand, ...args] = process.argv;

  switch (subcommand) {
    case 'chat':
      return cmdChat(args);
    case 'run':
      return cmdRun(args);
    case 'models':
      return cmdModels();
    case 'health':
      return cmdHealth();
    case 'help':
    case '--help':
    case '-h':
      return printHelp();
    default:
      if (subcommand) {
        console.error(`Unknown subcommand: ${subcommand}\n`);
      }
      printHelp();
      process.exit(1);
  }
}

// ---------------------------------------------------------------------------
// Subcommand: chat
// ---------------------------------------------------------------------------

async function cmdChat(args: string[]) {
  const client = new DongAI();
  let message = args.join(' ') || '';

  // If no inline message, prompt interactively (simple stdin read)
  if (!message) {
    const stdin = await readStdin();
    if (stdin.trim()) {
      message = stdin.trim();
    }
  }

  if (!message) {
    console.error('Usage: dongai chat <message>\n       echo "Hello" | dongai chat');
    process.exit(1);
  }

  const stream = args.includes('--stream') || args.includes('-s');

  const messages: ChatMessage[] = [{ role: 'user', content: message }];

  try {
    if (stream) {
      // Streaming mode
      for await (const delta of client.chatStream(messages)) {
        process.stdout.write(delta);
      }
      process.stdout.write('\n');
    } else {
      // Non-streaming
      const res = await client.chat(messages);
      const content = res.choices?.[0]?.message?.content ?? '';
      console.log(content);
      if (res.usage) {
        console.error(
          `\n--- tokens: ${res.usage.prompt_tokens} prompt + ${res.usage.completion_tokens} completion = ${res.usage.total_tokens} total ---`,
        );
      }
    }
  } catch (err: unknown) {
    handleError(err);
  }
}

// ---------------------------------------------------------------------------
// Subcommand: run
// ---------------------------------------------------------------------------

async function cmdRun(args: string[]) {
  const client = new DongAI();

  // Parse --project and --command from positional args
  let project = '';
  let command = '';

  for (let i = 0; i < args.length; i++) {
    if (args[i] === '--project' || args[i] === '-p') {
      project = args[++i] ?? '';
    } else if (args[i] === '--command' || args[i] === '-c') {
      command = args[++i] ?? '';
    }
  }

  if (!project || !command) {
    console.error('Usage: dongai run --project <name> --command <shell command>');
    process.exit(1);
  }

  const request: RunRequest = { project, command };

  try {
    const res = await client.run(request);
    console.log(`ID:     ${res.id}`);
    console.log(`Status: ${res.status}`);
    if (res.output) {
      console.log(`\n${res.output}`);
    }
    if (res.error) {
      console.error(`\nError: ${res.error}`);
    }
  } catch (err: unknown) {
    handleError(err);
  }
}

// ---------------------------------------------------------------------------
// Subcommand: models
// ---------------------------------------------------------------------------

async function cmdModels() {
  const client = new DongAI();

  try {
    const models = await client.listModels();
    if (models.length === 0) {
      console.log('No models available.');
      return;
    }

    // Aligned table output
    console.log('ID'.padEnd(48), 'OWNED BY'.padEnd(24), 'CREATED');
    console.log('-'.repeat(96));
    for (const m of models) {
      const date = new Date(m.created * 1000).toISOString().slice(0, 19).replace('T', ' ');
      console.log(m.id.padEnd(48), (m.owned_by ?? '').padEnd(24), date);
    }
  } catch (err: unknown) {
    handleError(err);
  }
}

// ---------------------------------------------------------------------------
// Subcommand: health
// ---------------------------------------------------------------------------

async function cmdHealth() {
  const client = new DongAI();

  try {
    const res = await client.health();
    console.log(`Status:  ${res.status}`);
    console.log(`Version: ${res.version}`);
    console.log(`Tenant:  ${res.tenant}`);
    console.log(`Uptime:  ${res.uptime_seconds}s`);
  } catch (err: unknown) {
    handleError(err);
  }
}

// ---------------------------------------------------------------------------
// Help
// ---------------------------------------------------------------------------

function printHelp() {
  console.log(`
dongai — CLI for the Dong AI Company API

USAGE
  dongai <subcommand> [options]

SUBCOMMANDS
  chat [message]        Send a chat message
    --stream, -s        Stream the response token-by-token
    (pipe stdin or pass inline text)

  run                   Execute a CEO project command
    --project, -p <name>    Project name (required)
    --command, -c <cmd>     Shell command (required)

  models                List available AI models

  health                Check API server health

  help                  Show this help message

ENVIRONMENT
  DONG_API_KEY          Bearer token for API authentication
  DONG_BASE_URL         API base URL (default: http://localhost:8648)

EXAMPLES
  dongai chat "Hello, world!"
  dongai chat --stream "Tell me a story"
  echo "Translate to French" | dongai chat
  dongai run --project my-app --command "npm test"
  dongai models
  dongai health
`);
}

// ---------------------------------------------------------------------------
// Utilities
// ---------------------------------------------------------------------------

/** Read all of stdin as a single string. */
function readStdin(): Promise<string> {
  return new Promise((resolve, reject) => {
    const chunks: Buffer[] = [];
    const stdin = process.stdin;

    // If stdin is a TTY, there is no piped data
    if (stdin.isTTY) {
      resolve('');
      return;
    }

    stdin.setEncoding('utf8');
    stdin.on('data', (chunk: string) => chunks.push(Buffer.from(chunk)));
    stdin.on('end', () => resolve(Buffer.concat(chunks).toString('utf8')));
    stdin.on('error', reject);
  });
}

/** Pretty-print an error from an SDK call. */
function handleError(err: unknown): void {
  if (err instanceof Error) {
    console.error(`Error: ${err.message}`);
  } else {
    console.error(`Error: ${String(err)}`);
  }
  process.exit(1);
}

// ---------------------------------------------------------------------------
// Run
// ---------------------------------------------------------------------------

main().catch((err) => {
  console.error('Fatal:', err);
  process.exit(1);
});
