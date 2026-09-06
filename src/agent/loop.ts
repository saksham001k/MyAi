import type { AgentTool } from "./tools.js";

export interface AgentModel {
  generate(prompt: string): Promise<string>;
}

export interface AgentEvent {
  type: "thought" | "action" | "observation" | "final";
  step: number;
  content: string;
  tool?: string;
  args?: Record<string, unknown>;
}

export interface AgentLoopOptions {
  maxSteps?: number;
  maxToolCalls?: number;
  onEvent?: (event: AgentEvent) => void;
}

export interface AgentResult {
  success: boolean;
  steps: number;
  answer: string;
  events: AgentEvent[];
}

function parseResponse(response: string): {
  thought?: string;
  action?: { tool: string; args: Record<string, unknown> };
  final?: string;
} {
  const match = response.match(/\{[\s\S]*\}/);
  if (match) {
    const parsed = JSON.parse(match[0]) as Record<string, unknown>;
    const action = parsed.action as Record<string, unknown> | undefined;
    if (action && typeof action.tool === "string") {
      return { thought: typeof parsed.thought === "string" ? parsed.thought : "", action: {
        tool: action.tool,
        args: (action.args ?? {}) as Record<string, unknown>
      } };
    }
    if (typeof parsed.final === "string") return { final: parsed.final };
  }
  const final = response.match(/Final Answer:\s*([\s\S]*)/i);
  if (final) return { final: final[1].trim() };
  throw new Error("Model response must contain a JSON action or Final Answer.");
}

export class AgentLoop {
  private readonly maxSteps: number;
  private readonly maxToolCalls: number;

  public constructor(
    private readonly model: AgentModel,
    private readonly tools: AgentTool[],
    options: AgentLoopOptions = {}
  ) {
    this.maxSteps = Math.max(1, Math.min(options.maxSteps ?? 10, 50));
    this.maxToolCalls = Math.max(1, Math.min(options.maxToolCalls ?? this.maxSteps, 100));
    this.onEvent = options.onEvent;
  }

  private readonly onEvent?: (event: AgentEvent) => void;

  public async run(goal: string): Promise<AgentResult> {
    const events: AgentEvent[] = [];
    const emit = (event: AgentEvent): void => {
      events.push(event);
      this.onEvent?.(event);
    };
    const schemas = this.tools.map((tool) => tool.schema);
    let prompt = `You are a local autonomous developer. Goal: ${goal}\nTools: ${JSON.stringify(schemas)}\nRespond with {"thought":"...","action":{"tool":"name","args":{...}}} or {"final":"..."}.`;
    let calls = 0;
    for (let step = 1; step <= this.maxSteps; step += 1) {
      let parsed: ReturnType<typeof parseResponse>;
      try {
        parsed = parseResponse(await this.model.generate(prompt));
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        emit({ type: "observation", step, content: message });
        return { success: false, steps: step, answer: message, events };
      }
      if (parsed.final) {
        emit({ type: "final", step, content: parsed.final });
        return { success: true, steps: step, answer: parsed.final, events };
      }
      emit({ type: "thought", step, content: parsed.thought ?? "" });
      emit({ type: "action", step, content: parsed.action!.tool, tool: parsed.action!.tool, args: parsed.action!.args });
      if (++calls > this.maxToolCalls) {
        const message = "Tool-call budget exhausted.";
        emit({ type: "final", step, content: message });
        return { success: false, steps: step, answer: message, events };
      }
      const tool = this.tools.find((candidate) => candidate.schema.name === parsed.action!.tool);
      if (!tool) {
        const message = `Unknown tool: ${parsed.action!.tool}`;
        emit({ type: "observation", step, content: message });
        prompt += `\nObservation: ${message}`;
        continue;
      }
      try {
        const observation = await tool.execute(parsed.action!.args);
        const content = JSON.stringify(observation);
        emit({ type: "observation", step, content });
        prompt += `\nThought: ${parsed.thought}\nAction: ${JSON.stringify(parsed.action)}\nObservation: ${content}`;
      } catch (error) {
        const content = error instanceof Error ? error.message : String(error);
        emit({ type: "observation", step, content });
        prompt += `\nObservation (tool error): ${content}`;
      }
    }
    const answer = "Maximum agent steps reached before the goal was verified.";
    emit({ type: "final", step: this.maxSteps, content: answer });
    return { success: false, steps: this.maxSteps, answer, events };
  }
}
