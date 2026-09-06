export type RiskClass = "SAFE" | "DESTRUCTIVE";

export interface PermissionOptions {
  confirmed?: boolean;
  confirmationToken?: string;
}

export const CONFIRMATION_TOKEN = "MYAI-CONFIRMED";

const destructivePatterns: RegExp[] = [
  /\brm\s+(?:-[^\s]*[rf][^\s]*\s+)*[^\n]*/i,
  /\bgit\s+push\b[^\n]*\s--force(?:-with-lease)?\b/i,
  /\b(?:mkfs|format(?:\.com)?|fdisk|diskpart|parted)\b/i,
  /(?:^|[\s"'=])(?:\/etc|\/usr|\/var|\/System|C:\\Windows)(?:[\\/]|$)/i,
  /\b(?:sudo\s+)?(?:chmod|chown)\s+(?:-R\s+)?(?:777|666)\b/i,
  /\b(?:shutdown|reboot|poweroff|killall|pkill)\b/i
];

export function classifyCommand(command: string | readonly string[]): RiskClass {
  const text = typeof command === "string" ? command : command.join(" ");
  return destructivePatterns.some((pattern) => pattern.test(text))
    ? "DESTRUCTIVE"
    : "SAFE";
}

export function isConfirmed(options: PermissionOptions = {}): boolean {
  return options.confirmed === true || options.confirmationToken === CONFIRMATION_TOKEN;
}

export function assertCommandAllowed(
  command: string | readonly string[],
  options: PermissionOptions = {}
): void {
  if (classifyCommand(command) === "DESTRUCTIVE" && !isConfirmed(options)) {
    throw new PermissionError(
      "Destructive command blocked. Provide confirmed=true or the MYAI-CONFIRMED token."
    );
  }
}

export class PermissionError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "PermissionError";
  }
}
