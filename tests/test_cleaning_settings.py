import json
import logging

import cleaning_settings as cleaning_settings_module


def test_load_cleaning_settings_returns_defaults_when_file_is_missing(tmp_path):
    settings = cleaning_settings_module.load_cleaning_settings(str(tmp_path / "missing.json"))

    assert settings == cleaning_settings_module.CLEANING_SETTINGS_DEFAULTS


def test_load_cleaning_settings_returns_defaults_when_file_is_invalid(tmp_path, caplog):
    settings_path = tmp_path / "broken.json"
    settings_path.write_text("{not-json", encoding="utf-8")

    with caplog.at_level(logging.WARNING):
        settings = cleaning_settings_module.load_cleaning_settings(str(settings_path))

    assert settings == cleaning_settings_module.CLEANING_SETTINGS_DEFAULTS
    assert "Could not read cleaning settings" in caplog.text


def test_save_cleaning_settings_writes_expected_fields(tmp_path):
    settings_path = tmp_path / "cleaning-settings.json"

    settings = cleaning_settings_module.save_cleaning_settings(
        "basic",
        preselect_saved_cleaning_mode=True,
        settings_path=str(settings_path),
    )

    assert settings == {
        "default_cleaning_mode": "basic",
        "preselect_saved_cleaning_mode": True,
    }
    assert json.loads(settings_path.read_text(encoding="utf-8")) == settings