"""Echorobotics lawn mower entity"""

import logging

from homeassistant.components.lawn_mower import (
    LawnMowerActivity,
    LawnMowerEntity,
    LawnMowerEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

import echoroboticsapi

from . import EchoRoboticsDataUpdateCoordinator
from .const import DOMAIN, RobotId
from .base import EchoRoboticsBaseEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up lawn mower platform."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [EchoRoboticsLawnMowerEntity(hass, coordinator, entry.data["robot_id"])]
    )


class EchoRoboticsLawnMowerEntity(EchoRoboticsBaseEntity, LawnMowerEntity):
    """Defining mower Entity."""

    _attr_name = None
    # _attr_translation_key = "lawn_mower"
    _attr_supported_features = (
        LawnMowerEntityFeature.DOCK | LawnMowerEntityFeature.START_MOWING
    )

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: EchoRoboticsDataUpdateCoordinator,
        robot_id: RobotId,
    ) -> None:
        """Initialize lawnmower entity."""
        super().__init__(robot_id, coordinator)
        self._attr_unique_id = f"{robot_id}-lawn-mower"

    @property
    def activity(self) -> LawnMowerActivity:
        coord: EchoRoboticsDataUpdateCoordinator = self.coordinator

        if self.pending_mode is not None:
            if self.pending_mode in ["work"]:
                return LawnMowerActivity.MOWING
            if self.pending_mode in ["chargeAndWork", "chargeAndStay"]:
                return LawnMowerActivity.DOCKED

        match self.status_info.status:
            case "Offline" | "Alarm" | "Warning" | "OffAfterAlarm":
                return LawnMowerActivity.ERROR
            case "Idle" | "WaitStation" | "Charge" | "Off":
                return LawnMowerActivity.DOCKED
            case (
                "GoUnloadStation"
                | "GoChargeStation"
                | "Work"
                | "LeaveStation"
                | "GoStation"
                | "Border"
                | "BorderCheck"
                | "BorderDiscovery"
            ):
                return LawnMowerActivity.MOWING
            case other:
                raise ValueError(f"unexpected status: {other}")

    async def async_start_mowing(self) -> None:
        """Resume schedule."""
        await self._set_mode("work")

    async def async_dock(self) -> None:
        """Parks the mower until next schedule."""
        await self._set_mode("chargeAndStay")
