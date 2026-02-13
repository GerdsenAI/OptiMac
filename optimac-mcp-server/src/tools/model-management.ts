/**
 * Model management tools: browse local models, check RAM fit,
 * serve/load/unload models, and manage the model directory.
 *
 * Core principle: never let the user load a model too big for available RAM.
 * We reserve ~20% headroom above the model size to prevent swap thrashing.
 */

import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { z } from "zod";
import { runCommand, LONG_TIMEOUT } from "../services/shell.js";
import { loadConfig, saveConfig } from "../services/config.js";
import { parseVmStat } from "../services/parsers.js";
import { checkPort } from "../services/net.js";
import { inferLocal } from "../services/inference.js";
import { readdirSync, statSync, existsSync } from "node:fs";
import { join, basename, extname } from "node:path";
import { homedir } from "node:os";

// Model file extensions we recognize
const MODEL_EXTENSIONS = new Set([
  ".gguf", ".bin", ".safetensors", ".pth", ".pt", ".onnx",
]);

// Minimum file size (MB) to be considered a model
const MIN_MODEL_SIZE_MB = 50;

interface ModelFileInfo {
  path: string;
  name: string;
  sizeMB: number;
  sizeGB: number;
  extension: string;
  directory: string;
  fitsInRAM: boolean;
  availableRAM_GB: number;
  requiredRAM_GB: number;
}

// checkPort imported from services/net.ts

/**
 * Get available RAM in MB from vm_stat + sysctl.
 * "Available" here means free + inactive + purgeable pages.
 */
async function getAvailableRAM(): Promise<{ totalMB: number; usedMB: number; availableMB: number }> {
  const vmResult = await runCommand("vm_stat", []);
  const sysResult = await runCommand("sysctl", ["hw.memsize", "hw.pagesize"]);
  const stats = parseVmStat(vmResult.stdout, sysResult.stdout);
  return {
    totalMB: stats.totalPhysicalMB,
    usedMB: stats.usedMB,
    availableMB: stats.totalPhysicalMB - stats.usedMB,
  };
}

/**
 * Check if a model of given size (MB) fits in RAM with 20% headroom.
 * Formula: modelSizeMB * 1.20 <= availableRAM
 */
function modelFitsInRAM(modelSizeMB: number, availableMB: number): boolean {
  const requiredMB = modelSizeMB * 1.20; // 20% headroom
  return requiredMB <= availableMB;
}

/**
 * Walk a directory tree up to maxDepth and collect model files.
 */
function scanForModels(dir: string, maxDepth = 4, currentDepth = 0): Array<{ path: string; sizeMB: number }> {
  const results: Array<{ path: string; sizeMB: number }> = [];
  if (currentDepth > maxDepth) return results;

  try {
    const entries = readdirSync(dir, { withFileTypes: true });
    for (const entry of entries) {
      const fullPath = join(dir, entry.name);
      if (entry.isDirectory() && !entry.name.startsWith(".")) {
        results.push(...scanForModels(fullPath, maxDepth, currentDepth + 1));
      } else if (entry.isFile()) {
        const ext = extname(entry.name).toLowerCase();
        if (MODEL_EXTENSIONS.has(ext)) {
          try {
            const stat = statSync(fullPath);
            const sizeMB = stat.size / (1024 * 1024);
            if (sizeMB >= MIN_MODEL_SIZE_MB) {
              results.push({ path: fullPath, sizeMB });
            }
          } catch { /* permission denied, etc. */ }
        }
      }
    }
  } catch { /* directory not readable */ }

  return results;
}

