"""Platform for switch integration."""
from __future__ import annotations

import logging

import echoroboticsapi
from echoroboticsapi.models import StatusInfo

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.components.switch import SwitchDeviceClass


from . import EchoRoboticsDataUpdateCoordinator
from .const import DOMAIN, RobotId
from .base import EchoRoboticsBaseEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up sensor entries."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            EchoRoboticsMainSwitch(
                robot_id=entry.data["robot_id"], coordinator=coordinator
            ),
        ]
    )


class EchoRoboticsMainSwitch(EchoRoboticsBaseEntity, SwitchEntity):
    """Sensor reporting the current state of the robot"""

    def __init__(
        self,
        robot_id: RobotId,
        coordinator: EchoRoboticsDataUpdateCoordinator,
    ) -> None:
        """Initialize the Sensor."""
        super().__init__(robot_id, coordinator)
        self.logger = logging.getLogger(__name__)

        self._attr_unique_id = f"{robot_id}-main-switch"
        self._attr_translation_key = "main_switch"
        self._attr_icon = "mdi:robot-mower"
        self._attr_device_class = SwitchDeviceClass.SWITCH

    @property
    def is_on(self):
        coord: EchoRoboticsDataUpdateCoordinator = self.coordinator

        return coord.smartmode.get_robot_mode() in ["chargeAndWork", "work"]

    @property
    def extra_state_attributes(self):
        return {
            "guessed_mode": self.coordinator.smartmode.get_robot_mode(),
        }

    async def async_turn_on(self, **kwargs):
        coord: EchoRoboticsDataUpdateCoordinator = self.coordinator
        await coord.async_schedule_multiple_refreshes()
        await coord.api.set_mode("work", use_current=True)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs):
        coord: EchoRoboticsDataUpdateCoordinator = self.coordinator
        await coord.async_schedule_multiple_refreshes()
        await coord.api.set_mode("chargeAndStay", use_current=True)
        self.async_write_ha_state()
