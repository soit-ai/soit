"""test_plugin_risk_classification

Risk is derived from what a plugin declares it may reach, so these fix the
mapping from declared permissions to a level a reviewer can act on.
"""

from app.modules.plugin.application.risk import classify_plugin_risk


def test_a_plugin_that_declares_nothing_is_low_risk():
    """Low because it can reach nothing, not because anyone vouched for it."""
    level, reasons = classify_plugin_risk({"permissions": {}})

    assert level == "low"
    assert reasons == []


def test_reading_secrets_is_high_risk():
    level, reasons = classify_plugin_risk(
        {"permissions": {"secrets": ["sec_stripe", "sec_pagerduty"]}}
    )

    assert level == "high"
    assert reasons == ["secrets: 2"]


def test_writing_to_storage_is_high_risk():
    level, reasons = classify_plugin_risk(
        {"permissions": {"storage": {"write": ["reports/"]}}}
    )

    assert level == "high"
    assert "storage write: 1" in reasons


def test_reaching_any_host_is_high_risk_but_named_hosts_are_not():
    """An allowlist is a boundary; a wildcard is the absence of one."""
    wildcard, wildcard_reasons = classify_plugin_risk(
        {"permissions": {"network": ["*"]}}
    )
    named, named_reasons = classify_plugin_risk(
        {"permissions": {"network": ["api.pagerduty.com"]}}
    )

    assert wildcard == "high"
    assert "network: any host" in wildcard_reasons
    assert named == "medium"
    assert "network: 1" in named_reasons


def test_reading_storage_alone_is_medium_risk():
    level, _ = classify_plugin_risk({"permissions": {"storage": {"read": ["docs/"]}}})

    assert level == "medium"


def test_the_highest_declared_scope_sets_the_level():
    level, reasons = classify_plugin_risk(
        {
            "permissions": {
                "network": ["api.example.com"],
                "secrets": ["sec_1"],
            }
        }
    )

    assert level == "high"
    # Both scopes are reported, so a reviewer sees the whole surface.
    assert "secrets: 1" in reasons
    assert "network: 1" in reasons


def test_the_manifest_answers_when_the_spec_declares_no_permissions():
    level, _ = classify_plugin_risk({}, {"permissions": {"secrets": ["sec_1"]}})

    assert level == "high"
