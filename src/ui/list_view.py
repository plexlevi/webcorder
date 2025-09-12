from __future__ import annotations
from tkinter import ttk

from .helpers import UrlTooltip
from .autosize import schedule as autosize_schedule


def _sort_column(tree, col, reverse):
    """Sort tree contents by column"""
    try:
        # Get all items and their values
        items = [(tree.item(item)['values'], item) for item in tree.get_children()]
        
        # Column indices
        col_index = {
            "Model": 0,
            "URL": 1,
            "Status": 2,
            "Auto": 3,
            "Elapsed": 4
        }.get(col, 0)
        
        # Custom sorting logic for different columns
        if col == "Elapsed":
            # Sort by elapsed time (convert to seconds for proper comparison)
            def elapsed_key(item):
                elapsed_str = item[0][col_index] if len(item[0]) > col_index else ""
                if not elapsed_str or elapsed_str == "":
                    return 0
                try:
                    # Parse MM:SS format
                    parts = elapsed_str.split(":")
                    if len(parts) == 2:
                        return int(parts[0]) * 60 + int(parts[1])
                    return 0
                except:
                    return 0
            items.sort(key=elapsed_key, reverse=reverse)
        elif col == "Auto":
            # Sort by Auto status (On before Off)
            def auto_key(item):
                auto_str = item[0][col_index] if len(item[0]) > col_index else ""
                return 0 if auto_str == "On" else 1
            items.sort(key=auto_key, reverse=reverse)
        elif col == "Status":
            # Sort by Status with custom priority (Recording first, then alphabetical)
            def status_key(item):
                status_str = item[0][col_index] if len(item[0]) > col_index else ""
                # Remove visual indicators for sorting
                if status_str.startswith("●"):
                    status_str = status_str[2:]  # Remove "● " prefix
                
                # Priority order: Recording, Live, Idle, others alphabetically
                priority = {
                    "Recording": 0,
                    "Live": 1,
                    "Idle": 2,
                    "": 3,  # Empty status (loaded URLs)
                    "Added": 4,  # Manual addition
                    "No stream": 5,
                    "Error": 6
                }
                return (priority.get(status_str, 99), status_str)
            items.sort(key=status_key, reverse=reverse)
        else:
            # Default string sorting for Model and URL
            def default_key(item):
                value = item[0][col_index] if len(item[0]) > col_index else ""
                # Remove visual indicators for Model column sorting
                if col == "Model" and value.startswith("●"):
                    value = value[2:]  # Remove "● " prefix
                return value.lower()
            items.sort(key=default_key, reverse=reverse)
        
        # Rearrange items in sorted positions
        for index, (values, item) in enumerate(items):
            tree.move(item, '', index)
        
        # Update column heading to show sort direction
        for column in ["Model", "URL", "Status", "Auto", "Elapsed"]:
            if column == col:
                direction = "▼" if reverse else "▲"
                tree.heading(column, text=f"{column} {direction}")
            else:
                tree.heading(column, text=column)
                
    except Exception as e:
        print(f"Sort error: {e}")


def _sort_column_toggle(tree, col):
    """Toggle sort direction and sort column"""
    # Toggle the sort direction (using getattr/setattr to avoid lint errors)
    sort_reverse = getattr(tree, '_sort_reverse', {})
    # Change logic: start with ascending (False), then toggle to descending (True)
    current_state = sort_reverse.get(col, True)  # Default to True so first click gives False (ascending)
    sort_reverse[col] = not current_state
    setattr(tree, '_sort_reverse', sort_reverse)
    _sort_column(tree, col, sort_reverse[col])


def build(parent, app=None) -> ttk.Treeview:
    # Use the parent directly as the container
    parent.columnconfigure(0, weight=1)
    parent.rowconfigure(0, weight=1)

    tree = ttk.Treeview(parent, columns=("Model", "URL", "Status", "Auto", "Elapsed"), show="headings", height=5)
    
    # Store sort direction for each column (using setattr to avoid lint errors)
    # Initialize to True so first click will be ascending (False)
    setattr(tree, '_sort_reverse', {"Model": True, "URL": True, "Status": True, "Auto": True, "Elapsed": True})
    
    # Set up column headings with sort functionality
    for col in ["Model", "URL", "Status", "Auto", "Elapsed"]:
        tree.heading(col, text=col, command=lambda c=col: _sort_column_toggle(tree, c))
    
    tree.column("Model", width=140, anchor="w", stretch=False)
    tree.column("URL", width=300, anchor="w", stretch=True, minwidth=120)
    tree.column("Status", width=100, anchor="w", stretch=False)
    tree.column("Auto", width=60, anchor="center", stretch=False)
    tree.column("Elapsed", width=80, anchor="center", stretch=False)
    tree.grid(row=0, column=0, sticky="nsew", padx=0, pady=0)  # Removed padding

    tree_scroll = ttk.Scrollbar(parent, command=tree.yview)
    tree.configure(yscrollcommand=tree_scroll.set)
    tree_scroll.grid(row=0, column=1, sticky="ns", padx=0, pady=0)  # Removed padding

    try:
        hscroll = ttk.Scrollbar(parent, orient="horizontal", command=tree.xview)
        tree.configure(xscrollcommand=hscroll.set)
        hscroll.grid(row=1, column=0, sticky="ew", padx=0, pady=0)  # Removed padding
    except Exception:
        pass

    UrlTooltip(tree)
    if app and hasattr(app, '_autosize_after_holder'):
        parent.bind("<Configure>", lambda e: autosize_schedule(tree, app, app._autosize_after_holder))

    return tree
