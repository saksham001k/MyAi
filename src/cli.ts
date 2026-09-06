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
import { AgentLoop } from "./agent/loop.js";
import { createAgentTools } from "./agent/tools.js";
import { IsolatedWorktree } from "./guardrails/worktree.js";
import { reviewWorktree, terminalReviewIO } from "./cli/reviewer.js";
import { startMcpServer } from "./mcp/server.js";
import { MyAiDatabase } from "./storage/db.js";
import { ProjectMemory } from "./agent/memory.js";
import { searchWeb, fetchDocumentation } from "./tools/webSearch.js";
import { BrowserSession } from "./tools/browser.js";
import { FrontendHealer } from "./engine/browserHealer.js";

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
  .command("build")
  .argument("<goal>")
  .option("--max-steps <number>", "maximum agent steps", "10")
  .action(async (goal: string, options: { maxSteps: string }) => {
    const database = new MyAiDatabase();
    const memory = new ProjectMemory(database);
    const provider = new OllamaProvider();
    const model = {
      generate: async (prompt: string) => provider.generatePatch(prompt, {
        filePath: "agent.ts", name: "task", kind: "SourceFile",
        startLine: 0, endLine: 0, source: ""
      }, "")
    };
    const worktree = new IsolatedWorktree(process.cwd(), `task-${Date.now()}`);
    let created = false;
    const io = terminalReviewIO();
    try {
      const workspace = await worktree.create();
      created = true;
      let currentGoal = goal;
      for (;;) {
        const loop = new AgentLoop(model, createAgentTools(workspace), {
          maxSteps: Number(options.maxSteps),
          memory,
          onEvent: (event) => console.log(chalk.cyan(`[${event.type}] ${event.content}`))
        });
        const result = await loop.run(currentGoal);
        if (!result.success) {
          console.log(chalk.red(result.answer));
          await worktree.discard();
          created = false;
          break;
        }
        const decision = await reviewWorktree(worktree, io, {
          accept: async () => worktree.acceptAndMerge(),
          discard: async () => worktree.discard(),
          retry: async (feedback) => { currentGoal = `${goal}\nReviewer feedback: ${feedback}`; }
        });
        const diffSummary = (await worktree.diff()).split("\n").slice(0, 40).join("\n");
        database.recordTask({
          goal: currentGoal,
          status: decision === "accepted" ? "accepted" : decision === "discarded" ? "discarded" : "retry",
          diffSummary,
          iterations: result.steps
        });
        if (decision === "accepted" || decision === "discarded") {
          created = false;
          break;
        }
      }
    } finally {
      if (created) await worktree.discard();
      database.close();
    }
  });

const rule = program.command("rule").description("Manage persistent project rules");
rule.command("add")
  .argument("<rule>")
  .description("Add a developer rule")
  .action((value: string) => {
    const database = new MyAiDatabase();
    try {
      const item = database.addRule(value);
      console.log(chalk.green(`Added rule #${item.id}: ${item.rule}`));
    } finally {
      database.close();
    }
  });
rule.command("list")
  .description("List active developer rules")
  .action(() => {
    const database = new MyAiDatabase();
    try {
      const rules = database.listRules();
      if (!rules.length) console.log("No project rules configured.");
      rules.forEach((item) => console.log(`${item.id}. ${item.rule}`));
    } finally {
      database.close();
    }
  });

program
  .command("history")
  .description("Display previous agent runs")
  .action(() => {
    const database = new MyAiDatabase();
    try {
      const history = database.listHistory();
      if (!history.length) console.log("No agent history recorded.");
      history.forEach((item) => {
        console.log(`${item.timestamp} [${item.status}] ${item.goal} (${item.iterations} iterations)`);
        if (item.diffSummary) console.log(chalk.gray(item.diffSummary));
      });
    } finally {
      database.close();
    }
  });

program
  .command("serve")
  .description("Run the MyAi tool suite as an MCP stdio server")
  .action(async () => startMcpServer(process.cwd()));

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
    const database = new MyAiDatabase();
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
    database.recordTask({
      goal: `fix ${testCommand}`,
      status: result.success ? "succeeded" : "failed",
      diffSummary: result.logs.slice(-1)[0] ?? "",
      iterations: result.logs.length
    });
    database.close();
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

program.command("browse")
  .argument("<url>")
  .description("Audit a URL with the local headless browser")
  .action(async (url: string) => {
    const browser = new BrowserSession();
    try {
      await browser.navigate(url);
      console.log(JSON.stringify({
        consoleErrors: browser.getConsoleErrors(),
        accessibility: await browser.getAccessibilitySnapshot()
      }, null, 2));
    } finally {
      await browser.close();
    }
  });

program.command("search")
  .argument("<query>")
  .description("Search public documentation without an API key")
  .option("--docs", "fetch and print the first result documentation")
  .action(async (query: string, options: { docs?: boolean }) => {
    const results = await searchWeb(query);
    if (options.docs && results[0]) {
      console.log(await fetchDocumentation(results[0].url));
      return;
    }
    results.forEach((result, index) => console.log(`${index + 1}. ${result.title}\n${result.url}\n${result.snippet}\n`));
  });

program.command("e2e")
  .argument("<testGoal>")
  .option("--command <command>", "development server command", "npm run dev")
  .option("--port <number>", "development server port", "3000")
  .action(async (testGoal: string, options: { command: string; port: string }) => {
    const healer = new FrontendHealer(new OllamaProvider(), { port: Number(options.port) });
    const result = await healer.run(options.command, testGoal);
    console.log(JSON.stringify(result, null, 2));
    if (!result.success) process.exitCode = 1;
  });

await program.parseAsync();
