from __future__ import annotations
import threading
import time
import random
import webbrowser
from pathlib import Path
from typing import Optional

import tkinter as tk
from tkinter import ttk, messagebox, filedialog

from src.autorecord.checker import resolve_page_url, check_session_status
from src.autorecord.stream_monitor import StreamMonitor
from src.models import Session
from src.storage import (
    load_urls as persist_load_urls,
    save_urls as persist_save_urls,
    load_settings as persist_load_settings,
    save_settings as persist_save_settings,
    load_models as persist_load_models,
    save_models as persist_save_models,
    add_model as persist_add_model,
    update_model_autorecord as persist_update_model_autorecord,
    remove_model as persist_remove_model,
)
from .helpers import attach_entry_context_menu
from src.recording import start_record as rec_start, stop_record as rec_stop
from .list_view import build as build_list_view
from .statusbar import build as build_statusbar
from .actions import build as build_actions
from .out_options_row import build as build_out_options_row
from src.media import create_vlc_player, is_vlc_available
from src.utils import set_log_callback


class App(ttk.Frame):
    def __init__(self, master: tk.Misc, root: Optional[tk.Tk] = None):
        super().__init__(master, padding=10)  # Doubled padding from 5 to 10
        self._root = root
        if root is not None:
            root.title("Webcorder – Stream Recorder")
            try:
                root.geometry("620x700")
                root.minsize(620, 700)
            except Exception:
                pass
        self.grid(sticky="nsew")

        self.master.columnconfigure(0, weight=1)
        self.master.rowconfigure(0, weight=1)
        self.columnconfigure(1, weight=1)
        for r in range(0, 8):  # Increased range for more rows
            try:
                self.rowconfigure(r, weight=0)
            except Exception:
                pass
        
        # Make main paned area (row 2) expandable
        self.rowconfigure(2, weight=1)

        # State variables
        self.url_var = tk.StringVar()
        self.container_var = tk.StringVar(value="mp4")
        self.output_folder_var = tk.StringVar(value=str(Path.home() / "Desktop"))
        self.status_var = tk.StringVar(value="Ready")
        self.record_status_var = tk.StringVar(value="[Idle]")
        self.resource_var = tk.StringVar(value="")
        
        # Status bar variables for styled display
        self.cpu_ram_var = tk.StringVar(value="")
        self.active_rec_var = tk.StringVar(value="0")

        # Session storage
        self.sessions: dict[str, Session] = {}

        # UI components (initialized later by build functions)
        self.record_btn = None  # Will be set by build_out_options_row
        self.autorecord_btn = None  # Will be set by build_actions
        self.autorecord_toggle_btn = None  # Will be set by build_actions
        
        # Callback list for separate windows to update their record buttons
        self._separate_window_callbacks = []
        
        # Track which models have open VLC windows (model_name -> window reference)
        self._open_vlc_windows = {}

        # Embedded preview state
        self._preview_player = None  # VLC player
        self._preview_current_url = None
        self._fullscreen_window = None
        self._fullscreen_player = None  # VLC player for fullscreen

        # Track all active processes for cleanup
        self._active_processes = set()
        self._proc_watch = set()  # Track PIDs of our spawned processes
        
        # Check VLC availability
        self._vlc_available = is_vlc_available()
        if not self._vlc_available:
            self.log_write("WARNING: VLC not available. Preview will be limited.")

        # Set up global log callback for resolver logging
        set_log_callback(self.log_write)

        # Initialize Update Manager
        from src.updater import UpdateManager
        from src.updater.token_manager import get_token_source, is_token_configured
        from src.storage import config_path
        
        # Log token status for debugging
        if is_token_configured():
            self.log_write(f"GitHub token loaded from: {get_token_source()}")
        else:
            self.log_write("WARNING: No GitHub token configured - updates may not work for private repo")
        
        self.update_manager = UpdateManager(
            config_path(), 
            repo_owner="plexlevi", 
            repo_name="webcorder"
            # github_token automatically loaded from secure sources
        )
        set_log_callback(self.log_write)

        # Initialize AutoRecord manager
        from src.autorecord.autorecord import AutoRecordManager
        self.autorecord = AutoRecordManager(self, log_callback=self.log_write)
        
        # Initialize Stream Monitor for automatic reconnection
        self.stream_monitor = StreamMonitor(self)

        # Load settings (may override defaults)
        try:
            self._load_settings()
        except Exception:
            pass

        # URL input row (row 0)
        ttk.Label(self, text="Stream URL:").grid(row=0, column=0, sticky="w", padx=(0, 6))
        url_entry = ttk.Entry(self, textvariable=self.url_var)
        url_entry.grid(row=0, column=1, columnspan=2, sticky="ew")
        ttk.Button(self, text="Add", command=self._add_url).grid(row=0, column=3, sticky="ew")
        attach_entry_context_menu(url_entry)

        # Actions row (row 1)
        build_actions(self)

        # Create main vertical paned window (row 2)
        # Build list view
        self._build_list_area()
        self.list_container.grid(row=2, column=0, columnspan=4, sticky="nsew", padx=5, pady=(3, 3))

        # Record row (row 3)
        build_out_options_row(self)

        # Build log area (row 4)
        self._build_log_area()
        self.log_container.grid(row=4, column=0, columnspan=4, sticky="ew", padx=5, pady=(0, 3))

        # Status bar (row 5)
        build_statusbar(self)

        # Configure custom button styles
        self._configure_button_styles()

        # Make main paned area expandable
        self.rowconfigure(2, weight=1)

        # Load URL list
        try:
            self._load_urls()
            # Add a small delay then reorder again to ensure proper positioning
            self.after(100, self._reorder_full_list)
            # Update all tree visuals to show Auto status correctly
            self.after(200, self._update_all_tree_visuals)
            # Restore AutoRecord state after everything is loaded
            self.after(300, self._restore_autorecord_state_from_settings)
            # Check for updates after everything is loaded
            self.after(500, self._check_for_updates_on_startup)
        except Exception:
            pass

    def _build_list_area(self):
        """Build the list area in a container frame"""
        # Create container frame
        self.list_container = ttk.Frame(self)
        
        # Add list view to container
        self._autosize_after_holder = [None]
        self.tree = build_list_view(self.list_container, self)
        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)
        self.tree.bind("<Double-1>", self._on_tree_double_click)
        self.tree.bind("<Button-3>", self._on_tree_right_click)  # Right click

    def _build_log_area(self):
        """Build the log area in a container frame with label"""
        # Create container frame
        self.log_container = ttk.Frame(self)
        
        # Log label at the top
        ttk.Label(self.log_container, text="Log:").grid(row=0, column=0, columnspan=4, sticky="w", padx=0, pady=(3, 0))
        
        # Log text area
        self.log = tk.Text(self.log_container, height=3, state="disabled", bg="white", fg="black")
        self.log.grid(row=1, column=0, columnspan=4, sticky="nsew", padx=0, pady=0)  # Removed padding
        
        # Configure log scrolling
        log_scroll = ttk.Scrollbar(self.log_container, command=self.log.yview)
        self.log.configure(yscrollcommand=log_scroll.set)
        log_scroll.grid(row=1, column=4, sticky="ns", padx=0, pady=0)  # Removed padding
        
        # Make log area expandable within its container
        self.log_container.columnconfigure(0, weight=1)
        self.log_container.rowconfigure(1, weight=1)

    def _configure_button_styles(self):
        """Configure custom button styles"""
        style = ttk.Style()
        
        # Green style for AutoRecord ON state
        style.configure("Green.TButton", 
                       foreground="green",
                       focuscolor="none")
        
        # Record button styles (existing functionality)
        style.configure("Record.TButton", 
                       foreground="black",
                       focuscolor="none")
        
        style.configure("RecordStop.TButton", 
                       foreground="red",
                       focuscolor="none")

    def _build_preview(self):
        """Build embedded video preview area"""
        # Create container frame
        self.preview_container = ttk.Frame(self)
        self.preview_container.columnconfigure(0, weight=1)
        self.preview_container.rowconfigure(0, weight=1)
        
        # Video canvas (embedded player area)
        self.video_canvas = tk.Canvas(
            self.preview_container, 
            bg='black', 
            height=300,
            relief=tk.SUNKEN,
            bd=2
        )
        self.video_canvas.grid(row=0, column=0, sticky="nsew", padx=0, pady=0)  # Removed padding
        
        # Controls frame
        controls_frame = ttk.Frame(self.preview_container)
        controls_frame.grid(row=1, column=0, sticky="ew", padx=0, pady=(3, 0))  # Minimal padding
        controls_frame.columnconfigure(1, weight=1)  # Expand after play button
        
        # Play/Stop button with graphical symbols as Label
        self.play_button = ttk.Label(
            controls_frame,
            text="▶",  # Play symbol
            font=("Segoe UI", 22),  # Even larger font for better visibility
            cursor="hand2",
            anchor="center"  # Center the text
        )
        self.play_button.grid(row=0, column=0, padx=(0, 10), sticky="")  # Natural alignment
        self.play_button.bind("<Button-1>", lambda e: self._toggle_preview())
        
        # Bind canvas events - only resize and keyboard
        self.video_canvas.bind('<Configure>', self._on_canvas_configure)
        
        # Make canvas focusable for keyboard events
        self.video_canvas.focus_set()
        self.video_canvas.bind('<Key-f>', lambda e: self._toggle_fullscreen())
        self.video_canvas.bind('<Key-F>', lambda e: self._toggle_fullscreen())
        # Alternative: bind Alt+Enter for fullscreen toggle
        self.master.bind('<Alt-Return>', lambda e: self._toggle_fullscreen())
        
        # Initialize VLC player if available
        if self._vlc_available:
            try:
                if hasattr(self, 'video_canvas') and self.video_canvas:
                    self._preview_player = create_vlc_player(self.video_canvas)
                    if self._preview_player:
                        self.log_write("VLC video player initialized")
                    else:
                        self.log_write("Failed to create VLC player")
                        self._vlc_available = False
                else:
                    self.log_write("Video canvas not available, VLC preview disabled")
                    self._vlc_available = False
            except Exception as e:
                self.log_write(f"VLC initialization failed: {e}")
                self._vlc_available = False
        
        if not self._vlc_available:
            self.log_write("VLC not available, preview disabled")

    def _toggle_preview(self):
        """Toggle preview playback"""
        if self._preview_player and self._preview_player.is_playing_state():
            self._stop_preview()
        else:
            self._start_preview_selected()

    def _start_preview_selected(self):
        """Start ffplay preview for selected model"""
        sid = self._get_selected_id()
        if not sid:
            self.status_var.set("No model selected for preview")
            return

        sess = self.sessions.get(sid)
        if not sess:
            return

        # Resolve stream if needed
        url = sess.resolved_url
        if not url:
            self.status_var.set("Resolving stream for preview...")
            url = self._resolve(sess.page_url)
            if url:
                sess.resolved_url = url
            else:
                self.status_var.set("No stream available for preview")
                return

        model_name = self._extract_model_name(sess.page_url) or "Unknown"
        self._start_vlc_preview(url, model_name)

    def _start_vlc_preview(self, url: str, model_name: str):
        """Start VLC preview with URL"""
        if not self._vlc_available or not self._preview_player:
            self.status_var.set("VLC not available for preview")
            return

        try:
            # Stop any existing preview
            self._stop_preview()
            
            # Load and play the stream
            if self._preview_player.load_url(url):
                # Set default volume
                self._preview_player.set_volume(50)  # Default volume
                
                if self._preview_player.play():
                    self._preview_current_url = url
                    if hasattr(self, 'play_button') and self.play_button:
                        self.play_button.config(text="⏹")
                    self.status_var.set(f"Preview playing: {model_name}")
                    self.log_write(f"Started VLC preview for {model_name}")
                else:
                    self.status_var.set("Failed to start VLC playback")
            else:
                self.status_var.set("Failed to load stream in VLC")
                
        except Exception as e:
            self.log_write(f"VLC error: {e}")
            self.status_var.set("Preview failed")

    def _stop_preview(self):
        """Stop embedded preview"""
        # Stop VLC player
        if self._preview_player:
            try:
                self._preview_player.stop()
                self.log_write("VLC preview stopped")
            except Exception as e:
                self.log_write(f"Error stopping VLC preview: {e}")
        
        # Stop fullscreen if active
        self._stop_fullscreen()
        
        # Update UI (only if components exist)
        self._preview_current_url = None
        if hasattr(self, 'play_button') and self.play_button:
            self.play_button.config(text="▶")
        self.status_var.set("Preview stopped")

    def _stop_fullscreen(self):
        """Stop fullscreen preview"""
        if self._fullscreen_window:
            try:
                if self._fullscreen_player:
                    self._fullscreen_player.stop()
                    self._fullscreen_player = None
                
                self._fullscreen_window.destroy()
                self._fullscreen_window = None
                
                self.log_write("Fullscreen preview closed")
            except Exception as e:
                self.log_write(f"Error closing fullscreen: {e}")

    def _on_canvas_configure(self, event):
        """Handle canvas resize for embedded player"""
        # VLC handles resizing automatically
        pass

    def _toggle_fullscreen(self):
        """Toggle fullscreen preview window"""
        if self._fullscreen_window:
            # Close fullscreen
            self._stop_fullscreen()
        else:
            # Open fullscreen
            if not self._preview_current_url:
                self.status_var.set("No stream playing for fullscreen")
                return
                
            try:
                self._fullscreen_window = tk.Toplevel()
                self._fullscreen_window.title("Fullscreen Preview")
                self._fullscreen_window.configure(bg="black")
                self._fullscreen_window.attributes('-fullscreen', True)
                
                # ESC to exit fullscreen
                self._fullscreen_window.bind('<Escape>', lambda e: self._toggle_fullscreen())
                self._fullscreen_window.bind('<Double-Button-1>', lambda e: self._toggle_fullscreen())
                
                # Create fullscreen canvas
                fullscreen_canvas = tk.Canvas(self._fullscreen_window, bg="black")
                fullscreen_canvas.pack(fill=tk.BOTH, expand=True)
                
                # Create VLC player for fullscreen
                self._fullscreen_player = create_vlc_player(fullscreen_canvas)
                
                if self._fullscreen_player:
                    # Load and play the same URL
                    if self._fullscreen_player.load_url(self._preview_current_url):
                        self._fullscreen_player.play()
                        self.log_write("Opened fullscreen preview (ESC or double-click to exit)")
                        
                        # Handle window close
                        self._fullscreen_window.protocol("WM_DELETE_WINDOW", self._toggle_fullscreen)
                    else:
                        self._fullscreen_window.destroy()
                        self._fullscreen_window = None
                        self.status_var.set("Failed to load stream in fullscreen")
                else:
                    self._fullscreen_window.destroy()
                    self._fullscreen_window = None
                    self.status_var.set("Failed to create fullscreen player")
                
            except Exception as e:
                self.log_write(f"Error creating fullscreen: {e}")
                if self._fullscreen_window:
                    self._fullscreen_window.destroy()
                    self._fullscreen_window = None

    def _on_tree_double_click(self, event):
        """Handle double-click on tree item to open stream in separate window"""
        sid = self._get_selected_id()
        if not sid:
            return
            
        sess = self.sessions.get(sid)
        if not sess:
            return
            
        model_name = self._extract_model_name(sess.page_url) or "Unknown"
        
        # Check if model already has an open VLC window
        if model_name in self._open_vlc_windows:
            # Focus existing window instead of creating new one
            existing_window = self._open_vlc_windows[model_name]
            if existing_window.winfo_exists():
                existing_window.lift()
                existing_window.focus_force()
                self.log_write(f"Focusing existing window for {model_name}")
                return
            else:
                # Window was closed, remove from tracking
                del self._open_vlc_windows[model_name]
        
        # Check if recording is already running - if so, use the existing resolved URL
        if (hasattr(sess, 'rec_proc') and sess.rec_proc and sess.rec_proc.poll() is None and 
            hasattr(sess, 'resolved_url') and sess.resolved_url):
            # Recording is active, use the existing URL immediately
            self.log_write(f"Opening recording stream for {model_name} (recording in progress)")
            self.status_var.set(f"Opening {model_name} (recording)")
            self._create_stream_window(sess.resolved_url, model_name, sid)
            return
        
        # Optimized stream checking: use cached URL if session is Live with resolved URL
        if sess.resolved_url and sess.status == "Live":
            # Session is already Live with resolved URL, use it directly
            self.log_write(f"Using cached stream URL for {model_name} (already Live)")
            self.status_var.set(f"Opening {model_name} (cached)")
            self._create_stream_window(sess.resolved_url, model_name, sid)
            return
        
        # Need to check stream - either no resolved URL or not Live
        self.log_write(f"Checking stream for {model_name}...")
        self.status_var.set(f"Checking {model_name}...")
        
        # Check stream in background
        def check_and_play():
            try:
                self.after(0, lambda: self.log_write(f"Starting stream check for {model_name}..."))
                # Check if stream is live
                resolved_url, status = check_session_status(sess.page_url)
                self.after(0, lambda: self.log_write(f"Check result: resolved_url={resolved_url}, status={status}"))
                
                sess.resolved_url = resolved_url
                sess.status = status
                
                # Update tree in main thread
                self.after(0, lambda: self._update_tree_item(sid, status))
                
                if status == "Live" and resolved_url:
                    # Open in separate window instead of preview
                    self.after(0, lambda session_id=sid: self._create_stream_window(resolved_url, model_name, session_id))
                    self.after(0, lambda: self.log_write(f"{model_name} is LIVE - opening in separate window"))
                    self.after(0, lambda: self.status_var.set(f"{model_name} - LIVE"))
                else:
                    self.after(0, lambda: self.log_write(f"{model_name} is not live or no stream found"))
                    self.after(0, lambda: self.status_var.set(f"{model_name} - Not live"))
                    
            except Exception as e:
                self.after(0, lambda: self.log_write(f"ERROR checking {model_name}: {e}"))
                self.after(0, lambda: self.status_var.set(f"Error checking {model_name}"))
        
        threading.Thread(target=check_and_play, daemon=True).start()

    def _on_tree_select(self, event=None):
        """Handle tree selection change"""
        # Update record button based on selected session
        self._update_record_button()
        # Update AutoRecord button state
        self._update_autorecord_status()

    def _on_tree_right_click(self, event):
        """Handle right-click on tree item to show context menu"""
        # Get the item at the clicked position
        item_id = self.tree.identify_row(event.y)
        if not item_id:
            return
            
        # Select the item first
        self.tree.selection_set(item_id)
        
        # Get session ID from the selected item
        sid = self._get_selected_id()
        if not sid:
            return
            
        sess = self.sessions.get(sid)
        if not sess:
            return
            
        # Create context menu
        context_menu = tk.Menu(self, tearoff=0)
        model_name = self._extract_model_name(sess.page_url) or "Unknown"
        
        # Main option - open in separate window
        context_menu.add_command(
            label=f"Open '{model_name}' in separate window",
            command=lambda: self._open_stream_in_new_window(sess.page_url, model_name)
        )
        
        context_menu.add_separator()
        
        # Additional useful options
        context_menu.add_command(
            label="Check stream status",
            command=lambda: self._check_single_session(sid)
        )
        
        context_menu.add_command(
            label="Force refresh stream",
            command=lambda: self._check_single_session(sid)
        )
        
        context_menu.add_command(
            label="Open in browser",
            command=lambda: self._open_url_in_browser(sess.page_url)
        )
        
        context_menu.add_command(
            label="Remove from list",
            command=lambda: self._remove_session(sid)
        )
        
        # Show context menu at cursor position
        try:
            context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            context_menu.grab_release()

    def _check_single_session(self, sid: str):
        """Check a single session's stream status - FORCE refresh mode"""
        sess = self.sessions.get(sid)
        if not sess:
            return
            
        model_name = self._extract_model_name(sess.page_url) or "Unknown"
        self.log_write(f"FORCE checking stream for {model_name} (ignoring cache)...")
        self.status_var.set(f"FORCE checking {model_name}...")
        
        def check_stream():
            try:
                from src.autorecord.checker import check_session_status
                # This will use force_fresh=True in resolve_page_url
                resolved_url, status = check_session_status(sess.page_url)
                
                # Update session
                sess.resolved_url = resolved_url
                sess.status = status or "Offline"
                
                self.after(0, lambda: self._update_tree_item(sid, sess.status))
                self.after(0, lambda: self.log_write(f"{model_name}: {sess.status} (force checked)"))
                self.after(0, lambda: self.status_var.set(f"Force checked {model_name}"))
                
            except Exception as e:
                self.after(0, lambda: self.log_write(f"Error force checking {model_name}: {e}"))
                self.after(0, lambda: self.status_var.set(f"Error checking {model_name}"))
        
        threading.Thread(target=check_stream, daemon=True).start()

    def _copy_url_to_clipboard(self, url: str):
        """Copy URL to clipboard"""
        try:
            self.clipboard_clear()
            self.clipboard_append(url)
            self.log_write(f"URL copied to clipboard: {url}")
        except Exception as e:
            self.log_write(f"Failed to copy URL: {e}")

    def _open_url_in_browser(self, url: str):
        """Open URL in default browser"""
        try:
            webbrowser.open(url)
            self.log_write(f"Opened URL in browser: {url}")
        except Exception as e:
            self.log_write(f"Failed to open URL in browser: {e}")

    def _remove_session(self, sid: str):
        """Remove a specific session from the list"""
        sess = self.sessions.get(sid)
        if not sess:
            return
            
        model_name = self._extract_model_name(sess.page_url) or "Unknown"
        
        # Confirm deletion
        result = messagebox.askyesno("Confirm deletion", 
                                   f"Are you sure you want to remove '{model_name}' from the list?")
        if not result:
            return
        
        # Remove from tree
        if hasattr(sess, 'tree_item_id') and sess.tree_item_id:
            try:
                self.tree.delete(sess.tree_item_id)
            except Exception:
                pass
        
        # Stop preview if this was the current one
        if self._preview_current_url == sess.resolved_url:
            self._stop_preview()
        
        # Remove from sessions
        if sid in self.sessions:
            # Remove from persistence
            persist_remove_model(self.sessions[sid].page_url)
            del self.sessions[sid]
        
        self.log_write(f"Removed {model_name} from list")
        self._save_urls()

    def _open_stream_in_new_window(self, page_url: str, model_name: str):
        """Open stream in a new window with volume control"""
        if not self._vlc_available:
            self.log_write("VLC not available for separate window playback")
            return
        
        # Find the session for this page URL
        target_session = None
        target_session_id = None
        self.log_write(f"Searching for session with page_url: {page_url}")
        self.log_write(f"Total sessions: {len(self.sessions)}")
        for sid, sess in self.sessions.items():
            self.log_write(f"Session {sid}: {sess.page_url}")
            if sess.page_url == page_url:
                target_session = sess
                target_session_id = sid
                self.log_write(f"MATCH found!")
                break
        
        # Debug log
        self.log_write(f"Found session for {model_name}: {target_session_id}")
        
        # Check if recording is already running - if so, use the existing resolved URL
        if (target_session and hasattr(target_session, 'rec_proc') and 
            target_session.rec_proc and target_session.rec_proc.poll() is None and 
            hasattr(target_session, 'resolved_url') and target_session.resolved_url):
            # Recording is active, use the existing URL immediately
            self.log_write(f"Opening recording stream for {model_name} (recording in progress)")
            self.status_var.set(f"Opening {model_name} (recording)")
            self._create_stream_window(target_session.resolved_url, model_name, target_session_id)
            return
        
        # Optimized stream checking: use cached URL if session is Live with resolved URL
        if (target_session and target_session.resolved_url and target_session.status == "Live"):
            # Session is already Live with resolved URL, use it directly
            self.log_write(f"Using cached stream URL for {model_name} (already Live)")
            self.status_var.set(f"Opening {model_name} (cached)")
            self._create_stream_window(target_session.resolved_url, model_name, target_session_id)
            return
            
        self.log_write(f"Opening {model_name} in new window...")
        self.status_var.set(f"Resolving stream for {model_name}...")
        
        # Resolve stream in background
        def resolve_and_open():
            try:
                self.after(0, lambda: self.log_write(f"Resolving stream for {model_name}..."))
                
                # Resolve stream URL
                from src.autorecord.checker import resolve_page_url
                def log_func(msg):
                    self.after(0, lambda: self.log_write(msg))
                
                resolved_url = resolve_page_url(page_url, log=log_func)
                
                if resolved_url:
                    # Update session with resolved URL if we found it
                    if target_session:
                        target_session.resolved_url = resolved_url
                        target_session.status = "Live"
                    
                    self.after(0, lambda: self._create_stream_window(resolved_url, model_name, target_session_id))
                else:
                    self.after(0, lambda: self.log_write(f"Failed to resolve stream for {model_name}"))
                    self.after(0, lambda: self.status_var.set(f"Failed to resolve {model_name}"))
                    
            except Exception as e:
                self.after(0, lambda: self.log_write(f"Error resolving {model_name}: {e}"))
                self.after(0, lambda: self.status_var.set(f"Error resolving {model_name}"))
        
        threading.Thread(target=resolve_and_open, daemon=True).start()

    def _create_stream_window(self, stream_url: str, model_name: str, session_id: Optional[str] = None):
        """Create a new window with VLC player and volume control"""
        # Debug log
        self.log_write(f"Creating window for {model_name} with session_id: {session_id}")
        
        # Create new window
        stream_window = tk.Toplevel(self.master)
        stream_window.title(f"Stream - {model_name}")
        stream_window.geometry("800x600")
        
        # Add to tracking
        self._open_vlc_windows[model_name] = stream_window
        
        # Center the window
        stream_window.update_idletasks()
        x = (stream_window.winfo_screenwidth() - stream_window.winfo_width()) // 2
        y = (stream_window.winfo_screenheight() - stream_window.winfo_height()) // 2
        stream_window.geometry(f"+{x}+{y}")
        
        # Configure window layout
        stream_window.columnconfigure(0, weight=1)
        stream_window.rowconfigure(0, weight=1)
        
        # Create main frame
        main_frame = ttk.Frame(stream_window)
        main_frame.pack(fill="both", expand=True, padx=5, pady=5)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(0, weight=1)
        
        # Video canvas
        video_canvas = tk.Canvas(main_frame, bg="black", height=400)
        video_canvas.grid(row=0, column=0, sticky="nsew", pady=(0, 5))
        
        # Fullscreen state tracking
        is_fullscreen = False
        original_geometry = None
        
        # Fullscreen toggle function
        def toggle_fullscreen(event=None):
            nonlocal is_fullscreen, original_geometry
            
            if not is_fullscreen:
                # Enter fullscreen
                original_geometry = stream_window.geometry()
                stream_window.attributes('-fullscreen', True)
                stream_window.focus_set()  # Ensure window has focus
                is_fullscreen = True
                self.log_write(f"Entered fullscreen for {model_name}")
            else:
                # Exit fullscreen
                stream_window.attributes('-fullscreen', False)
                if original_geometry:
                    stream_window.geometry(original_geometry)
                is_fullscreen = False
                self.log_write(f"Exited fullscreen for {model_name}")
        
        # Fullscreen binding csak F11 és Escape
        def on_escape(event=None):
            nonlocal is_fullscreen
            if is_fullscreen:
                toggle_fullscreen()
        
        stream_window.bind("<Escape>", on_escape)
        stream_window.bind("<F11>", toggle_fullscreen)  # F11 to toggle fullscreen
        stream_window.focus_set()  # Allow window to receive key events
        
        # Controls frame
        controls_frame = ttk.Frame(main_frame)
        controls_frame.grid(row=1, column=0, sticky="ew")
        controls_frame.columnconfigure(6, weight=1)  # Expand before status labels
        
        # Create custom styles for record button (same as main window)
        style = ttk.Style()
        # Normal record style (black/dark)
        style.configure("Record.TButton", 
                       foreground="black", 
                       font=("Segoe UI", 10, "bold"))
        # Stop style (red)
        style.configure("RecordStop.TButton", 
                       foreground="darkred", 
                       font=("Segoe UI", 10, "bold"))
        
        # Record/Stop button
        record_button = ttk.Button(controls_frame, text="⏺ Record", style="Record.TButton", width=10)
        record_button.grid(row=0, column=0, padx=(0, 10))
        
        # Elapsed time label (darkred, vastag betű a record gomb mellett - ugyanolyan mint a stop gomb)
        elapsed_label = ttk.Label(controls_frame, text="", font=("Segoe UI", 10, "bold"), foreground="darkred")
        elapsed_label.grid(row=0, column=1, padx=(0, 15))
        
        # Volume controls (same layout as main window)
        ttk.Label(controls_frame, text="Volume:").grid(row=0, column=2, padx=(0, 5))
        
        # Volume mute button
        volume_muted = False
        volume_before_mute = 50
        volume_button = ttk.Button(controls_frame, text="🔊", width=3)
        volume_button.grid(row=0, column=3, padx=(0, 5))
        
        volume_var = tk.DoubleVar(value=50)
        volume_scale = ttk.Scale(
            controls_frame, 
            from_=0, 
            to=100, 
            variable=volume_var,
            length=100,  # Same as main window
            orient="horizontal"
        )
        volume_scale.grid(row=0, column=4, padx=(0, 2))
        
        # Volume percentage label
        volume_label = ttk.Label(controls_frame, text="50%", anchor="center")
        volume_label.grid(row=0, column=5, padx=(2, 10))
        
        # Status label
        status_label = ttk.Label(controls_frame, text="Initializing...")
        status_label.grid(row=0, column=6, sticky="e")
        
        vlc_player = None  # Store VLC player reference locally
        
        def close_window():
            nonlocal vlc_player, is_fullscreen
            
            # Exit fullscreen if active
            if is_fullscreen:
                stream_window.attributes('-fullscreen', False)
            
            try:
                if vlc_player:
                    vlc_player.cleanup()
            except Exception:
                pass
            
            # Remove callback from main window (support both old and new formats)
            try:
                if session_id:
                    # Remove session-specific callback
                    callback_to_remove = None
                    for cb in self._separate_window_callbacks:
                        if isinstance(cb, dict) and cb.get('session_id') == session_id:
                            callback_to_remove = cb
                            break
                    if callback_to_remove:
                        self._separate_window_callbacks.remove(callback_to_remove)
                else:
                    # Remove old-style callback
                    self._separate_window_callbacks.remove(on_record_state_change)
            except ValueError:
                pass  # Already removed or not in list
            
            # Remove from tracking
            if model_name in self._open_vlc_windows:
                del self._open_vlc_windows[model_name]
            
            stream_window.destroy()
        
        # Mute/unmute functionality - minden ablak saját VLC player mute állapotát használja
        def toggle_mute():
            nonlocal vlc_player, volume_muted, volume_before_mute
            if vlc_player:
                try:
                    # Használjuk a VLC player saját mute funkcióját
                    vlc_player.toggle_mute()
                    
                    # Frissítsük a UI-t a player állapota alapján
                    if vlc_player.is_muted():
                        volume_button.config(text="🔇")
                        volume_label.config(text="0%")
                        # Volume slider is 0-ra ugrik mute-nál (normál video player viselkedés)
                        volume_var.set(0)
                    else:
                        volume_button.config(text="🔊")
                        # Vissza az eredeti hangerőhöz
                        current_volume = vlc_player.get_volume()
                        volume_label.config(text=f"{current_volume}%")
                        volume_var.set(current_volume)  # Slider visszaáll az eredeti értékre
                        
                except Exception as e:
                    print(f"Failed to toggle mute for separate window: {e}")
            else:
                # Nincs VLC player, helyi mute kezelés
                if volume_muted:
                    # Unmute: restore previous volume
                    volume_muted = False
                    volume_var.set(volume_before_mute)
                    volume_button.config(text="🔊")
                    volume_label.config(text=f"{int(volume_before_mute)}%")
                else:
                    # Mute: save current volume and set to 0
                    volume_muted = True
                    volume_before_mute = volume_var.get()
                    volume_var.set(0)
                    volume_button.config(text="🔇")
                    volume_label.config(text="0%")
        
        volume_button.config(command=toggle_mute)
        
        # Record button functionality - session specific
        def toggle_record():
            self.log_write(f"Toggle record called for session_id: {session_id}")
            if session_id:
                # Use the specific session for this window
                sess = self.sessions.get(session_id)
                self.log_write(f"Session found: {sess is not None}")
                if sess:
                    # Check if this session is currently recording
                    is_recording = hasattr(sess, 'rec_proc') and sess.rec_proc and sess.rec_proc.poll() is None
                    self.log_write(f"Is currently recording: {is_recording}")
                    if is_recording:
                        # Stop recording for this session
                        self.log_write(f"Stopping recording for session: {session_id}")
                        self._stop_recording_for_session(session_id)
                    else:
                        # Start recording for this session
                        self.log_write(f"Starting recording for session: {session_id}")
                        self._start_recording_for_session(session_id)
                    
                    # The session-specific functions will handle the window updates
                    # No need to manually update here since _notify_session_windows is called
                else:
                    self.log_write(f"Session not found for window: {model_name}")
            else:
                # Fallback to main window behavior if no session_id
                self.on_record_toggle()
                self.after(100, update_record_button)
        
        def update_status():
            self.log_write(f"update_status called for session_id: {session_id}")
            if session_id:
                sess = self.sessions.get(session_id)
                if sess and hasattr(sess, 'rec_proc') and sess.rec_proc and sess.rec_proc.poll() is None:
                    self.log_write(f"Setting status to Recording for session: {session_id}")
                    status_label.config(text="Recording")
                    
                    # Show elapsed recording time
                    if hasattr(sess, 'elapsed_seconds') and sess.elapsed_seconds > 0:
                        minutes = sess.elapsed_seconds // 60
                        seconds = sess.elapsed_seconds % 60
                        elapsed_label.config(text=f"{minutes:02d}:{seconds:02d}")
                    else:
                        elapsed_label.config(text="00:00")
                else:
                    self.log_write(f"Setting status to Playing for session: {session_id}")
                    status_label.config(text="Playing")
                    elapsed_label.config(text="")
            else:
                self.log_write("No session_id for update_status")
                status_label.config(text="No session")
                elapsed_label.config(text="")
        
        record_button.config(command=toggle_record)
        
        # Update record button state based on this window's session
        def update_record_button():
            self.log_write(f"Updating record button for session_id: {session_id}")
            if session_id:
                sess = self.sessions.get(session_id)
                if sess and hasattr(sess, 'rec_proc') and sess.rec_proc and sess.rec_proc.poll() is None:
                    self.log_write(f"Setting button to Stop for session: {session_id}")
                    record_button.config(text="⏹ Stop", style="RecordStop.TButton")
                else:
                    self.log_write(f"Setting button to Record for session: {session_id}")
                    record_button.config(text="⏺ Record", style="Record.TButton")
            else:
                self.log_write("No session_id, setting button to Record")
                record_button.config(text="⏺ Record", style="Record.TButton")
        
        # Callback function for session-specific updates (not used anymore but kept for compatibility)
        def on_record_state_change(is_recording: bool):
            # This will be replaced by session-specific updates
            update_record_button()
        
        # Register this window for session-specific updates
        if session_id:
            # Create a session-specific callback that only updates when this session changes
            def session_specific_callback():
                update_record_button()
                update_status()
            
            # Store callback with session_id for targeted updates
            callback_info = {
                'session_id': session_id,
                'callback': session_specific_callback
            }
            self._separate_window_callbacks.append(callback_info)
            self.log_write(f"Registered callback for session: {session_id}, total callbacks: {len(self._separate_window_callbacks)}")
            
            # Start a timer to update elapsed time every second during recording
            def update_elapsed_timer():
                if session_id:
                    sess = self.sessions.get(session_id)
                    if sess and hasattr(sess, 'rec_proc') and sess.rec_proc and sess.rec_proc.poll() is None:
                        # Only update elapsed time if recording
                        update_status()
                        # Schedule next update
                        stream_window.after(1000, update_elapsed_timer)
                    else:
                        # Not recording, schedule lighter updates
                        stream_window.after(5000, update_elapsed_timer)
                else:
                    # Window might be closing, stop updates
                    return
                    
            # Start the timer
            stream_window.after(1000, update_elapsed_timer)
            
        else:
            # Fallback to old behavior for windows without session_id
            self._separate_window_callbacks.append(on_record_state_change)
        
        # Set up record button styles for this window
        style = ttk.Style()
        style.configure("Record.TButton", 
                       foreground="black", 
                       font=("Segoe UI", 10, "bold"))
        style.configure("RecordStop.TButton", 
                       foreground="darkred", 
                       font=("Segoe UI", 10, "bold"))
        
        update_record_button()
        
        # Create VLC player for this window
        try:
            vlc_player = create_vlc_player(video_canvas)
            if vlc_player:
                
                # Volume change handler - intelligent mute kezelés
                def on_volume_change(value):
                    nonlocal vlc_player
                    try:
                        vol = int(float(value))
                        volume_label.config(text=f"{vol}%")
                        
                        if vlc_player:
                            # Ha mute-ban vagyunk és a felhasználó 0-nál nagyobb értékre állítja,
                            # akkor automatikusan unmute-oljunk (normál video player viselkedés)
                            if vlc_player.is_muted() and vol > 0:
                                vlc_player.unmute()  # Először unmute
                                volume_button.config(text="🔊")  # UI frissítés
                            
                            # Ha 0-ra állítjuk és nem voltunk mute-ban, akkor mute-oljunk
                            elif not vlc_player.is_muted() and vol == 0:
                                vlc_player.mute()  # Mute
                                volume_button.config(text="🔇")  # UI frissítés
                            
                            # Volume beállítása
                            vlc_player.set_volume(vol)
                            
                    except Exception:
                        pass
                
                volume_scale.config(command=on_volume_change)
                
                # Load and play stream
                if vlc_player.load_url(stream_url):
                    vlc_player.set_volume(int(volume_var.get()))
                    if vlc_player.play():
                        status_label.config(text="Playing")
                        self.log_write(f"Started playback for {model_name} in new window")
                        self.status_var.set(f"Opened {model_name} in new window")
                    else:
                        status_label.config(text="Failed to play")
                        self.log_write(f"Failed to start playback for {model_name}")
                else:
                    status_label.config(text="Failed to load")
                    self.log_write(f"Failed to load stream for {model_name}")
            else:
                status_label.config(text="VLC not available")
                self.log_write("Failed to create VLC player for new window")
                
        except Exception as e:
            status_label.config(text="Error")
            self.log_write(f"Error creating VLC player: {e}")
        
        # Handle window close
        stream_window.protocol("WM_DELETE_WINDOW", close_window)

    def _update_record_button(self):
        """Update record button text based on selected session"""
        if not self.record_btn:
            return  # Button not initialized yet
            
        sid = self._get_selected_id()
        is_recording = False
        
        if not sid:
            self.record_btn.configure(text="⏺ Record", style="Record.TButton")
        else:
            sess = self.sessions.get(sid)
            if not sess:
                self.record_btn.configure(text="⏺ Record", style="Record.TButton")
            else:
                # Check if this session is currently recording
                if hasattr(sess, 'rec_proc') and sess.rec_proc and sess.rec_proc.poll() is None:
                    self.record_btn.configure(text="⏹ Stop", style="RecordStop.TButton")
                    is_recording = True
                else:
                    self.record_btn.configure(text="⏺ Record", style="Record.TButton")
        
        # Notify all separate windows about the state change
        self._notify_separate_windows(is_recording)
    
    def _notify_separate_windows(self, is_recording: bool):
        """Notify all separate windows about record button state changes"""
        # Remove dead callbacks (windows that were closed)
        self._separate_window_callbacks = [cb for cb in self._separate_window_callbacks if cb is not None]
        
        # Call all remaining callbacks
        for callback in self._separate_window_callbacks[:]:  # Copy list to avoid modification during iteration
            try:
                if isinstance(callback, dict):
                    # New session-specific callback format
                    callback['callback']()
                else:
                    # Old global callback format
                    callback(is_recording)
            except Exception:
                # Remove callback if it fails (window probably closed)
                self._separate_window_callbacks.remove(callback)

    def _notify_session_windows(self, session_id: str):
        """Notify separate windows for a specific session about state changes"""
        self.log_write(f"_notify_session_windows called for session: {session_id}")
        self.log_write(f"Total callbacks registered: {len(self._separate_window_callbacks)}")
        
        # Remove dead callbacks
        self._separate_window_callbacks = [cb for cb in self._separate_window_callbacks if cb is not None]
        
        # Call session-specific callbacks
        for callback in self._separate_window_callbacks[:]:
            try:
                if isinstance(callback, dict) and callback.get('session_id') == session_id:
                    self.log_write(f"Calling callback for session: {session_id}")
                    callback['callback']()
                else:
                    self.log_write(f"Skipping callback: {callback}")
            except Exception as e:
                self.log_write(f"Callback failed: {e}")
                # Remove callback if it fails (window probably closed)
                self._separate_window_callbacks.remove(callback)

    def _get_selected_id(self):
        """Get selected session ID from tree"""
        sel = self.tree.selection()
        if not sel:
            return None
        tree_item_id = sel[0]
        
        # Find session by tree item ID
        for sid, sess in self.sessions.items():
            if hasattr(sess, 'tree_item_id') and sess.tree_item_id == tree_item_id:
                return sid
        
        # If not found, assume tree_item_id is the session_id (for new items)
        return tree_item_id if tree_item_id in self.sessions else None

    def _extract_model_name(self, page_url):
        """Extract model name from page URL - uses first path segment as model name"""
        try:
            from urllib.parse import urlparse
            parsed = urlparse(page_url)
            
            # Get the path and split it into segments
            path_parts = parsed.path.strip('/').split('/')
            
            # Take the first non-empty path segment as model name
            if path_parts and path_parts[0]:
                model_name = path_parts[0]
                
                # Clean up common prefixes/suffixes that might not be part of the actual model name
                # Remove leading underscore (common in some sites)
                if model_name.startswith('_'):
                    model_name = model_name[1:]
                
                # Remove trailing file extensions or parameters
                if '.' in model_name:
                    # Only remove extension if it looks like a file extension (3-4 chars)
                    parts = model_name.split('.')
                    if len(parts[-1]) <= 4 and parts[-1].isalpha():
                        model_name = '.'.join(parts[:-1])
                
                # Remove query parameters if somehow included
                if '?' in model_name:
                    model_name = model_name.split('?')[0]
                
                # Remove hash fragments if somehow included  
                if '#' in model_name:
                    model_name = model_name.split('#')[0]
                    
                return model_name if model_name else None
            
            return None
        except Exception as e:
            # Log the error for debugging but don't crash
            print(f"Error extracting model name from {page_url}: {e}")
            return None

    def _resolve(self, page_url):
        """Resolve page URL to stream URL"""
        try:
            return resolve_page_url(page_url)
        except Exception:
            return None

    def _add_url(self):
        """Add URL to session list"""
        url = self.url_var.get().strip()
        if not url:
            return
        
        # Create new session
        session_id = f"session_{int(time.time() * 1000)}"
        sess = Session(
            page_url=url,
            status="Added"
        )
        
        # Add to tree first
        tree_item_id = self.tree.insert("", "end", values=(
            self._extract_model_name(url) or "Unknown",
            url,
            "Added",
            "",  # Auto column
            ""   # Elapsed column
        ))
        
        # Set tree item ID on session
        sess.tree_item_id = tree_item_id
        
        # Store session with session_id as key
        self.sessions[session_id] = sess
        
        # Clear input
        self.url_var.set("")
        
        # Log the addition
        model_name = self._extract_model_name(url) or "Unknown"
        self.log_write(f"Added: {model_name} ({url})")
        
        # Save to new models format with autorecord status
        persist_add_model(url, autorecord=False)
        
        # Also save URLs for backward compatibility
        self._save_urls()

    def _load_settings(self):
        """Load settings from persistence"""
        settings = persist_load_settings()
        if settings:
            self.output_folder_var.set(settings.get("output_folder", str(Path.home() / "Desktop")))
            self.container_var.set(settings.get("container", "mp4"))
            
            # Store AutoRecord state for later restoration (will be restored in main init)
            self._autorecord_enabled_from_settings = settings.get("autorecord_enabled", False)

    def _restore_autorecord_state_from_settings(self):
        """Restore AutoRecord state from settings after UI is fully loaded"""
        try:
            # Check if we have stored autorecord state
            autorecord_enabled = getattr(self, '_autorecord_enabled_from_settings', False)
            
            if autorecord_enabled and hasattr(self, 'autorecord') and hasattr(self, 'autorecord_btn') and self.autorecord_btn:
                if not self.autorecord.is_running():
                    self.autorecord.start()
                    self.autorecord_btn.configure(text="🔄 AutoRecord ON", style="Green.TButton")
                    self._update_autorecord_status()
                    self.log_write("AutoRecord system restored from settings")
                else:
                    self.log_write("AutoRecord was already running")
        except Exception as e:
            self.log_write(f"Error restoring AutoRecord state: {e}")

    def _restore_autorecord_state(self):
        """Restore AutoRecord state from settings"""
        if hasattr(self, 'autorecord') and not self.autorecord.is_running():
            self.autorecord.start()
            if hasattr(self, 'autorecord_btn') and self.autorecord_btn:
                self.autorecord_btn.configure(text="🔄 AutoRecord ON", style="Green.TButton")
            self._update_autorecord_status()
            self.log_write("AutoRecord system restored from settings")

    def _check_for_updates_on_startup(self):
        """Check for updates when application starts up"""
        try:
            if hasattr(self, 'update_manager'):
                self.log_write("Checking for updates...")
                self.update_manager.check_for_updates_on_startup(self._root or self.master)
        except Exception as e:
            self.log_write(f"Update check failed: {e}")

    def _manual_update_check(self):
        """Manually check for updates (called from button)"""
        try:
            if hasattr(self, 'update_manager'):
                self.log_write("Manually checking for updates...")
                self.status_var.set("Checking for updates...")
                self.update_manager.check_for_updates_manually(self._root or self.master)
            else:
                self.log_write("Update manager not available")
        except Exception as e:
            self.log_write(f"Manual update check failed: {e}")
            self.status_var.set("Update check failed")

    def _save_settings(self):
        """Save settings to persistence"""
        settings = {
            "output_folder": self.output_folder_var.get(),
            "container": self.container_var.get(),
            "autorecord_enabled": hasattr(self, 'autorecord') and self.autorecord.is_running()
        }
        persist_save_settings(settings)

    def _load_urls(self):
        """Load URLs from persistence - supports both old and new format"""
        # Try to load from new models format first
        models = persist_load_models()
        autorecord_sessions = []  # Track which sessions should have autorecord enabled
        
        if models:
            for url, model_data in models.items():
                session_id = self._add_url_internal(url)
                # Track autorecord status for later restoration
                if model_data.get("autorecord", False):
                    autorecord_sessions.append(session_id)
        else:
            # Fallback to old format
            urls = persist_load_urls()
            for url in urls:
                self._add_url_internal(url)
        
        # Restore autorecord sessions after a short delay to ensure autorecord system is ready
        if autorecord_sessions:
            def restore_autorecord():
                for session_id in autorecord_sessions:
                    if hasattr(self, 'autorecord') and session_id in self.sessions:
                        self.autorecord.add_session(session_id)
                        model_name = self._extract_model_name(self.sessions[session_id].page_url) or "Unknown"
                        self.log_write(f"Restored AutoRecord for {model_name}")
                # Update tree visuals after restoring autorecord sessions
                self._update_all_tree_visuals()
            # Schedule restoration after UI is fully loaded
            self.after(1000, restore_autorecord)
        
        # Reorder list to put any recording items at top
        self._reorder_full_list()

    def _add_url_internal(self, url):
        """Internal add URL method - returns session_id"""
        session_id = f"session_{int(time.time() * 1000)}_{random.randint(1000,9999)}"
        sess = Session(
            page_url=url,
            status=""  # Empty status for loaded URLs
        )
        
        # Check autorecord status
        auto_status = "Off"  # Default value
        
        # Add to tree first
        tree_item_id = self.tree.insert("", "end", values=(
            self._extract_model_name(url) or "Unknown",
            url,
            "",  # Empty status for loaded URLs
            auto_status,  # Auto column with proper initial value
            ""   # Elapsed column
        ))
        
        # Set tree item ID on session
        sess.tree_item_id = tree_item_id
        
        # Store session
        self.sessions[session_id] = sess
        
        return session_id

    def _save_urls(self):
        """Save URLs with their autorecord status to models format"""
        models = {}
        for sess in self.sessions.values():
            url = sess.page_url
            # Get current autorecord status for this session
            autorecord_status = False
            if hasattr(self, 'autorecord'):
                # Find session ID for this URL
                for sid, session in self.sessions.items():
                    if session.page_url == url:
                        autorecord_status = self.autorecord.is_session_monitored(sid)
                        break
            
            models[url] = {
                "url": url,
                "autorecord": autorecord_status,
                "created_at": getattr(sess, 'created_at', None)
            }
        persist_save_models(models)

    def on_close(self):
        """Handle application close"""
        # Stop preview
        self._stop_preview()
        
        # Stop stream monitor
        if hasattr(self, 'stream_monitor'):
            try:
                self.stream_monitor.stop_monitoring()
            except Exception:
                pass
        
        # Cleanup update manager
        if hasattr(self, 'update_manager'):
            try:
                self.update_manager.cleanup()
            except Exception:
                pass
        
        # Save settings
        try:
            self._save_settings()
            self._save_urls()
        except Exception:
            pass

    def _cleanup_all_processes(self):
        """Egyszerű cleanup: csak aktív felvételek leállítása és cache törlése"""
        self.log_write("Program closing - stopping active recordings and clearing cache...")
        
        # 1. Aktív felvételek leállítása
        self._stop_active_recordings()
        
        # 2. Cache-elt stream URL-ek törlése
        self._clear_stream_cache()
        
        self.log_write("Cleanup completed.")

    def _stop_active_recordings(self):
        """Csak az aktív felvételek leállítása - gyorsan és egyszerűen"""
        for sess in self.sessions.values():
            if hasattr(sess, 'rec_proc') and sess.rec_proc:
                try:
                    # Egyszerű terminate - nincs várakozás
                    sess.rec_proc.terminate()
                    sess.rec_proc = None
                    sess.status = "Idle"
                    self.log_write(f"Stopped recording: {sess.page_url}")
                except Exception:
                    pass

    def _clear_stream_cache(self):
        """Cache-elt stream URL-ek törlése"""
        cleared_count = 0
        for sess in self.sessions.values():
            if hasattr(sess, 'resolved_url') and sess.resolved_url:
                sess.resolved_url = None
                cleared_count += 1
        
        if cleared_count > 0:
            self.log_write(f"Cleared {cleared_count} cached stream URLs")

    def _stop_all_our_recordings(self):
        """Stop only our recording sessions gracefully"""
        import time
        
        # First, send 'q' command to all ffmpeg processes to stop gracefully
        for sess in self.sessions.values():
            if hasattr(sess, 'rec_proc') and sess.rec_proc and sess.rec_proc.stdin:
                try:
                    sess.rec_proc.stdin.write(b'q\n')
                    sess.rec_proc.stdin.flush()
                    self.log_write(f"Sent graceful stop command to recording: {sess.page_url}")
                except:
                    pass
        
        # Give processes time to finish gracefully
        time.sleep(3)
        
        # Check which processes finished gracefully
        for sess in self.sessions.values():
            if hasattr(sess, 'rec_proc') and sess.rec_proc:
                try:
                    # Check if process is still running
                    if sess.rec_proc.poll() is None:
                        # Still running, try terminate
                        self.log_write(f"Process still running, terminating: {sess.page_url}")
                        sess.rec_proc.terminate()
                        sess.rec_proc.wait(timeout=5)
                    else:
                        self.log_write(f"Recording finished gracefully: {sess.page_url}")
                except:
                    try:
                        sess.rec_proc.kill()
                        self.log_write(f"Force killed recording process: {sess.page_url}")
                    except:
                        pass
                finally:
                    sess.rec_proc = None
                    sess.status = "Idle"

    def _browse_out(self):
        """Browse for output folder"""
        folder = filedialog.askdirectory(
            title="Select Output Folder",
            initialdir=self.output_folder_var.get()
        )
        if folder:
            self.output_folder_var.set(folder)

    def _remove_selected(self):
        """Remove selected URLs from list (supports multiple selection)"""
        selected_items = self.tree.selection()
        if not selected_items:
            messagebox.showerror("No selection", "Select one or more URLs in the list.")
            return
        
        # Confirm deletion if multiple items
        if len(selected_items) > 1:
            result = messagebox.askyesno("Confirm deletion", 
                                       f"Are you sure you want to delete {len(selected_items)} selected items?")
            if not result:
                return
        
        sessions_to_remove = []
        preview_url_to_stop = None
        
        # Collect sessions to remove
        for item_id in selected_items:
            # Find session by tree_item_id
            for sid, sess in self.sessions.items():
                if hasattr(sess, 'tree_item_id') and sess.tree_item_id == item_id:
                    sessions_to_remove.append(sid)
                    if self._preview_current_url == sess.resolved_url:
                        preview_url_to_stop = sess.resolved_url
                    break
        
        # Remove from tree
        for item_id in selected_items:
            try:
                self.tree.delete(item_id)
            except Exception:
                pass
        
        # Remove from sessions
        for sid in sessions_to_remove:
            if sid in self.sessions:
                del self.sessions[sid]
        
        # Stop preview if any of the deleted items was playing
        if preview_url_to_stop:
            self._stop_preview()
        
        self._save_urls()

    def _check_selected(self):
        """Check status of selected stream"""
        sid = self._get_selected_id()
        if not sid:
            messagebox.showerror("No selection", "Select a URL in the list.")
            return
        
        sess = self.sessions.get(sid)
        if not sess:
            return
            
        # Update status in background
        def check_worker():
            self.status_var.set(f"Checking {self._extract_model_name(sess.page_url) or 'stream'}...")
            try:
                resolved_url, status = check_session_status(sess.page_url)
                sess.resolved_url = resolved_url
                sess.status = status
                
                # Update tree
                self.after(0, lambda: self._update_tree_item(sid, status))
                self.after(0, lambda: self.status_var.set("Check completed"))
            except Exception as e:
                self.after(0, lambda: self.status_var.set(f"Check failed: {e}"))
        
        threading.Thread(target=check_worker, daemon=True).start()

    def _update_tree_item(self, sid, status):
        """Update tree item status and maintain recording items at top"""
        sess = self.sessions.get(sid)
        if not sess or not hasattr(sess, 'tree_item_id') or not sess.tree_item_id:
            return
            
        model_name = self._extract_model_name(sess.page_url) or "Unknown"
        
        # Format elapsed time
        elapsed_str = ""
        if hasattr(sess, 'elapsed_seconds') and sess.elapsed_seconds > 0:
            minutes = sess.elapsed_seconds // 60
            seconds = sess.elapsed_seconds % 60
            elapsed_str = f"{minutes:02d}:{seconds:02d}"
        
        try:
            # Add visual styling for recording items and AutoRecord monitoring
            model_display = model_name
            
            # Check if AutoRecord is enabled for this session
            is_autorecord = hasattr(self, 'autorecord') and self.autorecord.is_session_monitored(sid)
            auto_status = "On" if is_autorecord else "Off"
            
            if status == "Recording":
                # Make recording items with red circle (using Unicode red circle)
                model_display = f"● {model_name}"  # Red circle character
                self._pin_item_to_top(sess.tree_item_id)
            
            # Update the item values with new Auto column
            self.tree.item(sess.tree_item_id, values=(
                model_display,
                sess.page_url,
                status,
                auto_status,
                elapsed_str
            ))
            
            if status not in ["Recording"] and status in ["Idle", "", "Added", "Live", "No stream", "Error"]:
                self._move_item_to_normal_position(sess.tree_item_id)
                
        except Exception:
            pass

    def _pin_item_to_top(self, item_id):
        """Move a recording item to the top of the list"""
        try:
            # Get all recording items to maintain their relative order
            recording_items = []
            other_items = []
            
            # Categorize all items
            for child in self.tree.get_children():
                values = self.tree.item(child, "values")
                if len(values) > 2 and values[2] == "Recording":
                    recording_items.append(child)
                else:
                    other_items.append(child)
            
            # If this item is not already in recording items, add it
            if item_id not in recording_items:
                recording_items.append(item_id)
                if item_id in other_items:
                    other_items.remove(item_id)
            
            # Reorder: recording items first, then others
            new_order = recording_items + other_items
            
            # Move items to new positions
            for index, child in enumerate(new_order):
                self.tree.move(child, "", index)
                
        except Exception as e:
            self.log_write(f"Error pinning item to top: {e}")

    def _move_item_to_normal_position(self, item_id):
        """Move an item back to normal position (not pinned to top)"""
        try:
            # Get all items categorized
            recording_items = []
            other_items = []
            
            # Categorize all items
            for child in self.tree.get_children():
                values = self.tree.item(child, "values")
                if len(values) > 2 and values[2] == "Recording":
                    recording_items.append(child)
                else:
                    other_items.append(child)
            
            # Remove this item from recording items if it's there
            if item_id in recording_items:
                recording_items.remove(item_id)
                if item_id not in other_items:
                    other_items.append(item_id)
            
            # Reorder: recording items first, then others
            new_order = recording_items + other_items
            
            # Move items to new positions
            for index, child in enumerate(new_order):
                self.tree.move(child, "", index)
                
        except Exception as e:
            self.log_write(f"Error moving item to normal position: {e}")

    def _reorder_full_list(self):
        """Reorder the entire list to put all recording items at the top"""
        try:
            # Get all items categorized
            recording_items = []
            other_items = []
            
            # Categorize all items
            for child in self.tree.get_children():
                values = self.tree.item(child, "values")
                if len(values) > 2 and values[2] == "Recording":
                    recording_items.append(child)
                else:
                    other_items.append(child)
            
            # Reorder: recording items first, then others
            new_order = recording_items + other_items
            
            # Move items to new positions
            for index, child in enumerate(new_order):
                self.tree.move(child, "", index)
                
        except Exception as e:
            self.log_write(f"Error reordering full list: {e}")

    def log_write(self, message):
        """Write to log"""
        try:
            self.log.configure(state="normal")
            self.log.insert("end", f"{message}\n")
            self.log.see("end")
            self.log.configure(state="disabled")
        except Exception:
            print(f"LOG: {message}")

    def with_thread(self, target, *args, **kwargs):
        """Run function in background thread"""
        t = threading.Thread(target=target, args=args, kwargs=kwargs, daemon=True)
        t.start()
        return t

    def on_record_toggle(self):
        """Toggle recording for selected item"""
        sid = self._get_selected_id()
        if not sid:
            self.status_var.set("Please select a model to record")
            return
            
        sess = self.sessions.get(sid)
        if not sess:
            self.status_var.set("Session not found")
            return
        
        model_name = self._extract_model_name(sess.page_url) or "Unknown"
        
        # Check if recording is already running for this session (use rec_proc from Session model)
        if hasattr(sess, 'rec_proc') and sess.rec_proc and sess.rec_proc.poll() is None:
            # Stop recording
            self.status_var.set(f"Stopping recording for {model_name}...")
            rec_stop(self)
        else:
            # Start recording
            # Optimized stream checking: only re-check if no resolved URL or not Live
            if not sess.resolved_url or sess.status != "Live":
                self.status_var.set(f"Checking stream for {model_name}...")
                self.log_write(f"Stream check needed for {model_name} (no URL or not Live)")
                # Quick stream check using check_session_status
                resolved_url, status = check_session_status(sess.page_url)
                if not resolved_url:
                    self.status_var.set(f"No stream available for {model_name}")
                    return
                sess.resolved_url = resolved_url
                sess.status = status
                self._update_tree_item(sid, sess)
            else:
                self.log_write(f"Using cached stream URL for {model_name} (already Live)")
            
            self.status_var.set(f"Starting recording for {model_name}...")
            rec_start(self)

    def _start_recording_for_session(self, session_id: str):
        """Start recording for a specific session"""
        sess = self.sessions.get(session_id)
        if not sess:
            self.log_write(f"Session {session_id} not found")
            return
        
        model_name = self._extract_model_name(sess.page_url) or "Unknown"
        
        # Optimized stream checking: only re-check if no resolved URL or not Live
        if not sess.resolved_url or sess.status != "Live":
            self.log_write(f"Checking stream for {model_name}...")
            # Quick stream check
            from src.autorecord.checker import check_session_status
            resolved_url, status = check_session_status(sess.page_url)
            if not resolved_url:
                self.log_write(f"No stream available for {model_name}")
                return
            sess.resolved_url = resolved_url
            sess.status = status
            self._update_tree_item(session_id, status)
        else:
            self.log_write(f"Using cached stream URL for {model_name} (already Live)")
        
        self.log_write(f"Starting recording for {model_name}...")
        
        # Temporarily select this session for recording
        original_selection = self.tree.selection()
        if hasattr(sess, 'tree_item_id') and sess.tree_item_id:
            self.tree.selection_set(sess.tree_item_id)
        
        # Start recording using existing function
        from recording import start_record as rec_start
        rec_start(self)
        
        # Force immediate update of the tree item
        sess = self.sessions.get(session_id)
        if sess:
            self._update_tree_item(session_id, "Recording")
        
        # Restore original selection
        if original_selection:
            self.tree.selection_set(original_selection)
        
        # Notify session-specific windows immediately after recording starts
        self.log_write(f"Notifying separate windows for session: {session_id}")
        self._notify_session_windows(session_id)
        
    def _stop_recording_for_session(self, session_id: str):
        """Stop recording for a specific session"""
        sess = self.sessions.get(session_id)
        if not sess:
            self.log_write(f"Session {session_id} not found")
            return
        
        model_name = self._extract_model_name(sess.page_url) or "Unknown"
        
        if hasattr(sess, 'rec_proc') and sess.rec_proc and sess.rec_proc.poll() is None:
            self.log_write(f"Stopping recording for {model_name}...")
            
            # Temporarily select this session for stopping
            original_selection = self.tree.selection()
            if hasattr(sess, 'tree_item_id') and sess.tree_item_id:
                self.tree.selection_set(sess.tree_item_id)
            
            # Stop recording using existing function
            from recording import stop_record as rec_stop
            rec_stop(self)
            
            # Force immediate update of the tree item
            sess = self.sessions.get(session_id)
            if sess:
                self._update_tree_item(session_id, "Idle")
            
            # Restore original selection
            if original_selection:
                self.tree.selection_set(original_selection)
            
            # Notify session-specific windows immediately after recording stops
            self.log_write(f"Notifying separate windows for session: {session_id}")
            self._notify_session_windows(session_id)
        else:
            self.log_write(f"No active recording found for {model_name}")

    # AutoRecord Methods
    def _toggle_autorecord(self):
        """Toggle the AutoRecord system on/off"""
        if self.autorecord.is_running():
            self.autorecord.stop()
            if hasattr(self, 'autorecord_btn') and self.autorecord_btn:
                self.autorecord_btn.configure(text="🔄 AutoRecord OFF", style="")
            self.log_write("AutoRecord system stopped")
        else:
            self.autorecord.start()
            if hasattr(self, 'autorecord_btn') and self.autorecord_btn:
                self.autorecord_btn.configure(text="🔄 AutoRecord ON", style="Green.TButton")
            self._update_autorecord_status()
            self.log_write("AutoRecord system started")
        
        # Save the new AutoRecord state
        self._save_settings()
            
    def _toggle_autorecord_for_selected(self):
        """Toggle AutoRecord monitoring for the selected session"""
        sid = self._get_selected_id()
        if not sid:
            self.status_var.set("Please select a stream to add/remove from AutoRecord")
            return
            
        sess = self.sessions.get(sid)
        if not sess:
            self.status_var.set("Session not found")
            return
            
        model_name = self._extract_model_name(sess.page_url) or "Unknown"
        
        if self.autorecord.is_session_monitored(sid):
            self.autorecord.remove_session(sid)
            if hasattr(self, 'autorecord_toggle_btn') and self.autorecord_toggle_btn:
                self.autorecord_toggle_btn.configure(text="+ Add to AutoRecord")
            self.log_write(f"Removed {model_name} from AutoRecord monitoring")
            # Update persistence
            persist_update_model_autorecord(sess.page_url, False)
        else:
            self.autorecord.add_session(sid)
            if hasattr(self, 'autorecord_toggle_btn') and self.autorecord_toggle_btn:
                self.autorecord_toggle_btn.configure(text="- Remove from AutoRecord")
            self.log_write(f"Added {model_name} to AutoRecord monitoring")
            # Update persistence
            persist_update_model_autorecord(sess.page_url, True)
            
        self._update_autorecord_status()
        
    def _update_autorecord_status(self):
        """Update the AutoRecord status display"""
        # Update AutoRecord button state
        if hasattr(self, 'autorecord_toggle_btn') and self.autorecord_toggle_btn:
            sid = self._get_selected_id()
            if sid and self.autorecord.is_session_monitored(sid):
                self.autorecord_toggle_btn.configure(text="- Remove from AutoRecord")
            else:
                self.autorecord_toggle_btn.configure(text="+ Add to AutoRecord")
        
        # Update visual indicators for all items in the tree
        self._update_all_tree_visuals()
                
        # Schedule regular AutoRecord status update
        if not hasattr(self, '_autorecord_update_scheduled'):
            self._autorecord_update_scheduled = True
            self.after(5000, self._periodic_autorecord_update)  # Update every 5 seconds
            
    def _periodic_autorecord_update(self):
        """Periodically update AutoRecord status display"""
        try:
            self._update_autorecord_status()
        except Exception:
            pass
        # Schedule next update
        self.after(5000, self._periodic_autorecord_update)
    
    def _update_all_tree_visuals(self):
        """Update visual indicators for all items in the tree"""
        for sid, sess in self.sessions.items():
            if hasattr(sess, 'tree_item_id') and sess.tree_item_id:
                # Get current status and update display
                current_status = sess.status if hasattr(sess, 'status') else ""
                self._update_tree_item(sid, current_status)

    def _check_all(self):
        """Check all URLs in the list with parallel processing and delays - FORCE refresh mode"""
        if not self.sessions:
            messagebox.showinfo("No URLs", "Add some URLs first.")
            return
            
        session_count = len(self.sessions)
        self.status_var.set(f"Starting FORCE check of {session_count} streams...")
        self.log_write(f"Check All: Force checking {session_count} sessions (ignoring cache)")
        
        import asyncio
        import time
        
        # Track progress
        self._check_progress = {"completed": 0, "total": session_count}
        
        def check_single_session(sid, sess, delay_ms):
            """Check a single session with delay"""
            try:
                # Apply delay to avoid too many requests
                time.sleep(delay_ms / 1000.0)
                
                # Update status to show which one we're checking
                model_name = self._extract_model_name(sess.page_url) or "Unknown"
                self.after(0, lambda: self.status_var.set(f"FORCE checking {model_name}... ({self._check_progress['completed'] + 1}/{self._check_progress['total']})"))
                
                # FORCE check: always re-resolve regardless of existing cache
                self.after(0, lambda: self.log_write(f"FORCE checking {model_name} (ignoring existing cache)"))
                
                # Perform the actual check (check_session_status already uses force_fresh=True)
                resolved_url, status = check_session_status(sess.page_url)
                sess.resolved_url = resolved_url
                sess.status = status
                
                # Update progress counter
                self._check_progress["completed"] += 1
                
                # Update tree in main thread
                self.after(0, lambda s=sid, st=status, m=model_name: self._update_tree_item_with_progress(s, st, m))
                
                return True
            except Exception as e:
                # Update progress counter even on error
                self._check_progress["completed"] += 1
                model_name = self._extract_model_name(sess.page_url) or "Unknown"
                self.after(0, lambda s=sid, m=model_name, err=str(e): self._update_tree_item_error(s, m, err))
                return False
        
        def check_all_parallel():
            """Run all checks in parallel with staggered delays"""
            import concurrent.futures
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                # Submit all tasks with staggered delays
                futures = []
                for i, (sid, sess) in enumerate(self.sessions.items()):
                    delay = i * 800  # 800ms delay between each start
                    future = executor.submit(check_single_session, sid, sess, delay)
                    futures.append(future)
                
                # Wait for all to complete
                completed = 0
                successful = 0
                for future in concurrent.futures.as_completed(futures):
                    try:
                        if future.result():
                            successful += 1
                        completed += 1
                    except Exception:
                        completed += 1
                
                # Final status update
                self.after(0, lambda: self.status_var.set(f"Completed: {successful}/{completed} streams found"))
        
        # Start the parallel check in a background thread
        threading.Thread(target=check_all_parallel, daemon=True).start()
    
    def _update_tree_item_with_progress(self, sid, status, model_name):
        """Update tree item and show progress"""
        self._update_tree_item(sid, status)
        progress = self._check_progress
        if status and ("live" in status.lower() or "online" in status.lower()):
            self.log_write(f"✓ {model_name} - LIVE ({progress['completed']}/{progress['total']})")
        else:
            self.log_write(f"○ {model_name} - offline ({progress['completed']}/{progress['total']})")
    
    def _update_tree_item_error(self, sid, model_name, error):
        """Update tree item for error case"""
        self._update_tree_item(sid, "Error")
        progress = self._check_progress
        self.log_write(f"✗ {model_name} - error ({progress['completed']}/{progress['total']})")

def main():
    """Main entry point for the application"""
    root = tk.Tk()
    app = App(root, root)
    
    # Handle window close with cleanup
    def on_close():
        # Show exit message
        app.status_var.set("The program is preparing to exit...")
        app.update()  # Force UI update
        app._cleanup_all_processes()
        app.on_close()
        root.destroy()
    
    root.protocol("WM_DELETE_WINDOW", on_close)
    
    # Start the application
    root.mainloop()
