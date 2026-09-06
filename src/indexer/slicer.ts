import ts from "typescript";
import { readFileSync } from "node:fs";

export interface SymbolContext {
  filePath: string;
  name: string;
  kind: string;
  startLine: number;
  endLine: number;
  source: string;
}

const symbolKinds = new Set<ts.SyntaxKind>([
  ts.SyntaxKind.FunctionDeclaration,
  ts.SyntaxKind.MethodDeclaration,
  ts.SyntaxKind.ClassDeclaration,
  ts.SyntaxKind.Constructor,
  ts.SyntaxKind.GetAccessor,
  ts.SyntaxKind.SetAccessor
]);

function symbolName(node: ts.Node): string {
  if (ts.isConstructorDeclaration(node)) return "constructor";
  if (ts.isGetAccessorDeclaration(node) || ts.isSetAccessorDeclaration(node)) {
    return node.name.getText();
  }
  if (
    ts.isFunctionDeclaration(node) ||
    ts.isMethodDeclaration(node) ||
    ts.isClassDeclaration(node)
  ) {
    return node.name?.getText() ?? "<anonymous>";
  }
  return ts.SyntaxKind[node.kind];
}

export function extractSymbolAtLocation(
  filePath: string,
  line: number
): SymbolContext | null {
  if (!Number.isInteger(line) || line < 0) {
    throw new RangeError("line must be a non-negative zero-indexed integer");
  }
  const sourceText = readFileSync(filePath, "utf8");
  const sourceFile = ts.createSourceFile(
    filePath,
    sourceText,
    ts.ScriptTarget.Latest,
    true,
    ts.ScriptKind.TS
  );
  const offset = sourceFile.getPositionOfLineAndCharacter(
    Math.min(line, sourceFile.getLineStarts().length - 1),
    0
  );
  let best: ts.Node | undefined;
  const visit = (node: ts.Node): void => {
    if (node.getStart(sourceFile) <= offset && offset <= node.getEnd()) {
      if (symbolKinds.has(node.kind)) best = node;
      ts.forEachChild(node, visit);
    }
  };
  visit(sourceFile);
  if (!best) return null;
  const startLine = sourceFile.getLineAndCharacterOfPosition(best.getStart(sourceFile)).line;
  const endLine = sourceFile.getLineAndCharacterOfPosition(best.getEnd()).line;
  return {
    filePath,
    name: symbolName(best),
    kind: ts.SyntaxKind[best.kind],
    startLine,
    endLine,
    source: best.getText(sourceFile)
  };
}
