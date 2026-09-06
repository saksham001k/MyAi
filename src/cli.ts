#!/usr/bin/env node
import { Command } from "commander";
import chalk from "chalk";
import { existsSync, readFileSync } from "node:fs";
import { execFileSync } from "node:child_process";
import path from "node:path";
import readline from "node:readline/promises";
import { stdin as input, stdout as output } from "node:process";
import { ProcessSandbox } from "./engine/sandbox.js";
import { SelfHealingEngine } from "./engine/healer.js";
import { extractSymbolAtLocation } from "./indexer/slicer.js";
import { OllamaProvider } from "./providers/ollama.js";
import { checkOllama } from "./providers/health.js";

async function approve(filePath: string): Promise<boolean> {
  const staged = execFileSync("git", ["diff", "--cached", "--name-only", "--", filePath], { encoding: "utf8" }).trim();
  if (staged) return true;
  const prompt = readline.createInterface({ input, output });
  const answer = await prompt.question(`${chalk.yellow("Approve modification")} ${filePath}? [y/N] `);
  prompt.close();
  return /^y(es)?$/i.test(answer.trim());
}

function showDiff(filePath: string, before: string, after: string): void {
  const oldLines = before.split(/\r?\n/);
  const newLines = after.split(/\r?\n/);
  console.log(chalk.cyan(`\nProposed patch: ${filePath}`));
  for (let index = 0; index < Math.max(oldLines.length, newLines.length); index += 1) {
    if (oldLines[index] === newLines[index]) console.log(`  ${oldLines[index] ?? ""}`);
    else {
      if (oldLines[index] !== undefined) console.log(chalk.red(`- ${oldLines[index]}`));
      if (newLines[index] !== undefined) console.log(chalk.green(`+ ${newLines[index]}`));
    }
  }
}

const program = new Command()
  .name("myai")
  .description("Autonomous local developer repair engine");

program
  .command("inspect")
  .argument("<filePath>")
  .argument("<line>", "zero- or one-indexed source line", Number)
  .action((filePath: string, line: number) => {
    const resolved = path.resolve(filePath);
    if (!existsSync(resolved)) throw new Error(`File not found: ${resolved}`);
    const context = extractSymbolAtLocation(resolved, Math.max(0, line - 1));
    if (!context) throw new Error("No enclosing TypeScript symbol found.");
    console.log(`${chalk.cyan(context.name)} (${context.kind}) lines ${context.startLine + 1}-${context.endLine + 1}`);
    console.log(context.source);
  });

program
  .command("fix")
  .argument("<testCommand>")
  .option("--max-attempts <number>", "maximum repair attempts", "3")
  .action(async (testCommand: string, options: { maxAttempts: string }) => {
    const provider = new OllamaProvider();
    const engine = new SelfHealingEngine(
      new ProcessSandbox(),
      process.cwd(),
      provider,
      async (context, replacement) => {
        const before = readFileSync(context.filePath, "utf8");
        showDiff(context.filePath, before, replacement);
        return approve(context.filePath);
      }
    );
    const result = await engine.diagnoseAndRepair(testCommand, undefined, Number(options.maxAttempts));
    result.logs.forEach((log, index) => console.log(chalk.gray(`Attempt ${index + 1}:\n${log}`)));
    console.log(result.success ? chalk.green("Repair succeeded.") : chalk.red("Repair failed."));
  });

program
  .command("check")
  .description("Check the local Ollama service and list installed models")
  .action(async () => {
    const health = await checkOllama();
    if (!health.available) {
      console.log(chalk.yellow(health.notice));
      return;
    }
    console.log(chalk.green("Ollama detected at http://localhost:11434"));
    if (health.models.length === 0) {
      console.log(chalk.yellow("No local models installed."));
      return;
    }
    health.models.forEach((model) => console.log(`- ${model}`));
  });

await program.parseAsync();
