/**
 * AI stack management tools: Ollama, LM Studio, MLX, OpenClaw, Claude Code.
 * Start, stop, health-check, and manage AI inference services.
 */

import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { z } from "zod";
import { runCommand, LONG_TIMEOUT } from "../services/shell.js";
import { loadConfig } from "../services/config.js";
import { checkPort, httpGet, waitForPort } from "../services/net.js";

export function registerAIStackTools(server: McpServer): void {
  // ---- AI STACK STATUS ----
  server.registerTool(
    "optimac_ai_stack_status",
    {
      title: "AI Stack Status",
      description: `Check the status of all AI inference services: Ollama, LM Studio, MLX server.

Returns for each service:
  - running: whether the service is responding
  - port: which port it's listening on
  - models: loaded models (if API supports it)
  - memoryMB: approximate RSS of the service process

This is the first thing to check when inference feels slow or unresponsive.`,
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
      const stack: Record<string, Record<string, unknown>> = {};

      // Ollama
      const ollamaPort = config.aiStackPorts.ollama;
      const ollamaUp = await checkPort(ollamaPort);
      stack["ollama"] = { running: ollamaUp, port: ollamaPort };

      if (ollamaUp) {
        try {
          const tags = await httpGet(`http://127.0.0.1:${ollamaPort}/api/tags`);
          if (tags.status === 200) {
            const parsed = JSON.parse(tags.body);
            stack["ollama"]["models"] = (parsed.models ?? []).map(
              (m: { name: string; size: number }) => ({
                name: m.name,
                sizeMB: Math.round((m.size ?? 0) / (1024 * 1024)),
              })
            );
          }
        } catch (e) { console.error("[optimac] Ollama API unavailable:", e instanceof Error ? e.message : e); }

        // Get Ollama process RSS
        const ps = await runCommand("ps", ["aux"], { shell: true });
        const ollamaLine = ps.stdout.split("\n").find((l) => l.includes("ollama") && l.includes("serve"));
        if (ollamaLine) {
          const parts = ollamaLine.trim().split(/\s+/);
          stack["ollama"]["rssMB"] = Math.round(parseInt(parts[5] ?? "0", 10) / 1024);
          stack["ollama"]["pid"] = parseInt(parts[1] ?? "0", 10);
        }
      }

      // LM Studio
      const lmPort = config.aiStackPorts.lmstudio;
      const lmUp = await checkPort(lmPort);
      stack["lmstudio"] = { running: lmUp, port: lmPort };

      if (lmUp) {
        try {
          const models = await httpGet(`http://127.0.0.1:${lmPort}/v1/models`);
          if (models.status === 200) {
            const parsed = JSON.parse(models.body);
            stack["lmstudio"]["models"] = (parsed.data ?? []).map(
              (m: { id: string }) => m.id
            );
          }
        } catch (e) { console.error("[optimac] LM Studio API unavailable:", e instanceof Error ? e.message : e); }
      }

      // MLX Server
      const mlxPort = config.aiStackPorts.mlx;
      const mlxUp = await checkPort(mlxPort);
      stack["mlx_server"] = { running: mlxUp, port: mlxPort };

      if (mlxUp) {
        try {
          const models = await httpGet(`http://127.0.0.1:${mlxPort}/v1/models`);
          if (models.status === 200) {
            const parsed = JSON.parse(models.body);
            stack["mlx_server"]["models"] = (parsed.data ?? []).map(
              (m: { id: string }) => m.id
            );
          }
        } catch (e) { console.error("[optimac] MLX API unavailable:", e instanceof Error ? e.message : e); }
      }

      // OpenClaw
      const ocResult = await runCommand("pgrep", ["-f", "openclaw"]);
      stack["openclaw"] = {
        running: ocResult.exitCode === 0,
        pids: ocResult.stdout.split("\n").filter(Boolean).map(Number),
      };

      // Claude Code
      const ccResult = await runCommand("pgrep", ["-f", "claude"]);
      stack["claude_code"] = {
        running: ccResult.exitCode === 0,
        pids: ccResult.stdout.split("\n").filter(Boolean).map(Number),
      };

      return { content: [{ type: "text", text: JSON.stringify(stack, null, 2) }] };
    }
  );

  // ---- START OLLAMA ----
  server.registerTool(
    "optimac_ollama_start",
    {
      title: "Start Ollama",
      description: `Start the Ollama inference server. Ollama will serve models on port 11434.

If Ollama is already running, this is a no-op. If it's not installed, returns an error with install instructions.`,
      inputSchema: {},
      annotations: {
        readOnlyHint: false,
        destructiveHint: false,
        idempotentHint: true,
        openWorldHint: false,
      },
    },
    async () => {
      // Check if already running
      const config = loadConfig();
      if (await checkPort(config.aiStackPorts.ollama)) {
        return { content: [{ type: "text", text: JSON.stringify({ status: "already_running", port: config.aiStackPorts.ollama }, null, 2) }] };
      }

      // Check if installed
      const which = await runCommand("which", ["ollama"]);
      if (which.exitCode !== 0) {
        return {
          content: [{
            type: "text",
            text: JSON.stringify({
              status: "not_installed",
              install: "curl -fsSL https://ollama.com/install.sh | sh",
            }, null, 2),
          }],
          isError: true,
        };
      }

      // Start in background
      const result = await runCommand(
        "nohup",
        ["ollama", "serve", "&"],
        { shell: true, timeout: 5000 }
      );

      // Wait for port to come up
      let retries = 10;
      while (retries > 0) {
        if (await checkPort(config.aiStackPorts.ollama)) break;
        await new Promise((r) => setTimeout(r, 1000));
        retries--;
      }

      const running = await checkPort(config.aiStackPorts.ollama);
      return {
        content: [{
          type: "text",
          text: JSON.stringify({
            status: running ? "started" : "failed",
            port: config.aiStackPorts.ollama,
            message: running ? "Ollama server is now running" : "Ollama did not start within 10 seconds",
          }, null, 2),
        }],
      };
    }
  );

  // ---- STOP OLLAMA ----
  server.registerTool(
    "optimac_ollama_stop",
    {
      title: "Stop Ollama",
      description: `Stop the Ollama inference server. Useful for freeing memory before loading a different model in LM Studio or MLX.

On a 16GB M4, you almost certainly need to stop Ollama before running a large model elsewhere.`,
      inputSchema: {},
      annotations: {
        readOnlyHint: false,
        destructiveHint: false,
        idempotentHint: true,
        openWorldHint: false,
      },
    },
    async () => {
      const result = await runCommand("pkill", ["-f", "ollama serve"]);
      // Give it a moment
      await new Promise((r) => setTimeout(r, 2000));

      const config = loadConfig();
      const stillRunning = await checkPort(config.aiStackPorts.ollama);

      return {
        content: [{
          type: "text",
          text: JSON.stringify({
            status: stillRunning ? "still_running" : "stopped",
            message: stillRunning
              ? "Ollama is still running. Try optimac_kill_process with the PID."
              : "Ollama server stopped. Run optimac_purge_memory to reclaim freed pages.",
          }, null, 2),
        }],
      };
    }
  );

  // ---- OLLAMA MODEL MANAGEMENT ----
  server.registerTool(
    "optimac_ollama_models",
    {
      title: "Ollama Model Management",
      description: `List, pull, or remove Ollama models.

Args:
  - action: "list" | "pull" | "remove"
  - model: Model name (required for pull/remove, e.g., "llama3.1:8b-instruct-q4_0")

Pull downloads a model. Remove deletes it from disk. List shows all downloaded models with sizes.`,
      inputSchema: {
        action: z.enum(["list", "pull", "remove"]).describe("Action to perform"),
        model: z.string().optional().describe("Model name (required for pull/remove)"),
      },
      annotations: {
        readOnlyHint: false,
        destructiveHint: false,
        idempotentHint: false,
        openWorldHint: true,
      },
    },
    async ({ action, model }) => {
      if (action === "list") {
        const result = await runCommand("ollama", ["list"]);
        return { content: [{ type: "text", text: result.exitCode === 0 ? result.stdout : `Error: ${result.stderr}` }] };
      }

      if (!model) {
        return { content: [{ type: "text", text: "Error: model name is required for pull/remove" }], isError: true };
      }

      if (action === "pull") {
        const result = await runCommand("ollama", ["pull", model], { timeout: LONG_TIMEOUT });
        return {
          content: [{
            type: "text",
            text: JSON.stringify({
              status: result.exitCode === 0 ? "pulled" : "error",
              model,
              output: result.stdout || result.stderr,
            }, null, 2),
          }],
        };
      }

      if (action === "remove") {
        const result = await runCommand("ollama", ["rm", model]);
        return {
          content: [{
            type: "text",
            text: JSON.stringify({
              status: result.exitCode === 0 ? "removed" : "error",
              model,
              message: result.exitCode === 0
                ? `Model ${model} removed. Run optimac_purge_memory to reclaim disk cache pages.`
                : result.stderr,
            }, null, 2),
          }],
        };
      }

      return { content: [{ type: "text", text: "Error: invalid action" }], isError: true };
    }
  );

  // ---- MLX SERVER START ----
  server.registerTool(
    "optimac_mlx_serve",
    {
      title: "Start MLX Server",
      description: `Start an MLX-LM inference server for a specific model.

Args:
  - model: HuggingFace model ID (e.g., "mlx-community/Qwen2.5-7B-Instruct-4bit")
  - port: Port to serve on (default 8080)

Starts mlx_lm.server as a background process. Uses native Metal GPU acceleration.

IMPORTANT: On 16GB, stop Ollama first if it has a model loaded. Only one large model fits at a time.`,
      inputSchema: {
        model: z.string().min(1).describe("HuggingFace model ID (use mlx-community/ prefix for pre-converted)"),
        port: z.number().int().min(1024).max(65535).default(8080).describe("Port to serve on"),
      },
      annotations: {
        readOnlyHint: false,
        destructiveHint: false,
        idempotentHint: false,
        openWorldHint: true,
      },
    },
    async ({ model, port }) => {
      // Check if port is already in use
      if (await checkPort(port)) {
        return {
          content: [{
            type: "text",
            text: `Error: Port ${port} is already in use. Stop the existing service first or use a different port.`,
          }],
          isError: true,
        };
      }

      // Check if mlx_lm is installed
      const which = await runCommand("which", ["mlx_lm.server"], { shell: true });
      if (which.exitCode !== 0) {
        return {
          content: [{
            type: "text",
            text: JSON.stringify({
              status: "not_installed",
              install: "pip install mlx-lm --break-system-packages",
            }, null, 2),
          }],
          isError: true,
        };
      }

      // Start in background
      await runCommand(
        `nohup mlx_lm.server --model "${model}" --port ${port} > /tmp/mlx-server.log 2>&1 &`,
        [],
        { shell: true, timeout: 5000 }
      );

      // Wait for port
      let retries = 15;
      while (retries > 0) {
        if (await checkPort(port)) break;
        await new Promise((r) => setTimeout(r, 2000));
        retries--;
      }

      const running = await checkPort(port);
      return {
        content: [{
          type: "text",
          text: JSON.stringify({
            status: running ? "started" : "starting",
            model,
            port,
            message: running
              ? `MLX server running at http://127.0.0.1:${port}/v1 (OpenAI-compatible)`
              : "Server is starting (model download may be in progress). Check /tmp/mlx-server.log",
            log: "/tmp/mlx-server.log",
          }, null, 2),
        }],
      };
    }
  );

  // ---- STOP MLX SERVER ----
  server.registerTool(
    "optimac_mlx_stop",
    {
      title: "Stop MLX Server",
      description: `Stop any running mlx_lm.server processes. Frees GPU memory for other tasks.`,
      inputSchema: {},
      annotations: {
        readOnlyHint: false,
        destructiveHint: false,
        idempotentHint: true,
        openWorldHint: false,
      },
    },
    async () => {
      const result = await runCommand("pkill", ["-f", "mlx_lm.server"]);
      await new Promise((r) => setTimeout(r, 2000));

      return {
        content: [{
          type: "text",
          text: JSON.stringify({
            status: "stopped",
            message: "MLX server processes terminated. Run optimac_purge_memory to reclaim pages.",
          }, null, 2),
        }],
      };
    }
  );

  // ---- SWAP MODEL (the smart one) ----
  server.registerTool(
    "optimac_swap_model",
    {
      title: "Smart Model Swap",
      description: `Intelligently swap the currently loaded model for a different one. Handles the full lifecycle:

1. Identifies what's currently running (Ollama/MLX/LM Studio)
2. Stops the current inference server
3. Purges freed memory
4. Starts the new model on the specified runtime

This is the key tool for 16GB systems where only one model fits at a time.

Args:
  - runtime: "ollama" | "mlx" (which runtime to use for the new model)
  - model: Model identifier (Ollama tag or HuggingFace ID)
  - port: Port for the new server (default: runtime default)`,
      inputSchema: {
        runtime: z.enum(["ollama", "mlx"]).describe("Runtime for the new model"),
        model: z.string().min(1).describe("Model identifier"),
        port: z.number().int().optional().describe("Port override"),
      },
      annotations: {
        readOnlyHint: false,
        destructiveHint: true,
        idempotentHint: false,
        openWorldHint: true,
      },
    },
    async ({ runtime, model, port }) => {
      const config = loadConfig();
      const steps: Record<string, string> = {};

      // Step 1: Stop existing inference servers
      const ollamaUp = await checkPort(config.aiStackPorts.ollama);
      if (ollamaUp) {
        await runCommand("pkill", ["-f", "ollama serve"]);
        steps["stop_ollama"] = "stopped";
      }

      const mlxUp = await checkPort(config.aiStackPorts.mlx);
      if (mlxUp) {
        await runCommand("pkill", ["-f", "mlx_lm.server"]);
        steps["stop_mlx"] = "stopped";
      }

      // Step 2: Wait for processes to die
      await new Promise((r) => setTimeout(r, 3000));

      // Step 3: Purge memory
      await runCommand("sudo", ["purge"], { shell: true, timeout: LONG_TIMEOUT });
      steps["purge_memory"] = "done";

      // Step 4: Start new model
      if (runtime === "ollama") {
        const targetPort = port ?? config.aiStackPorts.ollama;
        await runCommand("nohup", ["ollama", "serve", "&"], { shell: true, timeout: 5000 });

        let retries = 10;
        while (retries > 0) {
          if (await checkPort(targetPort)) break;
          await new Promise((r) => setTimeout(r, 1000));
          retries--;
        }

        // Pull and run the model
        await runCommand("ollama", ["run", model], { timeout: LONG_TIMEOUT });
        steps["start_model"] = `ollama running ${model} on port ${targetPort}`;
      } else {
        const targetPort = port ?? config.aiStackPorts.mlx;
        await runCommand(
          `nohup mlx_lm.server --model "${model}" --port ${targetPort} > /tmp/mlx-server.log 2>&1 &`,
          [],
          { shell: true, timeout: 5000 }
        );

        let retries = 15;
        while (retries > 0) {
          if (await checkPort(targetPort)) break;
          await new Promise((r) => setTimeout(r, 2000));
          retries--;
        }

        steps["start_model"] = `mlx serving ${model} on port ${targetPort}`;
      }

      return {
        content: [{
          type: "text",
          text: JSON.stringify({ status: "complete", steps }, null, 2),
        }],
      };
    }
  );

  // ---- GPU STATISTICS ----
  server.registerTool(
    "optimac_gpu_stats",
    {
      title: "GPU Statistics",
      description: "Get detailed GPU power, frequency, and utilization metrics using powermetrics.",
      inputSchema: {},
      annotations: {
        readOnlyHint: true,
        destructiveHint: false, // Reading metrics isn't destructive
        idempotentHint: true,
        openWorldHint: false,
      },
    },
    async () => {
      // powermetrics requires sudo
      const result = await runCommand(
        "sudo",
        ["powermetrics", "--samplers", "gpu_power", "-i", "1000", "-n", "1"],
        { shell: true }
      );

      if (result.exitCode !== 0) {
        return {
          content: [{
            type: "text",
            text: `Error: ${result.stderr}. Ensure passwordless sudo is configured for 'powermetrics'.`,
          }],
          isError: true,
        };
      }

      // Parse output to find GPU relevant lines
      const lines = result.stdout.split("\n");
      const gpuLines = lines.filter((l) => {
        const lower = l.toLowerCase();
        return lower.includes("gpu") || lower.includes("ane") || lower.includes("power") || lower.includes("freq");
      }).slice(0, 20); // cap output

      return {
        content: [{
          type: "text",
          text: gpuLines.join("\n") || "No GPU metrics found in output.",
        }],
      };
    }
  );

  // ---- BENCHMARK MODEL ----
  server.registerTool(
    "optimac_model_benchmark",
    {
      title: "Benchmark Model",
      description: "Run a quick inference benchmark on a model to measure tokens per second. Uses the Ollama HTTP API for accurate timing.",
      inputSchema: {
        model: z.string().describe("Model name (e.g. llama3:latest)"),
        prompt: z.string().default("Explain quantum computing in exactly 100 words.").describe("Prompt to use for benchmarking"),
      },
    },
    async ({ model, prompt }) => {
      const config = loadConfig();
      const ollamaPort = config.aiStackPorts?.ollama ?? 11434;

      // Use Ollama HTTP API (non-streaming) — returns exact token counts
      const start = Date.now();
      try {
        const response = await fetch(`http://localhost:${ollamaPort}/api/generate`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ model, prompt, stream: false }),
          signal: AbortSignal.timeout(120000),
        });

        const elapsed = (Date.now() - start) / 1000;

        if (!response.ok) {
          const errText = await response.text();
          return {
            content: [{ type: "text", text: `Benchmark failed (HTTP ${response.status}): ${errText}` }],
            isError: true,
          };
        }

        const data = await response.json() as {
          response: string;
          total_duration?: number;
          load_duration?: number;
          prompt_eval_count?: number;
          prompt_eval_duration?: number;
          eval_count?: number;
          eval_duration?: number;
        };

        // Ollama returns durations in nanoseconds
        const totalDurS = data.total_duration ? data.total_duration / 1e9 : elapsed;
        const promptDurS = data.prompt_eval_duration ? data.prompt_eval_duration / 1e9 : 0;
        const evalDurS = data.eval_duration ? data.eval_duration / 1e9 : 0;
        const loadDurS = data.load_duration ? data.load_duration / 1e9 : 0;
        const evalTokens = data.eval_count ?? 0;
        const promptTokens = data.prompt_eval_count ?? 0;
        const evalTPS = evalDurS > 0 ? (evalTokens / evalDurS).toFixed(2) : "N/A";
        const promptTPS = promptDurS > 0 ? (promptTokens / promptDurS).toFixed(2) : "N/A";

        return {
          content: [{
            type: "text",
            text: JSON.stringify({
              model,
              totalDurationSeconds: totalDurS.toFixed(2),
              modelLoadSeconds: loadDurS.toFixed(2),
              promptEval: {
                tokens: promptTokens,
                durationSeconds: promptDurS.toFixed(2),
                tokensPerSecond: promptTPS,
              },
              generation: {
                tokens: evalTokens,
                durationSeconds: evalDurS.toFixed(2),
                tokensPerSecond: evalTPS,
              },
              outputSnippet: (data.response ?? "").substring(0, 300),
            }, null, 2),
          }],
        };
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : String(err);
        return {
          content: [{ type: "text", text: `Benchmark failed: ${msg}. Is Ollama running on port ${ollamaPort}?` }],
          isError: true,
        };
      }
    }
  );

  // ---- MLX QUANTIZE ----
  server.registerTool(
    "optimac_mlx_quantize",
    {
      title: "MLX Quantize Model",
      description: "Convert a HuggingFace model to MLX format with 4-bit quantization.",
      inputSchema: {
        model: z.string().describe("HuggingFace model ID (e.g. meta-llama/Llama-3.2-3B-Instruct)"),
      },
    },
    async ({ model }) => {
      const result = await runCommand(
        "python3",
        ["-m", "mlx_lm.convert", "--hf-path", model, "-q"],
        { timeout: 1800000 } // 30 mins
      );

      if (result.exitCode !== 0) {
        return {
          content: [{
            type: "text",
            text: `Quantization failed: ${result.stderr}`,
          }],
          isError: true,
        };
      }

      return {
        content: [{
          type: "text",
          text: `Quantization complete for ${model}.\nOutput:\n${result.stdout.substring(0, 1000)}...`,
        }],
      };
    }
  );
}
