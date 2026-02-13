/**
 * Edge-to-Edge management tools.
 * Configure, test, and manage remote inference endpoints on LANs.
 *
 * 4 tools:
 *   - optimac_edge_add: Add a new edge endpoint
 *   - optimac_edge_remove: Remove an edge endpoint
 *   - optimac_edge_list: List all endpoints with connectivity status
 *   - optimac_edge_test: Test inference on a specific endpoint
 */

import { z } from "zod";
import type { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { loadConfig, saveConfig } from "../services/config.js";
import { inferEdge, probeEdgeEndpoint } from "../services/inference-edge.js";

const RUNTIME_TYPES = ["ollama", "mlx", "lmstudio", "vllm", "anythingllm", "openai-compatible"] as const;

export function registerEdgeTools(server: McpServer): void {

  // ========================================
  // TOOL 1: optimac_edge_add
  // ========================================
  server.registerTool(
    "optimac_edge_add",
    {
      title: "Add Edge Endpoint",
      description: `Register a new edge inference endpoint for Edge-to-Edge routing.

Supports any OpenAI-compatible API server on the local network or same machine:
  - Ollama (remote): http://192.168.1.50:11434
  - MLX server: http://mac-studio.local:8080
  - vLLM: http://nvidia-box:8000
  - AnythingLLM: http://192.168.1.100:3001
  - LM Studio: http://workstation:1234

The endpoint is validated for connectivity before saving.

Args:
  - name: Unique identifier for this endpoint (e.g., "studio-ollama", "nvidia-vllm")
  - url: Base URL of the endpoint (e.g., "http://192.168.1.50:11434")
  - runtime_type: API compatibility type
  - api_key: Optional authentication key
  - default_model: Optional model to request (auto-detected if omitted)
  - priority: Routing priority 1-100 (lower = tried first, default 50)`,
      inputSchema: {
        name: z.string().min(1).regex(/^[a-zA-Z0-9_-]+$/).describe("Unique name for this endpoint (alphanumeric, hyphens, underscores)"),
        url: z.string().url().describe("Base URL of the endpoint (e.g., http://192.168.1.50:11434)"),
        runtime_type: z.enum(RUNTIME_TYPES).default("openai-compatible").describe("Runtime type for API compatibility"),
        api_key: z.string().optional().describe("Optional API key for authentication"),
        default_model: z.string().optional().describe("Default model to use (auto-detected if omitted)"),
        priority: z.number().int().min(1).max(100).default(50).describe("Routing priority: lower = tried first"),
      },
      annotations: { readOnlyHint: false, destructiveHint: false, idempotentHint: true, openWorldHint: true },
    },
    async ({ name, url, runtime_type, api_key, default_model, priority }) => {
      const config = loadConfig();

      // Check if name already exists
      if (config.edgeEndpoints[name]) {
        return {
          content: [{
            type: "text", text: JSON.stringify({
              warning: "ENDPOINT_EXISTS",
              name,
              message: `Edge endpoint "${name}" already exists. It will be updated.`,
              previous: config.edgeEndpoints[name],
            }, null, 2)
          }],
        };
      }

      // Build endpoint config
      const endpoint = {
        url: url.replace(/\/$/, ""),
        runtimeType: runtime_type,
        priority,
        ...(api_key ? { apiKey: api_key } : {}),
        ...(default_model ? { defaultModel: default_model } : {}),
      };

      // Validate connectivity
      const probe = await probeEdgeEndpoint(endpoint as any);

      // Save regardless of connectivity (user might add before server is running)
      config.edgeEndpoints[name] = endpoint as any;
      saveConfig(config);

      return {
        content: [{
          type: "text", text: JSON.stringify({
            status: "added",
            name,
            endpoint,
            connectivity: {
              reachable: probe.reachable,
              latencyMs: probe.latencyMs,
              models: probe.models,
              error: probe.error,
            },
            note: probe.reachable
              ? `Endpoint "${name}" is online with ${probe.models.length} model(s) available.`
              : `Endpoint "${name}" saved but currently unreachable. It will be available when the server starts.`,
          }, null, 2)
        }],
      };
    }
  );

  // ========================================
  // TOOL 2: optimac_edge_remove
  // ========================================
  server.registerTool(
    "optimac_edge_remove",
    {
      title: "Remove Edge Endpoint",
      description: `Remove a registered edge endpoint by name.

Args:
  - name: The name of the endpoint to remove`,
      inputSchema: {
        name: z.string().min(1).describe("Name of the endpoint to remove"),
      },
      annotations: { readOnlyHint: false, destructiveHint: true, idempotentHint: true, openWorldHint: false },
    },
    async ({ name }) => {
      const config = loadConfig();

      if (!config.edgeEndpoints[name]) {
        return {
          content: [{
            type: "text", text: JSON.stringify({
              error: "NOT_FOUND",
              name,
              available: Object.keys(config.edgeEndpoints),
              message: `Edge endpoint "${name}" not found.`,
            }, null, 2)
          }],
          isError: true,
        };
      }

      const removed = config.edgeEndpoints[name];
      delete config.edgeEndpoints[name];
      saveConfig(config);

      return {
        content: [{
          type: "text", text: JSON.stringify({
            status: "removed",
            name,
            removed,
            remaining: Object.keys(config.edgeEndpoints).length,
          }, null, 2)
        }],
      };
    }
  );

  // ========================================
  // TOOL 3: optimac_edge_list
  // ========================================
  server.registerTool(
    "optimac_edge_list",
    {
      title: "List Edge Endpoints",
      description: `List all configured edge endpoints with live connectivity status.

Each endpoint shows: name, URL, runtime type, priority, reachability, latency, available models.

Args:
  - check_connectivity: If true (default), probe each endpoint for status`,
      inputSchema: {
        check_connectivity: z.boolean().default(true).describe("Probe each endpoint for live status"),
      },
      annotations: { readOnlyHint: true, destructiveHint: false, idempotentHint: true, openWorldHint: true },
    },
    async ({ check_connectivity }) => {
      const config = loadConfig();
      const endpoints = config.edgeEndpoints;
      const names = Object.keys(endpoints);

      if (names.length === 0) {
        return {
          content: [{
            type: "text", text: JSON.stringify({
              count: 0,
              endpoints: [],
              message: "No edge endpoints configured. Use optimac_edge_add to register one.",
            }, null, 2)
          }],
        };
      }

      // Sort by priority
      const sorted = names.sort((a, b) => (endpoints[a].priority ?? 50) - (endpoints[b].priority ?? 50));

      const results = [];
      for (const name of sorted) {
        const ep = endpoints[name];
        const entry: Record<string, unknown> = {
          name,
          url: ep.url,
          runtimeType: ep.runtimeType,
          priority: ep.priority,
          defaultModel: ep.defaultModel || "(auto-detect)",
          hasApiKey: !!ep.apiKey,
        };

        if (check_connectivity) {
          const probe = await probeEdgeEndpoint(ep);
          entry.reachable = probe.reachable;
          entry.latencyMs = probe.latencyMs;
          entry.models = probe.models;
          if (probe.error) entry.error = probe.error;
        }

        results.push(entry);
      }

      return {
        content: [{
          type: "text", text: JSON.stringify({
            count: results.length,
            endpoints: results,
          }, null, 2)
        }],
      };
    }
  );

  // ========================================
  // TOOL 4: optimac_edge_test
  // ========================================
  server.registerTool(
    "optimac_edge_test",
    {
      title: "Test Edge Endpoint",
      description: `Send a test prompt to a specific edge endpoint and measure response quality and latency.

Uses a simple test prompt to verify the endpoint can actually perform inference,
not just accept connections. Returns the response, model used, latency, and quality assessment.

Args:
  - name: Name of the configured edge endpoint to test
  - prompt: Optional custom test prompt (default: "Say hello in one sentence.")`,
      inputSchema: {
        name: z.string().min(1).describe("Name of the edge endpoint to test"),
        prompt: z.string().default("Say hello in one sentence.").describe("Test prompt to send"),
      },
      annotations: { readOnlyHint: true, destructiveHint: false, idempotentHint: false, openWorldHint: true },
    },
    async ({ name, prompt }) => {
      const config = loadConfig();
      const endpoint = config.edgeEndpoints[name];

      if (!endpoint) {
        return {
          content: [{
            type: "text", text: JSON.stringify({
              error: "NOT_FOUND",
              name,
              available: Object.keys(config.edgeEndpoints),
            }, null, 2)
          }],
          isError: true,
        };
      }

      const start = Date.now();
      const result = await inferEdge(prompt, endpoint, name, {
        maxTokens: 256,
        temperature: 0.3,
        timeout: 30000,
      });
      const latencyMs = Date.now() - start;

      return {
        content: [{
          type: "text", text: JSON.stringify({
            name,
            url: endpoint.url,
            runtimeType: endpoint.runtimeType,
            test: {
              prompt,
              response: result.response,
              model: result.model,
              latencyMs,
              error: result.error,
              usage: result.usage,
            },
            verdict: result.error
              ? `FAIL: ${result.error}`
              : result.response
                ? `PASS: Endpoint responded in ${latencyMs}ms using model "${result.model}"`
                : "WARN: Endpoint returned empty response",
          }, null, 2)
        }],
      };
    }
  );
}
