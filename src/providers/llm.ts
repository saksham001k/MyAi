import type { SymbolContext } from "../indexer/slicer.js";

export interface LLMProvider {
  generatePatch(
    prompt: string,
    context: SymbolContext,
    errorTrace: string
  ): Promise<string>;
}

export interface ProviderOptions {
  model?: string;
  temperature?: number;
  fetchImpl?: typeof fetch;
}

function repairPrompt(prompt: string, context: SymbolContext, errorTrace: string): string {
  return [
    prompt,
    "",
    "Enclosing symbol:",
    `Name: ${context.name}`,
    `Kind: ${context.kind}`,
    `Lines: ${context.startLine}-${context.endLine}`,
    context.source,
    "",
    "Compiler or test traceback:",
    errorTrace,
    "",
    "Return ONLY the complete replacement block for this symbol. Do not use markdown fences or explanations."
  ].join("\n");
}

function extractText(value: unknown): string {
  if (typeof value === "string") return value.trim();
  if (!value || typeof value !== "object") throw new Error("LLM response did not contain text.");
  const record = value as Record<string, unknown>;
  const choices = record.choices;
  if (Array.isArray(choices) && choices.length > 0) {
    const message = choices[0] as Record<string, unknown>;
    const content = (message.message as Record<string, unknown> | undefined)?.content;
    if (typeof content === "string") return content.trim();
  }
  const content = record.content;
  if (Array.isArray(content)) {
    const text = content
      .map((item) => (item && typeof item === "object" ? (item as Record<string, unknown>).text : ""))
      .filter((item): item is string => typeof item === "string")
      .join("");
    if (text.trim()) return text.trim();
  }
  throw new Error("LLM response did not contain text.");
}

export class OpenAICompatibleProvider implements LLMProvider {
  private readonly fetchImpl: typeof fetch;
  private readonly model: string;
  private readonly temperature: number;

  public constructor(
    private readonly apiKey: string,
    private readonly baseUrl = "https://api.openai.com/v1",
    options: ProviderOptions = {}
  ) {
    this.fetchImpl = options.fetchImpl ?? fetch;
    this.model = options.model ?? "gpt-4o";
    this.temperature = options.temperature ?? 0.1;
  }

  public async generatePatch(
    prompt: string,
    context: SymbolContext,
    errorTrace: string
  ): Promise<string> {
    const response = await this.fetchImpl(`${this.baseUrl.replace(/\/$/, "")}/chat/completions`, {
      method: "POST",
      headers: { "content-type": "application/json", authorization: `Bearer ${this.apiKey}` },
      body: JSON.stringify({
        model: this.model,
        temperature: this.temperature,
        messages: [{ role: "user", content: repairPrompt(prompt, context, errorTrace) }]
      })
    });
    if (!response.ok) throw new Error(`OpenAI-compatible provider returned HTTP ${response.status}.`);
    return extractText(await response.json());
  }
}

export class AnthropicProvider implements LLMProvider {
  private readonly fetchImpl: typeof fetch;
  private readonly model: string;
  private readonly temperature: number;

  public constructor(
    private readonly apiKey: string,
    options: ProviderOptions = {}
  ) {
    this.fetchImpl = options.fetchImpl ?? fetch;
    this.model = options.model ?? "claude-3-5-sonnet-latest";
    this.temperature = options.temperature ?? 0.1;
  }

  public async generatePatch(
    prompt: string,
    context: SymbolContext,
    errorTrace: string
  ): Promise<string> {
    const response = await this.fetchImpl("https://api.anthropic.com/v1/messages", {
      method: "POST",
      headers: {
        "content-type": "application/json",
        "x-api-key": this.apiKey,
        "anthropic-version": "2023-06-01"
      },
      body: JSON.stringify({
        model: this.model,
        max_tokens: 4096,
        temperature: this.temperature,
        messages: [{ role: "user", content: repairPrompt(prompt, context, errorTrace) }]
      })
    });
    if (!response.ok) throw new Error(`Anthropic provider returned HTTP ${response.status}.`);
    return extractText(await response.json());
  }
}

export function createProviderFromEnvironment(
  options: ProviderOptions = {}
): LLMProvider {
  if (process.env.ANTHROPIC_API_KEY) {
    return new AnthropicProvider(process.env.ANTHROPIC_API_KEY, options);
  }
  const apiKey = process.env.OPENAI_API_KEY ?? "ollama";
  const baseUrl = process.env.OLLAMA_HOST
    ? `${process.env.OLLAMA_HOST.replace(/\/$/, "")}/v1`
    : "https://api.openai.com/v1";
  return new OpenAICompatibleProvider(apiKey, baseUrl, {
    ...options,
    model: options.model ?? (process.env.OLLAMA_HOST ? "qwen2.5-coder" : "gpt-4o")
  });
}

export { repairPrompt };
