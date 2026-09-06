import { describe, expect, it } from "vitest";
import { mkdtemp } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { MyAiDatabase } from "../src/storage/db.js";

describe("persistent project storage", () => {
  it("creates the schema and stores rules and task history", async () => {
    const root = await mkdtemp(path.join(os.tmpdir(), "myai-storage-"));
    const database = new MyAiDatabase(root);
    const rule = database.addRule("Always use vitest instead of jest");
    database.addRule("Never modify package-lock.json");
    const task = database.recordTask({
      goal: "Add tests for storage",
      status: "succeeded",
      diffSummary: "Added storage tests",
      iterations: 2
    });

    expect(database.listRules().map((item) => item.rule)).toEqual([
      "Always use vitest instead of jest",
      "Never modify package-lock.json"
    ]);
    expect(rule.id).toBe(1);
    expect(database.listHistory(1)[0]).toMatchObject({
      id: task.id,
      goal: "Add tests for storage",
      status: "succeeded",
      iterations: 2
    });
    expect(database.recentRelatedDiffs("storage tests")).toHaveLength(1);
    database.close();
  });
});
