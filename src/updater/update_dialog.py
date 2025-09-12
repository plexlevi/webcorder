"""
Update Dialog for WebCorder
UI component for showing update notifications and handling user choices
"""
from __future__ import annotations
import tkinter as tk
from tkinter import ttk, messagebox
from typing import Dict, Callable, Optional
import asyncio
import threading
from pathlib import Path


class UpdateDialog:
    """Dialog window for handling update notifications"""
    
    def __init__(self, parent, update_info: Dict, on_install: Callable, 
                 on_skip: Callable, on_dismiss: Callable):
        self.parent = parent
        self.update_info = update_info
        self.on_install = on_install
        self.on_skip = on_skip  
        self.on_dismiss = on_dismiss
        self.dialog: Optional[tk.Toplevel] = None
        self.progress_var: Optional[tk.DoubleVar] = None
        self.status_var: Optional[tk.StringVar] = None
        self.progress_frame: Optional[ttk.Frame] = None
        self.skip_var: Optional[tk.BooleanVar] = None
        
    def show(self):
        """Show the update dialog"""
        self.dialog = tk.Toplevel(self.parent)
        self.dialog.title("WebCorder Frissítés Elérhető")
        self.dialog.geometry("500x400")
        self.dialog.resizable(False, False)
        
        # Center the dialog
        self.dialog.transient(self.parent)
        self.dialog.grab_set()
        
        # Center on parent
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() - self.dialog.winfo_width()) // 2
        y = (self.dialog.winfo_screenheight() - self.dialog.winfo_height()) // 2
        self.dialog.geometry(f"+{x}+{y}")
        
        self._create_widgets()
        
        # Handle dialog close
        self.dialog.protocol("WM_DELETE_WINDOW", self._on_close)
        
    def _create_widgets(self):
        """Create dialog widgets"""
        main_frame = ttk.Frame(self.dialog, padding="20")
        main_frame.pack(fill="both", expand=True)
        
        # Header
        header_frame = ttk.Frame(main_frame)
        header_frame.pack(fill="x", pady=(0, 20))
        
        # Icon and title
        title_label = ttk.Label(header_frame, text="🎉 Új WebCorder verzió elérhető!", 
                               font=("Segoe UI", 14, "bold"))
        title_label.pack(anchor="w")
        
        # Version info
        version_info = f"Jelenlegi verzió: {self._get_current_version()}"
        version_info += f"\nÚj verzió: {self.update_info['version']}"
        
        version_label = ttk.Label(header_frame, text=version_info, 
                                 font=("Segoe UI", 10))
        version_label.pack(anchor="w", pady=(5, 0))
        
        # Release notes
        notes_frame = ttk.LabelFrame(main_frame, text="Újdonságok:", padding="10")
        notes_frame.pack(fill="both", expand=True, pady=(0, 20))
        
        # Scrollable text for release notes
        text_frame = ttk.Frame(notes_frame)
        text_frame.pack(fill="both", expand=True)
        
        scrollbar = ttk.Scrollbar(text_frame)
        scrollbar.pack(side="right", fill="y")
        
        notes_text = tk.Text(text_frame, wrap="word", height=8, 
                            yscrollcommand=scrollbar.set, 
                            font=("Segoe UI", 9))
        notes_text.pack(side="left", fill="both", expand=True)
        scrollbar.config(command=notes_text.yview)
        
        # Insert release notes
        release_notes = self.update_info.get('body', 'Nincs elérhető leírás.')
        notes_text.insert("1.0", release_notes)
        notes_text.config(state="disabled")
        
        # Progress bar (initially hidden)
        self.progress_frame = ttk.Frame(main_frame)
        
        self.status_var = tk.StringVar(value="")
        status_label = ttk.Label(self.progress_frame, textvariable=self.status_var)
        status_label.pack(anchor="w", pady=(0, 5))
        
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(self.progress_frame, 
                                          variable=self.progress_var,
                                          maximum=100)
        self.progress_bar.pack(fill="x", pady=(0, 10))
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill="x", pady=(10, 0))
        
        # Skip version checkbox
        self.skip_var = tk.BooleanVar()
        skip_check = ttk.Checkbutton(button_frame, 
                                   text=f"Ne kérdezd meg újra ezt a verziót ({self.update_info['version']})",
                                   variable=self.skip_var)
        skip_check.pack(anchor="w", pady=(0, 10))
        
        # Button container
        btn_container = ttk.Frame(button_frame)
        btn_container.pack(fill="x")
        
        # Install button
        install_btn = ttk.Button(btn_container, text="🔄 Telepítés most", 
                               command=self._on_install_clicked,
                               style="Accent.TButton")
        install_btn.pack(side="right", padx=(5, 0))
        
        # Dismiss button  
        dismiss_btn = ttk.Button(btn_container, text="🕒 Később", 
                               command=self._on_dismiss_clicked)
        dismiss_btn.pack(side="right", padx=(5, 0))
        
        # More info button
        info_btn = ttk.Button(btn_container, text="ℹ️ További info", 
                            command=self._on_more_info)
        info_btn.pack(side="left")
        
    def _on_install_clicked(self):
        """Handle install button click"""
        if not self.dialog or not self.progress_frame or not self.status_var or not self.progress_var:
            return
            
        # Show progress
        self.progress_frame.pack(fill="x", pady=(10, 0))
        self.status_var.set("Frissítés letöltése...")
        self.progress_var.set(0)
        
        # Disable buttons during installation
        for child in self.dialog.winfo_children():
            if isinstance(child, ttk.Frame):
                self._disable_buttons(child)
        
        # Start installation in background
        def install_worker():
            success = self.on_install(self.update_info, self._update_progress)
            if success:
                if self.dialog:
                    self.dialog.after(0, self._installation_success)
            else:
                if self.dialog:
                    self.dialog.after(0, self._installation_failed)
        
        threading.Thread(target=install_worker, daemon=True).start()
        
    def _on_dismiss_clicked(self):
        """Handle dismiss button click"""
        if self.skip_var and self.skip_var.get():
            self.on_skip(self.update_info['version'])
        self.on_dismiss()
        if self.dialog:
            self.dialog.destroy()
        
    def _on_more_info(self):
        """Open release page in browser"""
        import webbrowser
        webbrowser.open(self.update_info.get('html_url', ''))
        
    def _on_close(self):
        """Handle dialog close"""
        self._on_dismiss_clicked()
        
    def _update_progress(self, progress: float, status: str = ""):
        """Update progress bar and status"""
        def update_ui():
            if self.progress_var:
                self.progress_var.set(progress)
            if status and self.status_var:
                self.status_var.set(status)
        
        if self.dialog:
            self.dialog.after(0, update_ui)
        
    def _installation_success(self):
        """Handle successful installation"""
        if self.status_var:
            self.status_var.set("✅ Telepítés sikeresen elindítva!")
        
        if self.dialog:
            messagebox.showinfo("Telepítés", 
                              "A telepítő elindult. A WebCorder most bezáródik a frissítés befejezéséhez.",
                              parent=self.dialog)
            # Close application for update
            self.dialog.quit()
        else:
            messagebox.showinfo("Telepítés", 
                              "A telepítő elindult. A WebCorder most bezáródik a frissítés befejezéséhez.")
        
    def _installation_failed(self):
        """Handle failed installation"""
        if self.status_var:
            self.status_var.set("❌ Telepítés sikertelen!")
        
        if self.dialog:
            messagebox.showerror("Hiba", 
                               "A frissítés telepítése nem sikerült. Próbálja meg manuálisan.",
                               parent=self.dialog)
            self.dialog.destroy()
        else:
            messagebox.showerror("Hiba", 
                               "A frissítés telepítése nem sikerült. Próbálja meg manuálisan.")
        
    def _disable_buttons(self, widget):
        """Recursively disable all buttons in widget"""
        for child in widget.winfo_children():
            if isinstance(child, ttk.Button):
                child.config(state="disabled")
            elif hasattr(child, 'winfo_children'):
                self._disable_buttons(child)
                
    def _get_current_version(self) -> str:
        """Get current application version"""
        # TODO: Get from version manager or app constant
        return "1.0"
