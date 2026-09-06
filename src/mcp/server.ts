import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";
import { createAgentTools } from "../agent/tools.js";

export function createMcpServer(workspaceRoot = process.cwd()): McpServer {
  const server = new McpServer({ name: "myai", version: "1.0.0" });
  const tools = createAgentTools(workspaceRoot);
  for (const tool of tools) {
    if (tool.schema.name === "read_symbol") {
      server.tool("read_symbol", tool.schema.description, {
        filePath: z.string(), line: z.number().int()
      }, async ({ filePath, line }) => ({
        content: [{ type: "text", text: JSON.stringify(await tool.execute({ filePath, line })) }]
      }));
    } else if (tool.schema.name === "search_code") {
      server.tool("search_code", tool.schema.description, { pattern: z.string() }, async ({ pattern }) => ({
        content: [{ type: "text", text: JSON.stringify(await tool.execute({ pattern })) }]
      }));
    } else if (tool.schema.name === "apply_patch") {
      server.tool("apply_patch", tool.schema.description, {
        filePath: z.string(), startLine: z.number().int(), endLine: z.number().int(), replacementText: z.string()
      }, async (args) => ({
        content: [{ type: "text", text: JSON.stringify(await tool.execute(args)) }]
      }));
    } else if (tool.schema.name === "run_command") {
      server.tool("run_command", tool.schema.description, { command: z.string() }, async ({ command }) => ({
        content: [{ type: "text", text: JSON.stringify(await tool.execute({ command })) }]
      }));
    }
  }
  return server;
}

export async function startMcpServer(workspaceRoot = process.cwd()): Promise<void> {
  const server = createMcpServer(workspaceRoot);
  await server.connect(new StdioServerTransport());
}
