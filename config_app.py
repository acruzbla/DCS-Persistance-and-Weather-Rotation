"""
DCS Persistence Config GUI

This module provides a small graphical application to configure
the DCS persistence helper. It stores configuration in a JSON file
so that the main application can later read and act accordingly.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Literal, Any, Dict

import tkinter as tk
from tkinter import ttk, filedialog, messagebox

# ------------------------------
# Configuration model
# ------------------------------


SeasonType = Literal["summer", "autumn", "winter", "spring", "none"]
NextActionType = Literal[
    "none",
    "save_and_apply",
    "save_and_apply_next_rotation",
    "apply_rotation"
]


@dataclass
class AppConfig:
    """
    Represents the full configuration for the DCS persistence helper.
    This configuration is serialized to and from JSON.
    """

    # 1. DCS mission path
    mission_path: str = ""

    # 2. Hour persistence
    hour_persistence_enabled: bool = False

    # 3. Weather rotation
    weather_rotation_enabled: bool = False
    weather_season: SeasonType = "none"  # summer, autumn, winter, spring, none
    weather_bad_weather_percentage: int = 0  # 0-100

    # 4. Backup saves
    backup_saves_enabled: bool = False
    backup_saves_path: str = ""
    backup_saves_discord_enabled: bool = False
    backup_saves_discord_webhook: str = ""

    # 5. Program execution time (HH:MM)
    execution_time: str = "00:00"

    # 7. Errors to Discord
    send_errors_to_discord: bool = False
    error_discord_webhook: str = ""

    # Internal: next requested action from the config GUI
    next_action: NextActionType = "none"

    @staticmethod
    def get_default_config_path() -> Path:
        """
        Returns the default path to the JSON configuration file.
        By default, it is stored in the same directory as this module.
        """
        base_dir = Path(__file__).resolve().parent
        return base_dir / "dcs_persistence_config.json"

    @classmethod
    def load(cls, path: Path | None = None) -> "AppConfig":
        """
        Load configuration from a JSON file. If the file does not exist
        or is invalid, returns a default configuration instance.
        """
        if path is None:
            path = cls.get_default_config_path()

        if not path.exists():
            return cls()

        try:
            with path.open("r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            # If something goes wrong reading JSON, return defaults.
            return cls()

        return cls.from_dict(data)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AppConfig":
        """
        Create an AppConfig instance from a dictionary (e.g., loaded JSON).
        Missing keys will fall back to default values.
        """
        kwargs: Dict[str, Any] = {}

        # Direct mapping with safe fallback to defaults
        defaults = cls()

        kwargs["mission_path"] = data.get("mission_path", defaults.mission_path)
        kwargs["hour_persistence_enabled"] = bool(
            data.get("hour_persistence_enabled", defaults.hour_persistence_enabled)
        )

        kwargs["weather_rotation_enabled"] = bool(
            data.get("weather_rotation_enabled", defaults.weather_rotation_enabled)
        )
        kwargs["weather_season"] = data.get("weather_season", defaults.weather_season)
        kwargs["weather_bad_weather_percentage"] = int(
            data.get("weather_bad_weather_percentage",
                     defaults.weather_bad_weather_percentage)
        )

        kwargs["backup_saves_enabled"] = bool(
            data.get("backup_saves_enabled", defaults.backup_saves_enabled)
        )
        kwargs["backup_saves_path"] = data.get("backup_saves_path",
                                               defaults.backup_saves_path)
        kwargs["backup_saves_discord_enabled"] = bool(
            data.get("backup_saves_discord_enabled",
                     defaults.backup_saves_discord_enabled)
        )
        kwargs["backup_saves_discord_webhook"] = data.get(
            "backup_saves_discord_webhook", defaults.backup_saves_discord_webhook
        )

        kwargs["execution_time"] = data.get("execution_time",
                                            defaults.execution_time)

        kwargs["send_errors_to_discord"] = bool(
            data.get("send_errors_to_discord", defaults.send_errors_to_discord)
        )
        kwargs["error_discord_webhook"] = data.get(
            "error_discord_webhook", defaults.error_discord_webhook
        )

        kwargs["next_action"] = data.get("next_action", defaults.next_action)

        return cls(**kwargs)

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert this configuration object to a dictionary suitable for JSON.
        """
        return asdict(self)

    def save(self, path: Path | None = None) -> None:
        """
        Save this configuration to a JSON file.
        """
        if path is None:
            path = self.get_default_config_path()

        with path.open("w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=4)


# ------------------------------
# GUI Application
# ------------------------------


class ConfigGUI(tk.Tk):
    """
    Tkinter-based configuration window for the DCS persistence helper.
    """

    def __init__(self, config: AppConfig) -> None:
        super().__init__()

        self.title("DCS Persistence Config")
        self.config = config

        # Tkinter variables
        self.var_mission_path = tk.StringVar(value=config.mission_path)
        self.var_hour_persistence = tk.BooleanVar(
            value=config.hour_persistence_enabled
        )

        self.var_weather_rotation = tk.BooleanVar(
            value=config.weather_rotation_enabled
        )
        self.var_weather_season = tk.StringVar(value=config.weather_season)
        self.var_bad_weather = tk.IntVar(
            value=config.weather_bad_weather_percentage
        )

        self.var_backup_enabled = tk.BooleanVar(
            value=config.backup_saves_enabled
        )
        self.var_backup_path = tk.StringVar(value=config.backup_saves_path)
        self.var_backup_discord = tk.BooleanVar(
            value=config.backup_saves_discord_enabled
        )
        self.var_backup_discord_webhook = tk.StringVar(
            value=config.backup_saves_discord_webhook
        )

        self.var_execution_time = tk.StringVar(value=config.execution_time)

        self.var_errors_discord = tk.BooleanVar(
            value=config.send_errors_to_discord
        )
        self.var_error_discord_webhook = tk.StringVar(
            value=config.error_discord_webhook
        )

        # Build GUI
        self._build_widgets()
        self._update_state_dependent_widgets()

    # ---------- Layout helpers ----------

    def _build_widgets(self) -> None:
        """
        Build and arrange all GUI widgets.
        """
        main_frame = ttk.Frame(self, padding=10)
        main_frame.grid(row=0, column=0, sticky="nsew")

        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)

        row = 0

        # 1. Mission path
        ttk.Label(main_frame, text="DCS .miz mission path:").grid(
            row=row, column=0, sticky="w", pady=2
        )
        entry_miz = ttk.Entry(main_frame, textvariable=self.var_mission_path)
        entry_miz.grid(row=row, column=1, sticky="ew", pady=2)
        ttk.Button(main_frame, text="Browse...",
                   command=self._browse_miz).grid(
            row=row, column=2, padx=5, pady=2
        )
        row += 1

        ttk.Separator(main_frame, orient="horizontal").grid(
            row=row, column=0, columnspan=3, sticky="ew", pady=5
        )
        row += 1

        # 2. Hour persistence
        chk_hour = ttk.Checkbutton(
            main_frame,
            text="Enable hour persistence",
            variable=self.var_hour_persistence
        )
        chk_hour.grid(row=row, column=0, columnspan=3, sticky="w", pady=2)
        row += 1

        ttk.Separator(main_frame, orient="horizontal").grid(
            row=row, column=0, columnspan=3, sticky="ew", pady=5
        )
        row += 1

        # 3. Weather rotation
        chk_weather = ttk.Checkbutton(
            main_frame,
            text="Enable weather rotation",
            variable=self.var_weather_rotation,
            command=self._update_state_dependent_widgets
        )
        chk_weather.grid(row=row, column=0, columnspan=3, sticky="w", pady=2)
        row += 1

        # 3.1 Season (radio buttons)
        season_frame = ttk.LabelFrame(main_frame, text="Season")
        season_frame.grid(row=row, column=0, columnspan=3,
                        sticky="ew", pady=2)

        for i, (text, value) in enumerate(
            [
                ("Summer", "summer"),
                ("Autumn", "autumn"),
                ("Winter", "winter"),
                ("Spring", "spring"),
                ("Realistic", "realistic")  # NEW OPTION
            ]
        ):
            ttk.Radiobutton(
                season_frame,
                text=text,
                value=value,
                variable=self.var_weather_season,
                command=self._on_season_selected
            ).grid(row=0, column=i, padx=5, pady=2)


        row += 1

        # 3.2 Bad weather percentage
        ttk.Label(main_frame,
                  text="Bad weather percentage (0-100):").grid(
            row=row, column=0, sticky="w", pady=2
        )
        spin_bad_weather = ttk.Spinbox(
            main_frame,
            from_=0,
            to=100,
            textvariable=self.var_bad_weather,
            width=5
        )
        spin_bad_weather.grid(row=row, column=1, sticky="w", pady=2)
        row += 1

        ttk.Separator(main_frame, orient="horizontal").grid(
            row=row, column=0, columnspan=3, sticky="ew", pady=5
        )
        row += 1

        # 4. Backup saves
        chk_backup = ttk.Checkbutton(
            main_frame,
            text="Enable backup saves",
            variable=self.var_backup_enabled,
            command=self._update_state_dependent_widgets
        )
        chk_backup.grid(row=row, column=0, columnspan=3, sticky="w", pady=2)
        row += 1

        ttk.Label(main_frame, text="Backup saves path:").grid(
            row=row, column=0, sticky="w", pady=2
        )
        entry_backup_path = ttk.Entry(
            main_frame,
            textvariable=self.var_backup_path
        )
        entry_backup_path.grid(row=row, column=1, sticky="ew", pady=2)
        ttk.Button(main_frame, text="Browse...",
                   command=self._browse_backup_path).grid(
            row=row, column=2, padx=5, pady=2
        )
        row += 1

        chk_backup_discord = ttk.Checkbutton(
            main_frame,
            text="Send backup saves to Discord",
            variable=self.var_backup_discord,
            command=self._update_state_dependent_widgets
        )
        chk_backup_discord.grid(
            row=row, column=0, columnspan=3, sticky="w", pady=2
        )
        row += 1

        ttk.Label(main_frame, text="Discord webhook (saves):").grid(
            row=row, column=0, sticky="w", pady=2
        )
        entry_backup_webhook = ttk.Entry(
            main_frame,
            textvariable=self.var_backup_discord_webhook
        )
        entry_backup_webhook.grid(
            row=row, column=1, columnspan=2, sticky="ew", pady=2
        )
        row += 1

        ttk.Separator(main_frame, orient="horizontal").grid(
            row=row, column=0, columnspan=3, sticky="ew", pady=5
        )
        row += 1

        # 5. Execution time
        ttk.Label(main_frame, text="Execution time (HH:MM):").grid(
            row=row, column=0, sticky="w", pady=2
        )
        entry_time = ttk.Entry(
            main_frame,
            textvariable=self.var_execution_time,
            width=10
        )
        entry_time.grid(row=row, column=1, sticky="w", pady=2)
        row += 1

        ttk.Separator(main_frame, orient="horizontal").grid(
            row=row, column=0, columnspan=3, sticky="ew", pady=5
        )
        row += 1

        # 7. Errors to Discord
        chk_errors_discord = ttk.Checkbutton(
            main_frame,
            text="Send errors to Discord",
            variable=self.var_errors_discord,
            command=self._update_state_dependent_widgets
        )
        chk_errors_discord.grid(
            row=row, column=0, columnspan=3, sticky="w", pady=2
        )
        row += 1

        ttk.Label(main_frame, text="Discord webhook (errors):").grid(
            row=row, column=0, sticky="w", pady=2
        )
        entry_error_webhook = ttk.Entry(
            main_frame,
            textvariable=self.var_error_discord_webhook
        )
        entry_error_webhook.grid(
            row=row, column=1, columnspan=2, sticky="ew", pady=2
        )
        row += 1

        ttk.Separator(main_frame, orient="horizontal").grid(
            row=row, column=0, columnspan=3, sticky="ew", pady=5
        )
        row += 1

        # 6. Bottom buttons (actions)
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=row, column=0, columnspan=3, pady=5)

        ttk.Button(
            button_frame,
            text="Save and apply",
            command=self._on_save_and_apply
        ).grid(row=0, column=0, padx=5)

        ttk.Button(
            button_frame,
            text="Save and apply in next rotation",
            command=self._on_save_and_apply_next_rotation
        ).grid(row=0, column=1, padx=5)

        ttk.Button(
            button_frame,
            text="Apply rotation",
            command=self._on_apply_rotation
        ).grid(row=0, column=2, padx=5)

    # ---------- Event handlers ----------

    def _browse_miz(self) -> None:
        """
        Open a file dialog to choose the DCS .miz mission file.
        """
        filename = filedialog.askopenfilename(
            title="Select DCS .miz mission",
            filetypes=[("DCS mission files", "*.miz"), ("All files", "*.*")]
        )
        if filename:
            self.var_mission_path.set(filename)

    def _browse_backup_path(self) -> None:
        """
        Open a folder dialog to choose the backup saves path.
        """
        directory = filedialog.askdirectory(
            title="Select backup saves directory"
        )
        if directory:
            self.var_backup_path.set(directory)

    def _on_season_selected(self) -> None:
        """
        Ensures a valid season is selected when a radio button is pressed.
        """
        if self.var_weather_season.get() not in {
            "summer", "autumn", "winter", "spring", "realistic"
        }:
            self.var_weather_season.set("summer")


    def _on_save_and_apply(self) -> None:
        self._save_config_with_action("save_and_apply")

    def _on_save_and_apply_next_rotation(self) -> None:
        self._save_config_with_action("save_and_apply_next_rotation")

    def _on_apply_rotation(self) -> None:
        self._save_config_with_action("apply_rotation")

    # ---------- Helpers ----------

    def _update_state_dependent_widgets(self) -> None:
        """
        Enable/disable certain widgets based on related checkboxes.
        This method can be extended to manage more dependencies.
        """
        # Currently we do not store references to each entry/checkbutton
        # to enable/disable them individually. For simplicity, this
        # method is provided as a placeholder to be extended later
        # if needed (e.g., disabling webhook fields when checkboxes
        # are not selected).
        # You can add widget state management here if required.
        pass

    def _validate_execution_time(self) -> bool:
        """
        Validate that the execution time is in HH:MM format
        and hours/minutes are in a valid range.
        """
        value = self.var_execution_time.get().strip()
        if not value:
            messagebox.showerror(
                "Validation error",
                "Execution time cannot be empty (expected HH:MM)."
            )
            return False

        parts = value.split(":")
        if len(parts) != 2:
            messagebox.showerror(
                "Validation error",
                "Execution time must be in HH:MM format."
            )
            return False

        try:
            hours = int(parts[0])
            minutes = int(parts[1])
        except ValueError:
            messagebox.showerror(
                "Validation error",
                "Execution time must contain valid numbers (HH:MM)."
            )
            return False

        if not (0 <= hours <= 23 and 0 <= minutes <= 59):
            messagebox.showerror(
                "Validation error",
                "Execution time must be between 00:00 and 23:59."
            )
            return False

        return True

    def _save_config_with_action(self, action: NextActionType) -> None:
        """
        Collect GUI values, validate them, store them in the AppConfig,
        set the next_action field, save to JSON, and close the window.
        """
        if not self._validate_execution_time():
            return

        # Clamp bad weather percentage to 0-100
        try:
            bw = int(self.var_bad_weather.get())
        except ValueError:
            bw = 0
        bw = max(0, min(100, bw))
        self.var_bad_weather.set(bw)

        # Update config from GUI vars
        self.config.mission_path = self.var_mission_path.get().strip()
        self.config.hour_persistence_enabled = bool(
            self.var_hour_persistence.get()
        )

        self.config.weather_rotation_enabled = bool(
            self.var_weather_rotation.get()
        )
        season = self.var_weather_season.get()
        if season not in {"summer", "autumn", "winter", "spring", "realistic"}:
            season = "summer"   # default fallback

        self.config.weather_season = season  # type: ignore[assignment]
        self.config.weather_bad_weather_percentage = bw

        self.config.backup_saves_enabled = bool(self.var_backup_enabled.get())
        self.config.backup_saves_path = self.var_backup_path.get().strip()
        self.config.backup_saves_discord_enabled = bool(
            self.var_backup_discord.get()
        )
        self.config.backup_saves_discord_webhook = (
            self.var_backup_discord_webhook.get().strip()
        )

        self.config.execution_time = self.var_execution_time.get().strip()

        self.config.send_errors_to_discord = bool(
            self.var_errors_discord.get()
        )
        self.config.error_discord_webhook = (
            self.var_error_discord_webhook.get().strip()
        )

        self.config.next_action = action

        try:
            self.config.save()
            messagebox.showinfo(
                "Configuration saved",
                "Configuration saved successfully."
            )
            self.destroy()
        except Exception as exc:
            messagebox.showerror(
                "Save error",
                f"Could not save configuration:\n{exc}"
            )


# ------------------------------
# Entry point
# ------------------------------


def main() -> None:
    """
    Entry point for running the configuration GUI.
    """
    config_path = AppConfig.get_default_config_path()
    config = AppConfig.load(config_path)

    app = ConfigGUI(config)
    app.mainloop()


if __name__ == "__main__":
    main()
