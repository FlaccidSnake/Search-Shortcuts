# -*- coding: utf-8 -*-
"""
Anki Add-on: Search Shortcuts
Adds configurable shortcut buttons below the search bar for quick access to saved searches.
Each button can optionally be in "filter mode", where its search is added to the
current search instead of replacing it.
Copyright: 2026
License: GNU AGPLv3 or later <https://www.gnu.org/licenses/agpl.html>
"""
import re

from aqt.qt import *
from aqt import gui_hooks, mw
from aqt.utils import showInfo

# Storage key for saved searches
STORAGE_KEY = "search_shortcuts"


# ---------------------------------------------------------------------------
# Config helpers
# ---------------------------------------------------------------------------

def get_config():
    """Get addon configuration"""
    config = mw.addonManager.getConfig(__name__)
    if config is None:
        return {"num_shortcuts": 5, "button_labels": {}, "filter_mode": {}}
    return config

def get_num_shortcuts():
    """Get the configured number of shortcuts from addon config"""
    config = get_config()
    return min(max(config.get("num_shortcuts", 5), 1), 10)

def get_button_label(slot):
    """Get the custom label for a button slot, or default to heart + number"""
    config = get_config()
    button_labels = config.get("button_labels", {})
    return button_labels.get(str(slot), f"♡ {slot}")

def is_filter_mode(slot):
    """Return True if the given slot is in filter mode"""
    config = get_config()
    return bool(config.get("filter_mode", {}).get(str(slot), False))

def set_filter_mode(slot, enabled):
    """Persist the filter mode setting for the given slot"""
    config = get_config()
    modes = config.get("filter_mode", {})
    if enabled:
        modes[str(slot)] = True
    else:
        modes.pop(str(slot), None)
    config["filter_mode"] = modes
    mw.addonManager.writeConfig(__name__, config)


# ---------------------------------------------------------------------------
# Saved search storage
# ---------------------------------------------------------------------------

def load_shortcuts():
    """Load saved search shortcuts from the collection config"""
    meta = mw.col.get_config(STORAGE_KEY, {})
    num_shortcuts = get_num_shortcuts()
    # Default empty searches for configured number of slots
    return {str(i): meta.get(str(i), "") for i in range(1, num_shortcuts + 1)}

def save_shortcuts(shortcuts):
    """Save search shortcuts to the collection config"""
    mw.col.set_config(STORAGE_KEY, shortcuts)


# ---------------------------------------------------------------------------
# Tooltip
# ---------------------------------------------------------------------------

def update_tooltip(button, slot):
    """Refresh a button's tooltip from the saved search and filter mode"""
    search_text = load_shortcuts().get(str(slot), "")
    if search_text:
        tip = f"Slot {slot}: {search_text}"
        if is_filter_mode(slot):
            tip += "\n(Filter mode: adds to the current search)"
    else:
        tip = f"Slot {slot}: (empty - right-click to save current search)"
    button.setToolTip(tip)


# ---------------------------------------------------------------------------
# Search combining
# ---------------------------------------------------------------------------

def _wrap_if_or(text):
    """Wrap text in parentheses if it contains OR, so it stays grouped.

    In Anki, a space means AND and AND binds tighter than OR, so
    'a or b tag:x' would be read as 'a or (b tag:x)'. Wrapping avoids that.
    """
    if re.search(r"\bor\b", text, re.IGNORECASE):
        return f"({text})"
    return text

def combine_searches(current, saved):
    """Append the saved search to the current one (implicit AND)"""
    current = current.strip()
    saved = saved.strip()

    if not current:
        return saved
    if saved in current:
        # Already applied, don't duplicate it
        return current

    return f"{_wrap_if_or(current)} {_wrap_if_or(saved)}"


# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------

