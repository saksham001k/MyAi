import path from 'node:path';
import { promises as fs } from 'node:fs';

export const excluded = new Set(['.git', '.kiss', '.local-planning', '.venv', 'venv', 'node_modules', 'dist', 'build', 'models', 'runtime', 'data', 'testpic', '__pycache__']);
export function permitted(file: string): boolean {
  return !file.split(/[\\/]/).some(p => excluded.has(p) || p.startsWith('.env') || /\.(pem|key)$/i.test(p));
}
export async function inside(root: string, file: string): Promise<string> {
  const base = await fs.realpath(root);
  const resolved = path.resolve(base, file);
  if (!resolved.startsWith(base + path.sep) || !permitted(path.relative(base, resolved))) throw new Error('Path is outside the permitted project files.');
  let current = resolved;
  while (current !== base) {
    try {
      if ((await fs.lstat(current)).isSymbolicLink()) throw new Error('Symbolic links are not supported.');
    } catch (error) { if ((error as NodeJS.ErrnoException).code !== 'ENOENT') throw error; }
    current = path.dirname(current);
  }
  return resolved;
}
