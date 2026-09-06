import { promises as fs } from "node:fs";
import path from "node:path";
import { extractSymbolAtLocation } from "../indexer/slicer.js";
import { patchFileRange } from "../tools/filePatcher.js";
import { ProcessSandbox, type ProcessResult } from "../engine/sandbox.js";
import { searchWeb, fetchDocumentation } from "../tools/webSearch.js";
import { BrowserSession } from "../tools/browser.js";

export interface ToolSchema {
  name: string;
  description: string;
  parameters: Record<string, { type: string; required?: boolean; description?: string }>;
}

export interface AgentTool {
  schema: ToolSchema;
  execute(args: Record<string, unknown>): Promise<unknown>;
}

function stringArg(args: Record<string, unknown>, name: string): string {
  const value = args[name];
  if (typeof value !== "string" || !value) throw new TypeError(`${name} must be a non-empty string`);
  return value;
}

function numberArg(args: Record<string, unknown>, name: string): number {
  const value = args[name];
  if (typeof value !== "number" || !Number.isInteger(value)) throw new TypeError(`${name} must be an integer`);
  return value;
}

async function walk(root: string, directory = root): Promise<string[]> {
  const entries = await fs.readdir(directory, { withFileTypes: true });
  const results: string[] = [];
  for (const entry of entries) {
    if ([".git", "node_modules", "dist", ".venv"].includes(entry.name)) continue;
    const absolute = path.join(directory, entry.name);
    if (entry.isDirectory()) results.push(...await walk(root, absolute));
    else results.push(path.relative(root, absolute));
  }
  return results;
}

function resultText(result: ProcessResult): string {
  return [result.stdout, result.stderr].filter(Boolean).join("\n").trim();
}

function tokenize(command: string): string[] {
  const tokens: string[] = [];
  let token = "";
  let quote: "'" | '"' | null = null;
  for (const character of command.trim()) {
    if (quote) {
      if (character === quote) quote = null;
      else token += character;
    } else if (character === "'" || character === '"') quote = character;
    else if (/\s/.test(character)) {
      if (token) { tokens.push(token); token = ""; }
    } else token += character;
  }
  if (quote) throw new SyntaxError("command contains an unterminated quote");
  if (token) tokens.push(token);
  if (tokens.length === 0) throw new RangeError("command cannot be empty");
  return tokens;
}

export function createAgentTools(workspaceRoot: string, sandbox = new ProcessSandbox()): AgentTool[] {
  const root = path.resolve(workspaceRoot);
  const resolveInside = (file: string): string => {
    const resolved = path.resolve(root, file);
    if (!resolved.startsWith(`${root}${path.sep}`)) throw new Error("Path must remain inside the workspace.");
    return resolved;
  };
  return [
    {
      schema: {
        name: "search_web",
        description: "Search the public web without API keys using DuckDuckGo HTML.",
        parameters: { query: { type: "string", required: true }, maxResults: { type: "number" } }
      },
      async execute(args) {
        return searchWeb(stringArg(args, "query"), args.maxResults === undefined ? 5 : numberArg(args, "maxResults"));
      }
    },
    {
      schema: {
        name: "fetch_docs",
        description: "Fetch and clean public package or official documentation.",
        parameters: { url: { type: "string", required: true } }
      },
      async execute(args) {
        return { url: stringArg(args, "url"), content: await fetchDocumentation(stringArg(args, "url")) };
      }
    },
    {
      schema: {
        name: "browse_url",
        description: "Open a URL in a local headless browser and inspect console errors and accessibility.",
        parameters: { url: { type: "string", required: true } }
      },
      async execute(args) {
        const browser = new BrowserSession();
        try {
          await browser.navigate(stringArg(args, "url"));
          return { consoleErrors: browser.getConsoleErrors(), accessibility: await browser.getAccessibilitySnapshot() };
        } finally {
          await browser.close();
        }
      }
    },
    {
      schema: {
        name: "click_element",
        description: "Open a URL and click or fill one visible element.",
        parameters: {
          url: { type: "string", required: true }, selector: { type: "string", required: true },
          action: { type: "string", required: true }, value: { type: "string" }
        }
      },
      async execute(args) {
        const browser = new BrowserSession();
        try {
          await browser.navigate(stringArg(args, "url"));
          const action = stringArg(args, "action");
          if (action !== "click" && action !== "fill") throw new Error("action must be click or fill");
          await browser.interact(stringArg(args, "selector"), action, args.value as string | undefined);
          return { consoleErrors: browser.getConsoleErrors(), accessibility: await browser.getAccessibilitySnapshot() };
        } finally {
          await browser.close();
        }
      }
    },
    {
      schema: {
        name: "read_symbol",
        description: "Read the AST context for a TypeScript symbol at a source location.",
        parameters: {
          filePath: { type: "string", required: true },
          line: { type: "number", required: true }
        }
      },
      async execute(args) {
        const context = extractSymbolAtLocation(resolveInside(stringArg(args, "filePath")), numberArg(args, "line"));
        return context ?? { found: false };
      }
    },
    {
      schema: {
        name: "search_code",
        description: "Search workspace source files for a regular expression.",
        parameters: { pattern: { type: "string", required: true } }
      },
      async execute(args) {
        const pattern = new RegExp(stringArg(args, "pattern"), "m");
        const matches: Array<{ file: string; line: number; text: string }> = [];
        for (const file of await walk(root)) {
          const absolute = path.join(root, file);
          const text = await fs.readFile(absolute, "utf8").catch(() => "");
          text.split(/\r?\n/).forEach((line, index) => {
            if (pattern.test(line)) matches.push({ file, line: index, text: line });
            pattern.lastIndex = 0;
          });
        }
        return matches;
      }
    },
    {
      schema: {
        name: "apply_patch",
        description: "Replace an inclusive zero-indexed line range after TypeScript syntax validation.",
        parameters: {
          filePath: { type: "string", required: true },
          startLine: { type: "number", required: true },
          endLine: { type: "number", required: true },
          replacementText: { type: "string", required: true }
        }
      },
      async execute(args) {
        return {
          applied: await patchFileRange(
            resolveInside(stringArg(args, "filePath")),
            numberArg(args, "startLine"),
            numberArg(args, "endLine"),
            stringArg(args, "replacementText")
          )
        };
      }
    },
    {
      schema: {
        name: "run_command",
        description: "Run a test or build command inside the bounded process sandbox.",
        parameters: { command: { type: "string", required: true } }
      },
      async execute(args) {
        return sandbox.run(tokenize(stringArg(args, "command")), { cwd: root });
      }
    },
    {
      schema: {
        name: "git_diff",
        description: "Inspect current staged and unstaged git changes.",
        parameters: {}
      },
      async execute() {
        const result = await sandbox.run(["git", "diff", "HEAD"], { cwd: root });
        return { exitCode: result.exitCode, diff: resultText(result) };
      }
    }
  ];
}
