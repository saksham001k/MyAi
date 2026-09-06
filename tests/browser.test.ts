import { describe, expect, it } from "vitest";
import { BrowserSession } from "../src/tools/browser.js";

describe("browser assessment", () => {
  it("captures console errors and serializes semantic controls", async () => {
    const handlers: Record<string, (value: { type: () => string; text: () => string } | Error) => void> = {};
    const page = {
      on(event: string, callback: (value: { type: () => string; text: () => string } | Error) => void) {
        handlers[event] = callback;
      },
      async evaluate() {
        return { role: "document", name: "Test", children: [{ role: "button", name: "Save" }] };
      }
    };
    const session = new BrowserSession({ page: page as never });
    handlers.console?.({ type: () => "error", text: () => "broken" });
    handlers.pageerror?.(new Error("uncaught"));
    expect(session.getConsoleErrors()).toEqual(["broken", "uncaught"]);
    await expect(session.getAccessibilitySnapshot()).resolves.toMatchObject({
      children: [{ role: "button", name: "Save" }]
    });
  });
});
