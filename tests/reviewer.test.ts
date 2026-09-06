import { describe, expect, it } from "vitest";
import { summarizeDiff, reviewWorktree } from "../src/cli/reviewer.js";

describe("worktree review", () => {
  it("summarizes changed files and line counts", () => {
    expect(summarizeDiff("diff --git a/a.ts b/a.ts\n+++ b/a.ts\n@@\n-old\n+new\n")).toEqual({
      files: ["a.ts"], additions: 1, deletions: 1
    });
  });

  it("routes accept and discard decisions", async () => {
    let accepted = false;
    const result = await reviewWorktree(
      { diff: async () => "+++ b/a.ts\n+new\n" } as never,
      { question: async () => "a", write: () => undefined },
      { accept: async () => { accepted = true; }, retry: async () => undefined, discard: async () => undefined }
    );
    expect(result).toBe("accepted");
    expect(accepted).toBe(true);
  });
});
