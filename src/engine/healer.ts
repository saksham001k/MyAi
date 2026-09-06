import path from "node:path";
import type { ProcessResult, ProcessSandbox } from "./sandbox.js";
import { extractSymbolAtLocation, type SymbolContext } from "../indexer/slicer.js";
import { patchFileRange } from "../tools/filePatcher.js";
import type { LLMProvider } from "../providers/llm.js";

export interface TracebackLocation {
  filePath: string;
  line: number;
  column?: number;
}

export interface HealingResult {
  success: boolean;
  attempts: number;
  logs: string[];
}

export type PatchApproval = (
  context: SymbolContext,
  replacement: string
) => Promise<boolean>;

export function parseTraceback(error: string, cwd = process.cwd()): TracebackLocation | null {
  const pattern = /(?:^|[\s("'`])((?:[A-Za-z]:[\\/]|\/|\.{0,2}[\\/])?[^()\s"'`]+?\.(?:ts|tsx|js|jsx)):(\d+)(?::(\d+))?/m;
  const match = pattern.exec(error);
  if (!match) return null;
  return {
    filePath: path.resolve(cwd, match[1]),
    line: Number(match[2]) - 1,
    column: match[3] ? Number(match[3]) - 1 : undefined
  };
}

function outputOf(result: ProcessResult): string {
  return [result.stderr, result.stdout].filter(Boolean).join("\n");
}

function tokenize(command: string): string[] {
  const tokens: string[] = [];
  let token = "";
  let quote: "'" | '"' | null = null;
  for (const character of command.trim()) {
    if (quote) {
      if (character === quote) quote = null;
      else token += character;
    } else if (character === "'" || character === '"') {
      quote = character;
    } else if (/\s/.test(character)) {
      if (token) {
        tokens.push(token);
        token = "";
      }
    } else {
      token += character;
    }
  }
  if (quote) throw new SyntaxError("testCommand contains an unterminated quote");
  if (token) tokens.push(token);
  if (tokens.length === 0) throw new RangeError("testCommand cannot be empty");
  return tokens;
}

export class SelfHealingEngine {
  public constructor(
    private readonly sandbox: ProcessSandbox,
    private readonly cwd = process.cwd(),
    private readonly provider?: LLMProvider,
    private readonly approvePatch?: PatchApproval
  ) {}

  public async diagnoseAndRepair(
    testCommand: string,
    patchGenerator?: ((error: string, context: SymbolContext) => Promise<string>) | undefined,
    maxAttempts = 3
  ): Promise<HealingResult> {
    if (!Number.isInteger(maxAttempts) || maxAttempts < 1) {
      throw new RangeError("maxAttempts must be at least one");
    }
    const logs: string[] = [];
    for (let attempt = 1; attempt <= maxAttempts; attempt += 1) {
      const result = await this.sandbox.run(tokenize(testCommand), { cwd: this.cwd });
      const output = outputOf(result);
      logs.push(output);
      if (result.exitCode === 0) return { success: true, attempts: attempt, logs };
      if (attempt === maxAttempts) break;
      const location = parseTraceback(output, this.cwd);
      if (!location) break;
      const context = extractSymbolAtLocation(location.filePath, location.line);
      if (!context) break;
      const replacement = this.provider
        ? await this.provider.generatePatch(
            "Repair the failing TypeScript symbol with the smallest correct change.",
            context,
            output
          )
        : patchGenerator
          ? await patchGenerator(output, context)
          : (() => { throw new Error("A patch generator or LLM provider is required."); })();
      if (this.approvePatch && !(await this.approvePatch(context, replacement))) break;
      if (!(await patchFileRange(
        context.filePath,
        context.startLine,
        context.endLine,
        replacement
      ))) break;
    }
    return { success: false, attempts: Math.min(maxAttempts, logs.length), logs };
  }
}
