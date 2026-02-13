"""
Floating terminal widget for OptiMac.

A draggable, resizable mini-terminal that hovers above other windows.
Uses PyObjC (NSPanel) with the retro CRT green-on-black theme from
themes.py. Action outputs are piped here when the widget is visible.

The widget provides:
  - Command input field with history (up/down arrows)
  - Real-time output streaming from menu bar actions
  - Always-on-top floating behavior
  - Retro terminal aesthetic (Menlo, green on black)
"""

import subprocess
import threading
from datetime import datetime

from gerdsenai_optimac.gui import themes

try:
    from AppKit import (
        NSPanel,
        NSMakeRect,
        NSColor,
        NSFont,
        NSScrollView,
        NSTextView,
        NSTextField,
        NSButton,
        NSBezelStyleSmallSquare,
        NSFloatingWindowLevel,
        NSTitledWindowMask,
        NSClosableWindowMask,
        NSResizableWindowMask,
        NSMiniaturizableWindowMask,
        NSBackingStoreBuffered,
        NSForegroundColorAttributeName,
        NSFontAttributeName,
    )
    from Foundation import NSObject, NSRange

    HAS_APPKIT = True
except ImportError:
    HAS_APPKIT = False


# ── Theme color helpers ──────────────────────────────────────────────


def _hex_to_rgba(hex_str, alpha=1.0):
    """Convert hex color string to RGBA tuple (0.0–1.0)."""
    h = hex_str.lstrip("#")
    r, g, b = int(h[0:2], 16) / 255.0, int(h[2:4], 16) / 255.0, int(h[4:6], 16) / 255.0
    return (r, g, b, alpha)


_BG = _hex_to_rgba(themes.BG_COLOR, 0.92)
_FG = _hex_to_rgba(themes.FG_COLOR)
_FG_DIM = _hex_to_rgba(themes.FG_DIM)
_ACCENT = _hex_to_rgba(themes.ACCENT_COLOR)
_FONT_NAME = themes.FONT_FAMILY
_FONT_SIZE = float(themes.FONT_SIZE)


