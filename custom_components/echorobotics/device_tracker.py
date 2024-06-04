import logging


from homeassistant.config_entries import ConfigEntry
from homeassistant.components.device_tracker import SourceType
from homeassistant.components.device_tracker.config_entry import TrackerEntity
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.core import HomeAssistant, callback
import echoroboticsapi

from . import EchoRoboticsDataUpdateCoordinator
from .const import DOMAIN, RobotId
from .base import EchoRoboticsBaseEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
):
    """Set up the device tracker."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            EchoRoboticsLocation(
                hass, coordinator=coordinator, robot_id=entry.data["robot_id"]
            )
        ]
    )


class EchoRoboticsLocation(EchoRoboticsBaseEntity, TrackerEntity):
    """Representation of an Echorobotics robot location device tracker."""

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: EchoRoboticsDataUpdateCoordinator,
        robot_id: RobotId,
    ) -> None:
        """Initialize location entity."""
        super().__init__(robot_id, coordinator)
        self._attr_unique_id = f"{robot_id}-location"
        self._attr_translation_key = "location"

    @property
    def status_info(self) -> echoroboticsapi.StatusInfo | None:
        """Shorthand for internal use in this class"""
        return self.coordinator.get_status_info(self.robot_id)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()

    @property
    def longitude(self):
        if self.status_info:
            return self.status_info.position.longitude
        else:
            return None

    @property
    def latitude(self):
        if self.status_info:
            return self.status_info.position.latitude
        else:
            return None

    @property
    def source_type(self):
        """Return device tracker source type."""
        return SourceType.GPS

    @property
    def force_update(self):
        """Disable forced updated since we are polling via the coordinator updates."""
        return False
