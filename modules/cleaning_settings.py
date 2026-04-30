from config import APP_CONFIG_FILE, CLEANING_SETTINGS_FILE
from app_config import APP_CONFIG_DEFAULTS, load_app_config, update_app_config


CLEANING_SETTINGS_DEFAULTS = {
    "default_cleaning_mode": APP_CONFIG_DEFAULTS["preferred_cleaning_mode"],
    "preselect_saved_cleaning_mode": APP_CONFIG_DEFAULTS["auto_apply_cleaning_mode"],
    "basic_strategy_settings": APP_CONFIG_DEFAULTS["basic_strategy_settings"],
    "speechbrain_strategy_settings": APP_CONFIG_DEFAULTS["speechbrain_strategy_settings"],
}


def load_cleaning_settings(settings_path=APP_CONFIG_FILE):
    legacy_path = CLEANING_SETTINGS_FILE if settings_path == APP_CONFIG_FILE else None
    app_config = load_app_config(settings_path, legacy_cleaning_settings_path=legacy_path)

    return {
        "default_cleaning_mode": app_config["preferred_cleaning_mode"],
        "preselect_saved_cleaning_mode": app_config["auto_apply_cleaning_mode"],
        "basic_strategy_settings": app_config["basic_strategy_settings"],
        "speechbrain_strategy_settings": app_config["speechbrain_strategy_settings"],
    }


def save_cleaning_settings(
    default_cleaning_mode,
    preselect_saved_cleaning_mode=True,
    settings_path=APP_CONFIG_FILE,
    basic_strategy_settings=None,
    speechbrain_strategy_settings=None,
):
    app_config_updates = {
        "preferred_cleaning_mode": default_cleaning_mode,
        "auto_apply_cleaning_mode": preselect_saved_cleaning_mode,
    }

    if basic_strategy_settings is not None:
        app_config_updates["basic_strategy_settings"] = basic_strategy_settings

    if speechbrain_strategy_settings is not None:
        app_config_updates["speechbrain_strategy_settings"] = speechbrain_strategy_settings

    updated_config = update_app_config(
        app_config_updates,
        config_path=settings_path,
        legacy_cleaning_settings_path=None,
    )

    return {
        "default_cleaning_mode": updated_config["preferred_cleaning_mode"],
        "preselect_saved_cleaning_mode": updated_config["auto_apply_cleaning_mode"],
        "basic_strategy_settings": updated_config["basic_strategy_settings"],
        "speechbrain_strategy_settings": updated_config["speechbrain_strategy_settings"],
    }