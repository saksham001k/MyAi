import { promises as fs } from "node:fs";
import path from "node:path";
import ts from "typescript";

export async function patchFileRange(
  filePath: string,
  startLine: number,
  endLine: number,
  replacementText: string
): Promise<boolean> {
  if (!Number.isInteger(startLine) || !Number.isInteger(endLine) ||
      startLine < 0 || endLine < startLine) {
    throw new RangeError("startLine and endLine must be valid inclusive zero-indexed lines");
  }
  const original = await fs.readFile(filePath, "utf8");
  const newline = original.includes("\r\n") ? "\r\n" : "\n";
  const lines = original.split(/\r?\n/);
  if (startLine >= lines.length || endLine >= lines.length) return false;
  const replacement = replacementText.replace(/\r\n/g, "\n").split("\n");
  const updated = [
    ...lines.slice(0, startLine),
    ...replacement,
    ...lines.slice(endLine + 1)
  ].join(newline);
  const diagnostics = ts.transpileModule(updated, {
    fileName: filePath,
    compilerOptions: { target: ts.ScriptTarget.ES2022 },
    reportDiagnostics: true
  }).diagnostics ?? [];
  if (diagnostics.length > 0) return false;
  const temporary = `${filePath}.${process.pid}.${Date.now()}.tmp`;
  try {
    await fs.writeFile(temporary, updated, "utf8");
    await fs.rename(temporary, filePath);
    return true;
  } finally {
    await fs.rm(temporary, { force: true });
  }
}
