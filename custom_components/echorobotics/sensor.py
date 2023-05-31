"""Platform for sensor integration."""
from __future__ import annotations

import logging

import echoroboticsapi
from echoroboticsapi.models import StatusInfo

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import (
    STATE_CLASS_MEASUREMENT,
    PERCENTAGE,
)

from . import EchoRoboticsDataUpdateCoordinator
from .const import DOMAIN, RobotId


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up a sensor entries."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            EchoRoboticsStateSensor(
                robot_id=entry.data["robot_id"], coordinator=coordinator
            ),
            EchoRoboticsBatterySensor(
                robot_id=entry.data["robot_id"],
                coordinator=coordinator,
            ),
        ]
    )


class EchoRoboticsSensor(
    CoordinatorEntity[EchoRoboticsDataUpdateCoordinator], SensorEntity
):
    """Sensor reporting the current state of the robot"""

    _attr_has_entity_name = True

    def __init__(
        self,
        robot_id: RobotId,
        coordinator: EchoRoboticsDataUpdateCoordinator,
    ) -> None:
        """Initialize the Sensor."""
        super().__init__(coordinator)
        self.logger = logging.getLogger(__name__)
        self.coordinator = coordinator
        self.robot_id = robot_id
        self._attr_attribution = "echorobotics.com"
        self._attr_device_class = None
        self._attr_native_unit_of_measurement = None
        self._attr_state_class = None
        self._attr_device_info = DeviceInfo(
            name=robot_id,
            identifiers={(DOMAIN, robot_id)},
            entry_type=None,
        )
        # read data from coordinator, which should have data by now
        self._read_coordinator_data()

    def _get_status_info(self) -> StatusInfo | None:
        if self.coordinator.data:
            laststatuses: echoroboticsapi.models.LastStatuses = self.coordinator.data
            for si in laststatuses.statuses_info:
                if si.robot == self.robot_id:
                    return si
            self.logger.warning(
                "robot_id %s not found in %s", self.robot_id, laststatuses
            )
        return None

    def _read_coordinator_data(self) -> None:
        pass

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._read_coordinator_data()
        self.async_write_ha_state()


class EchoRoboticsStateSensor(EchoRoboticsSensor):
    def __init__(
        self, robot_id: RobotId, coordinator: EchoRoboticsDataUpdateCoordinator
    ):
        super().__init__(robot_id, coordinator)
        self._attr_unique_id = f"{robot_id}-state"
        self._attr_icon = "mdi:robot-mower"
        self._attr_state_class = STATE_CLASS_MEASUREMENT
        self._attr_translation_key = "state_sensor"

    def _read_coordinator_data(self) -> None:
        super()._read_coordinator_data()
        si = self._get_status_info()
        if si is None:
            self._attr_native_value = None
        else:
            self._attr_native_value = si.status


class EchoRoboticsBatterySensor(EchoRoboticsSensor):
    def __init__(
        self, robot_id: RobotId, coordinator: EchoRoboticsDataUpdateCoordinator
    ):
        super().__init__(robot_id, coordinator)
        self._attr_unique_id = f"{robot_id}-state"
        self._attr_device_class = SensorDeviceClass.BATTERY
        self._attr_native_unit_of_measurement = PERCENTAGE
        self._attr_state_class = STATE_CLASS_MEASUREMENT
        self._attr_translation_key = "battery_sensor"
        self._attr_suggested_display_precision = 1

    def _read_coordinator_data(self) -> None:
        super()._read_coordinator_data()
        si = self._get_status_info()
        if si is None:
            self._attr_native_value = None
        else:
            self._attr_native_value = si.estimated_battery_level
