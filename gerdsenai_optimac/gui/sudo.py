"""
Privilege escalation for macOS menu bar app.

Uses osascript to invoke the native macOS authentication dialog,
so the user sees the familiar password prompt — not a silent failure.
"""

import subprocess
import shlex


def run_privileged(command, description="OptiMac needs administrator access"):
    """
    Run a shell command with administrator privileges.

    Uses macOS's native ``do shell script ... with administrator privileges``
    which presents the system authentication dialog.

    Args:
        command: Shell command string or list of args.
        description: Context shown alongside the password prompt.

    Returns:
        (success: bool, output: str)
    """
    if isinstance(command, list):
        cmd_str = " ".join(shlex.quote(str(c)) for c in command)
    else:
        cmd_str = command

    # Escape for AppleScript string literal
    escaped = cmd_str.replace("\\", "\\\\").replace('"', '\\"')

    script = f'do shell script "{escaped}" ' f"with administrator privileges"

    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=60,
        )
        output = result.stdout.strip()
        if result.returncode != 0:
            stderr = result.stderr.strip()
            if "User canceled" in stderr or "canceled" in stderr.lower():
                return False, "Cancelled by user"
            output = stderr if stderr else f"Command failed (exit {result.returncode})"
            return False, output
        return True, output
    except subprocess.TimeoutExpired:
        return False, "Command timed out"
    except Exception as e:
        return False, str(e)


def run_privileged_batch(commands, progress_callback=None):
    """
    Run multiple privileged commands in sequence.

    Prompts for the password once using a combined script, avoiding
    repeated auth dialogs.

    Args:
        commands: List of (description, command_string_or_list) tuples.
        progress_callback: Optional callable(step_index, total, description).

    Returns:
        (all_succeeded: bool, results: list[tuple[bool, str]])
    """
    if not commands:
        return True, []

    # Build a single combined shell script
    parts = []
    for _desc, cmd in commands:
        if isinstance(cmd, list):
            cmd_str = " ".join(shlex.quote(str(c)) for c in cmd)
        else:
            cmd_str = cmd
        parts.append(cmd_str)

    combined = " && ".join(parts)
    escaped = combined.replace("\\", "\\\\").replace('"', '\\"')

    script = f'do shell script "{escaped}" ' f"with administrator privileges"

    total = len(commands)
    if progress_callback:
        progress_callback(0, total, "Authenticating…")

    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=120,
        )

        if result.returncode != 0:
            stderr = result.stderr.strip()
            if "canceled" in stderr.lower():
                return False, [(False, "Cancelled by user")]
            return False, [(False, stderr or f"Failed (exit {result.returncode})")]

        # All commands succeeded as a batch
        results = [(True, "") for _ in commands]
        if progress_callback:
            for i, (desc, _) in enumerate(commands):
                progress_callback(i + 1, total, desc)
        return True, results

    except subprocess.TimeoutExpired:
        return False, [(False, "Timed out")]
    except Exception as e:
        return False, [(False, str(e))]
