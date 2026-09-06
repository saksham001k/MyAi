import { MyAiDatabase, type TaskHistory } from "../storage/db.js";

export class ProjectMemory {
  public constructor(private readonly database: MyAiDatabase) {}

  public promptContext(goal: string): string {
    const rules = this.database.listRules();
    const diffs = this.database.recentRelatedDiffs(goal, 3);
    const sections = [
      "Persistent project memory:",
      rules.length
        ? `Developer rules:\n${rules.map((item) => `- ${item.rule}`).join("\n")}`
        : "Developer rules:\n- None recorded.",
      diffs.length
        ? `Recent related task history:\n${diffs.map(formatHistory).join("\n")}`
        : "Recent related task history:\n- None recorded."
    ];
    return sections.join("\n");
  }
}

function formatHistory(item: TaskHistory): string {
  return `- ${item.status} (${item.iterations} iteration${item.iterations === 1 ? "" : "s"}): ${item.goal}\n  Diff: ${item.diffSummary || "No diff summary recorded."}`;
}
