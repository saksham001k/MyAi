export interface WebResult {
  title: string;
  url: string;
  snippet: string;
}

export interface FetchOptions {
  fetchImpl?: typeof fetch;
}

function decode(value: string): string {
  return value.replace(/&amp;/g, "&").replace(/&quot;/g, '"')
    .replace(/&#x27;|&#39;/g, "'").replace(/&lt;/g, "<").replace(/&gt;/g, ">")
    .replace(/<[^>]+>/g, "").replace(/\s+/g, " ").trim();
}

export async function searchWeb(query: string, maxResults = 5, options: FetchOptions = {}): Promise<WebResult[]> {
  if (!query.trim()) throw new Error("Search query cannot be empty.");
  const limit = Math.max(1, Math.min(Math.floor(maxResults), 20));
  const fetchImpl = options.fetchImpl ?? fetch;
  const response = await fetchImpl(`https://html.duckduckgo.com/html/?q=${encodeURIComponent(query)}`, {
    headers: { "User-Agent": "MyAi/1.0 (local developer tool)" }
  });
  if (!response.ok) throw new Error(`DuckDuckGo returned HTTP ${response.status}.`);
  const html = await response.text();
  const results: WebResult[] = [];
  const pattern = /<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>([\s\S]*?)<\/a>[\s\S]*?<a[^>]+class="result__snippet"[^>]*>([\s\S]*?)<\/a>/gi;
  for (const match of html.matchAll(pattern)) {
    let url = decode(match[1]);
    const uddg = url.match(/[?&]uddg=([^&]+)/);
    if (uddg) url = decode(decodeURIComponent(uddg[1]));
    results.push({ url, title: decode(match[2]), snippet: decode(match[3]) });
    if (results.length >= limit) break;
  }
  return results;
}

export async function fetchDocumentation(url: string, options: FetchOptions = {}): Promise<string> {
  const parsed = new URL(url);
  if (!["http:", "https:"].includes(parsed.protocol)) throw new Error("Documentation URL must use HTTP or HTTPS.");
  const response = await (options.fetchImpl ?? fetch)(url, {
    headers: { "User-Agent": "MyAi/1.0 (local developer)" }
  });
  if (!response.ok) throw new Error(`Documentation request returned HTTP ${response.status}.`);
  const html = await response.text();
  const text = decode(html
    .replace(/<script[\s\S]*?<\/script>|<style[\s\S]*?<\/style>|<noscript[\s\S]*?<\/noscript>/gi, " ")
    .replace(/<\/(p|div|li|h[1-6]|pre|code|br)>/gi, "\n")
    .replace(/<[^>]+>/g, " "));
  const words = text.split(/\s+/).filter(Boolean);
  return words.slice(0, 500).join(" ");
}
