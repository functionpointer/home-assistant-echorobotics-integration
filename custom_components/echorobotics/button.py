"""Platform for button integration."""

from __future__ import annotations

import logging
import re

import echoroboticsapi
from echoroboticsapi.models import Mode
import typing

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
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
        + [
            EchoRoboticsForceDataUpdateButton(
                coordinator=coordinator, robot_id=entry.data["robot_id"]
            ),
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

        self.raw_mode = mode
        # regex from https://stackoverflow.com/questions/1175208/elegant-python-function-to-convert-camelcase-to-snake-case
        self.nice_mode = re.sub(r"(?<!^)(?=[A-Z])", "_", self.raw_mode).lower()
        self._attr_translation_key = self.nice_mode
        self._attr_unique_id = f"{robot_id}-{mode}"
        self._attr_icon = self.iconmap.get(mode, None)

    async def async_press(self) -> None:
        """Press the button."""
        await self._set_mode(self.raw_mode)


class EchoRoboticsForceDataUpdateButton(EchoRoboticsBaseEntity, ButtonEntity):
    def __init__(
        self, coordinator: EchoRoboticsDataUpdateCoordinator, robot_id: RobotId
    ):
        super().__init__(robot_id, coordinator)
        self.logger = logging.getLogger(__name__)

        self._attr_translation_key = "force_data_update"
        self._attr_unique_id = f"{robot_id}-force-data-update"
        self._attr_icon = "mdi:database-sync"
        self._attr_entity_category = EntityCategory.CONFIG

    async def async_press(self) -> None:
        await self.coordinator.async_request_refresh()

    @property
    def available(self) -> bool:
        return True
