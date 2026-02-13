/**
 * Shared inference engine for local model communication.
 * Used by both model-management (model_chat) and model-tasks (bridge tools).
 *
 * Auto-detects running runtime, auto-reloads expired Ollama models,
 * handles all error cases, and returns structured results.
 * Supports both blocking and streaming modes.
 */

import { runCommand } from "./shell.js";
import { loadConfig } from "./config.js";
import { checkPort } from "./net.js";
import { execFile, ChildProcess } from "node:child_process";

export interface InferenceResult {
    response: string;
    model: string;
    runtime: string;
    usage: { prompt_tokens?: number; completion_tokens?: number; total_tokens?: number };
    error?: string;
    partial?: boolean; // true if response was cut short by timeout (streaming)
}

/**
 * Send a prompt to whatever local model is currently running.
 * Auto-detects runtime (Ollama, MLX, LM Studio) by probing configured ports.
 * If Ollama is detected but no model is loaded, attempts to reload the most recently used one.
 *
 * @param prompt - The user-side prompt to send
 * @param options.system - Optional system prompt
 * @param options.maxTokens - Max tokens for response (default 4096)
 * @param options.temperature - Sampling temperature (default 0.2)
 * @param options.runtime - Force a specific runtime instead of auto-detecting ("ollama" | "mlx" | "lmstudio")
 * @param options.timeout - Request timeout in ms (default 180000 = 3 min)
 * @param options.stream - Use streaming mode (returns partial results on timeout)
 */
export async function inferLocal(
    prompt: string,
    options: {
        system?: string;
        maxTokens?: number;
        temperature?: number;
        runtime?: "ollama" | "mlx" | "lmstudio";
        timeout?: number;
        stream?: boolean;
    } = {}
): Promise<InferenceResult> {
    const config = loadConfig();
    const { system, maxTokens = 4096, temperature = 0.2, timeout = 180000, stream = false } = options;

    const portMap: Record<string, number> = {
        ollama: config.aiStackPorts.ollama,
        mlx: config.aiStackPorts.mlx,
        lmstudio: config.aiStackPorts.lmstudio,
    };

    // Find active runtime (or use forced one)
    let targetRuntime = options.runtime ?? "";
    let targetPort = options.runtime ? portMap[options.runtime] ?? 0 : 0;

    if (!targetRuntime) {
        for (const rt of ["ollama", "mlx", "lmstudio"]) {
            if (await checkPort(portMap[rt])) {
                targetRuntime = rt;
                targetPort = portMap[rt];
                break;
            }
        }
    } else if (targetPort && !(await checkPort(targetPort))) {
        return {
            response: "",
            model: "",
            runtime: targetRuntime,
            usage: {},
            error: `RUNTIME_NOT_RUNNING: ${targetRuntime} is not responding on port ${targetPort}. Start it first with optimac_model_serve.`,
        };
    }

    if (!targetPort) {
        return {
            response: "",
            model: "",
            runtime: "",
            usage: {},
            error: "NO_RUNTIME: No inference server running. Use optimac_model_serve first.",
        };
    }

    // Get model name (Ollama-specific: may need to reload)
    let modelName = "";
    if (targetRuntime === "ollama") {
        const psResult = await runCommand("ollama", ["ps"]);
        if (psResult.exitCode === 0) {
            const lines = psResult.stdout.split("\n").filter(Boolean).slice(1);
            if (lines.length > 0) {
                modelName = lines[0].trim().split(/\s+/)[0];
            }
        }

        // Auto-reload if model expired
        if (!modelName) {
            const listResult = await runCommand("ollama", ["list"]);
            if (listResult.exitCode === 0) {
                const listLines = listResult.stdout.split("\n").filter(Boolean).slice(1);
                if (listLines.length > 0) {
                    const firstModel = listLines[0].trim().split(/\s+/)[0];
                    if (firstModel) {
                        // Use Ollama HTTP API to reload (avoids shell injection from echo pipe)
                        const reloadBody = JSON.stringify({
                            model: firstModel,
                            prompt: "",
                            keep_alive: "5m",
                        });
                        await runCommand(
                            "curl",
                            [
                                "-s", "-X", "POST",
                                `http://127.0.0.1:${targetPort}/api/generate`,
                                "-H", "Content-Type: application/json",
                                "-d", reloadBody,
                            ],
                            { timeout: 60000 }
                        );
                        modelName = firstModel;
                    }
                }
            }
            if (!modelName) {
                return {
                    response: "",
                    model: "",
                    runtime: "ollama",
                    usage: {},
                    error: "NO_MODEL: Ollama running but no models installed.",
                };
            }
        }
    }

    // Build request
    const messages: Array<{ role: string; content: string }> = [];
    if (system) messages.push({ role: "system", content: system });
    messages.push({ role: "user", content: prompt });

    const requestBody = JSON.stringify({
        model: modelName || "default",
        messages,
        temperature,
        max_tokens: maxTokens,
        stream,
    });

    // --- Streaming mode ---
    if (stream) {
        return inferStreaming(targetPort, requestBody, modelName, targetRuntime, timeout);
    }

    // --- Blocking mode ---
    const curlResult = await runCommand(
        "curl",
        [
            "-s", "-X", "POST",
            `http://127.0.0.1:${targetPort}/v1/chat/completions`,
            "-H", "Content-Type: application/json",
            "-d", requestBody,
        ],
        { timeout }
    );

    if (curlResult.exitCode !== 0) {
        return {
            response: "",
            model: modelName,
            runtime: targetRuntime,
            usage: {},
            error: `INFERENCE_FAILED: ${curlResult.stderr}`,
        };
    }

    try {
        const parsed = JSON.parse(curlResult.stdout);
        return {
            response: parsed.choices?.[0]?.message?.content ?? "",
            model: parsed.model || modelName || "unknown",
            runtime: targetRuntime,
            usage: parsed.usage ?? {},
        };
    } catch {
        return {
            response: "",
            model: modelName,
            runtime: targetRuntime,
            usage: {},
            error: `PARSE_ERROR: ${curlResult.stdout.substring(0, 500)}`,
        };
    }
}