export function registerModelManagementTools(server: McpServer): void {

  // ---- LIST LOCAL MODELS WITH RAM FIT CHECK ----
  server.registerTool(
    "optimac_models_available",
    {
      title: "List Available Local Models",
      description: `Scan the model base directory and common model locations for downloaded model files.
Returns only models that fit in currently available RAM (with ~20% headroom).

Scans for: .gguf, .safetensors, .bin, .pth, .pt, .onnx files > 50MB.
Search locations: modelBaseDir (from config), ~/.ollama/models, ~/.cache/huggingface/hub,
~/.cache/lm-studio/models, ~/models.

Each model shows: path, size, whether it fits in current RAM, and required vs available RAM.
Models that would cause swap thrashing are filtered out by default.`,
      inputSchema: {
        show_all: z.boolean().default(false).describe("Show all models including those too large for current RAM"),
      },
      annotations: {
        readOnlyHint: true,
        destructiveHint: false,
        idempotentHint: true,
        openWorldHint: false,
      },
    },
    async ({ show_all }) => {
      const config = loadConfig();
      const ram = await getAvailableRAM();
      const home = homedir();

      // Build search directories
      const searchDirs: string[] = [];
      if (config.modelBaseDir && existsSync(config.modelBaseDir)) {
        searchDirs.push(config.modelBaseDir);
      }
      for (const d of [
        join(home, ".ollama", "models"),
        join(home, ".cache", "huggingface", "hub"),
        join(home, ".cache", "lm-studio", "models"),
        join(home, "models"),
      ]) {
        if (existsSync(d) && !searchDirs.includes(d)) {
          searchDirs.push(d);
        }
      }

      // Scan all directories
      const allModels: ModelFileInfo[] = [];
      for (const dir of searchDirs) {
        const found = scanForModels(dir);
        for (const { path, sizeMB } of found) {
          const fits = modelFitsInRAM(sizeMB, ram.availableMB);
          allModels.push({
            path,
            name: basename(path),
            sizeMB: Math.round(sizeMB),
            sizeGB: Math.round(sizeMB / 1024 * 10) / 10,
            extension: extname(path).toLowerCase(),
            directory: dir,
            fitsInRAM: fits,
            availableRAM_GB: Math.round(ram.availableMB / 1024 * 10) / 10,
            requiredRAM_GB: Math.round(sizeMB * 1.2 / 1024 * 10) / 10,
          });
        }
      }

      // Sort by size descending
      allModels.sort((a, b) => b.sizeMB - a.sizeMB);

      // Filter to only models that fit (unless show_all)
      const filtered = show_all ? allModels : allModels.filter((m) => m.fitsInRAM);

      return {
        content: [{
          type: "text",
          text: JSON.stringify({
            systemRAM: {
              totalGB: Math.round(ram.totalMB / 1024 * 10) / 10,
              usedGB: Math.round(ram.usedMB / 1024 * 10) / 10,
              availableGB: Math.round(ram.availableMB / 1024 * 10) / 10,
            },
            headroomPolicy: "20% above model size reserved for system + inference overhead",
            searchedDirectories: searchDirs,
            totalModelsFound: allModels.length,
            modelsShown: filtered.length,
            modelsFilteredOut: allModels.length - filtered.length,
            models: filtered,
          }, null, 2),
        }],
      };
    }
  );

  // ---- LIST OLLAMA AVAILABLE MODELS ----
  server.registerTool(
    "optimac_ollama_available",
    {
      title: "Ollama Available Models",
      description: `List Ollama models that are downloaded and can be served.
Only returns models that fit in currently available RAM with 20% headroom.
Also shows currently running models via 'ollama ps'.`,
      inputSchema: {
        show_all: z.boolean().default(false).describe("Show all models including those too large for current RAM"),
      },
      annotations: {
        readOnlyHint: true,
        destructiveHint: false,
        idempotentHint: true,
        openWorldHint: false,
      },
    },
    async ({ show_all }) => {
      const ram = await getAvailableRAM();

      // Get installed models
      const listResult = await runCommand("ollama", ["list"]);
      if (listResult.exitCode !== 0) {
        return {
          content: [{ type: "text", text: JSON.stringify({ error: "Ollama not available", stderr: listResult.stderr }) }],
          isError: true,
        };
      }

      // Parse ollama list output
      const lines = listResult.stdout.split("\n").filter(Boolean);
      const models: Array<{
        name: string;
        id: string;
        sizeMB: number;
        sizeGB: number;
        modified: string;
        fitsInRAM: boolean;
        requiredRAM_GB: number;
      }> = [];

      for (const line of lines.slice(1)) { // skip header
        const parts = line.trim().split(/\s+/);
        if (parts.length < 4) continue;
        const name = parts[0];
        const id = parts[1];
        // Parse size (e.g., "4.7 GB" or "350 MB")
        let sizeMB = 0;
        const sizeStr = parts[2] + " " + parts[3];
        const sizeMatch = sizeStr.match(/([\d.]+)\s*(GB|MB)/i);
        if (sizeMatch) {
          const val = parseFloat(sizeMatch[1]);
          sizeMB = sizeMatch[2].toUpperCase() === "GB" ? val * 1024 : val;
        }
        const modified = parts.slice(4).join(" ");
        const fits = modelFitsInRAM(sizeMB, ram.availableMB);

        models.push({
          name,
          id,
          sizeMB: Math.round(sizeMB),
          sizeGB: Math.round(sizeMB / 1024 * 10) / 10,
          modified,
          fitsInRAM: fits,
          requiredRAM_GB: Math.round(sizeMB * 1.2 / 1024 * 10) / 10,
        });
      }

      // Get running models
      const psResult = await runCommand("ollama", ["ps"]);
      const runningModels = psResult.exitCode === 0 ? psResult.stdout : "Unable to check";

      // Filter
      const filtered = show_all ? models : models.filter((m) => m.fitsInRAM);

      return {
        content: [{
          type: "text",
          text: JSON.stringify({
            availableRAM_GB: Math.round(ram.availableMB / 1024 * 10) / 10,
            headroomPolicy: "20% above model size reserved",
            totalInstalled: models.length,
            canRunNow: models.filter((m) => m.fitsInRAM).length,
            tooLargeForRAM: models.filter((m) => !m.fitsInRAM).length,
            models: filtered,
            currentlyRunning: runningModels,
          }, null, 2),
        }],
      };
    }
  );

  // ---- SERVE/LOAD A MODEL ----
  server.registerTool(
    "optimac_model_serve",
    {
      title: "Serve/Load a Model",
      description: `Load and serve a model for inference. Checks RAM availability before loading.

Supports two runtimes:
  - ollama: Loads a model by name (e.g., "llama3.2:3b", "qwen2.5:7b")
  - mlx: Starts mlx_lm.server with a HuggingFace model ID or local path

Safety: Refuses to load models that would exceed available RAM (with 20% headroom).
Use optimac_models_available or optimac_ollama_available first to see what fits.

Args:
  - runtime: "ollama" | "mlx"
  - model: Model name (Ollama tag) or path/HuggingFace ID (MLX)
  - force: Override RAM safety check (default false)`,
      inputSchema: {
        runtime: z.enum(["ollama", "mlx"]).describe("Inference runtime to use"),
        model: z.string().min(1).describe("Model name, path, or HuggingFace ID"),
        force: z.boolean().default(false).describe("Override RAM safety check"),
      },
      annotations: {
        readOnlyHint: false,
        destructiveHint: false,
        idempotentHint: false,
        openWorldHint: true,
      },
    },
    async ({ runtime, model, force }) => {
      const config = loadConfig();
      const ram = await getAvailableRAM();

      // For Ollama models, check size from ollama list
      if (runtime === "ollama" && !force) {
        const listResult = await runCommand("ollama", ["list"]);
        if (listResult.exitCode === 0) {
          const lines = listResult.stdout.split("\n");
          for (const line of lines) {
            if (line.startsWith(model) || line.includes(model)) {
              const sizeMatch = line.match(/([\d.]+)\s*(GB|MB)/i);
              if (sizeMatch) {
                const val = parseFloat(sizeMatch[1]);
                const sizeMB = sizeMatch[2].toUpperCase() === "GB" ? val * 1024 : val;
                if (!modelFitsInRAM(sizeMB, ram.availableMB)) {
                  return {
                    content: [{
                      type: "text",
                      text: JSON.stringify({
                        error: "MODEL_TOO_LARGE",
                        model,
                        modelSizeGB: Math.round(sizeMB / 1024 * 10) / 10,
                        requiredGB: Math.round(sizeMB * 1.2 / 1024 * 10) / 10,
                        availableGB: Math.round(ram.availableMB / 1024 * 10) / 10,
                        suggestion: "Free memory first: stop other models (optimac_model_unload), purge memory (optimac_purge_memory), or use a smaller model.",
                        override: "Set force=true to bypass this check (may cause swap thrashing).",
                      }, null, 2),
                    }],
                    isError: true,
                  };
                }
              }
              break;
            }
          }
        }
      }

      // For local files, check file size
      if (!force && existsSync(model)) {
        try {
          const stat = statSync(model);
          const sizeMB = stat.size / (1024 * 1024);
          if (!modelFitsInRAM(sizeMB, ram.availableMB)) {
            return {
              content: [{
                type: "text",
                text: JSON.stringify({
                  error: "MODEL_TOO_LARGE",
                  model,
                  modelSizeGB: Math.round(sizeMB / 1024 * 10) / 10,
                  requiredGB: Math.round(sizeMB * 1.2 / 1024 * 10) / 10,
                  availableGB: Math.round(ram.availableMB / 1024 * 10) / 10,
                  suggestion: "Free memory first or use a smaller quantization.",
                  override: "Set force=true to bypass.",
                }, null, 2),
              }],
              isError: true,
            };
          }
        } catch { /* can't stat, proceed anyway */ }
      }

      // SERVE with selected runtime
      if (runtime === "ollama") {
        // Ensure Ollama is running
        const ollamaPort = config.aiStackPorts.ollama;
        if (!(await checkPort(ollamaPort))) {
          await runCommand("nohup", ["ollama", "serve", "&"], { shell: true, timeout: 5000 });
          let retries = 10;
          while (retries > 0) {
            if (await checkPort(ollamaPort)) break;
            await new Promise((r) => setTimeout(r, 1000));
            retries--;
          }
        }

        // Load the model (ollama run with /bye to just load it)
        const result = await runCommand(
          `echo "/bye" | ollama run "${model}"`,
          [],
          { shell: true, timeout: LONG_TIMEOUT }
        );

        // Check if it loaded
        const psResult = await runCommand("ollama", ["ps"]);

        return {
          content: [{
            type: "text",
            text: JSON.stringify({
              status: result.exitCode === 0 ? "loaded" : "error",
              runtime: "ollama",
              model,
              port: ollamaPort,
              api: `http://127.0.0.1:${ollamaPort}/v1`,
              runningModels: psResult.stdout,
              message: result.exitCode === 0
                ? `Model '${model}' loaded in Ollama. API ready at :${ollamaPort}`
                : `Failed to load: ${result.stderr}`,
            }, null, 2),
          }],
        };
      } else {
        // MLX runtime
        const mlxPort = config.aiStackPorts.mlx;

        // Stop existing MLX server if running
        if (await checkPort(mlxPort)) {
          await runCommand("pkill", ["-f", "mlx_lm.server"]);
          await new Promise((r) => setTimeout(r, 2000));
        }

        // Start MLX server
        await runCommand(
          `nohup python3 -m mlx_lm.server --model "${model}" --port ${mlxPort} > /tmp/mlx-server.log 2>&1 &`,
          [],
          { shell: true, timeout: 5000 }
        );

        // Wait for port
        let retries = 20;
        while (retries > 0) {
          if (await checkPort(mlxPort)) break;
          await new Promise((r) => setTimeout(r, 2000));
          retries--;
        }

        const running = await checkPort(mlxPort);
        return {
          content: [{
            type: "text",
            text: JSON.stringify({
              status: running ? "serving" : "starting",
              runtime: "mlx",
              model,
              port: mlxPort,
              api: `http://127.0.0.1:${mlxPort}/v1`,
              message: running
                ? `MLX server running with '${model}' at :${mlxPort}`
                : "Server starting (model download may be in progress). Check /tmp/mlx-server.log",
              log: "/tmp/mlx-server.log",
            }, null, 2),
          }],
        };
      }
    }
  );

  // ---- UNLOAD / STOP MODEL ----
  server.registerTool(
    "optimac_model_unload",
    {
      title: "Unload/Stop Model",
      description: `Unload a running model to free RAM. Stops the serving process.

For Ollama: Unloads the model from memory (keeps it downloaded).
For MLX: Stops the mlx_lm.server process entirely.
For all: Stops all running inference servers.

After unloading, run optimac_purge_memory to reclaim freed pages immediately.`,
      inputSchema: {
        runtime: z.enum(["ollama", "mlx", "all"]).default("all").describe("Which runtime to unload from"),
      },
      annotations: {
        readOnlyHint: false,
        destructiveHint: false,
        idempotentHint: true,
        openWorldHint: false,
      },
    },
    async ({ runtime }) => {
      const config = loadConfig();
      const results: Record<string, string> = {};

      if (runtime === "ollama" || runtime === "all") {
        // Unload all Ollama models (set keepalive to 0)
        const psResult = await runCommand("ollama", ["ps"]);
        if (psResult.exitCode === 0 && psResult.stdout.trim()) {
          // Parse running model names
          const lines = psResult.stdout.split("\n").filter(Boolean).slice(1);
          for (const line of lines) {
            const modelName = line.trim().split(/\s+/)[0];
            if (modelName) {
              await runCommand(
                `curl -s http://127.0.0.1:${config.aiStackPorts.ollama}/api/generate -d '{"model":"${modelName}","keep_alive":0}'`,
                [],
                { shell: true, timeout: 10000 }
              );
              results[`ollama:${modelName}`] = "unloaded";
            }
          }
        }
        if (Object.keys(results).length === 0 && (runtime === "ollama")) {
          results["ollama"] = "no models were loaded";
        }
      }

      if (runtime === "mlx" || runtime === "all") {
        const mlxUp = await checkPort(config.aiStackPorts.mlx);
        if (mlxUp) {
          await runCommand("pkill", ["-f", "mlx_lm.server"]);
          await new Promise((r) => setTimeout(r, 2000));
          results["mlx"] = "server stopped";
        } else {
          results["mlx"] = "was not running";
        }
      }

      // Get RAM after unload
      const ram = await getAvailableRAM();

      return {
        content: [{
          type: "text",
          text: JSON.stringify({
            status: "complete",
            unloaded: results,
            ramAfterUnload: {
              availableGB: Math.round(ram.availableMB / 1024 * 10) / 10,
              usedGB: Math.round(ram.usedMB / 1024 * 10) / 10,
            },
            nextStep: "Run optimac_purge_memory to immediately reclaim freed pages.",
          }, null, 2),
        }],
      };
    }
  );

  // ---- RUNNING MODELS STATUS ----
  server.registerTool(
    "optimac_models_running",
    {
      title: "Currently Running Models",
      description: `Show all models currently loaded and serving across all runtimes.
Returns running models from Ollama (via ollama ps) and MLX (via port check + API).`,
      inputSchema: {},
      annotations: {
        readOnlyHint: true,
        destructiveHint: false,
        idempotentHint: true,
        openWorldHint: false,
      },
    },
    async () => {
      const config = loadConfig();
      const ram = await getAvailableRAM();
      const running: Record<string, unknown> = {};

      // Ollama
      const ollamaUp = await checkPort(config.aiStackPorts.ollama);
      if (ollamaUp) {
        const psResult = await runCommand("ollama", ["ps"]);
        running["ollama"] = {
          serverRunning: true,
          port: config.aiStackPorts.ollama,
          loadedModels: psResult.exitCode === 0 ? psResult.stdout : "unable to check",
        };
      } else {
        running["ollama"] = { serverRunning: false };
      }

      // MLX
      const mlxUp = await checkPort(config.aiStackPorts.mlx);
      if (mlxUp) {
        let models = "unknown";
        try {
          const modelsResult = await runCommand(
            "curl",
            ["-s", `http://127.0.0.1:${config.aiStackPorts.mlx}/v1/models`],
          );
          if (modelsResult.exitCode === 0) {
            const parsed = JSON.parse(modelsResult.stdout);
            models = (parsed.data ?? []).map((m: { id: string }) => m.id).join(", ");
          }
        } catch { /* API unavailable */ }
        running["mlx"] = {
          serverRunning: true,
          port: config.aiStackPorts.mlx,
          model: models,
        };
      } else {
        running["mlx"] = { serverRunning: false };
      }

      // LM Studio
      const lmUp = await checkPort(config.aiStackPorts.lmstudio);
      if (lmUp) {
        let models = "unknown";
        try {
          const modelsResult = await runCommand(
            "curl",
            ["-s", `http://127.0.0.1:${config.aiStackPorts.lmstudio}/v1/models`],
          );
          if (modelsResult.exitCode === 0) {
            const parsed = JSON.parse(modelsResult.stdout);
            models = (parsed.data ?? []).map((m: { id: string }) => m.id).join(", ");
          }
        } catch { /* API unavailable */ }
        running["lmstudio"] = {
          serverRunning: true,
          port: config.aiStackPorts.lmstudio,
          model: models,
        };
      } else {
        running["lmstudio"] = { serverRunning: false };
      }

      return {
        content: [{
          type: "text",
          text: JSON.stringify({
            ram: {
              totalGB: Math.round(ram.totalMB / 1024 * 10) / 10,
              usedGB: Math.round(ram.usedMB / 1024 * 10) / 10,
              availableGB: Math.round(ram.availableMB / 1024 * 10) / 10,
            },
            services: running,
          }, null, 2),
        }],
      };
    }
  );

  // ---- SET MODEL DIRECTORY ----
  server.registerTool(
    "optimac_model_dir_set",
    {
      title: "Set Model Base Directory",
      description: `Set the base directory where model files are stored.
This directory is scanned by optimac_models_available to find downloadable model files.

Args:
  - path: Absolute path to the model directory (e.g., "/Volumes/M2 Raid0/AI Models")`,
      inputSchema: {
        path: z.string().min(1).describe("Absolute path to model directory"),
      },
      annotations: {
        readOnlyHint: false,
        destructiveHint: false,
        idempotentHint: true,
        openWorldHint: false,
      },
    },
    async ({ path }) => {
      if (!existsSync(path)) {
        return {
          content: [{ type: "text", text: JSON.stringify({ error: `Directory does not exist: ${path}` }) }],
          isError: true,
        };
      }

      const config = loadConfig();
      config.modelBaseDir = path;
      saveConfig(config);

      return {
        content: [{
          type: "text",
          text: JSON.stringify({
            status: "saved",
            modelBaseDir: path,
            message: `Model directory set to: ${path}. Use optimac_models_available to scan for models.`,
          }, null, 2),
        }],
      };
    }
  );

  // ---- GET MODEL DIRECTORY ----
  server.registerTool(
    "optimac_model_dir_get",
    {
      title: "Get Model Base Directory",
      description: `Get the currently configured model base directory.`,
      inputSchema: {},
      annotations: {
        readOnlyHint: true,
        destructiveHint: false,
        idempotentHint: true,
        openWorldHint: false,
      },
    },
    async () => {
      const config = loadConfig();
      return {
        content: [{
          type: "text",
          text: JSON.stringify({
            modelBaseDir: config.modelBaseDir || "(not set)",
            exists: config.modelBaseDir ? existsSync(config.modelBaseDir) : false,
          }, null, 2),
        }],
      };
    }
  );

  // ---- CHAT / INFERENCE WITH LOADED MODEL ----
  server.registerTool(
    "optimac_model_chat",
    {
      title: "Chat with Loaded Model",
      description: `Send a prompt to a currently loaded model and get a response.
Uses the OpenAI-compatible /v1/chat/completions endpoint exposed by Ollama, MLX, or LM Studio.

Automatically detects which runtime has a model loaded. If multiple are running,
specify the runtime parameter.

Args:
  - prompt: The user message to send
  - system: Optional system prompt
  - runtime: "auto" (detect first available), "ollama", "mlx", or "lmstudio"
  - temperature: Sampling temperature (default 0.3)
  - max_tokens: Maximum tokens to generate (default 1024)`,
      inputSchema: {
        prompt: z.string().min(1).describe("The message to send to the model"),
        system: z.string().optional().describe("Optional system prompt"),
        runtime: z.enum(["auto", "ollama", "mlx", "lmstudio"]).default("auto").describe("Which runtime to use (auto-detect by default)"),
        temperature: z.number().min(0).max(2).default(0.3).describe("Sampling temperature"),
        max_tokens: z.number().positive().default(1024).describe("Max tokens to generate"),
      },
      annotations: {
        readOnlyHint: true,
        destructiveHint: false,
        idempotentHint: false,
        openWorldHint: true,
      },
    },
    async ({ prompt, system, runtime, temperature, max_tokens }) => {
      // Delegate to the shared inference engine
      const runtimeOpt = runtime === "auto" ? undefined : runtime as "ollama" | "mlx" | "lmstudio";

      const result = await inferLocal(prompt, {
        system,
        maxTokens: max_tokens,
        temperature,
        runtime: runtimeOpt,
        timeout: 120000,
      });

      if (result.error) {
        return {
          content: [{
            type: "text",
            text: JSON.stringify({
              error: result.error,
              runtime: result.runtime || runtime,
              model: result.model,
            }, null, 2),
          }],
          isError: true,
        };
      }

      return {
        content: [{
          type: "text",
          text: JSON.stringify({
            runtime: result.runtime,
            model: result.model,
            response: result.response,
            usage: result.usage,
          }, null, 2),
        }],
      };
    }
  );

  // ---- RAM CHECK FOR A SPECIFIC MODEL ----
  server.registerTool(
    "optimac_model_ram_check",
    {
      title: "Check if Model Fits in RAM",
      description: `Check if a specific model can be loaded without causing swap thrashing.
Takes model size in GB and checks against available RAM with 20% headroom.

Use this before loading a model to verify it will run smoothly.

Args:
  - size_gb: Model size in GB (e.g., 4.7 for a 4.7GB model)
  - model_name: Optional model name for the report`,
      inputSchema: {
        size_gb: z.number().positive().describe("Model size in GB"),
        model_name: z.string().optional().describe("Optional model name for the report"),
      },
      annotations: {
        readOnlyHint: true,
        destructiveHint: false,
        idempotentHint: true,
        openWorldHint: false,
      },
    },
    async ({ size_gb, model_name }) => {
      const ram = await getAvailableRAM();
      const sizeMB = size_gb * 1024;
      const fits = modelFitsInRAM(sizeMB, ram.availableMB);
      const requiredGB = Math.round(sizeMB * 1.2 / 1024 * 10) / 10;
      const availableGB = Math.round(ram.availableMB / 1024 * 10) / 10;
      const headroomGB = Math.round((ram.availableMB - sizeMB * 1.2) / 1024 * 10) / 10;

      return {
        content: [{
          type: "text",
          text: JSON.stringify({
            model: model_name || `${size_gb}GB model`,
            modelSizeGB: size_gb,
            requiredWithHeadroomGB: requiredGB,
            availableRAM_GB: availableGB,
            totalRAM_GB: Math.round(ram.totalMB / 1024 * 10) / 10,
            fits: fits,
            headroomAfterLoadGB: fits ? headroomGB : 0,
            verdict: fits
              ? `Safe to load. ${headroomGB}GB headroom remaining after load.`
              : `NOT SAFE. Need ${requiredGB}GB but only ${availableGB}GB available. Free ${Math.round((requiredGB - availableGB) * 10) / 10}GB first.`,
            suggestions: fits ? [] : [
              "Unload current models: optimac_model_unload",
              "Purge memory: optimac_purge_memory",
              "Use a smaller quantization (e.g., Q4 instead of Q8)",
              "Kill memory-heavy processes: optimac_top_processes sort_by=memory",
            ],
          }, null, 2),
        }],
      };
    }
  );
}
