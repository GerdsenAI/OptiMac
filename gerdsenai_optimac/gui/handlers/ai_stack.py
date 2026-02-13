"""
AI Stack handler — Ollama, MLX, GPU, and model management.
"""

import subprocess
import threading

import rumps

from gerdsenai_optimac.gui.commands import run_command, run_command_threaded
from gerdsenai_optimac.gui.dialogs import show_result, StatusProgress
from gerdsenai_optimac.gui.sudo import run_privileged


def build_menu(app):
    """Build AI Stack submenu and attach callbacks to *app*."""
    menu = rumps.MenuItem("🧠 AI Stack")

    menu.add(
        rumps.MenuItem(
            "Start Ollama",
            callback=lambda _: start_ollama(app),
        )
    )
    menu.add(
        rumps.MenuItem(
            "Stop Ollama",
            callback=lambda _: stop_ollama(app),
        )
    )
    menu.add(rumps.separator)
    menu.add(
        rumps.MenuItem(
            "Start MLX Server",
            callback=lambda _: start_mlx(app),
        )
    )
    menu.add(
        rumps.MenuItem(
            "Stop MLX Server",
            callback=lambda _: stop_mlx(app),
        )
    )
    menu.add(rumps.separator)
    menu.add(
        rumps.MenuItem(
            "Pull Model",
            callback=lambda _: pull_model(app),
        )
    )
    menu.add(
        rumps.MenuItem(
            "MLX Quantize Model",
            callback=lambda _: mlx_quantize(app),
        )
    )
    menu.add(rumps.separator)
    menu.add(
        rumps.MenuItem(
            "Check Status",
            callback=lambda _: check_status(app),
        )
    )
    menu.add(
        rumps.MenuItem(
            "List Models",
            callback=lambda _: list_models(app),
        )
    )
    menu.add(
        rumps.MenuItem(
            "GPU Utilization",
            callback=lambda _: gpu_utilization(app),
        )
    )
    menu.add(
        rumps.MenuItem(
            "Benchmark Model",
            callback=lambda _: benchmark_model(app),
        )
    )
    return menu


# ── Tier 2 — Safe Actions ─────────────────────────────────────


def start_ollama(app):
    progress = StatusProgress(app.status_item, "Ollama")
    progress.update("Starting server…")

    def _cb(ok, out):
        if ok:
            progress.finish("Ollama running")
            rumps.notification("OptiMac", "Ollama", "Server started")
        else:
            progress.fail("Ollama failed")
            rumps.notification("OptiMac", "Ollama", f"Failed: {out}")

    run_command_threaded(["ollama", "serve"], callback=_cb, timeout=10)


def stop_ollama(app):
    progress = StatusProgress(app.status_item, "Ollama")
    progress.update("Stopping…")
    ok, _ = run_command(["pkill", "-f", "ollama serve"])
    if ok:
        progress.finish("Ollama stopped")
    else:
        progress.finish("Ollama was not running")
    rumps.notification(
        "OptiMac",
        "Ollama",
        "Server stopped" if ok else "Not running",
    )


