from __future__ import annotations
import tkinter.font as tkfont


def schedule(tree, tk_root, after_handle_ref) -> None:
    try:
        if after_handle_ref[0]:
            try:
                top = tk_root.winfo_toplevel()
            except Exception:
                top = tk_root
            top.after_cancel(after_handle_ref[0])
    except Exception:
        pass
    try:
        top = tk_root.winfo_toplevel()
    except Exception:
        top = tk_root
    after_handle_ref[0] = top.after(50, autosize_columns, tree, after_handle_ref)


def autosize_columns(tree, after_handle_ref) -> None:
    try:
        font = tkfont.nametofont("TkDefaultFont")
        max_model = len("Model")
        for item_id in tree.get_children(""):
            vals = tree.item(item_id, "values")
            if not vals:
                continue
            txt = str(vals[0])
            if len(txt) > max_model:
                max_model = len(txt)
        model_samples = ["Model"]
        for item_id in tree.get_children(""):
            vals = tree.item(item_id, "values")
            if vals and vals[0]:
                model_samples.append(str(vals[0]))
        model_px = max((font.measure(s) for s in model_samples), default=80) + 24
        model_px = max(100, min(model_px, 240))
        status_samples = ["Status", "Recording", "Checking…", "Unavailable", "No stream", "Live", "Idle", "Error"]
        status_px = max((font.measure(s) for s in status_samples), default=80) + 24
        status_px = max(90, min(status_px, 160))
        elapsed_px = font.measure("00:00:00") + 24
        elapsed_px = max(80, min(elapsed_px, 100))
        tree.column("Model", width=int(model_px), stretch=False)
        tree.column("Status", width=int(status_px), stretch=False)
        tree.column("Elapsed", width=int(elapsed_px), stretch=False)
        tree.column("URL", stretch=True, minwidth=120)
    except Exception:
        pass
    finally:
        after_handle_ref[0] = None
