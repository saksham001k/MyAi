import Database from "better-sqlite3";
import { mkdirSync } from "node:fs";
import path from "node:path";

export interface TaskHistory {
  id: number;
  goal: string;
  timestamp: string;
  status: string;
  diffSummary: string;
  iterations: number;
}

export interface ProjectRule {
  id: number;
  rule: string;
  createdAt: string;
}

export class MyAiDatabase {
  private readonly db: Database.Database;

  public constructor(root = process.cwd()) {
    const directory = path.join(path.resolve(root), ".myai");
    mkdirSync(directory, { recursive: true });
    this.db = new Database(path.join(directory, "history.db"));
    this.db.pragma("journal_mode = WAL");
    this.db.exec(`
      CREATE TABLE IF NOT EXISTS task_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        goal TEXT NOT NULL,
        timestamp TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        status TEXT NOT NULL,
        diff_summary TEXT NOT NULL DEFAULT '',
        iterations INTEGER NOT NULL DEFAULT 0
      );
      CREATE TABLE IF NOT EXISTS project_rules (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        rule TEXT NOT NULL UNIQUE,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
      );
      CREATE TABLE IF NOT EXISTS task_attempts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        task_id INTEGER NOT NULL,
        attempt INTEGER NOT NULL,
        status TEXT NOT NULL,
        output TEXT NOT NULL DEFAULT '',
        FOREIGN KEY(task_id) REFERENCES task_history(id)
      );
    `);
  }

  public addRule(rule: string): ProjectRule {
    const value = rule.trim();
    if (!value) throw new Error("Rule cannot be empty.");
    this.db.prepare("INSERT OR IGNORE INTO project_rules (rule) VALUES (?)").run(value);
    return this.db.prepare(
      "SELECT id, rule, created_at AS createdAt FROM project_rules WHERE rule = ?"
    ).get(value) as ProjectRule;
  }

  public listRules(): ProjectRule[] {
    return this.db.prepare(
      "SELECT id, rule, created_at AS createdAt FROM project_rules ORDER BY id"
    ).all() as ProjectRule[];
  }

  public recordTask(input: Omit<TaskHistory, "id" | "timestamp">): TaskHistory {
    const result = this.db.prepare(
      "INSERT INTO task_history (goal, status, diff_summary, iterations) VALUES (?, ?, ?, ?)"
    ).run(input.goal, input.status, input.diffSummary, input.iterations);
    return this.db.prepare(
      "SELECT id, goal, timestamp, status, diff_summary AS diffSummary, iterations FROM task_history WHERE id = ?"
    ).get(result.lastInsertRowid) as TaskHistory;
  }

  public listHistory(limit = 50): TaskHistory[] {
    const safeLimit = Math.max(1, Math.min(Math.floor(limit), 500));
    return this.db.prepare(
      `SELECT id, goal, timestamp, status, diff_summary AS diffSummary, iterations
       FROM task_history ORDER BY id DESC LIMIT ${safeLimit}`
    ).all() as TaskHistory[];
  }

  public recentRelatedDiffs(goal: string, limit = 3): TaskHistory[] {
    const words = goal.toLowerCase().split(/\W+/).filter((word) => word.length > 2).slice(0, 8);
    const rows = this.listHistory(100);
    const related = rows.filter((row) => {
      const text = `${row.goal} ${row.diffSummary}`.toLowerCase();
      return words.length === 0 || words.some((word) => text.includes(word));
    });
    return related.slice(0, Math.max(0, Math.min(limit, 10)));
  }

  public close(): void {
    this.db.close();
  }
}
