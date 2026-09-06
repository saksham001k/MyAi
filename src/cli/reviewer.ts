import { promises as fs } from "node:fs";
import readline from "node:readline/promises";
import type { IsolatedWorktree } from "../guardrails/worktree.js";

export interface ReviewSummary {
  files: string[];
  additions: number;
  deletions: number;
}

export function summarizeDiff(diff: string): ReviewSummary {
  const files = [...diff.matchAll(/^\+\+\+ b\/(.+)$/gm)].map((match) => match[1]);
  const additions = diff.split(/\r?\n/).filter((line) => line.startsWith("+") && !line.startsWith("+++")).length;
  const deletions = diff.split(/\r?\n/).filter((line) => line.startsWith("-") && !line.startsWith("---")).length;
  return { files, additions, deletions };
}

export interface ReviewIO {
  question(prompt: string): Promise<string>;
  write(text: string): void;
}

export async function reviewWorktree(
  worktree: IsolatedWorktree,
  io: ReviewIO,
  actions: {
    accept: () => Promise<void>;
    retry: (feedback: string) => Promise<void>;
    discard: () => Promise<void>;
  }
): Promise<"accepted" | "discarded" | "retried"> {
  const diff = await worktree.diff();
  const summary = summarizeDiff(diff);
  io.write(`\nModified files: ${summary.files.join(", ") || "none"}\n+${summary.additions} / -${summary.deletions}\n`);
  while (true) {
    const choice = (await io.question("[a] Accept & Merge  [d] View Full Diff  [r] Retry with Feedback  [c] Discard & Cancel: ")).trim().toLowerCase();
    if (choice === "a") { await actions.accept(); return "accepted"; }
    if (choice === "d") { io.write(diff || "No changes.\n"); continue; }
    if (choice === "r") { await actions.retry(await io.question("Feedback: ")); return "retried"; }
    if (choice === "c") { await actions.discard(); return "discarded"; }
    io.write("Choose a, d, r, or c.\n");
  }
}

export function terminalReviewIO(): ReviewIO {
  const rl = readline.createInterface({ input: process.stdin, output: process.stdout });
  return {
    question: (prompt) => rl.question(prompt),
    write: (text) => process.stdout.write(text)
  };
}
