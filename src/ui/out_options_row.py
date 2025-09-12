from __future__ import annotations
from tkinter import ttk
import tkinter as tk


def build(app) -> ttk.Frame:
    btn_frame = ttk.Frame(app)
    btn_frame.grid(row=3, column=0, columnspan=4, pady=(4, 4), sticky="ew")  # Row 3 - between list and log
    btn_frame.columnconfigure(1, weight=1)  # Changed to column 1 for proper alignment
    

    
    # Output folder - left aligned
    ttk.Label(btn_frame, text="Output:").grid(row=0, column=0, sticky="w", padx=(0, 5))
    output_entry = ttk.Entry(btn_frame, textvariable=app.output_folder_var, width=30)
    output_entry.grid(row=0, column=1, sticky="ew", padx=(0, 5))
    browse_btn = ttk.Button(btn_frame, text="Browse", command=app._browse_out, width=8)
    browse_btn.grid(row=0, column=2, sticky="w", padx=(5, 0))
    
    # Container
    ttk.Label(btn_frame, text="Container:").grid(row=0, column=3, sticky="e", padx=(10, 5))
    app.container_combo = ttk.Combobox(btn_frame, textvariable=app.container_var, values=["mp4", "mkv"], state="readonly", width=6)
    app.container_combo.grid(row=0, column=4, sticky="e")
    
    return btn_frame
