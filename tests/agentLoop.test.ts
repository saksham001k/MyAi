import { describe, expect, it } from "vitest";
import { AgentLoop } from "../src/agent/loop.js";
import type { AgentTool } from "../src/agent/tools.js";

describe("AgentLoop", () => {
  it("executes actions, feeds observations back, and finishes", async () => {
    const seen: string[] = [];
    const tool: AgentTool = {
      schema: { name: "check", description: "check", parameters: {} },
      async execute() { seen.push("called"); return { exitCode: 0 }; }
    };
    let calls = 0;
    const result = await new AgentLoop({
      async generate(prompt) {
        calls += 1;
        return calls === 1
          ? '{"thought":"verify","action":{"tool":"check","args":{}}}'
          : '{"final":"Goal verified"}';
      }
    }, [tool]).run("verify the project");
    expect(result.success).toBe(true);
    expect(result.steps).toBe(2);
    expect(seen).toEqual(["called"]);
    expect(result.events.some((event) => event.type === "observation")).toBe(true);
  });
});
