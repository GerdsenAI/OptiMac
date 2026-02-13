"""
Command execution utilities.
Extracted from gerdsenai_optimac_improved.py v2.3.

Provides shell command execution with output handling for both
terminal widgets (tkinter) and callback-based menu bar app.
"""

import subprocess
import threading
from datetime import datetime


def run_command(command, timeout=30):
    """
    Execute a shell command and return (success, output).
    Works without a GUI -- suitable for menu bar actions.
    """
    try:
        result = subprocess.run(
            command if isinstance(command, list) else command.split(),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        output = result.stdout.strip()
        if result.returncode != 0 and result.stderr:
            output += f"\n{result.stderr.strip()}"
        return result.returncode == 0, output
    except subprocess.TimeoutExpired:
        return False, f"Command timed out after {timeout}s"
    except Exception as e:
        return False, str(e)


def run_command_threaded(command, callback=None, timeout=30):
    """
    Execute a shell command in a background thread.
    Calls callback(success, output) when done.
    """

    def _worker():
        success, output = run_command(command, timeout=timeout)
        if callback:
            callback(success, output)

    t = threading.Thread(target=_worker, daemon=True)
    t.start()
    return t


def timestamp():
    """Return formatted timestamp string."""
    return datetime.now().strftime("[%H:%M:%S]")


def run_command_with_output(command, widget=None, callback=None, timeout=30):
    """
    Execute a command and pipe output to a terminal widget.

    If widget is provided and visible, output streams there in real-time.
    Otherwise falls back to callback(success, output) behavior.

    Args:
        command: Shell command string or list.
        widget: Optional TerminalWidget instance.
        callback: Optional callback(success, output) for completion.
        timeout: Command timeout in seconds.
    """
    if widget and widget.is_visible():
        cmd_str = command if isinstance(command, str) else " ".join(command)
        widget.run_shell(cmd_str)
    else:
        run_command_threaded(command, callback=callback, timeout=timeout)
