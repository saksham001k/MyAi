import { OLLAMA_URL, OllamaProvider } from "./ollama.js";

export const OLLAMA_NOTICE =
  "Ollama not detected. Run 'ollama run qwen2.5-coder:1.5b' to start your free local brain.";

export interface OllamaHealth {
  available: boolean;
  models: string[];
  notice?: string;
}

export async function checkOllama(
  provider = new OllamaProvider()
): Promise<OllamaHealth> {
  try {
    const models = await provider.listModels();
    return { available: true, models };
  } catch {
    return { available: false, models: [], notice: OLLAMA_NOTICE };
  }
}

export { OLLAMA_URL };
