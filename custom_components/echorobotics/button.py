"""Platform for button integration."""
from __future__ import annotations

import logging

import echoroboticsapi
from echoroboticsapi.models import Mode
import typing

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.components.button import ButtonDeviceClass, ButtonEntity

from . import EchoRoboticsDataUpdateCoordinator
from .base import EchoRoboticsBaseEntity
from .const import DOMAIN, RobotId


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up button entries."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            EchoRoboticsSetModeButton(
                mode=m, coordinator=coordinator, robot_id=entry.data["robot_id"]
            )
            for m in typing.get_args(echoroboticsapi.models.Mode)
        ]
    )


class EchoRoboticsSetModeButton(EchoRoboticsBaseEntity, ButtonEntity):
    """Button"""

    iconmap = {
        "work": "mdi:mower-on",
        "chargeAndStay": "mdi:sleep",
        "chargeAndWork": "mdi:mower-on",
    }

    def __init__(
        self,
        mode: Mode,
        coordinator: EchoRoboticsDataUpdateCoordinator,
        robot_id: RobotId,
    ) -> None:
        """Initialize the Button."""
        super().__init__(robot_id, coordinator)
        self.logger = logging.getLogger(__name__)

        self.mode = mode
        self._attr_name = f"{mode}"
        self._attr_unique_id = f"{robot_id}-{mode}"
        self._attr_icon = self.iconmap.get(mode, None)

    @property
    def _api(self) -> echoroboticsapi.Api:
        return self.coordinator.api

    async def async_press(self) -> None:
        """Press the button."""
        returncode = await self._api.set_mode(self.mode)
        if returncode != 200:
            raise ValueError(
                f"couldn't set mode {self.mode}, api returned {returncode}"
            )
        await self.coordinator.async_schedule_multiple_refreshes()