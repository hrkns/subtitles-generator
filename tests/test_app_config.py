import json

import app_config as app_config_module


def test_load_app_config_returns_defaults_when_file_is_missing(tmp_path):
    config = app_config_module.load_app_config(
        config_path=str(tmp_path / "missing.json"),
        legacy_cleaning_settings_path=None,
    )

    assert config == app_config_module.APP_CONFIG_DEFAULTS


def test_load_app_config_merges_nested_strategy_settings(tmp_path):
    config_path = tmp_path / "app-config.json"
    config_path.write_text(
        json.dumps(
            {
                "last_input_path": "/tmp/input",
                "basic_strategy_settings": {
                    "high_pass_cutoff_hz": 200,
                },
            }
        ),
        encoding="utf-8",
    )

    config = app_config_module.load_app_config(
        config_path=str(config_path),
        legacy_cleaning_settings_path=None,
    )

    assert config["last_input_path"] == "/tmp/input"
    assert config["basic_strategy_settings"] == {
        "high_pass_cutoff_hz": 200,
        "low_pass_cutoff_hz": 7600,
        "apply_dynamic_range_compression": True,
        "apply_normalization": True,
    }


def test_load_app_config_migrates_legacy_cleaning_settings(tmp_path):
    legacy_path = tmp_path / "legacy-cleaning.json"
    legacy_path.write_text(
        json.dumps(
            {
                "default_cleaning_mode": "basic",
                "preselect_saved_cleaning_mode": True,
            }
        ),
        encoding="utf-8",
    )

    config = app_config_module.load_app_config(
        config_path=str(tmp_path / "missing.json"),
        legacy_cleaning_settings_path=str(legacy_path),
    )

    assert config["preferred_cleaning_mode"] == "basic"
    assert config["auto_apply_cleaning_mode"] is True


def test_update_app_config_preserves_existing_nested_values(tmp_path):
    config_path = tmp_path / "app-config.json"
    app_config_module.save_app_config(
        {
            "preferred_cleaning_mode": "basic",
            "basic_strategy_settings": {
                "high_pass_cutoff_hz": 180,
            },
        },
        config_path=str(config_path),
    )

    updated_config = app_config_module.update_app_config(
        {
            "last_output_path": "/tmp/output",
            "speechbrain_strategy_settings": {
                "validate_runtime_before_launch": False,
            },
        },
        config_path=str(config_path),
        legacy_cleaning_settings_path=None,
    )

    assert updated_config["preferred_cleaning_mode"] == "basic"
    assert updated_config["last_output_path"] == "/tmp/output"
    assert updated_config["basic_strategy_settings"]["high_pass_cutoff_hz"] == 180
    assert updated_config["speechbrain_strategy_settings"] == {
        "model_source": "speechbrain/metricgan-plus-voicebank",
        "validate_runtime_before_launch": False,
    }
