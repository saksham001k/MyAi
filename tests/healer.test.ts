import { describe, expect, it } from "vitest";
import { mkdtemp, readFile, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { ProcessSandbox } from "../src/engine/sandbox.js";
import { SelfHealingEngine } from "../src/engine/healer.js";

describe("SelfHealingEngine", () => {
  it("repairs a failing fixture and reruns it", async () => {
    const directory = await mkdtemp(path.join(os.tmpdir(), "myai-healer-"));
    const file = path.join(directory, "fixture.ts");
    await writeFile(file, "function answer() {\n  return missing;\n}\nconsole.log(answer());\n");
    const engine = new SelfHealingEngine(new ProcessSandbox(), directory);
    const result = await engine.diagnoseAndRepair(
      `node -e "const fs=require('fs'); const p=process.argv[1]; const s=fs.readFileSync(p,'utf8'); if (s.includes('missing')) { console.error(p+':2:10: missing'); process.exit(1); }" fixture.ts`,
      async (_error, context) => context.source.replace("missing", "42")
    );
    expect(result.success).toBe(true);
    expect(result.attempts).toBe(2);
    expect(await readFile(file, "utf8")).toContain("return 42;");
  });
});
