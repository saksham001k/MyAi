/** Single-request local source worker. No model, account or network calls. */
import { createAgentTools } from './agent/tools.js';
const [, , root, request] = process.argv;
try {
  if (!root || !request) throw new Error('Usage: worker <project-root> <JSON-request>');
  const input = JSON.parse(request) as { tool: string; args: Record<string, unknown> };
  // The HTTP coordinator grants only structural inspection to this worker.
  if (input.tool !== 'read_symbol') throw new Error('Worker only supports read_symbol.');
  const tool = createAgentTools(root).find(t => t.schema.name === input.tool)!;
  process.stdout.write(JSON.stringify(await tool.execute(input.args)));
} catch (error) {
  process.stderr.write(error instanceof Error ? error.message : String(error));
  process.exitCode = 1;
}
