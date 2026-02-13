/**
 * Model Tasks: Bidirectional AI Bridge
 *
 * These tools enable local ↔ cloud inference as equal peers.
 * Local models can read files, review code, generate content, edit files,
 * summarize codebases, and commit changes — all orchestrated through MCP.
 * When local models need stronger reasoning, they escalate to cloud APIs.
 * When cloud models need privacy or heavy generation, they delegate to local.
 *
 * Architecture:
 *   Local Model (edge, generation/execution) ←→ MCP ←→ Cloud Model (reasoning/knowledge)
 *   Neither side owns the other. The MCP server bridges both directions.
 *
 * Privacy: sensitive work stays on-device. Heavy inference stays local.
 * Cloud handles broader knowledge and stronger reasoning when needed.
 */

import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { z } from "zod";
import { runCommand, LONG_TIMEOUT } from "../services/shell.js";
import { loadConfig } from "../services/config.js";
import { inferLocal } from "../services/inference.js";
import { stripCodeFences, assessResponseQuality } from "../services/text.js";
import {
  readFileSync,
  writeFileSync,
  readdirSync,
  statSync,
  existsSync,
} from "node:fs";
import { join, basename, extname, relative } from "node:path";
import { homedir } from "node:os";

// ---- SAFETY HELPERS ----

