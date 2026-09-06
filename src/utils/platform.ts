import os from "node:os";
import path from "node:path";

export type PlatformOS = "windows" | "macos" | "linux";
export type PlatformArch = "x64" | "arm64";

export interface PlatformInfo {
  os: PlatformOS;
  arch: PlatformArch;
  runtimeTag: string;
  executableName: string;
}

export function detectPlatform(): PlatformInfo {
  const currentOs: PlatformOS = process.platform === "win32"
    ? "windows" : process.platform === "darwin" ? "macos" : "linux";
  const arch: PlatformArch = process.arch === "arm64" ? "arm64" : "x64";
  return {
    os: currentOs,
    arch,
    runtimeTag: `${currentOs === "windows" ? "win" : currentOs === "macos" ? "darwin" : "linux"}-${arch}`,
    executableName: currentOs === "windows" ? "llama-server.exe" : "llama-server"
  };
}

export function resolveRuntimeBinary(root: string, binary = "llama-server"): string {
  const info = detectPlatform();
  const name = info.os === "windows" && binary === "llama-server" ? info.executableName : binary;
  return path.resolve(root, "runtime", info.runtimeTag, name);
}

export function normalizePath(value: string): string {
  return path.normalize(path.resolve(value));
}

export function pathsEqual(left: string, right: string): boolean {
  const a = normalizePath(left);
  const b = normalizePath(right);
  return process.platform === "linux" ? a === b : a.toLowerCase() === b.toLowerCase();
}

export const hostPlatform = os.platform();
