import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.components.device_tracker import SOURCE_TYPE_GPS
from homeassistant.components.device_tracker.config_entry import TrackerEntity
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
import echoroboticsapi


from . import EchoRoboticsDataUpdateCoordinator
from .const import DOMAIN, RobotId

_LOGGER = logging.getLogger(__name__)


class EchoRoboticsBaseEntity(CoordinatorEntity[EchoRoboticsDataUpdateCoordinator]):
    _attr_has_entity_name = True

    def __init__(
        self, robot_id: RobotId, coordinator: EchoRoboticsDataUpdateCoordinator
    ):
        super().__init__(coordinator)
        self.logger = logging.getLogger(__name__)
        self.robot_id = robot_id

        self._attr_attribution = "echorobotics.com"
        self._attr_device_info = DeviceInfo(
            name=robot_id,
            identifiers={(DOMAIN, robot_id)},
            entry_type=None,
            manufacturer="Echorobotics",
        )
        self._read_coordinator_data()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._read_coordinator_data()
        self.async_write_ha_state()

    def _read_coordinator_data(self) -> None:
        self._attr_available = bool(self.status_info)

    @property
    def status_info(self) -> echoroboticsapi.StatusInfo:
        """Shorthand for use in this class and subclasses"""
        return self.coordinator.get_status_info(self.robot_id)