/**
 * Streaming inference via curl --no-buffer.
 * Processes Server-Sent Events (SSE) from the OpenAI-compatible API,
 * accumulates response content, and returns partial results on timeout.
 */
function inferStreaming(
    port: number,
    requestBody: string,
    modelName: string,
    runtime: string,
    timeout: number
): Promise<InferenceResult> {
    return new Promise((resolve) => {
        let content = "";
        let model = modelName;
        let usage: InferenceResult["usage"] = {};
        let timedOut = false;
        let proc: ChildProcess | null = null;

        const timer = setTimeout(() => {
            timedOut = true;
            if (proc) proc.kill("SIGTERM");
        }, timeout);

        proc = execFile(
            "curl",
            [
                "-s", "--no-buffer", "-X", "POST",
                `http://127.0.0.1:${port}/v1/chat/completions`,
                "-H", "Content-Type: application/json",
                "-d", requestBody,
            ],
            { maxBuffer: 50 * 1024 * 1024 }, // 50 MB buffer for long generations
            (error, stdout, stderr) => {
                clearTimeout(timer);

                if (error && !timedOut && !content) {
                    resolve({
                        response: "",
                        model,
                        runtime,
                        usage,
                        error: `STREAM_FAILED: ${stderr || error.message}`,
                    });
                    return;
                }

                // If we already accumulated content from events, use that
                if (content) {
                    resolve({
                        response: content,
                        model,
                        runtime,
                        usage,
                        partial: timedOut,
                    });
                    return;
                }

                // Otherwise try to parse the full output (some servers batch)
                try {
                    const lines = stdout.split("\n");
                    for (const line of lines) {
                        if (!line.startsWith("data: ")) continue;
                        const data = line.slice(6).trim();
                        if (data === "[DONE]") continue;
                        try {
                            const chunk = JSON.parse(data);
                            const delta = chunk.choices?.[0]?.delta?.content ?? "";
                            content += delta;
                            if (chunk.model) model = chunk.model;
                            if (chunk.usage) usage = chunk.usage;
                        } catch { /* skip malformed chunk */ }
                    }
                    resolve({
                        response: content || "",
                        model,
                        runtime,
                        usage,
                        partial: timedOut,
                    });
                } catch {
                    resolve({
                        response: "",
                        model,
                        runtime,
                        usage,
                        error: `PARSE_ERROR: ${stdout.substring(0, 500)}`,
                    });
                }
            }
        );

        // Real-time chunk processing from stdout
        if (proc.stdout) {
            let buffer = "";
            proc.stdout.on("data", (chunk: Buffer) => {
                buffer += chunk.toString();
                const lines = buffer.split("\n");
                buffer = lines.pop() ?? ""; // keep incomplete line in buffer

                for (const line of lines) {
                    if (!line.startsWith("data: ")) continue;
                    const data = line.slice(6).trim();
                    if (data === "[DONE]") continue;
                    try {
                        const parsed = JSON.parse(data);
                        const delta = parsed.choices?.[0]?.delta?.content ?? "";
                        content += delta;
                        if (parsed.model) model = parsed.model;
                        if (parsed.usage) usage = parsed.usage;
                    } catch { /* skip malformed */ }
                }
            });
        }
    });
}