class TerminalWidget:
    """
    Floating mini-terminal window.

    Usage:
        widget = TerminalWidget()
        widget.show()
        widget.append("Hello from OptiMac\\n")
        widget.run_shell("ls -la /tmp")
    """

    def __init__(self):
        self._panel = None
        self._text_view = None
        self._input_field = None
        self._command_history = []
        self._history_index = -1
        self._visible = False
        self._delegate = None
        self._close_delegate = None
        self._on_close_callback = None

        if HAS_APPKIT:
            self._build()

    def _build(self):
        """Build the NSPanel and its subviews."""
        # Create floating panel
        frame = NSMakeRect(100, 200, 520, 320)
        style = (
            NSTitledWindowMask
            | NSClosableWindowMask
            | NSResizableWindowMask
            | NSMiniaturizableWindowMask
        )
        self._panel = NSPanel.alloc().initWithContentRect_styleMask_backing_defer_(
            frame, style, NSBackingStoreBuffered, False
        )
        self._panel.setTitle_("OptiMac Terminal")
        self._panel.setLevel_(NSFloatingWindowLevel)
        self._panel.setFloatingPanel_(True)
        self._panel.setBecomesKeyOnlyIfNeeded_(True)
        self._panel.setMinSize_((360, 200))

        # Delegate for close-button sync
        self._close_delegate = _PanelCloseDelegate.alloc().initWithWidget_(self)
        self._panel.setDelegate_(self._close_delegate)

        # Background color
        bg_color = NSColor.colorWithCalibratedRed_green_blue_alpha_(*_BG)
        self._panel.setBackgroundColor_(bg_color)

        content = self._panel.contentView()
        content_frame = content.frame()
        cw = content_frame.size.width
        ch = content_frame.size.height

        # ── Scroll view + text view (output area) ──
        input_height = 28
        button_width = 60
        padding = 4

        scroll_frame = NSMakeRect(
            padding,
            input_height + padding * 2,
            cw - padding * 2,
            ch - input_height - padding * 3,
        )
        scroll_view = NSScrollView.alloc().initWithFrame_(scroll_frame)
        scroll_view.setHasVerticalScroller_(True)
        scroll_view.setHasHorizontalScroller_(False)
        scroll_view.setAutoresizingMask_(0b010010)  # Flex width + height
        scroll_view.setBorderType_(0)  # No border

        text_frame = NSMakeRect(0, 0, scroll_frame.size.width, scroll_frame.size.height)
        self._text_view = NSTextView.alloc().initWithFrame_(text_frame)
        self._text_view.setEditable_(False)
        self._text_view.setSelectable_(True)
        self._text_view.setRichText_(False)
        self._text_view.setBackgroundColor_(bg_color)
        self._text_view.setTextColor_(
            NSColor.colorWithCalibratedRed_green_blue_alpha_(*_FG)
        )
        self._text_view.setFont_(NSFont.fontWithName_size_(_FONT_NAME, _FONT_SIZE))
        self._text_view.setAutoresizingMask_(0b010010)

        scroll_view.setDocumentView_(self._text_view)
        content.addSubview_(scroll_view)

        # ── Input field ──
        input_frame = NSMakeRect(
            padding, padding, cw - button_width - padding * 3, input_height
        )
        self._input_field = NSTextField.alloc().initWithFrame_(input_frame)
        self._input_field.setFont_(NSFont.fontWithName_size_(_FONT_NAME, _FONT_SIZE))
        self._input_field.setTextColor_(
            NSColor.colorWithCalibratedRed_green_blue_alpha_(*_FG)
        )
        self._input_field.setBackgroundColor_(
            NSColor.colorWithCalibratedRed_green_blue_alpha_(0.0, 0.06, 0.0, 1.0)
        )
        self._input_field.setFocusRingType_(1)  # None
        self._input_field.setBordered_(True)
        self._input_field.setPlaceholderString_("Type a command...")
        self._input_field.setAutoresizingMask_(0b000010)  # Flex width
        content.addSubview_(self._input_field)

        # ── Run button ──
        btn_frame = NSMakeRect(
            cw - button_width - padding, padding, button_width, input_height
        )
        run_btn = NSButton.alloc().initWithFrame_(btn_frame)
        run_btn.setTitle_("Run")
        run_btn.setBezelStyle_(NSBezelStyleSmallSquare)
        run_btn.setFont_(NSFont.fontWithName_size_(_FONT_NAME, _FONT_SIZE))
        run_btn.setAutoresizingMask_(0b000001)  # Anchored right

        # Set action via delegate
        self._delegate = _TerminalDelegate.alloc().initWithWidget_(self)
        run_btn.setTarget_(self._delegate)
        run_btn.setAction_(self._delegate.runCommand_)
        self._input_field.setTarget_(self._delegate)
        self._input_field.setAction_(self._delegate.runCommand_)
        content.addSubview_(run_btn)

        # Welcome message
        self._append_styled(
            "OptiMac Terminal v1.0\n"
            "Type a command or use menu actions.\n"
            "\u2500" * 40 + "\n",
            color=_FG_DIM,
        )

    def set_on_close(self, callback):
        """Register a callback invoked when the panel is closed via ✕."""
        self._on_close_callback = callback

    def show(self):
        """Show and focus the terminal widget."""
        if not HAS_APPKIT or not self._panel:
            return
        self._panel.makeKeyAndOrderFront_(None)
        self._visible = True

    def hide(self):
        """Hide the terminal widget."""
        if not HAS_APPKIT or not self._panel:
            return
        self._panel.orderOut_(None)
        self._visible = False

    def toggle(self):
        """Toggle visibility."""
        if self._visible:
            self.hide()
        else:
            self.show()

    def is_visible(self):
        """Return whether the widget is currently visible."""
        return self._visible

    def append(self, text):
        """Append plain text to the terminal output."""
        if not HAS_APPKIT or not self._text_view:
            return
        self._append_styled(text, color=_FG)

    def append_info(self, text):
        """Append informational text (dimmed)."""
        if not HAS_APPKIT or not self._text_view:
            return
        self._append_styled(text, color=_FG_DIM)

    def append_action(self, action_name, result_text):
        """Append action result with header."""
        ts = datetime.now().strftime("%H:%M:%S")
        self._append_styled(
            f"\n[{ts}] {action_name}\n",
            color=_ACCENT,
        )
        self._append_styled(result_text + "\n", color=_FG)

    def clear(self):
        """Clear all terminal output."""
        if not HAS_APPKIT or not self._text_view:
            return
        storage = self._text_view.textStorage()
        length = storage.mutableString().length()
        if length > 0:
            storage.deleteCharactersInRange_(NSRange(0, length))

    def run_shell(self, command):
        """Run a shell command and pipe output to the widget."""
        ts = datetime.now().strftime("%H:%M:%S")
        self._append_styled(f"\n[{ts}] $ {command}\n", color=_ACCENT)

        def _worker():
            try:
                proc = subprocess.Popen(
                    command,
                    shell=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                )
                for line in proc.stdout:
                    self._append_on_main(line, _FG)
                proc.wait()
                if proc.returncode != 0:
                    self._append_on_main(f"[exit {proc.returncode}]\n", _FG_DIM)
                else:
                    self._append_on_main("[done]\n", _FG_DIM)
            except Exception as e:
                self._append_on_main(f"[error] {e}\n", _FG_DIM)

        threading.Thread(target=_worker, daemon=True).start()

    def _handle_command(self):
        """Handle command from input field."""
        if not self._input_field:
            return
        cmd = self._input_field.stringValue().strip()
        if not cmd:
            return

        self._command_history.append(cmd)
        self._history_index = -1
        self._input_field.setStringValue_("")

        if cmd.lower() == "clear":
            self.clear()
        elif cmd.lower() == "help":
            self._append_styled(
                "\nAvailable commands:\n"
                "  clear    -- Clear terminal output\n"
                "  help     -- Show this message\n"
                "  Any other input runs as a shell command.\n\n",
                color=_FG_DIM,
            )
        else:
            self.run_shell(cmd)

    def _handle_panel_close(self):
        """Called by the close delegate when panel ✕ is clicked."""
        self._visible = False
        if self._on_close_callback:
            self._on_close_callback()

    def _append_styled(self, text, color=_FG):
        """Append attributed string to the text view."""
        if not self._text_view:
            return
        try:
            from Foundation import NSAttributedString

            attrs = {
                NSForegroundColorAttributeName: NSColor.colorWithCalibratedRed_green_blue_alpha_(
                    *color
                ),
                NSFontAttributeName: NSFont.fontWithName_size_(_FONT_NAME, _FONT_SIZE),
            }
            attr_str = NSAttributedString.alloc().initWithString_attributes_(
                text, attrs
            )
            storage = self._text_view.textStorage()
            storage.appendAttributedString_(attr_str)
            # Auto-scroll to bottom
            end = storage.mutableString().length()
            self._text_view.scrollRangeToVisible_(NSRange(end, 0))
        except Exception:
            pass

    def _append_on_main(self, text, color):
        """Thread-safe append by dispatching to main thread."""
        try:
            from PyObjCTools import AppHelper

            AppHelper.callAfter(self._append_styled, text, color)
        except Exception:
            self._append_styled(text, color)


if HAS_APPKIT:

    class _TerminalDelegate(NSObject):
        """Objective-C delegate for button/field actions."""

        def initWithWidget_(self, widget):
            self = self.init()
            if self is None:
                return None
            self._widget = widget
            return self

        def runCommand_(self, sender):
            self._widget._handle_command()

    class _PanelCloseDelegate(NSObject):
        """Delegate that syncs visibility state when panel is closed via ✕."""

        def initWithWidget_(self, widget):
            self = self.init()
            if self is None:
                return None
            self._widget = widget
            return self

        def windowWillClose_(self, notification):
            self._widget._handle_panel_close()

else:
    _TerminalDelegate = None
    _PanelCloseDelegate = None
