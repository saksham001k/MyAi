import { describe, expect, it, vi } from "vitest";
import { OpenAICompatibleProvider, repairPrompt } from "../src/providers/llm.js";
import { OllamaProvider, stripPatchFences } from "../src/providers/ollama.js";

const context = {
  filePath: "src/math.ts",
  name: "add",
  kind: "FunctionDeclaration",
  startLine: 0,
  endLine: 2,
  source: "function add() { return missing; }"
};

describe("LLM providers", () => {
  it("formats structural repair context and parses OpenAI responses", async () => {
    const fetchImpl = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(JSON.stringify({ choices: [{ message: { content: "function add() { return 42; }" } }] }), {
        status: 200,
        headers: { "content-type": "application/json" }
      })
    );
    const provider = new OpenAICompatibleProvider("test-key", "http://localhost:11434/v1", { fetchImpl });
    const result = await provider.generatePatch("Fix syntax.", context, "src/math.ts:1:20 missing");
    expect(result).toContain("return 42");
    const body = JSON.parse(fetchImpl.mock.calls[0][1]?.body as string) as {
      temperature: number;
      messages: Array<{ content: string }>;
    };
    expect(body.temperature).toBe(0.1);
    expect(body.messages[0].content).toContain("Enclosing symbol:");
    expect(repairPrompt("Fix", context, "trace")).toContain("ONLY the complete replacement block");
  });

  it("uses Ollama without credentials and strips markdown fences", async () => {
    const fetchImpl = vi.fn<typeof fetch>()
      .mockResolvedValueOnce(new Response(JSON.stringify({ models: [{ name: "qwen2.5-coder:1.5b" }] })))
      .mockResolvedValueOnce(new Response(JSON.stringify({
        response: "```typescript\nfunction add() { return 42; }\n```"
      })));
    const provider = new OllamaProvider({ fetchImpl });
    const result = await provider.generatePatch("Repair it.", context, "missing");
    expect(result).toBe("function add() { return 42; }");
    expect(fetchImpl.mock.calls[1][0]).toBe("http://localhost:11434/api/generate");
    const body = JSON.parse(fetchImpl.mock.calls[1][1]?.body as string) as {
      model: string;
      options: { temperature: number; num_predict: number };
    };
    expect(body.model).toBe("qwen2.5-coder:1.5b");
    expect(body.options).toEqual({ temperature: 0.1, num_predict: 512 });
    expect(stripPatchFences("Explanation\nfunction add() {}")).toBe("function add() {}");
  });
});
