import net from "node:net";
import path from "node:path";
import { BrowserSession } from "../tools/browser.js";
import { ProcessSandbox } from "./sandbox.js";
import { extractSymbolAtLocation } from "../indexer/slicer.js";
import { patchFileRange } from "../tools/filePatcher.js";
import type { LLMProvider } from "../providers/llm.js";

export interface BrowserHealingResult {
  success: boolean;
  attempts: number;
  consoleErrors: string[];
  accessibility: unknown;
  server?: { command: string; exitCode: number | null; stderr: string };
}

export interface BrowserHealerOptions {
  root?: string;
  port?: number;
  maxAttempts?: number;
  waitMs?: number;
  sandbox?: ProcessSandbox;
  browser?: BrowserSession;
}

function waitForPort(port: number, host: string, timeoutMs: number): Promise<void> {
  const deadline = Date.now() + timeoutMs;
  return new Promise((resolve, reject) => {
    const attempt = (): void => {
      const socket = net.createConnection({ host, port });
      socket.once("connect", () => { socket.destroy(); resolve(); });
      socket.once("error", () => {
        socket.destroy();
        if (Date.now() >= deadline) reject(new Error(`Server did not listen on ${host}:${port}.`));
        else setTimeout(attempt, 100);
      });
    };
    attempt();
  });
}

export class FrontendHealer {
  private readonly root: string;
  private readonly port: number;
  private readonly maxAttempts: number;
  private readonly sandbox: ProcessSandbox;

  public constructor(private readonly provider: LLMProvider, options: BrowserHealerOptions = {}) {
    this.root = path.resolve(options.root ?? process.cwd());
    this.port = options.port ?? 3000;
    this.maxAttempts = Math.max(1, Math.min(options.maxAttempts ?? 3, 5));
    this.sandbox = options.sandbox ?? new ProcessSandbox(30_000);
  }

  public async run(command: string | readonly string[], testGoal: string, options: BrowserHealerOptions = {}): Promise<BrowserHealingResult> {
    const process = this.sandbox.start(
      typeof command === "string" ? command.trim().split(/\s+/) : command,
      { cwd: this.root, timeoutMs: 120_000 }
    );
    const browser = options.browser ?? new BrowserSession();
    let errors: string[] = [];
    let accessibility: unknown = null;
    try {
      await waitForPort(this.port, "127.0.0.1", options.waitMs ?? 15_000);
      for (let attempt = 1; attempt <= this.maxAttempts; attempt += 1) {
        browser.clearConsoleErrors();
        await browser.navigate(`http://127.0.0.1:${this.port}`);
        errors = browser.getConsoleErrors();
        accessibility = await browser.getAccessibilitySnapshot();
        if (!errors.length) return { success: true, attempts: attempt, consoleErrors: errors, accessibility };
        const location = this.extractLocation(errors.join("\n"));
        if (!location) break;
        const filePath = path.resolve(this.root, location.file);
        if (!filePath.startsWith(`${this.root}${path.sep}`)) break;
        const context = extractSymbolAtLocation(filePath, location.line);
        if (!context) break;
        const prompt = `Goal: ${testGoal}\nBrowser errors:\n${errors.join("\n")}\nReplace only this component:\n${context.source}`;
        const replacement = await this.provider.generatePatch(prompt, context, errors.join("\n"));
        patchFileRange(filePath, context.startLine, context.endLine, replacement);
      }
      return { success: false, attempts: this.maxAttempts, consoleErrors: errors, accessibility };
    } finally {
      if (!options.browser) await browser.close();
      process.stop();
    }
  }

  private extractLocation(text: string): { file: string; line: number } | undefined {
    const match = /(?:^|[\s("'`])((?:[A-Za-z]:[\\/]|\/|\.{0,2}[\\/])?[^()\s"'`]+?\.(?:ts|tsx|js|jsx)):(\d+)/m.exec(text);
    return match ? { file: match[1], line: Number(match[2]) } : undefined;
  }
}
