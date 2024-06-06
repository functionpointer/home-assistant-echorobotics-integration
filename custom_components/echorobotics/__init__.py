"""The echorobotics integration."""

from __future__ import annotations

import asyncio
import logging

import aiohttp
import async_timeout
import echoroboticsapi
import time

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.helpers.typing import UNDEFINED
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.helpers import device_registry, entity_registry

from .const import (
    DOMAIN,
    UPDATE_INTERVAL,
    RobotId,
    GETCONFIG_UPDATE_INTERVAL,
    HISTORY_UPDATE_INTERVAL,
    UNAVAILABLE_TIMEOUT,
    UNAVAILABLE_FETCHES,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.BUTTON,
    Platform.DEVICE_TRACKER,
    Platform.SWITCH,
    Platform.LAWN_MOWER,
]


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
    smartmode = echoroboticsapi.SmartMode(entry.data["robot_id"])
    api.register_smart_mode(smartmode)
    smartfetch = echoroboticsapi.SmartFetch(
        api, fetch_history_wait_time=HISTORY_UPDATE_INTERVAL
    )
    # missing: validate api connection

    coordinator = EchoRoboticsDataUpdateCoordinator(hass, api, smartmode, smartfetch)
    hass.data[DOMAIN][entry.entry_id] = coordinator
    await coordinator.async_config_entry_first_refresh()

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Migrate old entry."""
    _LOGGER.debug("Migrating from version %s", config_entry.version)

    if config_entry.version > 2:
        # no downgrades from future versions
        return False

    if config_entry.version == 1:
        robot_id = config_entry.data["robot_id"]
        # -main-switch was renamed to -auto-mow-switch
        old_unique_id = f"{robot_id}-main-switch"
        new_unique_id = f"{robot_id}-auto-mow-switch"
        ent_reg = entity_registry.async_get(hass)
        auto_mow_switch_entity_id = ent_reg.async_get_entity_id(
            Platform.SWITCH, DOMAIN, old_unique_id
        )
        new_entity_id = (
            auto_mow_switch_entity_id.replace("_none", "_auto_mow")
            if auto_mow_switch_entity_id.lower().endswith("_none")
            else UNDEFINED
        )
        _LOGGER.info(
            "Migrating unique_id from [%s] to [%s] and new entity_id [%s]",
            old_unique_id,
            new_unique_id,
            new_entity_id,
        )
        ent_reg.async_update_entity(
            auto_mow_switch_entity_id,
            new_unique_id=new_unique_id,
            new_entity_id=new_entity_id,
        )

        hass.config_entries.async_update_entry(config_entry, version=2)
        _LOGGER.info("Migration to version %s successful", config_entry.version)
        return True

    return False


class EchoRoboticsDataUpdateCoordinator(DataUpdateCoordinator):
    """My custom coordinator."""

    def __init__(
        self,
        hass,
        api: echoroboticsapi.Api,
        smartmode: echoroboticsapi.SmartMode,
        smartfetch: echoroboticsapi.SmartFetch,
    ):
        """Initialize my coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
        )
        self.api = api
        self.smartmode = smartmode
        self.smartfetch = smartfetch

        self.history_tstamp: int = 0

        self.getconfig_data: echoroboticsapi.GetConfig | None = None
        self.getconfig_tstamp: int = 0
        self.laststatuses_data: echoroboticsapi.LastStatuses | None = None
        self.laststatuses_tstamp: int = 0
        self.fetch_fail_count: int = 0

        self.pending_mode: echoroboticsapi.Mode | None = None
        """pending_mode used for improved handling of echorobotics long response time
        
        when an entity (button, switch or lawn_mower) calls for a mode change (_set_mode),
        more info see EchoRoboticsBaseEntity._set_mode
        """

    async def async_schedule_multiple_refreshes(self):
        async def refresh_later(sleep: float):
            await asyncio.sleep(sleep)
            _LOGGER.debug("fetching state after %ss", sleep)
            await self.async_request_refresh()

        for sleeptime in [2, 10, 20, 40, 60]:
            task = asyncio.create_task(refresh_later(sleeptime))

    def get_status_info(self, robot_id: RobotId) -> echoroboticsapi.StatusInfo | None:
        too_old: bool = (
            time.monotonic()
            > self.laststatuses_tstamp + UNAVAILABLE_TIMEOUT.total_seconds()
        )
        too_many_fetches_failed: bool = self.fetch_fail_count >= UNAVAILABLE_FETCHES
        should_be_unavailable = too_many_fetches_failed and too_old

        if self.laststatuses_data is not None and (not should_be_unavailable):
            laststatuses: echoroboticsapi.models.LastStatuses = self.laststatuses_data
            for si in laststatuses.statuses_info:
                if si.robot == robot_id:
                    return si
            self.logger.warning("robot_id %s not found in %s", robot_id, laststatuses)
        return None

    async def _fetch_getconfig(self):
        """Fetch getconfig from robot, but not on every update"""
        time_to_fetch = (
            time.monotonic()
            > self.getconfig_tstamp + GETCONFIG_UPDATE_INTERVAL.total_seconds()
        )

        if self.getconfig_data is None or time_to_fetch:
            newdata: echoroboticsapi.GetConfig | None = None
            _LOGGER.debug("fetching getconfig reload=True")

            async with async_timeout.timeout(10):
                await self.api.get_config(reload=True)

            async with async_timeout.timeout(30):
                while newdata is None or not newdata.config_validated:
                    await asyncio.sleep(2)
                    _LOGGER.debug("fetching getconfig reload=False")
                    newdata = await self.api.get_config(reload=False)
                _LOGGER.debug("getconfig success")

            if newdata is None or not newdata.config_validated:
                self.getconfig_data = None
                _LOGGER.debug("could not getconfig")
            else:
                self.getconfig_data = newdata
                self.getconfig_tstamp = time.monotonic()

    async def _async_update_data(self) -> float:
        """Fetch data from API endpoint.

        This is the place to pre-process the data to lookup tables
        so entities can quickly look up their data.
        """
        # Note: asyncio.TimeoutError and aiohttp.ClientError are already
        # handled by the data update coordinator.

        try:
            getconfig_task = asyncio.create_task(self._fetch_getconfig())
            async with async_timeout.timeout(5):
                status = await self.smartfetch.smart_fetch()
                if status is None:
                    _LOGGER.info("received empty update")
                else:
                    _LOGGER.debug("received state %s", status)
            await getconfig_task
        except aiohttp.ClientResponseError as e:
            if e.status == 401:
                raise ConfigEntryAuthFailed from e
            else:
                _LOGGER.warning(f"failed to fetch update {e}")
                raise e
        else:
            self.fetch_fail_count = -1  # will be set to 0 by finally
            self.laststatuses_data = status
            self.laststatuses_tstamp = time.monotonic()
            return self.laststatuses_tstamp
        finally:
            self.fetch_fail_count += 1
