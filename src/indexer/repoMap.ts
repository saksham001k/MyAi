import { promises as fs } from "node:fs";
import path from "node:path";
import ts from "typescript";

export interface RepoMapOptions {
  root?: string;
}

const ignored = new Set(["node_modules", "dist", ".git"]);

async function files(root: string, directory = root): Promise<string[]> {
  const entries = await fs.readdir(directory, { withFileTypes: true });
  const result: string[] = [];
  for (const entry of entries) {
    if (entry.name.startsWith(".") || ignored.has(entry.name)) continue;
    const absolute = path.join(directory, entry.name);
    if (entry.isDirectory()) result.push(...await files(root, absolute));
    else if (/\.(ts|tsx)$/.test(entry.name)) result.push(absolute);
  }
  return result;
}

function typeText(node: ts.Node | undefined, source: ts.SourceFile): string {
  return node ? node.getText(source) : "";
}

function signature(node: ts.Node, source: ts.SourceFile): string | null {
  if (ts.isFunctionDeclaration(node) && node.modifiers?.some((m) => m.kind === ts.SyntaxKind.ExportKeyword)) {
    const name = node.name?.text ?? "default";
    const parameters = node.parameters.map((p) => `${p.name.getText(source)}${p.type ? `: ${p.type.getText(source)}` : ""}`).join(", ");
    return `function ${name}(${parameters})${node.type ? `: ${node.type.getText(source)}` : ""}`;
  }
  if (ts.isClassDeclaration(node) && node.modifiers?.some((m) => m.kind === ts.SyntaxKind.ExportKeyword)) {
    const members = node.members.map((member) => {
      if (ts.isMethodDeclaration(member)) {
        const params = member.parameters.map((p) => `${p.name.getText(source)}${p.type ? `: ${p.type.getText(source)}` : ""}`).join(", ");
        return `  ${member.name.getText(source)}(${params})${member.type ? `: ${member.type.getText(source)}` : ""}`;
      }
      if (ts.isPropertyDeclaration(member)) return `  ${member.name.getText(source)}${member.type ? `: ${member.type.getText(source)}` : ""}`;
      return null;
    }).filter((item): item is string => item !== null);
    return [`class ${node.name?.text ?? "default"} {`, ...members, "}"].join("\n");
  }
  if (ts.isInterfaceDeclaration(node) && node.modifiers?.some((m) => m.kind === ts.SyntaxKind.ExportKeyword)) {
    return `interface ${node.name.text} {\n${node.members.map((m) => `  ${m.getText(source).replace(/[{].*$/s, "").trim()}`).join("\n")}\n}`;
  }
  if (ts.isTypeAliasDeclaration(node) && node.modifiers?.some((m) => m.kind === ts.SyntaxKind.ExportKeyword)) {
    return `type ${node.name.text} = ${node.type.getText(source)}`;
  }
  if (ts.isEnumDeclaration(node) && node.modifiers?.some((m) => m.kind === ts.SyntaxKind.ExportKeyword)) {
    return `enum ${node.name.text} { ${node.members.map((m) => m.name.getText(source)).join(", ")} }`;
  }
  return null;
}

export async function generateRepoMap(maxTokens = 800, options: RepoMapOptions = {}): Promise<string> {
  if (!Number.isInteger(maxTokens) || maxTokens < 1) throw new RangeError("maxTokens must be positive");
  const root = path.resolve(options.root ?? process.cwd());
  const lines: string[] = ["# Repository API Map"];
  for (const file of (await files(root)).sort()) {
    const source = await fs.readFile(file, "utf8");
    const sourceFile = ts.createSourceFile(file, source, ts.ScriptTarget.Latest, true, ts.ScriptKind.TS);
    const signatures = sourceFile.statements.map((node) => signature(node, sourceFile)).filter((item): item is string => item !== null);
    if (signatures.length) lines.push(`\n## ${path.relative(root, file)}`, ...signatures);
  }
  const compact = lines.join("\n");
  const budget = maxTokens * 4;
  return compact.length <= budget ? compact : `${compact.slice(0, budget - 1)}…`;
}
