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
}
