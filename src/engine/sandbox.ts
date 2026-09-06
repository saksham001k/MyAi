import { execa, type ResultPromise } from "execa";
import { assertCommandAllowed, type PermissionOptions } from "../guardrails/permissions.js";

export interface SandboxOptions extends PermissionOptions {
  cwd?: string;
  env?: NodeJS.ProcessEnv;
  timeoutMs?: number;
}

export interface FailureLocation {
  file: string;
  line: number;
  column?: number;
}

export interface ProcessResult {
  command: string;
  exitCode: number | null;
  stdout: string;
  stderr: string;
  timedOut: boolean;
  failure?: FailureLocation;
}

const failurePattern =
  /(?:^|[\s("'`])((?:[A-Za-z]:[\\/]|\/|\.{0,2}[\\/])?[^()\s"'`]+?\.(?:ts|tsx|js|jsx)):(\d+)(?::(\d+))?/m;

export function parseFailureLocation(stderr: string): FailureLocation | undefined {
  const match = failurePattern.exec(stderr);
  if (!match) return undefined;
  return {
    file: match[1],
    line: Number(match[2]),
    column: match[3] ? Number(match[3]) : undefined
  };
}

function commandText(command: string | readonly string[]): string {
  return typeof command === "string" ? command : command.join(" ");
}

export class ProcessSandbox {
  public constructor(private readonly defaultTimeoutMs = 15_000) {
    if (!Number.isFinite(defaultTimeoutMs) || defaultTimeoutMs <= 0) {
      throw new RangeError("defaultTimeoutMs must be greater than zero");
    }
  }

  public async run(
    command: string | readonly string[],
    options: SandboxOptions = {}
  ): Promise<ProcessResult> {
    assertCommandAllowed(command, options);
    const text = commandText(command);
    const timeoutMs = options.timeoutMs ?? this.defaultTimeoutMs;
    if (!Number.isFinite(timeoutMs) || timeoutMs <= 0) {
      throw new RangeError("timeoutMs must be greater than zero");
    }

    const child: ResultPromise = typeof command !== "string"
      ? execa(command[0], command.slice(1), {
          cwd: options.cwd,
          env: options.env,
          timeout: timeoutMs,
          killSignal: "SIGTERM",
          reject: false
        })
      : execa(command, {
          cwd: options.cwd,
          env: options.env,
          timeout: timeoutMs,
          killSignal: "SIGTERM",
          shell: false,
          reject: false
        });
    const result = await child;
    const timedOut = result.timedOut === true;
    const stdout = String(result.stdout ?? "");
    const stderr = String(result.stderr ?? "");
    return {
      command: text,
      exitCode: result.exitCode ?? null,
      stdout,
      stderr,
      timedOut,
      failure: parseFailureLocation(stderr)
    };
  }
}
