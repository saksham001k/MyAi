import { describe, expect, it } from "vitest";
import { ProcessSandbox } from "../src/engine/sandbox.js";

describe("ProcessSandbox", () => {
  it("captures stdout and exit codes", async () => {
    const result = await new ProcessSandbox().run(["node", "-e", "process.stdout.write('ready')"]);
    expect(result.exitCode).toBe(0);
    expect(result.stdout).toBe("ready");
    expect(result.timedOut).toBe(false);
  });

  it("captures stderr and parses TypeScript locations", async () => {
    const result = await new ProcessSandbox().run([
      "node",
      "-e",
      "process.stderr.write('src/main.ts:12:7: failure'); process.exit(2)"
    ]);
    expect(result.exitCode).toBe(2);
    expect(result.stderr).toContain("failure");
    expect(result.failure).toEqual({ file: "src/main.ts", line: 12, column: 7 });
  });

  it("terminates commands that exceed the timeout", async () => {
    const result = await new ProcessSandbox(50).run(
      ["node", "-e", "setTimeout(() => {}, 1000)"],
      { timeoutMs: 50 }
    );
    expect(result.timedOut).toBe(true);
    expect(result.exitCode).not.toBe(0);
  });
});