def start_mlx(app):
    response = rumps.Window(
        "Enter HuggingFace model ID or local path:",
        title="Start MLX Server",
        default_text="mlx-community/Qwen2.5-7B-Instruct-4bit",
        ok="Start",
        cancel="Cancel",
    ).run()
    if response.clicked:
        model = response.text.strip()
        if model:
            port = app.config.get(
                "aiStackPorts",
                {},
            ).get("mlx", 8080)
            progress = StatusProgress(app.status_item, "MLX")
            progress.update(f"Starting on port {port}…")
            subprocess.Popen(
                [
                    "python3",
                    "-m",
                    "mlx_lm.server",
                    "--model",
                    model,
                    "--port",
                    str(port),
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            progress.finish(f"MLX on :{port}")
            rumps.notification(
                "OptiMac",
                "MLX",
                f"Starting {model}\nPort {port}",
            )


def stop_mlx(app):
    progress = StatusProgress(app.status_item, "MLX")
    progress.update("Stopping…")
    run_command(["pkill", "-f", "mlx_lm.server"])
    progress.finish("MLX stopped")
    rumps.notification("OptiMac", "MLX", "Server stopped")


def pull_model(app):
    response = rumps.Window(
        "Enter model name to pull from Ollama registry:",
        title="Pull Ollama Model",
        default_text="llama3.2:3b",
        ok="Pull",
        cancel="Cancel",
    ).run()
    if response.clicked:
        model = response.text.strip()
        if model:
            progress = StatusProgress(
                app.status_item,
                "Pull",
            )
            progress.update(f"Pulling {model}…")

            def _worker():
                ok, out = run_command(
                    ["ollama", "pull", model],
                    timeout=600,
                )
                if ok:
                    progress.finish(f"Pulled {model}")
                    rumps.notification(
                        "OptiMac",
                        "Models",
                        f"Successfully pulled {model}",
                    )
                else:
                    progress.fail("Pull failed")
                    rumps.notification(
                        "OptiMac",
                        "Models",
                        f"Failed: {out[:200]}",
                    )

            threading.Thread(
                target=_worker,
                daemon=True,
            ).start()


def mlx_quantize(app):
    response = rumps.Window(
        "Enter HuggingFace model ID to quantize:\n\n"
        "This converts a model to MLX format with 4-bit\n"
        "quantization for efficient Apple Silicon inference.",
        title="MLX Quantize Model",
        default_text="meta-llama/Llama-3.2-3B-Instruct",
        ok="Quantize",
        cancel="Cancel",
    ).run()
    if response.clicked:
        model = response.text.strip()
        if model:
            progress = StatusProgress(
                app.status_item,
                "Quantize",
            )
            progress.update(f"Quantizing {model}…")

            def _worker():
                ok, out = run_command(
                    [
                        "python3",
                        "-m",
                        "mlx_lm.convert",
                        "--hf-path",
                        model,
                        "-q",
                    ],
                    timeout=1800,
                )
                if ok:
                    progress.finish("Quantization complete")
                    rumps.notification(
                        "OptiMac",
                        "MLX",
                        f"Quantized {model}",
                    )
                else:
                    progress.fail("Quantize failed")
                    rumps.notification(
                        "OptiMac",
                        "MLX",
                        f"Failed: {out[:200]}",
                    )

            threading.Thread(
                target=_worker,
                daemon=True,
            ).start()


# ── Tier 1 — Informational ────────────────────────────────────


def check_status(app):
    import socket

    ports = app.config.get(
        "aiStackPorts",
        {
            "ollama": 11434,
            "lmstudio": 1234,
            "mlx": 8080,
        },
    )
    lines = []
    for name, port in ports.items():
        try:
            with socket.socket(
                socket.AF_INET,
                socket.SOCK_STREAM,
            ) as s:
                s.settimeout(1)
                running = (
                    s.connect_ex(
                        ("127.0.0.1", port),
                    )
                    == 0
                )
        except OSError:
            running = False
        icon = "● RUNNING" if running else "○ stopped"
        lines.append(f"  {name:<12} {icon}  (:{port})")

    show_result(
        "AI Stack Status",
        "Local inference services:",
        "\n".join(lines),
    )


def list_models(app):
    progress = StatusProgress(app.status_item, "Models")
    progress.update("Querying Ollama…")
    ok, out = run_command(["ollama", "list"], timeout=10)
    progress.finish()

    if ok and out:
        show_result("Ollama Models", "Installed models:", out)
    else:
        show_result(
            "Ollama Models",
            "No models found",
            "Ollama may not be running.\n" "Start it from AI Stack → Start Ollama.",
        )


def gpu_utilization(app):
    progress = StatusProgress(app.status_item, "GPU")
    progress.update("Reading GPU metrics…")

    ok, out = run_privileged("powermetrics --samplers gpu_power -i 1000 -n 1")
    progress.finish()

    if ok and out:
        # Extract key GPU lines
        lines = []
        for line in out.split("\n"):
            line_l = line.lower()
            if any(
                k in line_l
                for k in [
                    "gpu",
                    "ane",
                    "power",
                    "freq",
                    "active",
                ]
            ):
                lines.append(line.strip())
        body = "\n".join(lines[:20]) if lines else out[:500]
        show_result("GPU Utilization", "Apple Silicon GPU:", body)
    else:
        if "Cancelled" not in (out or ""):
            show_result(
                "GPU Utilization",
                "Failed to read GPU metrics",
                out or "powermetrics requires admin access",
            )


def benchmark_model(app):
    response = rumps.Window(
        "Enter model name for inference benchmark:\n\n"
        "Runs a short prompt and measures tokens/second.",
        title="Benchmark Model",
        default_text="llama3.2:3b",
        ok="Run Benchmark",
        cancel="Cancel",
    ).run()
    if not response.clicked:
        return
    model = response.text.strip()
    if not model:
        return

    progress = StatusProgress(app.status_item, "Benchmark")
    progress.update(f"Benchmarking {model}…")

    def _worker():
        import time as _time

        prompt = "Explain quantum computing in exactly 100 words."
        start = _time.time()
        ok, out = run_command(
            ["ollama", "run", model, prompt],
            timeout=120,
        )
        elapsed = _time.time() - start

        progress.finish()

        if ok and out:
            words = len(out.split())
            # Rough token estimate (≈1.3 tokens per word)
            tokens = int(words * 1.3)
            tps = tokens / elapsed if elapsed > 0 else 0
            body = (
                f"  Model:       {model}\n"
                f"  Time:        {elapsed:.1f}s\n"
                f"  Output:      ~{tokens} tokens\n"
                f"  Speed:       ~{tps:.1f} tok/s\n"
                f"  ─────────────────────\n"
                f"  {out[:400]}"
            )
            show_result(
                "Benchmark Results",
                f"{model} inference speed:",
                body,
            )
        else:
            show_result(
                "Benchmark",
                "Failed",
                out or "Could not run model",
            )

    threading.Thread(target=_worker, daemon=True).start()
