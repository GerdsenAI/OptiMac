"""
Native macOS dialog helpers for OptiMac menu bar app.

Every interaction should feel intentional:
  - Information stays until you dismiss it.
  - Dangerous actions require explicit confirmation.
  - Progress is visible, not silent.

Uses rumps for simple dialogs and lightweight AppKit where needed.
"""

import rumps


# ── Terminal Widget Reference ─────────────────────────────────────────

_terminal_widget = None


def set_terminal_widget(widget):
    """Register the terminal widget so action output auto-pipes there."""
    global _terminal_widget
    _terminal_widget = widget


# ── Informational Results ─────────────────────────────────────────────


def show_result(title, heading, body):
    """
    Display an informational result that persists until dismissed.

    Uses a rumps.Window with a scrollable text area so the user can
    actually *read* the content — unlike notification banners that
    vanish in seconds.

    Args:
        title: Window title bar text.
        heading: Bold heading above the text area.
        body: Monospaced detail text (multi-line).
    """
    w = rumps.Window(
        message=heading,
        title=title,
        default_text=body,
        ok="Done",
        cancel=None,
        dimensions=(440, 220),
    )
    w.run()

    # Auto-pipe to terminal widget when visible
    if _terminal_widget and _terminal_widget.is_visible():
        _terminal_widget.append_action(title, body)


# ── Confirmation Gates ────────────────────────────────────────────────


def confirm_action(title, message, proceed_label="Proceed", cancel_label="Cancel"):
    """
    Ask the user to explicitly confirm a consequential action.

    Returns True if the user clicked the proceed button.

    The language should be specific, never generic 'Are you sure?':
        confirm_action(
            "Clear Application Caches",
            "This will remove 2.3 GB of cached data from\\n"
            "~/Library/Caches. Applications may run slower\\n"
            "until they rebuild their caches.\\n\\n"
            "This cannot be undone.",
        )
    """
    response = rumps.alert(
        title=title,
        message=message,
        ok=proceed_label,
        cancel=cancel_label,
    )
    # rumps.alert returns 1 for OK, 0 for Cancel
    return response == 1


# ── Status Bar Progress ───────────────────────────────────────────────


class StatusProgress:
    """
    Show progress in the menu bar status item.

    Usage:
        progress = StatusProgress(status_item, "Maintenance")
        progress.update("Purging memory…", step=1, total=3)
        progress.update("Flushing DNS…", step=2, total=3)
        progress.finish("Maintenance complete")

    The status item text is restored when finish() is called.
    """

    def __init__(self, status_item, task_name):
        self._item = status_item
        self._task = task_name
        self._original_title = status_item.title

    def update(self, message, step=None, total=None):
        """Update the status item with current progress."""
        if step is not None and total is not None:
            self._item.title = f">> {self._task} ({step}/{total}): {message}"
        else:
            self._item.title = f">> {message}"

    def finish(self, message=None, restore=True):
        """
        Mark the operation as complete.

        Shows a brief completion indicator, then optionally restores
        the original status text.
        """
        if message:
            self._item.title = f"[OK] {message}"
        if restore:
            # Restore after a beat so the user sees the indicator
            import threading

            def _restore():
                import time

                time.sleep(2.0)
                self._item.title = self._original_title

            threading.Thread(target=_restore, daemon=True).start()

    def fail(self, message=None):
        """Mark the operation as failed and restore status."""
        if message:
            self._item.title = f"[FAIL] {message}"
        import threading

        def _restore():
            import time

            time.sleep(3.0)
            self._item.title = self._original_title

        threading.Thread(target=_restore, daemon=True).start()


# ── Action Feedback ──────────────────────────────────────────────────


def notify_action(title, message, status_item=None):
    """
    Provide instant feedback for completed actions.

    1. Posts a macOS notification with the OptiMac icon.
    2. Optionally flashes the status bar with a brief confirmation.

    Args:
        title: Notification title (e.g. "Wi-Fi").
        message: Detail text (e.g. "Disabled successfully").
        status_item: Optional rumps.MenuItem to flash status on.
    """
    rumps.notification("OptiMac", title, message)

    if status_item:
        original = status_item.title

        status_item.title = f"[OK] {title}"
        import threading

        def _restore():
            import time

            time.sleep(2.0)
            status_item.title = original

        threading.Thread(target=_restore, daemon=True).start()
