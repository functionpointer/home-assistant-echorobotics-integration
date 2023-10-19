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
from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import (
    PERCENTAGE,
)

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
            EchoRoboticsStateSensor(
                robot_id=entry.data["robot_id"], coordinator=coordinator
            ),
            EchoRoboticsBatterySensor(
                robot_id=entry.data["robot_id"],
                coordinator=coordinator,
            ),
        ]
    )


class EchoRoboticsSensor(EchoRoboticsBaseEntity, SensorEntity):
    """Sensor reporting the current state of the robot"""

    def __init__(
        self,
        robot_id: RobotId,
        coordinator: EchoRoboticsDataUpdateCoordinator,
    ) -> None:
        """Initialize the Sensor."""
        super().__init__(robot_id, coordinator)
        self.logger = logging.getLogger(__name__)

        self._attr_device_class = None
        self._attr_native_unit_of_measurement = None
        self._attr_state_class = None


class EchoRoboticsStateSensor(EchoRoboticsSensor):
    NORMALIZE_CASE = {
        "Offline": "offline",
        "Alarm": "alarm",
        "Idle": "idle",
        "WaitStation": "wait_station",
        "Charge": "charge",
        "GoUnloadStation": "go_unload_station",
        "GoChargeStation": "go_charge_station",
        "Work": "work",
        "LeaveStation": "leave_station",
        "Off": "off",
        "GoStation": "go_station",
        "Unknown": "unknown",
        "Warning": "warning",
        "Border": "border",
        "BorderCheck": "border_check",
        "BorderDiscovery": "border_discovery",
        "OffAfterAlarm": "off_after_alarm",
    }

    def __init__(
        self, robot_id: RobotId, coordinator: EchoRoboticsDataUpdateCoordinator
    ):
        super().__init__(robot_id, coordinator)
        self._attr_unique_id = f"{robot_id}-state"
        self._attr_icon = "mdi:robot-mower"
        self._attr_state_class = None
        self._attr_translation_key = "state_sensor"
        self._attr_device_class = SensorDeviceClass.ENUM

    @property
    def options(self) -> list[str] | None:
        return list(self.NORMALIZE_CASE.values())

    def _read_coordinator_data(self) -> None:
        super()._read_coordinator_data()
        si = self.status_info
        if si is None:
            self._attr_native_value = None
        else:
            self._attr_native_value = self.NORMALIZE_CASE.get(si.status, si.status)


class EchoRoboticsBatterySensor(EchoRoboticsSensor):
    def __init__(
        self, robot_id: RobotId, coordinator: EchoRoboticsDataUpdateCoordinator
    ):
        super().__init__(robot_id, coordinator)
        self._attr_unique_id = f"{robot_id}-battery"
        self._attr_name = "Battery"
        self._attr_device_class = SensorDeviceClass.BATTERY
        self._attr_native_unit_of_measurement = PERCENTAGE
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_translation_key = "battery_sensor"
        self._attr_suggested_display_precision = 1

    def _read_coordinator_data(self) -> None:
        super()._read_coordinator_data()
        si = self.status_info
        if si is None:
            self._attr_native_value = None
        else:
            self._attr_native_value = round(si.estimated_battery_level, ndigits=1)
