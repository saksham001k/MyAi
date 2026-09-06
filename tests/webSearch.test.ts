import { describe, expect, it } from "vitest";
import { fetchDocumentation, searchWeb } from "../src/tools/webSearch.js";

function response(body: string): Response {
  return new Response(body, { status: 200, headers: { "content-type": "text/html" } });
}

describe("zero-key web search", () => {
  it("parses DuckDuckGo result links and snippets", async () => {
    const html = '<a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com">Example &amp; Docs</a><a class="result__snippet">A useful snippet.</a>';
    const results = await searchWeb("example", 5, { fetchImpl: async () => response(html) });
    expect(results).toEqual([{ title: "Example & Docs", url: "https://example.com", snippet: "A useful snippet." }]);
  });

  it("removes scripts and HTML while bounding documentation text", async () => {
    const docs = await fetchDocumentation("https://example.com/docs", {
      fetchImpl: async () => response("<script>secret()</script><h1>API</h1><p>Use <code>fetch</code>.</p>")
    });
    expect(docs).toBe("API Use fetch .");
    expect(docs).not.toContain("secret");
  });
});