/** Reject git refs containing shell metacharacters */
function sanitizeGitRef(ref: string): string {
  if (/[;&|`$(){}\[\]!\\<>\n\r]/.test(ref)) {
    throw new Error(`Unsafe characters in git ref: ${ref}`);
  }
  return ref;
}

/** Check if a path is within the user's home directory */
function isPathSafe(targetPath: string): boolean {
  const home = homedir();
  const resolved = join(targetPath); // resolve relative paths
  return resolved.startsWith(home);
}

// ---- FILE HELPERS ----

function readFileSafe(path: string): string {
  try {
    return readFileSync(path, "utf-8");
  } catch (e) {
    return `[ERROR: Cannot read ${path}: ${e instanceof Error ? e.message : String(e)}]`;
  }
}

/**
 * Collect files matching simple glob-like patterns.
 * Supports: exact paths, directory/* (one level), directory/** (recursive)
 */
function resolveFiles(patterns: string[], maxFiles = 50): Array<{ path: string; content: string; sizeMB: number }> {
  const results: Array<{ path: string; content: string; sizeMB: number }> = [];
  const seen = new Set<string>();

  for (const pattern of patterns) {
    if (seen.size >= maxFiles) break;

    // Exact file
    if (existsSync(pattern) && statSync(pattern).isFile()) {
      if (!seen.has(pattern)) {
        seen.add(pattern);
        const stat = statSync(pattern);
        results.push({
          path: pattern,
          content: readFileSafe(pattern),
          sizeMB: stat.size / (1024 * 1024),
        });
      }
      continue;
    }

    // Directory patterns: dir/*, dir/**
    const isRecursive = pattern.endsWith("/**");
    const isShallow = pattern.endsWith("/*");
    if (isRecursive || isShallow) {
      const dir = pattern.replace(/\/\*\*?$/, "");
      if (existsSync(dir) && statSync(dir).isDirectory()) {
        walkDir(dir, isRecursive ? 10 : 1, 0, results, seen, maxFiles);
      }
    }
  }

  return results;
}

function walkDir(
  dir: string,
  maxDepth: number,
  depth: number,
  results: Array<{ path: string; content: string; sizeMB: number }>,
  seen: Set<string>,
  maxFiles: number
): void {
  if (depth > maxDepth || seen.size >= maxFiles) return;
  try {
    const entries = readdirSync(dir, { withFileTypes: true });
    for (const entry of entries) {
      if (seen.size >= maxFiles) break;
      const full = join(dir, entry.name);
      if (entry.name.startsWith(".") || entry.name === "node_modules" || entry.name === "dist") continue;
      if (entry.isFile()) {
        const ext = extname(entry.name).toLowerCase();
        const textExts = new Set([
          ".ts", ".tsx", ".js", ".jsx", ".py", ".rs", ".go", ".java", ".c", ".cpp", ".h",
          ".md", ".txt", ".json", ".yaml", ".yml", ".toml", ".cfg", ".ini", ".sh", ".bash",
          ".html", ".css", ".scss", ".sql", ".xml", ".csv", ".env", ".gitignore",
          ".swift", ".kt", ".rb", ".php", ".lua", ".r", ".jl", ".zig", ".vim",
          ".dockerfile", ".makefile", ".cmake",
        ]);
        const nameMatches = ["Makefile", "Dockerfile", "LICENSE", "README", ".flake8", ".eslintrc"].some(
          (n) => entry.name === n || entry.name.startsWith(n)
        );
        if (textExts.has(ext) || nameMatches || ext === "") {
          const stat = statSync(full);
          if (stat.size < 512 * 1024) { // Skip files > 512KB
            if (!seen.has(full)) {
              seen.add(full);
              results.push({ path: full, content: readFileSafe(full), sizeMB: stat.size / (1024 * 1024) });
            }
          }
        }
      } else if (entry.isDirectory()) {
        walkDir(full, maxDepth, depth + 1, results, seen, maxFiles);
      }
    }
  } catch { /* permission denied */ }
}

function buildFileContext(files: Array<{ path: string; content: string }>, basePath?: string): string {
  return files.map((f) => {
    const display = basePath ? relative(basePath, f.path) : f.path;
    return `=== FILE: ${display} ===\n${f.content}\n`;
  }).join("\n");
}

// ---- REGISTER ALL BRIDGE TOOLS ----

export function registerModelTaskTools(server: McpServer): void {

  // ========================================
  // TOOL 1: optimac_model_task
  // The universal task executor. Cloud delegates, edge executes.
  // ========================================
  server.registerTool(
    "optimac_model_task",
    {
      title: "Delegate Task to Local Model",
      description: `The universal cloud-to-edge bridge. Send a task to the local model with file context.

Claude (cloud) delegates work to a local model (edge). The local model reads the files,
performs the task, and returns the result. Optionally writes output to a file.

Use this for ANY task you want a local model to handle: refactoring, analysis,
documentation, code generation, translation, data transformation, etc.

Args:
  - task: What you want the model to do (natural language instruction)
  - files: Array of file paths or glob patterns to include as context
  - output_path: Optional path to write the model's response to disk
  - system: Optional system prompt to set model behavior
  - max_tokens: Max tokens for response (default 4096)

Examples:
  "Add type annotations to all functions" + files: ["src/**/*.ts"]
  "Write unit tests for this module" + files: ["src/utils.ts"] + output_path: "tests/utils.test.ts"
  "Translate this README to Spanish" + files: ["README.md"] + output_path: "README.es.md"`,
      inputSchema: {
        task: z.string().min(1).describe("What the local model should do"),
        files: z.array(z.string()).default([]).describe("File paths or glob patterns (e.g., ['src/*.ts', 'README.md'])"),
        output_path: z.string().optional().describe("Write model output to this file path"),
        system: z.string().optional().describe("System prompt for the local model"),
        max_tokens: z.number().positive().default(4096).describe("Max tokens for model response"),
      },
      annotations: { readOnlyHint: false, destructiveHint: false, idempotentHint: false, openWorldHint: true },
    },
    async ({ task, files, output_path, system, max_tokens }) => {
      // Resolve and read files
      const resolvedFiles = files.length > 0 ? resolveFiles(files) : [];
      const fileContext = resolvedFiles.length > 0
        ? `\n\nFILES PROVIDED:\n${buildFileContext(resolvedFiles)}`
        : "";

      const prompt = `${task}${fileContext}\n\nRespond with ONLY the requested output. No explanations, no markdown code fences unless the output itself is markdown.`;

      const result = await inferLocal(prompt, {
        system: system || "You are a precise task executor. Follow instructions exactly. Output only what is requested.",
        maxTokens: max_tokens,
      });

      if (result.error) {
        return { content: [{ type: "text", text: JSON.stringify({ error: result.error, filesRead: resolvedFiles.length }, null, 2) }], isError: true };
      }

      // Write output if requested
      let writeStatus = "";
      if (output_path && result.response) {
        if (!isPathSafe(output_path)) {
          writeStatus = `WRITE BLOCKED: path '${output_path}' is outside the user's home directory`;
        } else {
          try {
            writeFileSync(output_path, result.response, "utf-8");
            writeStatus = `Written to ${output_path}`;
          } catch (e) {
            writeStatus = `WRITE FAILED: ${e instanceof Error ? e.message : String(e)}`;
          }
        }
      }

      return {
        content: [{
          type: "text",
          text: JSON.stringify({
            model: result.model,
            runtime: result.runtime,
            filesRead: resolvedFiles.map((f: { path: string }) => f.path),
            response: result.response,
            outputWritten: writeStatus || undefined,
            usage: result.usage,
          }, null, 2),
        }],
      };
    }
  );

  // ========================================
  // TOOL 2: optimac_model_code_review
  // Git-aware code review by local model.
  // ========================================
  server.registerTool(
    "optimac_model_code_review",
    {
      title: "Code Review by Local Model",
      description: `Have the local model review code changes. Git-aware: can review uncommitted changes,
a specific commit, or a branch diff.

Args:
  - target: "uncommitted" (default), a commit hash, or "branch:main..feature"
  - repo_path: Path to the git repository
  - context_files: Additional files to include for context
  - focus: What to focus on (e.g., "security", "performance", "correctness")`,
      inputSchema: {
        target: z.string().default("uncommitted").describe("What to review: 'uncommitted', commit hash, or 'branch:base..head'"),
        repo_path: z.string().describe("Path to the git repository"),
        context_files: z.array(z.string()).default([]).describe("Additional context files to include"),
        focus: z.string().optional().describe("Review focus: security, performance, correctness, style, etc."),
      },
      annotations: { readOnlyHint: true, destructiveHint: false, idempotentHint: true, openWorldHint: true },
    },
    async ({ target, repo_path, context_files, focus }) => {
      // Get the diff using safe argument arrays with cwd
      let diffOutput: string;
      let diffLabel: string;

      if (target === "uncommitted") {
        const unstaged = await runCommand("git", ["diff"], { cwd: repo_path, timeout: 15000 });
        const staged = await runCommand("git", ["diff", "--cached"], { cwd: repo_path, timeout: 15000 });
        diffOutput = [unstaged.stdout, staged.stdout].filter(Boolean).join("\n");
        diffLabel = "Uncommitted changes (staged + unstaged)";

        if (!diffOutput && unstaged.exitCode !== 0) {
          return { content: [{ type: "text", text: JSON.stringify({ error: `Git command failed: ${unstaged.stderr}` }) }], isError: true };
        }
      } else if (target.startsWith("branch:")) {
        const range = sanitizeGitRef(target.replace("branch:", ""));
        const result = await runCommand("git", ["diff", range], { cwd: repo_path, timeout: 15000 });
        diffOutput = result.stdout;
        diffLabel = `Branch diff: ${range}`;

        if (result.exitCode !== 0 && !diffOutput) {
          return { content: [{ type: "text", text: JSON.stringify({ error: `Git command failed: ${result.stderr}` }) }], isError: true };
        }
      } else {
        const safeTarget = sanitizeGitRef(target);
        const result = await runCommand("git", ["show", safeTarget], { cwd: repo_path, timeout: 15000 });
        diffOutput = result.stdout;
        diffLabel = `Commit: ${safeTarget}`;

        if (result.exitCode !== 0 && !diffOutput) {
          return { content: [{ type: "text", text: JSON.stringify({ error: `Git command failed: ${result.stderr}` }) }], isError: true };
        }
      }

      // Get recent log for context
      const logResult = await runCommand("git", ["log", "--oneline", "-5"], { cwd: repo_path, timeout: 5000 });

      // Read additional context files
      const contextData = context_files.length > 0 ? resolveFiles(context_files) : [];
      const contextSection = contextData.length > 0
        ? `\n\nADDITIONAL CONTEXT FILES:\n${buildFileContext(contextData, repo_path)}`
        : "";

      const focusInstruction = focus ? `\nFOCUS AREA: Pay special attention to ${focus} issues.` : "";

      const prompt = `Review the following code changes and provide a structured assessment.

DIFF (${diffLabel}):
${diffOutput}

RECENT COMMITS:
${logResult.stdout}${contextSection}${focusInstruction}

Provide your review in this format:
SUMMARY: (1-2 sentence overview)
ISSUES: (numbered list of problems found, or "None")
SUGGESTIONS: (numbered list of improvements)
VERDICT: APPROVE / REQUEST_CHANGES / NEEDS_DISCUSSION`;

      const result = await inferLocal(prompt, {
        system: "You are a senior software engineer performing a thorough code review. Be specific, cite line numbers when possible, and be constructive.",
        maxTokens: 2048,
      });

      if (result.error) {
        return { content: [{ type: "text", text: JSON.stringify({ error: result.error }) }], isError: true };
      }

      return {
        content: [{
          type: "text",
          text: JSON.stringify({
            model: result.model,
            runtime: result.runtime,
            target: diffLabel,
            review: result.response,
            diffLines: diffOutput.split("\n").length,
            usage: result.usage,
          }, null, 2),
        }],
      };
    }
  );

  // ========================================
  // TOOL 3: optimac_model_generate
  // Generate a new file from a prompt.
  // ========================================
  server.registerTool(
    "optimac_model_generate",
    {
      title: "Generate File with Local Model",
      description: `Have the local model generate a new file and write it to disk.

The model receives context files (optional) and a description of what to create.
Output is written directly to the specified path.

Args:
  - description: What file to generate (natural language)
  - output_path: Where to write the generated file
  - context_files: Reference files for style/structure/API context
  - language: Target language/format hint (e.g., "typescript", "python", "markdown")`,
      inputSchema: {
        description: z.string().min(1).describe("What to generate"),
        output_path: z.string().min(1).describe("File path to write the output"),
        context_files: z.array(z.string()).default([]).describe("Reference files for context"),
        language: z.string().optional().describe("Language/format hint"),
      },
      annotations: { readOnlyHint: false, destructiveHint: false, idempotentHint: false, openWorldHint: true },
    },
    async ({ description, output_path, context_files, language }) => {
      const contextData = context_files.length > 0 ? resolveFiles(context_files) : [];
      const contextSection = contextData.length > 0
        ? `\n\nREFERENCE FILES (match their style and patterns):\n${buildFileContext(contextData)}`
        : "";

      const langHint = language ? `\nOUTPUT FORMAT: ${language}` : "";
      const fileHint = `\nOUTPUT FILE: ${basename(output_path)} (${extname(output_path) || "no extension"})`;

      const prompt = `Generate the following file:

${description}${fileHint}${langHint}${contextSection}

Output ONLY the raw file contents. No markdown code fences. No explanations. No preamble. Just the file content, ready to be written to disk.`;

      const result = await inferLocal(prompt, {
        system: "You are a file generator. Output only raw file contents. Never wrap in code fences. Never add explanations. The output will be written directly to disk.",
        maxTokens: 8192,
      });

      if (result.error) {
        return { content: [{ type: "text", text: JSON.stringify({ error: result.error }) }], isError: true };
      }

      // Clean response: strip leading/trailing code fences if model added them despite instructions
      let cleaned = result.response;
      cleaned = stripCodeFences(cleaned);

      if (!isPathSafe(output_path)) {
        return { content: [{ type: "text", text: JSON.stringify({ error: `Write blocked: path '${output_path}' is outside the user's home directory` }) }], isError: true };
      }

      try {
        writeFileSync(output_path, cleaned, "utf-8");
      } catch (e) {
        return { content: [{ type: "text", text: JSON.stringify({ error: `Write failed: ${e instanceof Error ? e.message : String(e)}` }) }], isError: true };
      }

      return {
        content: [{
          type: "text",
          text: JSON.stringify({
            model: result.model,
            runtime: result.runtime,
            generated: output_path,
            sizeBytes: Buffer.byteLength(cleaned, "utf-8"),
            contextFilesUsed: contextData.map((f) => f.path),
            usage: result.usage,
          }, null, 2),
        }],
      };
    }
  );

  // ========================================
  // TOOL 4: optimac_model_edit
  // Edit an existing file with local model.
  // ========================================
  server.registerTool(
    "optimac_model_edit",
    {
      title: "Edit File with Local Model",
      description: `Have the local model edit an existing file based on instructions.

The model receives the current file contents and edit instructions.
It returns the complete modified file, which is written back to disk.
A backup of the original is saved as <filename>.bak.

Args:
  - file_path: Path to the file to edit
  - instructions: What changes to make (natural language)
  - context_files: Additional files for context (e.g., related modules)
  - create_backup: Save .bak before overwriting (default true)`,
      inputSchema: {
        file_path: z.string().min(1).describe("Path to the file to edit"),
        instructions: z.string().min(1).describe("What changes to make"),
        context_files: z.array(z.string()).default([]).describe("Additional context files"),
        create_backup: z.boolean().default(true).describe("Save .bak backup before overwriting"),
      },
      annotations: { readOnlyHint: false, destructiveHint: false, idempotentHint: false, openWorldHint: true },
    },
    async ({ file_path, instructions, context_files, create_backup }) => {
      if (!existsSync(file_path)) {
        return { content: [{ type: "text", text: JSON.stringify({ error: `File not found: ${file_path}` }) }], isError: true };
      }

      const originalContent = readFileSafe(file_path);
      const contextData = context_files.length > 0 ? resolveFiles(context_files) : [];
      const contextSection = contextData.length > 0
        ? `\n\nRELATED FILES:\n${buildFileContext(contextData)}`
        : "";

      const prompt = `Edit the following file according to the instructions.

FILE: ${file_path}
CURRENT CONTENTS:
${originalContent}
${contextSection}

INSTRUCTIONS: ${instructions}

Output the COMPLETE modified file. Include ALL content, not just the changed parts. No markdown code fences. No explanations. Just the complete file ready to be saved.`;

      const result = await inferLocal(prompt, {
        system: "You are a precise file editor. Output the complete modified file. Never omit sections with comments like '// ... rest unchanged'. Include every line.",
        maxTokens: 8192,
      });

      if (result.error) {
        return { content: [{ type: "text", text: JSON.stringify({ error: result.error }) }], isError: true };
      }

      // Clean response
      let cleaned = result.response;
      cleaned = stripCodeFences(cleaned);

      // Backup
      if (create_backup) {
        try {
          writeFileSync(`${file_path}.bak`, originalContent, "utf-8");
        } catch { /* backup failed, continue anyway */ }
      }

      if (!isPathSafe(file_path)) {
        return { content: [{ type: "text", text: JSON.stringify({ error: `Write blocked: path '${file_path}' is outside the user's home directory` }) }], isError: true };
      }

      // Write
      try {
        writeFileSync(file_path, cleaned, "utf-8");
      } catch (e) {
        return { content: [{ type: "text", text: JSON.stringify({ error: `Write failed: ${e instanceof Error ? e.message : String(e)}` }) }], isError: true };
      }

      // Compute simple diff stats
      const origLines = originalContent.split("\n").length;
      const newLines = cleaned.split("\n").length;

      return {
        content: [{
          type: "text",
          text: JSON.stringify({
            model: result.model,
            runtime: result.runtime,
            edited: file_path,
            backup: create_backup ? `${file_path}.bak` : "none",
            originalLines: origLines,
            newLines: newLines,
            linesDelta: newLines - origLines,
            usage: result.usage,
          }, null, 2),
        }],
      };
    }
  );

  // ========================================
  // TOOL 5: optimac_model_summarize
  // Summarize files, directories, or codebases.
  // ========================================
  server.registerTool(
    "optimac_model_summarize",
    {
      title: "Summarize with Local Model",
      description: `Have the local model summarize files, directories, or an entire codebase.

Reads the specified files/directories and produces a structured summary.
Useful for onboarding, documentation, or understanding unfamiliar code.

Args:
  - paths: Files or directories to summarize (supports globs)
  - focus: What to focus on ("architecture", "api", "dependencies", "security", etc.)
  - format: Output format ("brief", "detailed", "bullet-points")`,
      inputSchema: {
        paths: z.array(z.string()).min(1).describe("Files or directories to summarize"),
        focus: z.string().optional().describe("Focus area: architecture, api, dependencies, security"),
        format: z.enum(["brief", "detailed", "bullet-points"]).default("detailed").describe("Summary format"),
      },
      annotations: { readOnlyHint: true, destructiveHint: false, idempotentHint: true, openWorldHint: true },
    },
    async ({ paths, focus, format }) => {
      const resolvedFiles = resolveFiles(paths);

      if (resolvedFiles.length === 0) {
        return { content: [{ type: "text", text: JSON.stringify({ error: "No readable files found in the specified paths." }) }], isError: true };
      }

      const focusInstruction = focus ? `\nFOCUS: Emphasize ${focus} aspects.` : "";
      const formatInstruction = format === "brief" ? "Keep it under 200 words."
        : format === "bullet-points" ? "Use a structured bullet-point format."
          : "Provide a thorough, detailed analysis.";

      const prompt = `Summarize the following ${resolvedFiles.length} file(s):

${buildFileContext(resolvedFiles)}
${focusInstruction}

FORMAT: ${formatInstruction}

Provide a clear, structured summary that would help someone quickly understand this codebase.`;

      const result = await inferLocal(prompt, {
        system: "You are a technical analyst. Produce clear, accurate summaries. Identify key patterns, dependencies, and design decisions.",
        maxTokens: 4096,
      });

      if (result.error) {
        return { content: [{ type: "text", text: JSON.stringify({ error: result.error }) }], isError: true };
      }

      return {
        content: [{
          type: "text",
          text: JSON.stringify({
            model: result.model,
            runtime: result.runtime,
            filesAnalyzed: resolvedFiles.map((f) => f.path),
            fileCount: resolvedFiles.length,
            totalSizeKB: Math.round(resolvedFiles.reduce((sum, f) => sum + f.sizeMB * 1024, 0)),
            summary: result.response,
            usage: result.usage,
          }, null, 2),
        }],
      };
    }
  );

  // ========================================
  // TOOL 6: optimac_model_commit
  // Git commit with model-generated message.
  // ========================================
  server.registerTool(
    "optimac_model_commit",
    {
      title: "Git Commit via Local Model",
      description: `Have the local model review uncommitted changes, generate a commit message, and optionally execute the commit.

The model sees the full diff and recent commit history for style matching.

Args:
  - repo_path: Path to the git repository
  - auto_commit: If true, stages all changes and commits. If false, returns the suggested message only.
  - files_to_stage: Specific files to stage (default: all modified/untracked)
  - style: Commit style hint ("conventional", "descriptive", "short")`,
      inputSchema: {
        repo_path: z.string().describe("Path to the git repository"),
        auto_commit: z.boolean().default(false).describe("Execute the commit automatically"),
        files_to_stage: z.array(z.string()).default([]).describe("Specific files to stage (empty = all changes)"),
        style: z.enum(["conventional", "descriptive", "short"]).default("conventional").describe("Commit message style"),
      },
      annotations: { readOnlyHint: false, destructiveHint: false, idempotentHint: false, openWorldHint: true },
    },
    async ({ repo_path, auto_commit, files_to_stage, style }) => {
      // Get status and diff using safe cwd option
      const statusResult = await runCommand("git", ["status"], { cwd: repo_path, timeout: 10000 });
      const unstaged = await runCommand("git", ["diff"], { cwd: repo_path, timeout: 15000 });
      const staged = await runCommand("git", ["diff", "--cached"], { cwd: repo_path, timeout: 15000 });
      const diffOutput = [unstaged.stdout, staged.stdout].filter(Boolean).join("\n");
      const logResult = await runCommand("git", ["log", "--oneline", "-10"], { cwd: repo_path, timeout: 5000 });

      if (!diffOutput.trim() && !statusResult.stdout.includes("Untracked")) {
        return { content: [{ type: "text", text: JSON.stringify({ message: "No uncommitted changes found.", status: statusResult.stdout }) }] };
      }

      // Get untracked file contents too
      const untrackedResult = await runCommand(
        "git", ["ls-files", "--others", "--exclude-standard"],
        { cwd: repo_path, timeout: 5000 }
      );
      let untrackedContext = "";
      if (untrackedResult.stdout.trim()) {
        const untrackedFiles = untrackedResult.stdout.trim().split("\n").slice(0, 10);
        const untrackedContents = untrackedFiles.map((f) => {
          const fullPath = join(repo_path, f);
          const content = readFileSafe(fullPath);
          return `=== NEW FILE: ${f} ===\n${content.substring(0, 2000)}\n`;
        }).join("\n");
        untrackedContext = `\n\nNEW UNTRACKED FILES:\n${untrackedContents}`;
      }

      const styleGuide = style === "conventional"
        ? "Use conventional commits format: type(scope): description. Types: feat, fix, docs, refactor, test, chore."
        : style === "short"
          ? "Keep it to one line, under 72 characters."
          : "Write a descriptive multi-line message with a summary line and body.";

      const prompt = `Generate a git commit message for the following changes.

GIT STATUS:
${statusResult.stdout}

GIT DIFF:
${diffOutput.substring(0, 6000)}${untrackedContext}

RECENT COMMITS (match this style):
${logResult.stdout}

STYLE: ${styleGuide}

Output ONLY the commit message text. No explanations. No code fences. If multi-line, first line is the summary, then a blank line, then the body.`;

      const result = await inferLocal(prompt, {
        system: "You are a git commit message generator. Output only the commit message. Be precise and descriptive. Match the repository's existing style.",
        maxTokens: 512,
      });

      if (result.error) {
        return { content: [{ type: "text", text: JSON.stringify({ error: result.error }) }], isError: true };
      }

      // Clean the message
      let commitMsg = result.response.trim();
      // Remove wrapping quotes if model added them
      if ((commitMsg.startsWith('"') && commitMsg.endsWith('"')) || (commitMsg.startsWith("'") && commitMsg.endsWith("'"))) {
        commitMsg = commitMsg.slice(1, -1);
      }

      if (!auto_commit) {
        return {
          content: [{
            type: "text",
            text: JSON.stringify({
              model: result.model,
              runtime: result.runtime,
              suggestedMessage: commitMsg,
              filesChanged: statusResult.stdout,
              autoCommit: false,
              hint: "Set auto_commit=true to execute this commit, or use the message manually.",
              usage: result.usage,
            }, null, 2),
          }],
        };
      }

      // Auto-commit: stage and commit using safe argument arrays
      const stageArgs = files_to_stage.length > 0
        ? ["add", ...files_to_stage]
        : ["add", "-A"];

      const stageResult = await runCommand("git", stageArgs, { cwd: repo_path, timeout: 10000 });
      if (stageResult.exitCode !== 0) {
        return { content: [{ type: "text", text: JSON.stringify({ error: `Stage failed: ${stageResult.stderr}`, suggestedMessage: commitMsg }) }], isError: true };
      }

      // Commit using -m flag as a separate argument (no shell escaping needed)
      const commitResult = await runCommand(
        "git", ["commit", "-m", commitMsg],
        { cwd: repo_path, timeout: 15000 }
      );

      return {
        content: [{
          type: "text",
          text: JSON.stringify({
            model: result.model,
            runtime: result.runtime,
            commitMessage: commitMsg,
            commitResult: commitResult.exitCode === 0 ? "SUCCESS" : "FAILED",
            commitOutput: commitResult.stdout || commitResult.stderr,
            usage: result.usage,
          }, null, 2),
        }],
      };
    }
  );

  // ========================================
  // TOOL 7: optimac_cloud_escalate
  // Edge-to-Cloud: local model hits limits, escalate to cloud API.
  // ========================================
  server.registerTool(
    "optimac_cloud_escalate",
    {
      title: "Escalate to Cloud AI",
      description: `Edge-to-Cloud bridge: send a task to a cloud AI provider when the local model
isn't capable enough (complex reasoning, large context, specialized knowledge).

Supports OpenRouter (100+ models), Anthropic (Claude), and OpenAI (GPT-4).
API keys must be configured in ~/.optimac/config.json under cloudEndpoints.

Use this when:
  - Local model produces low-quality output that needs cloud verification
  - Task requires reasoning beyond local model capacity
  - Need a specific cloud model's capabilities (vision, tool use, etc.)
  - Context window of local model is too small

Args:
  - prompt: The task/prompt to send to the cloud
  - provider: "openrouter" (default), "anthropic", or "openai"
  - model: Override the default model for this provider
  - system: System prompt
  - files: File paths to include as context
  - max_tokens: Max tokens for response`,
      inputSchema: {
        prompt: z.string().min(1).describe("Task to send to cloud AI"),
        provider: z.enum(["openrouter", "anthropic", "openai"]).default("openrouter").describe("Cloud AI provider"),
        model: z.string().optional().describe("Override default model for this provider"),
        system: z.string().optional().describe("System prompt"),
        files: z.array(z.string()).default([]).describe("File paths to include as context"),
        max_tokens: z.number().positive().default(4096).describe("Max tokens for response"),
      },
      annotations: { readOnlyHint: true, destructiveHint: false, idempotentHint: false, openWorldHint: true },
    },
    async ({ prompt, provider, model, system, files, max_tokens }) => {
      const config = loadConfig();
      const endpoint = config.cloudEndpoints[provider];

      if (!endpoint.apiKey) {
        return {
          content: [{
            type: "text",
            text: JSON.stringify({
              error: "NO_API_KEY",
              provider,
              message: `No API key configured for ${provider}. Set it in ~/.optimac/config.json under cloudEndpoints.${provider}.apiKey`,
              configPath: "~/.optimac/config.json",
            }, null, 2),
          }],
          isError: true,
        };
      }

      // Build context from files
      const resolvedFiles = files.length > 0 ? resolveFiles(files) : [];
      const fileContext = resolvedFiles.length > 0
        ? `\n\nFILES:\n${buildFileContext(resolvedFiles)}`
        : "";

      const fullPrompt = `${prompt}${fileContext}`;

      // Build messages
      const messages: Array<{ role: string; content: string }> = [];
      if (system) messages.push({ role: "system", content: system });
      messages.push({ role: "user", content: fullPrompt });

      const selectedModel = model || endpoint.defaultModel;
      const requestBody = JSON.stringify({
        model: selectedModel,
        messages,
        max_tokens,
        stream: false,
      });

      // Build headers based on provider
      const headers: string[] = ["-H", "Content-Type: application/json"];
      if (provider === "anthropic") {
        headers.push("-H", `x-api-key: ${endpoint.apiKey}`);
        headers.push("-H", "anthropic-version: 2023-06-01");
      } else {
        headers.push("-H", `Authorization: Bearer ${endpoint.apiKey}`);
      }

      // Anthropic uses a different endpoint path and body format
      let url: string;
      let body: string;
      if (provider === "anthropic") {
        url = `${endpoint.url}/messages`;
        const anthropicBody: Record<string, unknown> = {
          model: selectedModel,
          max_tokens,
          messages: messages.filter((m) => m.role !== "system"),
        };
        const systemMsg = messages.find((m) => m.role === "system");
        if (systemMsg) anthropicBody.system = systemMsg.content;
        body = JSON.stringify(anthropicBody);
      } else {
        url = `${endpoint.url}/chat/completions`;
        body = requestBody;
      }

      const curlResult = await runCommand(
        "curl",
        ["-s", "-X", "POST", url, ...headers, "-d", body],
        { timeout: 120000 }
      );

      if (curlResult.exitCode !== 0) {
        return {
          content: [{
            type: "text",
            text: JSON.stringify({ error: "CLOUD_REQUEST_FAILED", stderr: curlResult.stderr }, null, 2),
          }],
          isError: true,
        };
      }

      try {
        const parsed = JSON.parse(curlResult.stdout);

        // Handle different response formats
        let responseText: string;
        let usage: Record<string, unknown>;

        if (provider === "anthropic") {
          responseText = parsed.content?.[0]?.text ?? "(no content)";
          usage = parsed.usage ?? {};
        } else {
          responseText = parsed.choices?.[0]?.message?.content ?? "(no content)";
          usage = parsed.usage ?? {};
        }

        return {
          content: [{
            type: "text",
            text: JSON.stringify({
              provider,
              model: selectedModel,
              response: responseText,
              filesIncluded: resolvedFiles.map((f) => f.path),
              usage,
            }, null, 2),
          }],
        };
      } catch {
        return {
          content: [{
            type: "text",
            text: JSON.stringify({
              error: "CLOUD_PARSE_ERROR",
              provider,
              rawResponse: curlResult.stdout.substring(0, 2000),
            }, null, 2),
          }],
          isError: true,
        };
      }
    }
  );

  // ========================================
  // TOOL 8: optimac_model_route
  // Smart routing: decide edge vs cloud based on task complexity.
  // ========================================
  server.registerTool(
    "optimac_model_route",
    {
      title: "Smart Route: Edge or Cloud",
      description: `Intelligent routing that decides whether to use a local model (edge) or cloud AI
based on the task characteristics. Tries local first; if the response quality is
insufficient or the task exceeds local capabilities, auto-escalates to cloud.

Strategy:
  - Simple tasks (summarize, format, translate): local model (fast, free, private)
  - Complex tasks (multi-step reasoning, large context): cloud model
  - If local model returns empty/low-quality: auto-retry on cloud
  - Respects privacy: files marked sensitive always stay local

Args:
  - task: The task to perform
  - files: File paths for context
  - prefer: "local" (default), "cloud", or "auto"
  - sensitive: If true, NEVER escalate to cloud (privacy mode)
  - output_path: Optional file to write output to
  - cloud_provider: Which cloud to use if escalating (default: openrouter)`,
      inputSchema: {
        task: z.string().min(1).describe("The task to perform"),
        files: z.array(z.string()).default([]).describe("File paths for context"),
        prefer: z.enum(["local", "cloud", "auto"]).default("auto").describe("Preferred execution target"),
        sensitive: z.boolean().default(false).describe("If true, never send to cloud"),
        output_path: z.string().optional().describe("Write output to this file"),
        cloud_provider: z.enum(["openrouter", "anthropic", "openai"]).default("openrouter").describe("Cloud provider for escalation"),
      },
      annotations: { readOnlyHint: false, destructiveHint: false, idempotentHint: false, openWorldHint: true },
    },
    async ({ task, files, prefer, sensitive, output_path, cloud_provider }) => {
      const resolvedFiles = files.length > 0 ? resolveFiles(files) : [];
      const fileContext = resolvedFiles.length > 0
        ? `\n\nFILES:\n${buildFileContext(resolvedFiles)}`
        : "";

      const fullPrompt = `${task}${fileContext}\n\nRespond with ONLY the requested output.`;
      const systemPrompt = "You are a precise task executor. Follow instructions exactly. Output only what is requested.";

      let executedOn = "local";
      let response = "";
      let modelUsed = "";
      let usage: Record<string, unknown> = {};
      let escalated = false;

      // Try local first (unless prefer=cloud)
      if (prefer !== "cloud") {
        const localResult = await inferLocal(fullPrompt, {
          system: systemPrompt,
          maxTokens: 4096,
        });

        const quality = assessResponseQuality(localResult.response);
        if (!localResult.error && quality.ok) {
          response = localResult.response;
          modelUsed = localResult.model;
          usage = localResult.usage;
          executedOn = `local (${localResult.runtime})`;
        } else if (sensitive) {
          // Can't escalate -- return whatever we got
          response = localResult.response || localResult.error || "Local model failed and sensitive mode prevents cloud escalation.";
          modelUsed = localResult.model || "none";
          executedOn = "local (failed, sensitive mode)";
        } else if (prefer === "local") {
          // Tried local, it failed, but user prefers local
          response = localResult.response || localResult.error || "Local model failed.";
          modelUsed = localResult.model || "none";
          executedOn = "local (failed)";
        }
        // else: fall through to cloud
      }

      // Escalate to cloud if needed
      if (!response && !sensitive) {
        const config = loadConfig();
        const endpoint = config.cloudEndpoints[cloud_provider];

        if (!endpoint.apiKey) {
          return {
            content: [{
              type: "text",
              text: JSON.stringify({
                error: "ESCALATION_FAILED",
                reason: `No API key for ${cloud_provider}. Configure in ~/.optimac/config.json`,
                localAttempted: prefer !== "cloud",
              }, null, 2),
            }],
            isError: true,
          };
        }

        // Build cloud request
        const messages: Array<{ role: string; content: string }> = [
          { role: "system", content: systemPrompt },
          { role: "user", content: fullPrompt },
        ];

        const selectedModel = endpoint.defaultModel;
        const headers: string[] = ["-H", "Content-Type: application/json"];

        let url: string;
        let body: string;

        if (cloud_provider === "anthropic") {
          url = `${endpoint.url}/messages`;
          headers.push("-H", `x-api-key: ${endpoint.apiKey}`);
          headers.push("-H", "anthropic-version: 2023-06-01");
          body = JSON.stringify({
            model: selectedModel,
            max_tokens: 4096,
            system: systemPrompt,
            messages: [{ role: "user", content: fullPrompt }],
          });
        } else {
          url = `${endpoint.url}/chat/completions`;
          headers.push("-H", `Authorization: Bearer ${endpoint.apiKey}`);
          body = JSON.stringify({ model: selectedModel, messages, max_tokens: 4096, stream: false });
        }

        const curlResult = await runCommand(
          "curl",
          ["-s", "-X", "POST", url, ...headers, "-d", body],
          { timeout: 120000 }
        );

        if (curlResult.exitCode === 0) {
          try {
            const parsed = JSON.parse(curlResult.stdout);
            if (cloud_provider === "anthropic") {
              response = parsed.content?.[0]?.text ?? "";
            } else {
              response = parsed.choices?.[0]?.message?.content ?? "";
            }
            modelUsed = selectedModel;
            usage = parsed.usage ?? {};
            executedOn = `cloud (${cloud_provider})`;
            escalated = true;
          } catch {
            response = "Cloud response parse error.";
            executedOn = `cloud (${cloud_provider}, parse error)`;
          }
        } else {
          response = `Cloud request failed: ${curlResult.stderr}`;
          executedOn = `cloud (${cloud_provider}, request failed)`;
        }
      }

      // Write output if requested
      let writeStatus = "";
      if (output_path && response) {
        if (!isPathSafe(output_path)) {
          writeStatus = `WRITE BLOCKED: path '${output_path}' is outside the user's home directory`;
        } else {
          let cleaned = response;
          cleaned = stripCodeFences(cleaned);
          try {
            writeFileSync(output_path, cleaned, "utf-8");
            writeStatus = `Written to ${output_path}`;
          } catch (e) {
            writeStatus = `WRITE FAILED: ${e instanceof Error ? e.message : String(e)}`;
          }
        }
      }

      return {
        content: [{
          type: "text",
          text: JSON.stringify({
            executedOn,
            model: modelUsed,
            escalated,
            sensitive,
            filesRead: resolvedFiles.map((f) => f.path),
            response,
            outputWritten: writeStatus || undefined,
            usage,
          }, null, 2),
        }],
      };
    }
  );
}