def add_search_shortcuts(browser):
    """Add search shortcut buttons below the search bar"""

    num_shortcuts = get_num_shortcuts()

    # Create container widget for buttons
    container = QWidget()
    button_layout = QHBoxLayout()
    button_layout.setContentsMargins(0, 5, 0, 5)
    button_layout.setSpacing(5)
    container.setLayout(button_layout)

    # Create configured number of shortcut buttons
    for i in range(1, num_shortcuts + 1):
        button = QPushButton(get_button_label(i))
        button.setFlat(True)
        button.setMinimumWidth(50)
        button.setMinimumHeight(25)

        update_tooltip(button, i)

        # Left click: execute saved search
        button.clicked.connect(lambda checked, slot=i: execute_search(browser, slot))

        # Right click: context menu
        button.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        button.customContextMenuRequested.connect(
            lambda pos, btn=button, slot=i: show_context_menu(browser, btn, slot, pos)
        )

        button_layout.addWidget(button, stretch=1)

    # Add container to browser layout (row 1, span all columns)
    layout = browser.form.gridLayout
    layout.addWidget(container, 1, 0, 1, layout.columnCount())

def execute_search(browser, slot):
    """Execute the search saved in the given slot"""
    saved = load_shortcuts().get(str(slot), "")

    if not saved:
        showInfo(f"Slot {slot} is empty. Right-click to save current search.")
        return

    if is_filter_mode(slot):
        current = browser.form.searchEdit.currentText()
        search_text = combine_searches(current, saved)
    else:
        search_text = saved

    browser.form.searchEdit.setEditText(search_text)
    browser.search_for(search_text)

def show_context_menu(browser, button, slot, pos):
    """Show context menu for saving/renaming/filter mode/clearing"""
    menu = QMenu()

    # Save current search action
    save_action = menu.addAction("Save current search")
    save_action.triggered.connect(lambda: save_current_search(browser, button, slot))

    # Rename button action
    rename_action = menu.addAction("Rename button")
    rename_action.triggered.connect(lambda: rename_button(browser, button, slot))

    menu.addSeparator()

    # Filter mode checkbox
    filter_action = menu.addAction("Filter mode (add to current search)")
    filter_action.setCheckable(True)
    filter_action.setChecked(is_filter_mode(slot))
    filter_action.triggered.connect(
        lambda checked: toggle_filter_mode(button, slot, checked)
    )

    # Clear search action
    if load_shortcuts().get(str(slot), ""):
        menu.addSeparator()
        clear_action = menu.addAction("Clear saved search")
        clear_action.triggered.connect(lambda: clear_search(browser, button, slot))

    # Show menu at button position
    menu.exec(button.mapToGlobal(pos))

def toggle_filter_mode(button, slot, enabled):
    """Turn filter mode on/off for a slot"""
    set_filter_mode(slot, enabled)
    update_tooltip(button, slot)

def save_current_search(browser, button, slot):
    """Save the current search text to the given slot"""
    current_search = browser.form.searchEdit.currentText()

    if not current_search.strip():
        showInfo("Search bar is empty. Type a search first, then right-click to save it.")
        return

    shortcuts = load_shortcuts()
    shortcuts[str(slot)] = current_search
    save_shortcuts(shortcuts)

    update_tooltip(button, slot)
    showInfo(f"Saved search to slot {slot}")

def clear_search(browser, button, slot):
    """Clear the saved search in the given slot"""
    shortcuts = load_shortcuts()
    shortcuts[str(slot)] = ""
    save_shortcuts(shortcuts)

    update_tooltip(button, slot)
    showInfo(f"Cleared slot {slot}")

def rename_button(browser, button, slot):
    """Rename the button label"""
    from aqt.utils import getText

    current_label = get_button_label(slot)

    new_label, ok = getText(
        f"Enter new label for button {slot}:",
        default=current_label,
        title="Rename Button"
    )

    if ok and new_label is not None:
        new_label = new_label.strip()

        config = get_config()
        if "button_labels" not in config:
            config["button_labels"] = {}

        if new_label:
            config["button_labels"][str(slot)] = new_label
        else:
            # If empty, remove custom label (revert to default)
            config["button_labels"].pop(str(slot), None)

        mw.addonManager.writeConfig(__name__, config)

        button.setText(new_label if new_label else f"♡ {slot}")
        showInfo(f"Button {slot} renamed! Label will persist across sessions.")

# Register the hook to add buttons when browser opens
gui_hooks.browser_will_show.append(add_search_shortcuts)