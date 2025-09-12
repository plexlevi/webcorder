from __future__ import annotations
from tkinter import ttk
import tkinter as tk


def build(app) -> ttk.Frame:
    btns_lr = ttk.Frame(app)
    btns_lr.grid(row=1, column=0, columnspan=4, sticky="ew", padx=0, pady=(3, 3))  # Added minimal padding

    ttk.Button(btns_lr, text="Check All", command=app._check_all).grid(row=0, column=0, sticky="w")
    
    # AutoRecord controls
    ttk.Separator(btns_lr, orient='vertical').grid(row=0, column=1, sticky="ns", padx=(10, 10))
    
    # AutoRecord toggle button
    app.autorecord_btn = ttk.Button(btns_lr, text="🔄 AutoRecord OFF", command=app._toggle_autorecord)
    app.autorecord_btn.grid(row=0, column=2, sticky="w", padx=(0, 6))
    
    # Add/Remove from AutoRecord button
    app.autorecord_toggle_btn = ttk.Button(btns_lr, text="➕ Add to AutoRecord", command=app._toggle_autorecord_for_selected)
    app.autorecord_toggle_btn.grid(row=0, column=3, sticky="w")

    # Separator and Update check button  
    ttk.Separator(btns_lr, orient='vertical').grid(row=0, column=4, sticky="ns", padx=(10, 10))
    
    # Check for Updates button
    update_btn = ttk.Button(btns_lr, text="🔄 Check Updates", command=app._manual_update_check)
    update_btn.grid(row=0, column=5, sticky="w")

    return btns_lr
