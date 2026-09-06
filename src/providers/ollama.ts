import type { SymbolContext } from "../indexer/slicer.js";
import type { LLMProvider } from "./llm.js";

export const OLLAMA_URL = "http://localhost:11434";
export const DEFAULT_MODEL = "qwen2.5-coder:1.5b";

function promptFor(prompt: string, context: SymbolContext, errorTrace: string): string {
  return [
    prompt,
    "",
    "Replace only this TypeScript symbol:",
    `Name: ${context.name}`,
    `Kind: ${context.kind}`,
    `Lines: ${context.startLine}-${context.endLine}`,
    context.source,
    "",
    "Failure output:",
    errorTrace,
    "",
    "Return only the complete replacement TypeScript block. Do not include markdown fences, explanations, or conversational text."
  ].join("\n");
}

export function stripPatchFences(value: string): string {
  const fenced = value.match(/```(?:typescript|ts|javascript|js)?\s*([\s\S]*?)```/i);
  if (fenced) return fenced[1].trim();
  const lines = value.trim().split(/\r?\n/);
  const start = lines.findIndex((line) => /^(?:export\s+)?(?:async\s+)?(?:function|class|interface|type)\b/.test(line.trim()));
  return start > 0 ? lines.slice(start).join("\n").trim() : value.trim();
}

export interface OllamaOptions {
  host?: string;
  model?: string;
  fetchImpl?: typeof fetch;
}

export class OllamaProvider implements LLMProvider {
  private readonly host: string;
  private readonly fetchImpl: typeof fetch;
  private model: string;

  public constructor(options: OllamaOptions = {}) {
    this.host = (options.host ?? OLLAMA_URL).replace(/\/$/, "");
    this.fetchImpl = options.fetchImpl ?? fetch;
    this.model = options.model ?? DEFAULT_MODEL;
  }

  public async generatePatch(
    prompt: string,
    context: SymbolContext,
    errorTrace: string
  ): Promise<string> {
    if (!(await this.hasModel(this.model))) {
      const models = await this.listModels();
      if (models.length === 0) {
        throw new Error(`No Ollama models installed. Run 'ollama run ${DEFAULT_MODEL}' to start your free local brain.`);
      }
      this.model = models[0];
    }
    const response = await this.fetchImpl(`${this.host}/api/generate`, {
      method: "POST",
      body: JSON.stringify({
        model: this.model,
        prompt: promptFor(prompt, context, errorTrace),
        stream: false,
        options: { temperature: 0.1, num_predict: 512 }
      })
    });
    if (!response.ok) throw new Error(`Ollama returned HTTP ${response.status}.`);
    const payload = await response.json() as { response?: unknown };
    if (typeof payload.response !== "string" || !payload.response.trim()) {
      throw new Error("Ollama returned no patch text.");
    }
    return stripPatchFences(payload.response);
  }

  public async isAvailable(): Promise<boolean> {
    try {
      const response = await this.fetchImpl(`${this.host}/api/tags`);
      return response.ok;
    } catch {
      return false;
    }
  }

  public async listModels(): Promise<string[]> {
    const response = await this.fetchImpl(`${this.host}/api/tags`);
    if (!response.ok) throw new Error(`Ollama returned HTTP ${response.status}.`);
    const payload = await response.json() as { models?: Array<{ name?: string }> };
    return (payload.models ?? [])
      .map((model) => model.name)
      .filter((name): name is string => Boolean(name));
  }

  private async hasModel(model: string): Promise<boolean> {
    try {
      return (await this.listModels()).includes(model);
    } catch {
      throw new Error("Ollama not detected. Run 'ollama run qwen2.5-coder:1.5b' to start your free local brain.");
    }
  }
}
