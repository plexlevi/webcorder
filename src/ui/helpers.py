from __future__ import annotations
import tkinter as tk
from tkinter import ttk


def attach_entry_context_menu(entry: ttk.Entry):
    menu = tk.Menu(entry, tearoff=False)
    menu.add_command(label="Kivágás", command=lambda: entry.event_generate("<<Cut>>"))
    menu.add_command(label="Másolás", command=lambda: entry.event_generate("<<Copy>>"))
    menu.add_command(label="Beillesztés", command=lambda: entry.event_generate("<<Paste>>"))

    def show_menu(event):
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    entry.bind("<Button-3>", show_menu)


class UrlTooltip:
    def __init__(self, tree: ttk.Treeview):
        self.tree = tree
        self._win = None
        self._after = None
        self._last = (None, None)
        self.tree.bind("<Motion>", self._on_motion)
        self.tree.bind("<Leave>", lambda e: self.hide())

    def _on_motion(self, event):
        row = self.tree.identify_row(event.y)
        col = self.tree.identify_column(event.x)
        if not row or col != "#2":
            self.hide()
            return
        if (row, col) == self._last:
            return
        self._last = (row, col)
        vals = self.tree.item(row, "values")
        if not vals or len(vals) < 2:
            self.hide()
            return
        url = str(vals[1])
        if self._after:
            try:
                self.tree.after_cancel(self._after)
            except Exception:
                pass
        self._after = self.tree.after(400, self._delayed_show, event.x_root, event.y_root + 16, url)

    def _delayed_show(self, x: int, y: int, url: str):
        try:
            self.show(x, y, url)
        except Exception:
            pass

    def show(self, x, y, text):
        self.hide()
        try:
            win = tk.Toplevel(self.tree)
            win.wm_overrideredirect(True)
            win.wm_geometry(f"+{x}+{y}")
            lbl = ttk.Label(win, text=text, background="#FFFFE0", relief="solid", borderwidth=1, padding=(4, 2))
            lbl.pack()
            self._win = win
        except Exception:
            self._win = None

    def hide(self):
        if self._after:
            try:
                self.tree.after_cancel(self._after)
            except Exception:
                pass
            self._after = None
        if self._win:
            try:
                self._win.destroy()
            except Exception:
                pass
            self._win = None
