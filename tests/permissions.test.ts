import { describe, expect, it } from "vitest";
import {
  CONFIRMATION_TOKEN,
  PermissionError,
  assertCommandAllowed,
  classifyCommand
} from "../src/guardrails/permissions.js";

describe("command permissions", () => {
  it("classifies ordinary commands as safe", () => {
    expect(classifyCommand("npm test")).toBe("SAFE");
  });

  it("blocks destructive commands without confirmation", () => {
    expect(() => assertCommandAllowed("rm -rf build")).toThrow(PermissionError);
    expect(() => assertCommandAllowed("git push --force origin main")).toThrow(PermissionError);
  });

  it("allows destructive commands with the explicit token", () => {
    expect(() =>
      assertCommandAllowed("rm -rf build", { confirmationToken: CONFIRMATION_TOKEN })
    ).not.toThrow();
  });
});
