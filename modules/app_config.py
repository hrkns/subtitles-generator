import json
import logging
import os
from copy import deepcopy

from config import APP_CONFIG_FILE, CLEANING_SETTINGS_FILE


APP_CONFIG_DEFAULTS = {
    "last_input_path": "",
    "last_output_path": "",
    "preferred_cleaning_mode": None,
    "auto_apply_cleaning_mode": False,
    "basic_strategy_settings": {
        "high_pass_cutoff_hz": 120,
        "low_pass_cutoff_hz": 7600,
        "apply_dynamic_range_compression": True,
        "apply_normalization": True,
    },
    "speechbrain_strategy_settings": {
        "model_source": "speechbrain/metricgan-plus-voicebank",
        "validate_runtime_before_launch": True,
    },
}


def _merge_with_defaults(defaults, persisted):
    merged = {}
    persisted = persisted if isinstance(persisted, dict) else {}

    for key, default_value in defaults.items():
        if isinstance(default_value, dict):
            merged[key] = _merge_with_defaults(default_value, persisted.get(key, {}))
        else:
            merged[key] = deepcopy(persisted.get(key, default_value))

    return merged


def _deep_merge(base, updates):
    merged = deepcopy(base)

    for key, value in updates.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = deepcopy(value)

    return merged


def _load_json_dict(file_path, description):
    if not os.path.exists(file_path):
        return None

    try:
        with open(file_path, "r", encoding="utf-8") as file:
            persisted_data = json.load(file)
    except (OSError, json.JSONDecodeError) as e:
        logging.warning(f"Could not read {description} from {file_path}: {str(e)}")
        return None

    if not isinstance(persisted_data, dict):
        logging.warning(f"Ignoring invalid {description} content from {file_path}: expected an object.")
        return None

    return persisted_data


def _load_legacy_cleaning_settings(file_path):
    legacy_settings = _load_json_dict(file_path, "legacy cleaning settings")
    if legacy_settings is None:
        return None

    return {
        "preferred_cleaning_mode": legacy_settings.get("default_cleaning_mode"),
        "auto_apply_cleaning_mode": legacy_settings.get("preselect_saved_cleaning_mode", False),
        "basic_strategy_settings": legacy_settings.get("basic_strategy_settings", {}),
        "speechbrain_strategy_settings": legacy_settings.get("speechbrain_strategy_settings", {}),
    }


def load_app_config(config_path=APP_CONFIG_FILE, legacy_cleaning_settings_path=CLEANING_SETTINGS_FILE):
    persisted_config = _load_json_dict(config_path, "app config")

    if persisted_config is None and legacy_cleaning_settings_path:
        persisted_config = _load_legacy_cleaning_settings(legacy_cleaning_settings_path)

    return _merge_with_defaults(APP_CONFIG_DEFAULTS, persisted_config or {})


def save_app_config(app_config, config_path=APP_CONFIG_FILE):
    merged_config = _merge_with_defaults(APP_CONFIG_DEFAULTS, app_config or {})

    config_dir = os.path.dirname(config_path)
    if config_dir:
        os.makedirs(config_dir, exist_ok=True)

    with open(config_path, "w", encoding="utf-8") as file:
        json.dump(merged_config, file, ensure_ascii=True, indent=2)

    return merged_config


def update_app_config(config_updates, config_path=APP_CONFIG_FILE, legacy_cleaning_settings_path=CLEANING_SETTINGS_FILE):
    current_config = load_app_config(
        config_path=config_path,
        legacy_cleaning_settings_path=legacy_cleaning_settings_path,
    )
    merged_config = _deep_merge(current_config, config_updates or {})
    return save_app_config(merged_config, config_path=config_path)