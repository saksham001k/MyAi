import { promises as fs } from "node:fs";
import os from "node:os";
import path from "node:path";
import { ProcessSandbox } from "../engine/sandbox.js";

export class IsolatedWorktree {
  public readonly branch: string;
  public path = "";
  private readonly sandbox: ProcessSandbox;

  public constructor(
    private readonly repositoryRoot: string,
    taskId: string,
    sandbox = new ProcessSandbox()
  ) {
    this.branch = `myai-feature/${taskId.replace(/[^a-zA-Z0-9._-]/g, "-")}`;
    this.sandbox = sandbox;
  }

  public async create(): Promise<string> {
    const parent = await fs.mkdtemp(path.join(os.tmpdir(), "myai-worktree-"));
    this.path = path.join(parent, "workspace");
    const result = await this.sandbox.run(
      ["git", "worktree", "add", "-b", this.branch, this.path, "HEAD"],
      { cwd: this.repositoryRoot }
    );
    if (result.exitCode !== 0) throw new Error(result.stderr || "Unable to create isolated worktree.");
    return this.path;
  }

  public async discard(): Promise<void> {
    if (!this.path) return;
    await this.sandbox.run(["git", "worktree", "remove", "--force", this.path], { cwd: this.repositoryRoot });
    await this.sandbox.run(["git", "branch", "-D", this.branch], { cwd: this.repositoryRoot });
  }

  public async diff(): Promise<string> {
    const result = await this.sandbox.run(["git", "diff", "HEAD"], { cwd: this.path });
    return result.stdout;
  }

  public async acceptAndMerge(): Promise<void> {
    const staged = await this.sandbox.run(["git", "add", "-A"], { cwd: this.path });
    if (staged.exitCode !== 0) throw new Error(staged.stderr || "Unable to stage worktree changes.");
    const snapshot = await this.sandbox.run(
      ["git", "commit", "-m", "MyAi autonomous worktree snapshot"],
      { cwd: this.path }
    );
    if (snapshot.exitCode !== 0) throw new Error(snapshot.stderr || "Unable to snapshot worktree changes.");
    const result = await this.sandbox.run(
      ["git", "merge", "--squash", this.branch],
      { cwd: this.repositoryRoot }
    );
    if (result.exitCode !== 0) throw new Error(result.stderr || "Unable to squash-merge worktree branch.");
    const commit = await this.sandbox.run(
      ["git", "commit", "-m", "Apply MyAi autonomous changes"],
      { cwd: this.repositoryRoot }
    );
    if (commit.exitCode !== 0) throw new Error(commit.stderr || "Unable to commit squashed changes.");
    await this.discard();
  }
}
