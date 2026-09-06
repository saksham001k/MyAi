import { describe, expect, it } from "vitest";
import { mkdtemp, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { extractSymbolAtLocation } from "../src/indexer/slicer.js";

describe("AST context slicer", () => {
  it("extracts the innermost method with zero-indexed bounds", async () => {
    const directory = await mkdtemp(path.join(os.tmpdir(), "myai-slicer-"));
    const file = path.join(directory, "sample.ts");
    await writeFile(file, [
      "class Calculator {",
      "  add(a: number, b: number) {",
      "    return a + b;",
      "  }",
      "}"
    ].join("\n"));
    const context = extractSymbolAtLocation(file, 2);
    expect(context?.name).toBe("add");
    expect(context?.kind).toBe("MethodDeclaration");
    expect(context?.startLine).toBe(1);
    expect(context?.endLine).toBe(3);
    expect(context?.source).toContain("return a + b;");
  });
});
