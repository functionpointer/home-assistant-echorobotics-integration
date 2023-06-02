"""The echorobotics integration."""
from __future__ import annotations

import asyncio
import logging

import async_timeout
import echoroboticsapi
import time

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, UPDATE_INTERVAL, RobotId, GETCONFIG_UPDATE_INTERVAL

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BUTTON, Platform.DEVICE_TRACKER]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up echorobotics from a config entry."""

    hass.data.setdefault(DOMAIN, {})

    api = echoroboticsapi.Api(
        websession=async_create_clientsession(
            hass,
            cookies=echoroboticsapi.create_cookies(
                user_id=entry.data["user_id"], user_token=entry.data["user_token"]
            ),
        ),
        robot_ids=[entry.data["robot_id"]],
    )
    # missing: validate api connection

    coordinator = EchoRoboticsDataUpdateCoordinator(hass, api)
    hass.data[DOMAIN][entry.entry_id] = coordinator
    await coordinator.async_config_entry_first_refresh()

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


class EchoRoboticsDataUpdateCoordinator(DataUpdateCoordinator):
    """My custom coordinator."""

    def __init__(self, hass, api: echoroboticsapi.Api):
        """Initialize my coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
        )
        self.api = api
        self.getconfig_data: echoroboticsapi.GetConfig | None = None
        self.getconfig_tstamp: int = 0

    async def async_schedule_multiple_refreshes(self):
        async def refresh_later(sleep: float):
            await asyncio.sleep(sleep)
            _LOGGER.debug("fetching state after %ss", sleep)
            await self.async_request_refresh()

        for sleeptime in [2, 10, 20, 40, 60]:
            asyncio.create_task(refresh_later(sleeptime))

    def get_status_info(self, robot_id: RobotId) -> echoroboticsapi.StatusInfo | None:
        if self.data:
            laststatuses: echoroboticsapi.models.LastStatuses = self.data
            for si in laststatuses.statuses_info:
                if si.robot == robot_id:
                    return si
            self.logger.warning(
                "robot_id %s not found in %s", self.robot_id, laststatuses
            )
        return None

    async def _fetch_getconfig(self):
        """Fetch getconfig from robot, but not on every update"""
        if self.getconfig_data is None or time.time() > self.getconfig_tstamp+GETCONFIG_UPDATE_INTERVAL:
            newdata: echoroboticsapi.GetConfig | None = None
            async with async_timeout.timeout(10):
                await self.api.get_config(reload=True)

            async with async_timeout.timeout(30):
                while newdata is None or not newdata.config_validated:
                    await asyncio.sleep(2)
                    newdata = await self.api.get_config(reload=False)

            if newdata is None or not newdata.config_validated:
                self.getconfig_data = None
            else:
                self.getconfig_data = newdata

    async def _async_update_data(self) -> echoroboticsapi.LastStatuses | None:
        """Fetch data from API endpoint.

        This is the place to pre-process the data to lookup tables
        so entities can quickly look up their data.
        """
        # Note: asyncio.TimeoutError and aiohttp.ClientError are already
        # handled by the data update coordinator.

        getconfig_task = asyncio.create_task(self._fetch_getconfig())
        async with async_timeout.timeout(10):
            status = await self.api.last_statuses()
            if status is None:
                _LOGGER.info("received empty update")
            else:
                _LOGGER.debug("received state %s", status)
        await getconfig_task
        return status
