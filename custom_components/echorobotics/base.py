import asyncio
import logging

from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.core import callback
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

        self._attr_device_info = DeviceInfo(
            name=robot_id,
            configuration_url=f"https://myrobot.echorobotics.com/fleet-dashboard/robot/{robot_id}",
            sw_version=(
                coordinator.getconfig_data.data.brain_version
                if coordinator.getconfig_data
                else None
            ),
            identifiers={(DOMAIN, robot_id)},
            entry_type=None,
            manufacturer="Echorobotics",
        )
        self._read_coordinator_data()

    @property
    def attribution(self):
        return "echorobotics.com"

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

    @property
    def _api(self) -> echoroboticsapi.Api:
        return self.coordinator.api

    @property
    def pending_mode(self) -> echoroboticsapi.Mode | None:
        return self.coordinator.pending_mode

    async def _set_mode(self, mode: echoroboticsapi.Mode):
        """Set the robot's mode

        Basically just calls self.coordinator.api.set_mode
        However, set_mode has long latency.
        Specifically, the api call returns quickly,
        but get_robot_mode() still returns the old mode for many seconds.
        It could also completely fail :/

        Both Homeassistant nor users don't like feedback taking that long,
        so this method improves it like this:
        The new mode is stored in self.coordinator.pending_mode.

        Entities immediately report the new state using that,
        and report in attributes that it is a pending change.
        When get_robot_mode() finally reports the new state,
        pending_mode is set back to None again.

        If set_mode fails, pending_mode is also set back to None,
        causing entities to report the old state again.
        """
        if self.pending_mode is not None:
            self.logger.warning(
                f"skip mode_set to {mode}: pending_mode != None ({self.coordinator.pending_mode})"
            )
            return

        coord: EchoRoboticsDataUpdateCoordinator = self.coordinator
        await coord.async_schedule_multiple_refreshes()
        self.coordinator.pending_mode = mode
        try:
            job = asyncio.create_task(coord.api.set_mode(mode, use_current=True))
            self.async_write_ha_state()  # cause entities to report pending_mode
            async with asyncio.timeout(40):
                await job  # perform set_mode call
                # this returns as soon as api.current() reports it has worked,
                # which will also cause get_robot_mode() to report the new mode
        finally:
            self.coordinator.pending_mode = None
            self.async_write_ha_state()  # cause entities to report the new actual mode
