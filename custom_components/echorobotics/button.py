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
from .const import DOMAIN, RobotId


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up button entries."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            EchoRoboticsSetModeButton(mode=m, coordinator=coordinator, robot_id=entry.data["robot_id"])
            for m in typing.get_args(echoroboticsapi.models.Mode)
        ]
    )

class EchoRoboticsSetModeButton(ButtonEntity):
    """Button"""

    _attr_has_entity_name = True
    iconmap = {"work": "mdi:mower-on", "chargeAndStay": "mdi:sleep", "chargeAndWork": "mdi:mower-on"}

    def __init__(
        self,
        mode: Mode,
        coordinator: EchoRoboticsDataUpdateCoordinator,
        robot_id: RobotId,
    ) -> None:
        """Initialize the Button."""
        super().__init__()
        self.mode = mode
        self.coordinator = coordinator
        self.logger = logging.getLogger(__name__)
        self.robot_id = robot_id
        self._attr_attribution = "echorobotics.com"
        self._attr_name = f"{mode}"
        self._attr_unique_id = f"{robot_id}-{mode}"
        self._attr_icon = self.iconmap.get(mode, None)
        self._attr_device_info = DeviceInfo(
            name=robot_id,
            identifiers={(DOMAIN, robot_id)},
            entry_type=None,
        )

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
