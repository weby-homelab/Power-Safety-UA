from unittest.mock import patch
from app.config_runtime import migrate_legacy_icons, get_config, invalidate_config_cache


def test_migrate_exact_legacy_default_icons():
    cfg = {
        "advanced": {
            "text": {
                "event_up": "🟢 <b>{time} Світло з'явилося</b>",
                "event_down": "🔴 <b>{time} Світло зникло</b>",
            }
        }
    }
    modified = migrate_legacy_icons(cfg)
    assert modified is True
    assert cfg["advanced"]["text"]["event_up"] == "💡 <b>{time} Світло з'явилося</b>"
    assert cfg["advanced"]["text"]["event_down"] == "⚡️ <b>{time} Світло зникло</b>"


def test_custom_user_text_preserved_intact():
    cfg_custom = {
        "advanced": {
            "text": {
                "event_up": "🟢 Світло нарешті дали! ({time})",
                "event_down": "🔴 Увага: знеструмлення ({time})",
            }
        }
    }
    modified = migrate_legacy_icons(cfg_custom)
    assert modified is False
    assert (
        cfg_custom["advanced"]["text"]["event_up"] == "🟢 Світло нарешті дали! ({time})"
    )
    assert (
        cfg_custom["advanced"]["text"]["event_down"]
        == "🔴 Увага: знеструмлення ({time})"
    )


def test_partial_custom_migration():
    # One default, one custom
    cfg = {
        "advanced": {
            "text": {
                "event_up": "🟢 <b>{time} Світло з'явилося</b>",
                "event_down": "🔴 Custom outage text",
            }
        }
    }
    modified = migrate_legacy_icons(cfg)
    assert modified is True
    assert cfg["advanced"]["text"]["event_up"] == "💡 <b>{time} Світло з'явилося</b>"
    assert cfg["advanced"]["text"]["event_down"] == "🔴 Custom outage text"


def test_get_config_triggers_migration_and_save():
    invalidate_config_cache()
    legacy_cfg = {
        "advanced": {
            "text": {
                "event_up": "🟢 <b>{time} Світло з'явилося</b>",
                "event_down": "🔴 <b>{time} Світло зникло</b>",
            }
        }
    }
    saved_payloads = []

    with (
        patch(
            "app.config_runtime.StorageUtils.load_json_sync", return_value=legacy_cfg
        ),
        patch(
            "app.config_runtime.StorageUtils.save_json_sync",
            side_effect=lambda path, data: saved_payloads.append(data),
        ),
    ):
        loaded = get_config()
        assert (
            loaded["advanced"]["text"]["event_up"]
            == "💡 <b>{time} Світло з'явилося</b>"
        )
        assert len(saved_payloads) == 1
        assert (
            saved_payloads[0]["advanced"]["text"]["event_up"]
            == "💡 <b>{time} Світло з'явилося</b>"
        )
        assert (
            saved_payloads[0]["advanced"]["text"]["event_down"]
            == "⚡️ <b>{time} Світло зникло</b>"
        )
    invalidate_config_cache()
