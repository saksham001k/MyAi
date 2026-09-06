import { describe, expect, it } from "vitest";
import { mkdtemp, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { generateRepoMap } from "../src/indexer/repoMap.js";

describe("repository map", () => {
  it("keeps exported signatures and omits implementation bodies", async () => {
    const root = await mkdtemp(path.join(os.tmpdir(), "myai-map-"));
    await writeFile(path.join(root, "api.ts"), [
      "export function greet(name: string): string {",
      "  return `hello ${name}`;",
      "}",
      "function privateHelper() { return true; }",
      "export interface User { id: string; }"
    ].join("\n"));
    const map = await generateRepoMap(800, { root });
    expect(map).toContain("function greet(name: string): string");
    expect(map).toContain("interface User");
    expect(map).not.toContain("privateHelper");
    expect(map).not.toContain("return `hello");
  });
});
