import json
import logging
import os

from config import CLEANING_SETTINGS_FILE


CLEANING_SETTINGS_DEFAULTS = {
    "default_cleaning_mode": None,
    "preselect_saved_cleaning_mode": False,
}


def load_cleaning_settings(settings_path=CLEANING_SETTINGS_FILE):
    settings = CLEANING_SETTINGS_DEFAULTS.copy()

    if not os.path.exists(settings_path):
        return settings

    try:
        with open(settings_path, "r", encoding="utf-8") as file:
            persisted_settings = json.load(file)
    except (OSError, json.JSONDecodeError) as e:
        logging.warning(f"Could not read cleaning settings from {settings_path}: {str(e)}")
        return settings

    if not isinstance(persisted_settings, dict):
        logging.warning(f"Ignoring invalid cleaning settings content from {settings_path}: expected an object.")
        return settings

    for key in settings:
        if key in persisted_settings:
            settings[key] = persisted_settings[key]

    return settings


def save_cleaning_settings(default_cleaning_mode, preselect_saved_cleaning_mode=True, settings_path=CLEANING_SETTINGS_FILE):
    settings = {
        "default_cleaning_mode": default_cleaning_mode,
        "preselect_saved_cleaning_mode": preselect_saved_cleaning_mode,
    }

    settings_dir = os.path.dirname(settings_path)
    if settings_dir:
        os.makedirs(settings_dir, exist_ok=True)

    with open(settings_path, "w", encoding="utf-8") as file:
        json.dump(settings, file, ensure_ascii=True, indent=2)

    return settings