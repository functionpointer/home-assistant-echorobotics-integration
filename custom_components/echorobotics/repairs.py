"""Repairs for echorobotics integration."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir

from .const import DOMAIN

PAID_SUBSCRIPTION_ISSUE_SUFFIX = "_paid_subscription_required"


def _issue_id(entry_id: str) -> str:
    """Build a stable issue id per config entry."""
    return f"{entry_id}{PAID_SUBSCRIPTION_ISSUE_SUFFIX}"


def async_create_paid_subscription_issue(
    hass: HomeAssistant, entry_id: str
) -> None:
    """Create a repair issue for a missing paid subscription."""
    ir.async_create_issue(
        hass,
        DOMAIN,
        _issue_id(entry_id),
        is_fixable=False,
        severity=ir.IssueSeverity.ERROR,
        translation_key="paid_subscription_required",
    )


def async_delete_paid_subscription_issue(
    hass: HomeAssistant, entry_id: str
) -> None:
    """Delete the repair issue for a missing paid subscription, if present."""
    ir.async_delete_issue(hass, DOMAIN, _issue_id(entry_id))
