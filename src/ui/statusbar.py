from __future__ import annotations
import tkinter as tk
from tkinter import ttk

# from core.monitoring import system_usage  # Temporarily disabled


def build(app):
    status_bar = ttk.Frame(app)
    status_bar.grid(row=5, column=0, columnspan=4, sticky="ew", pady=(6, 0))  # Row 5 - at the bottom
    status_bar.columnconfigure(0, weight=0)
    status_bar.columnconfigure(1, weight=1)
    ttk.Label(status_bar, textvariable=app.status_var, anchor="w").grid(row=0, column=0, sticky="w")
    
    # Create a frame for resource info with multiple labels
    resource_frame = ttk.Frame(status_bar)
    resource_frame.grid(row=0, column=1, sticky="e")
    
    # CPU and RAM info
    app.cpu_ram_var = tk.StringVar(value="")
    cpu_ram_lbl = ttk.Label(resource_frame, textvariable=app.cpu_ram_var, anchor="e")
    try:
        cpu_ram_lbl.configure(font=("TkFixedFont", 9))
    except Exception:
        pass
    cpu_ram_lbl.grid(row=0, column=0, sticky="e")
    
    # Active rec label
    active_rec_lbl = ttk.Label(resource_frame, text=" | Active rec: ", anchor="e")
    try:
        active_rec_lbl.configure(font=("TkFixedFont", 9))
    except Exception:
        pass
    active_rec_lbl.grid(row=0, column=1, sticky="e")
    
    # Active rec number (red and bold)
    app.active_rec_var = tk.StringVar(value="-")  # Start with dash
    app.active_num_lbl = ttk.Label(resource_frame, textvariable=app.active_rec_var, anchor="w")
    try:
        app.active_num_lbl.configure(font=("TkFixedFont", 9), foreground="black")  # Start with black
    except Exception:
        pass
    app.active_num_lbl.grid(row=0, column=2, sticky="w")
    
    # AutoRecord status
    autorecord_lbl = ttk.Label(resource_frame, text=" | AutoRec: ", anchor="e")
    try:
        autorecord_lbl.configure(font=("TkFixedFont", 9))
    except Exception:
        pass
    autorecord_lbl.grid(row=0, column=3, sticky="e")
    
    # AutoRecord status value
    app.autorecord_statusbar_var = tk.StringVar(value="OFF")
    app.autorecord_statusbar_lbl = ttk.Label(resource_frame, textvariable=app.autorecord_statusbar_var, anchor="w")
    try:
        app.autorecord_statusbar_lbl.configure(font=("TkFixedFont", 9), foreground="gray")
    except Exception:
        pass
    app.autorecord_statusbar_lbl.grid(row=0, column=4, sticky="w")

    # No disk/gpu background sampling; keep UI light
    try:
        # Kick off periodic monitoring updates
        app.after(1000, lambda: _tick(app))
    except Exception:
        pass


def _tick(app):
    try:
        active = 0
        for sess in getattr(app, "sessions", {}).values():
            try:
                if getattr(sess, "rec_proc", None) and sess.rec_proc.poll() is None:
                    active += 1
            except Exception:
                pass
        
        # Update CPU/RAM info
        if hasattr(app, 'cpu_ram_var'):
            try:
                import psutil
                cpu = psutil.cpu_percent(interval=None)
                ram = getattr(psutil.virtual_memory(), 'percent', 0)
                app.cpu_ram_var.set(f"CPU: {cpu:.0f}% | RAM: {ram:.0f}%")
            except Exception:
                app.cpu_ram_var.set("CPU: 0% | RAM: 0%")
        
        # Update active recordings count with conditional styling
        if hasattr(app, 'active_rec_var') and hasattr(app, 'active_num_lbl'):
            if active == 0:
                app.active_rec_var.set("-")
                # Set to black color for zero recordings
                try:
                    app.active_num_lbl.configure(foreground="black", font=("TkFixedFont", 9))
                except Exception:
                    pass
            else:
                app.active_rec_var.set(str(active))
                # Set to red and bold for active recordings
                try:
                    app.active_num_lbl.configure(foreground="red", font=("TkFixedFont", 9, "bold"))
                except Exception:
                    pass
        
        # Keep old resource_var for compatibility
        if hasattr(app, 'resource_var'):
            app.resource_var.set("CPU/RAM monitoring disabled")  # system_usage(active)
            
        # Update AutoRecord status in statusbar
        if hasattr(app, 'autorecord_statusbar_var') and hasattr(app, 'autorecord_statusbar_lbl') and hasattr(app, 'autorecord'):
            try:
                status_info = app.autorecord.get_status_info()
                if status_info['enabled']:
                    status_text = f"ON ({status_info['monitored_count']})"
                    app.autorecord_statusbar_var.set(status_text)
                    app.autorecord_statusbar_lbl.configure(foreground="green", font=("TkFixedFont", 9, "bold"))
                else:
                    app.autorecord_statusbar_var.set("OFF")
                    app.autorecord_statusbar_lbl.configure(foreground="gray", font=("TkFixedFont", 9))
            except Exception:
                app.autorecord_statusbar_var.set("OFF")
                app.autorecord_statusbar_lbl.configure(foreground="gray", font=("TkFixedFont", 9))
            
    except Exception:
        # Keep UI resilient even if something goes wrong
        pass
    try:
        # Stop scheduling if app is closing
        if getattr(app, "_shutting_down", False):
            return
        app.after(1000, lambda: _tick(app))
    except Exception:
        pass
