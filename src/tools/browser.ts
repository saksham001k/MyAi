import type { Browser, Page } from "playwright";

export interface BrowserOptions {
  browser?: Browser;
  page?: Page;
}

export interface AccessibilityNode {
  role: string;
  name?: string;
  value?: string;
  children?: AccessibilityNode[];
}

export class BrowserSession {
  private browser?: Browser;
  private page?: Page;
  private readonly consoleErrors: string[] = [];

  public constructor(private readonly options: BrowserOptions = {}) {
    this.browser = options.browser;
    this.page = options.page;
    this.page?.on("console", (message) => {
      if (message.type() === "error") this.consoleErrors.push(message.text());
    });
    this.page?.on("pageerror", (error) => this.consoleErrors.push(error.message));
  }

  public async launch(headless = true): Promise<void> {
    if (this.page) return;
    const { chromium } = await import("playwright");
    this.browser = await chromium.launch({ headless });
    this.page = await this.browser.newPage();
    this.page.on("console", (message) => {
      if (message.type() === "error") this.consoleErrors.push(message.text());
    });
    this.page.on("pageerror", (error) => this.consoleErrors.push(error.message));
  }

  public async navigate(url: string): Promise<void> {
    if (!this.page) await this.launch();
    await this.page!.goto(url, { waitUntil: "domcontentloaded" });
  }

  public getConsoleErrors(): string[] {
    return [...this.consoleErrors];
  }

  public clearConsoleErrors(): void {
    this.consoleErrors.length = 0;
  }

  public async getAccessibilitySnapshot(): Promise<AccessibilityNode | null> {
    if (!this.page) throw new Error("Browser session has not been launched.");
    return this.page.evaluate(() => {
      const elements = Array.from(document.querySelectorAll(
        "button,a,input,textarea,select,[role],h1,h2,h3,h4,h5,h6"
      )).slice(0, 100);
      const children = elements.map((element) => {
        const typed = element as HTMLInputElement;
        const role = element.getAttribute("role") ||
          (element.tagName === "A" ? "link" : element.tagName.toLowerCase());
        return {
          role,
          name: (element.getAttribute("aria-label") || element.textContent || typed.placeholder || "").trim().slice(0, 160),
          value: typed.value || undefined
        };
      });
      return { role: "document", name: document.title, children };
    }) as Promise<AccessibilityNode>;
  }

  public async takeScreenshot(outputPath: string): Promise<void> {
    if (!this.page) throw new Error("Browser session has not been launched.");
    await this.page.screenshot({ path: outputPath, type: "png" });
  }

  public async interact(selector: string, action: "click" | "fill", value?: string): Promise<void> {
    if (!this.page) throw new Error("Browser session has not been launched.");
    const locator = this.page.locator(selector);
    await locator.waitFor({ state: "visible" });
    if (action === "click") await locator.click();
    else {
      if (value === undefined) throw new Error("fill requires a value.");
      await locator.fill(value);
    }
  }

  public async close(): Promise<void> {
    await this.browser?.close();
    this.browser = undefined;
    this.page = undefined;
  }
}
