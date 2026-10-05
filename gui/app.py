"""
gui/app.py

Tkinter GUI for ORVIX.

Responsibilities:
- Show configured gestures/mappings
- Add / edit / delete mappings
- Browse for a .bat file
- Start / stop the camera
- Show the currently detected gesture + status
- Show a live camera preview with landmarks drawn
"""

from __future__ import annotations

import re
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Optional

import cv2
from PIL import Image, ImageTk

from core.controller import Controller
from core.state import RuntimeState
from mapping.manager import MappingManager
from utils.constants import (
    ACTION_HOLD_HOTKEY,
    ACTION_HOTKEY,
    ACTION_TYPES,
    MAPPABLE_GESTURES,
)
from utils.logger import get_logger

log = get_logger("gui.app")


class OrvixApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("ORVIX — Gesture Automation System")
        self.geometry("880x560")
        self.resizable(False, False)

        self.mapping_manager = MappingManager()
        self.controller: Optional[Controller] = None
        self._camera_thread: Optional[threading.Thread] = None
        self._camera_running = False

        self._build_layout()
        self._refresh_mapping_table()

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def _build_layout(self) -> None:
        header = tk.Label(self, text="ORVIX", font=("Segoe UI", 20, "bold"))
        header.pack(pady=(12, 0))
        sub = tk.Label(self, text="Gesture Automation System", font=("Segoe UI", 10))
        sub.pack(pady=(0, 10))

        main = tk.Frame(self)
        main.pack(fill="both", expand=True, padx=12, pady=6)

        # Left: mapping table + controls
        left = tk.Frame(main)
        left.pack(side="left", fill="both", expand=True)

        columns = ("gesture", "type", "value", "enabled")
        self.tree = ttk.Treeview(left, columns=columns, show="headings", height=12)
        for col, label, width in [
            ("gesture", "Gesture", 100),
            ("type", "Type", 70),
            ("value", "Action Value", 260),
            ("enabled", "Enabled", 70),
        ]:
            self.tree.heading(col, text=label)
            self.tree.column(col, width=width, anchor="w")
        self.tree.pack(fill="both", expand=True)

        btns = tk.Frame(left)
        btns.pack(fill="x", pady=8)
        tk.Button(btns, text="+ Add Mapping", command=self._on_add).pack(side="left", padx=4)
        tk.Button(btns, text="Edit", command=self._on_edit).pack(side="left", padx=4)
        tk.Button(btns, text="Delete", command=self._on_delete).pack(side="left", padx=4)
        tk.Button(btns, text="Toggle Enabled", command=self._on_toggle_enabled).pack(side="left", padx=4)

        camera_btns = tk.Frame(left)
        camera_btns.pack(fill="x", pady=(16, 4))
        self.start_btn = tk.Button(camera_btns, text="Start Camera", command=self._on_start_camera, bg="#2e7d32", fg="white")
        self.start_btn.pack(side="left", padx=4)
        self.stop_btn = tk.Button(camera_btns, text="Stop Camera", command=self._on_stop_camera, state="disabled")
        self.stop_btn.pack(side="left", padx=4)

        self.status_var = tk.StringVar(value="Status: Idle")
        self.gesture_var = tk.StringVar(value="Current Gesture: —")
        tk.Label(left, textvariable=self.gesture_var, font=("Segoe UI", 11, "bold")).pack(anchor="w", pady=(12, 0))
        tk.Label(left, textvariable=self.status_var, font=("Segoe UI", 10)).pack(anchor="w")

        # Right: camera preview
        right = tk.Frame(main, width=360, height=270, bg="black")
        right.pack(side="right", padx=(12, 0))
        right.pack_propagate(False)
        self.preview_label = tk.Label(right, bg="black", text="Camera preview", fg="white")
        self.preview_label.pack(fill="both", expand=True)

    # ------------------------------------------------------------------
    # Mapping table
    # ------------------------------------------------------------------

    def _refresh_mapping_table(self) -> None:
        for row in self.tree.get_children():
            self.tree.delete(row)
        for gesture, entry in self.mapping_manager.all_mappings().items():
            self.tree.insert(
                "", "end", iid=gesture,
                values=(gesture, entry.get("type", "batch"), self._format_mapping_value(entry), entry.get("enabled", True)),
            )

    def _selected_gesture(self) -> Optional[str]:
        sel = self.tree.selection()
        return sel[0] if sel else None

    @staticmethod
    def _format_mapping_value(entry: dict) -> str:
        action_type = entry.get("type", "batch")
        if action_type == ACTION_HOTKEY:
            keys = entry.get("keys", [])
            if isinstance(keys, list):
                return " + ".join(str(key) for key in keys)
            return str(keys)
        if action_type == ACTION_HOLD_HOTKEY:
            modifier = str(entry.get("modifier", "")).strip()
            key = str(entry.get("key", "")).strip()
            if modifier and key:
                return f"{modifier} + {key} (hold)"
            return f"{modifier} + {key}".strip(" +")
        return entry.get("path", "")

    @staticmethod
    def _parse_hotkey_keys(raw_text: str) -> list[str]:
        parts = [
            part.strip()
            for part in re.split(r"\s*(?:,|\+)\s*", raw_text.strip())
            if part.strip()
        ]
        return parts

    def _on_add(self) -> None:
        self._open_mapping_dialog(existing_gesture=None)

    def _on_edit(self) -> None:
        gesture = self._selected_gesture()
        if not gesture:
            messagebox.showinfo("Edit Mapping", "Select a mapping to edit first.")
            return
        self._open_mapping_dialog(existing_gesture=gesture)

    def _on_delete(self) -> None:
        gesture = self._selected_gesture()
        if not gesture:
            messagebox.showinfo("Delete Mapping", "Select a mapping to delete first.")
            return
        if messagebox.askyesno("Delete Mapping", f"Delete mapping for {gesture}?"):
            self.mapping_manager.delete_mapping(gesture)
            self._refresh_mapping_table()

    def _on_toggle_enabled(self) -> None:
        gesture = self._selected_gesture()
        if not gesture:
            return
        current = self.mapping_manager.all_mappings()[gesture].get("enabled", True)
        self.mapping_manager.set_enabled(gesture, not current)
        self._refresh_mapping_table()

    def _open_mapping_dialog(self, existing_gesture: Optional[str]) -> None:
        dialog = tk.Toplevel(self)
        dialog.title("Add Mapping" if existing_gesture is None else "Edit Mapping")
        dialog.geometry("560x330")
        dialog.grab_set()

        existing_entry = self.mapping_manager.all_mappings().get(existing_gesture, {})

        tk.Label(dialog, text="Gesture:").grid(row=0, column=0, sticky="w", padx=10, pady=10)
        gesture_var = tk.StringVar(value=existing_gesture or MAPPABLE_GESTURES[0])
        gesture_combo = ttk.Combobox(dialog, textvariable=gesture_var, values=MAPPABLE_GESTURES, state="readonly")
        gesture_combo.grid(row=0, column=1, padx=10, pady=10, sticky="ew")
        if existing_gesture is not None:
            gesture_combo.config(state="disabled")

        tk.Label(dialog, text="Action Type:").grid(row=1, column=0, sticky="w", padx=10, pady=10)
        action_type_var = tk.StringVar(value=existing_entry.get("type", "batch") if existing_gesture else "batch")
        action_type_combo = ttk.Combobox(
            dialog,
            textvariable=action_type_var,
            values=ACTION_TYPES,
            state="readonly",
        )
        action_type_combo.grid(row=1, column=1, padx=10, pady=10, sticky="ew")

        batch_frame = tk.Frame(dialog)
        batch_frame.grid(row=2, column=0, columnspan=3, sticky="ew")
        tk.Label(batch_frame, text="Batch file (.bat):").grid(row=0, column=0, sticky="w", padx=10, pady=10)
        path_var = tk.StringVar(value=existing_entry.get("path", "") if existing_gesture else "")
        path_entry = tk.Entry(batch_frame, textvariable=path_var, width=34)
        path_entry.grid(row=0, column=1, padx=10, pady=10, sticky="ew")

        def browse() -> None:
            path = filedialog.askopenfilename(filetypes=[("Batch files", "*.bat")])
            if path:
                path_var.set(path)

        browse_btn = tk.Button(batch_frame, text="Browse...", command=browse)
        browse_btn.grid(row=0, column=2, padx=(0, 10))

        hotkey_frame = tk.Frame(dialog)
        hotkey_frame.grid(row=3, column=0, columnspan=3, sticky="ew")
        tk.Label(hotkey_frame, text="Keys (comma separated):").grid(row=0, column=0, sticky="w", padx=10, pady=10)
        keys_var = tk.StringVar(
            value=", ".join(existing_entry.get("keys", []))
            if isinstance(existing_entry.get("keys", []), list)
            else str(existing_entry.get("keys", ""))
        )
        tk.Entry(hotkey_frame, textvariable=keys_var, width=34).grid(row=0, column=1, padx=10, pady=10, sticky="ew")

        hold_frame = tk.Frame(dialog)
        hold_frame.grid(row=4, column=0, columnspan=3, sticky="ew")
        tk.Label(hold_frame, text="Modifier:").grid(row=0, column=0, sticky="w", padx=10, pady=8)
        modifier_var = tk.StringVar(value=str(existing_entry.get("modifier", "alt")) if existing_gesture else "alt")
        tk.Entry(hold_frame, textvariable=modifier_var, width=16).grid(row=0, column=1, padx=10, pady=8, sticky="w")
        tk.Label(hold_frame, text="Trigger Key:").grid(row=1, column=0, sticky="w", padx=10, pady=8)
        hold_key_var = tk.StringVar(value=str(existing_entry.get("key", "tab")) if existing_gesture else "tab")
        tk.Entry(hold_frame, textvariable=hold_key_var, width=16).grid(row=1, column=1, padx=10, pady=8, sticky="w")
        tk.Label(
            hold_frame,
            text=f"Repeat interval: {0.4:.1f}s configured in code",
            fg="#555555",
        ).grid(row=2, column=0, columnspan=2, sticky="w", padx=10, pady=(4, 10))
        dialog.grid_columnconfigure(1, weight=1)
        batch_frame.grid_columnconfigure(1, weight=1)
        hotkey_frame.grid_columnconfigure(1, weight=1)
        hold_frame.grid_columnconfigure(1, weight=1)

        def refresh_action_fields(*_ignored) -> None:
            action_type = action_type_var.get()
            if action_type == ACTION_HOTKEY:
                batch_frame.grid_remove()
                hotkey_frame.grid()
                hold_frame.grid_remove()
            elif action_type == ACTION_HOLD_HOTKEY:
                batch_frame.grid_remove()
                hotkey_frame.grid_remove()
                hold_frame.grid()
            else:
                hotkey_frame.grid_remove()
                hold_frame.grid_remove()
                batch_frame.grid()

        action_type_var.trace_add("write", refresh_action_fields)
        refresh_action_fields()

        def save():
            gesture = gesture_var.get()
            action_type = action_type_var.get()

            if action_type == ACTION_HOTKEY:
                keys = self._parse_hotkey_keys(keys_var.get())
                if not keys:
                    messagebox.showerror("Invalid Mapping", "Please enter at least one hotkey key.")
                    return
                if existing_gesture is not None:
                    self.mapping_manager.edit_mapping(existing_gesture, action_type=action_type, keys=keys)
                else:
                    self.mapping_manager.add_mapping(gesture, action_type=action_type, keys=keys)
            elif action_type == ACTION_HOLD_HOTKEY:
                modifier = modifier_var.get().strip()
                hold_key = hold_key_var.get().strip()
                if not modifier or not hold_key:
                    messagebox.showerror("Invalid Mapping", "Please enter both a modifier and a trigger key.")
                    return
                if existing_gesture is not None:
                    self.mapping_manager.edit_mapping(
                        existing_gesture,
                        action_type=action_type,
                        modifier=modifier,
                        key=hold_key,
                    )
                else:
                    self.mapping_manager.add_mapping(
                        gesture,
                        action_type=action_type,
                        modifier=modifier,
                        key=hold_key,
                    )
            else:
                path = path_var.get().strip()
                if not path:
                    messagebox.showerror("Invalid Mapping", "Please select a .bat file.")
                    return
                if not path.lower().endswith(".bat"):
                    messagebox.showerror("Invalid Mapping", "Only .bat files are supported for batch mappings.")
                    return

                if existing_gesture is not None:
                    self.mapping_manager.edit_mapping(existing_gesture, action_type=action_type, path=path)
                else:
                    self.mapping_manager.add_mapping(gesture, path=path, action_type=action_type)

            self._refresh_mapping_table()
            dialog.destroy()

        tk.Button(dialog, text="Save", command=save, bg="#1565c0", fg="white").grid(
            row=2, column=1, pady=16, sticky="e"
        )

    # ------------------------------------------------------------------
    # Camera control
    # ------------------------------------------------------------------

    def _on_start_camera(self) -> None:
        if self._camera_running:
            return

        try:
            self.controller = Controller(mapping_manager=self.mapping_manager)
        except Exception as e:  # model missing, etc.
            messagebox.showerror("Startup Error", str(e))
            log.exception("Failed to create controller")
            return

        self._camera_running = True
        self.start_btn.config(state="disabled")
        self.stop_btn.config(state="normal")
        self.status_var.set("Status: Camera running")

        self._camera_thread = threading.Thread(target=self._camera_loop, daemon=True)
        self._camera_thread.start()

    def _camera_loop(self) -> None:
        try:
            self.controller.start(on_frame=self._on_frame)
        except Exception as e:
            log.exception("Camera loop crashed")
            self.after(0, lambda: messagebox.showerror("Camera Error", str(e)))
        finally:
            self.after(0, self._reset_camera_buttons)

    def _on_frame(self, frame, gesture: str, state: RuntimeState) -> None:
        # Runs on the camera thread — only touch Tk widgets via `after`.
        self.after(0, lambda: self._update_preview(frame, gesture, state))

    def _update_preview(self, frame, gesture: str, state: RuntimeState) -> None:
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        rgb = cv2.resize(rgb, (360, 270))
        img = ImageTk.PhotoImage(image=Image.fromarray(rgb))
        self.preview_label.imgtk = img  # keep a reference so it isn't garbage collected
        self.preview_label.configure(image=img)

        self.gesture_var.set(f"Current Gesture: {gesture}")
        self.status_var.set(f"Status: {state.name}")

    def _on_stop_camera(self) -> None:
        if self.controller is not None:
            self.controller.stop()
        self._reset_camera_buttons()

    def _reset_camera_buttons(self) -> None:
        self._camera_running = False
        self.start_btn.config(state="normal")
        self.stop_btn.config(state="disabled")
        self.status_var.set("Status: Idle")

    def _on_close(self) -> None:
        self._on_stop_camera()
        self.destroy()


def main():
    app = OrvixApp()
    app.mainloop()


if __name__ == "__main__":
    main()
