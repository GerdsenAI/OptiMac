/**
 * Edge-to-Edge inference service.
 * Sends prompts to remote OpenAI-compatible endpoints on the LAN or same machine.
 *
 * Supports: Ollama (remote), MLX, LM Studio, vLLM, AnythingLLM, or any
 * server exposing /v1/chat/completions.
 */

import { runCommand } from "./shell.js";
import type { InferenceResult } from "./inference.js";
import type { EdgeEndpoint } from "./config.js";

/**
 * Send a prompt to a remote edge endpoint.
 *
 * @param prompt - The user-side prompt
 * @param endpoint - Edge endpoint configuration (url, apiKey, runtimeType, etc.)
 * @param endpointName - Friendly name of the endpoint (for logging)
 * @param options.system - Optional system prompt
 * @param options.maxTokens - Max tokens for response (default 4096)
 * @param options.temperature - Sampling temperature (default 0.2)
 * @param options.timeout - Request timeout in ms (default 120000 = 2 min)
 */
export async function inferEdge(
    prompt: string,
    endpoint: EdgeEndpoint,
    endpointName: string,
    options: {
        system?: string;
        maxTokens?: number;
        temperature?: number;
        timeout?: number;
    } = {}
): Promise<InferenceResult> {
    const { system, maxTokens = 4096, temperature = 0.2, timeout = 120000 } = options;

    // Detect model if not specified
    let modelName = endpoint.defaultModel || "";
    if (!modelName) {
        modelName = await detectEdgeModel(endpoint);
    }

    // Build messages
    const messages: Array<{ role: string; content: string }> = [];
    if (system) messages.push({ role: "system", content: system });
    messages.push({ role: "user", content: prompt });

    const requestBody = JSON.stringify({
        model: modelName || "default",
        messages,
        temperature,
        max_tokens: maxTokens,
        stream: false,
    });

    // Build headers
    const headers: string[] = ["-H", "Content-Type: application/json"];
    if (endpoint.apiKey) {
        headers.push("-H", `Authorization: Bearer ${endpoint.apiKey}`);
    }

    const url = `${endpoint.url.replace(/\/$/, "")}/v1/chat/completions`;

    const curlResult = await runCommand(
        "curl",
        ["-s", "-X", "POST", url, ...headers, "-d", requestBody],
        { timeout }
    );

    if (curlResult.exitCode !== 0) {
        return {
            response: "",
            model: modelName,
            runtime: `edge:${endpointName}`,
            usage: {},
            error: `EDGE_FAILED: ${curlResult.stderr || `exit code ${curlResult.exitCode}`}`,
        };
    }

    try {
        const parsed = JSON.parse(curlResult.stdout);

        // Handle error responses from the edge server
        if (parsed.error) {
            return {
                response: "",
                model: modelName,
                runtime: `edge:${endpointName}`,
                usage: {},
                error: `EDGE_ERROR: ${typeof parsed.error === "string" ? parsed.error : parsed.error.message || JSON.stringify(parsed.error)}`,
            };
        }

        return {
            response: parsed.choices?.[0]?.message?.content ?? "",
            model: parsed.model || modelName || "unknown",
            runtime: `edge:${endpointName}`,
            usage: parsed.usage ?? {},
        };
    } catch {
        return {
            response: "",
            model: modelName,
            runtime: `edge:${endpointName}`,
            usage: {},
            error: `PARSE_ERROR: ${curlResult.stdout.substring(0, 500)}`,
        };
    }
}

/**
 * Auto-detect the model name from an edge endpoint by querying /v1/models.
 * Returns the first available model name, or empty string on failure.
 */
async function detectEdgeModel(endpoint: EdgeEndpoint): Promise<string> {
    const headers: string[] = ["-H", "Content-Type: application/json"];
    if (endpoint.apiKey) {
        headers.push("-H", `Authorization: Bearer ${endpoint.apiKey}`);
    }

    const url = `${endpoint.url.replace(/\/$/, "")}/v1/models`;

    try {
        const result = await runCommand("curl", ["-s", "--max-time", "5", url, ...headers]);
        if (result.exitCode === 0 && result.stdout) {
            const parsed = JSON.parse(result.stdout);
            const models = parsed.data || parsed.models || [];
            if (models.length > 0) {
                return models[0].id || models[0].name || "";
            }
        }
    } catch {
        // Model detection is best-effort
        console.error(`[optimac] edge model detection failed for ${endpoint.url}`);
    }
    return "";
}

/**
 * Check if an edge endpoint is reachable by probing its health or models endpoint.
 * Returns { reachable, latencyMs, models? }.
 */
export async function probeEdgeEndpoint(endpoint: EdgeEndpoint): Promise<{
    reachable: boolean;
    latencyMs: number;
    models: string[];
    error?: string;
}> {
    const start = Date.now();
    const headers: string[] = [];
    if (endpoint.apiKey) {
        headers.push("-H", `Authorization: Bearer ${endpoint.apiKey}`);
    }

    const url = `${endpoint.url.replace(/\/$/, "")}/v1/models`;

    try {
        const result = await runCommand("curl", ["-s", "--max-time", "5", url, ...headers]);
        const latencyMs = Date.now() - start;

        if (result.exitCode !== 0) {
            return { reachable: false, latencyMs, models: [], error: result.stderr || "connection failed" };
        }

        const parsed = JSON.parse(result.stdout);
        const modelsData = parsed.data || parsed.models || [];
        const models = modelsData.map((m: { id?: string; name?: string }) => m.id || m.name || "unknown");

        return { reachable: true, latencyMs, models };
    } catch (e) {
        return {
            reachable: false,
            latencyMs: Date.now() - start,
            models: [],
            error: e instanceof Error ? e.message : "probe failed",
        };
    }
}
