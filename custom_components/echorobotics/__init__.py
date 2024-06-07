"""The echorobotics integration."""

from __future__ import annotations

import asyncio
import logging
import random

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

    def _should_be_unavailable(self):
        too_old: bool = (
            time.monotonic()
            > self.laststatuses_tstamp + UNAVAILABLE_TIMEOUT.total_seconds()
        )
        too_many_fetches_failed: bool = self.fetch_fail_count >= UNAVAILABLE_FETCHES
        should_be_unavailable = too_many_fetches_failed and too_old
        return should_be_unavailable

    def get_status_info(self, robot_id: RobotId) -> echoroboticsapi.StatusInfo | None:
        if self.laststatuses_data is not None and (not self._should_be_unavailable()):
            laststatuses: echoroboticsapi.models.LastStatuses = self.laststatuses_data
            for si in laststatuses.statuses_info:
                if si.robot == robot_id:
                    return si
            _LOGGER.warning("robot_id %s not found in %s", robot_id, laststatuses)
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

    async def _async_update_data(self) -> bool:
        """Fetch data from API endpoint.

        We don't actually use the return value of this
        Data is actually stored in self.getconfig_data and self.laststatuses_data

        This integration has a smart way of handling transient errors.
        Instead of going unavailable immediately, we stay available for a limited time.
        It is specified by self._should_be_unavailable()

        Every fetch operation either results in success or failure.
        We update the base variables behind self._should_be_unavailable().
        If we got a result, we return True.
        If we got a fail but should be available, we return False.
        If we got a fail but should not be available, re re-raise the error.

        Every return causes entities to be updated, which decide their own availability based on BaseEchoRoboticsEntity::available().
        The first re-raised error does that too. Consecutive ones do not.
        """

        exception = None
        try:

            async def _smartfetch():
                async with async_timeout.timeout(5):
                    status = await self.smartfetch.smart_fetch()
                    if status is None:
                        _LOGGER.info("received empty update")
                    else:
                        _LOGGER.debug("received state %s", status)
                    return status

            fetch_result, status = await asyncio.gather(
                self._fetch_getconfig(), _smartfetch(), return_exceptions=True
            )

            if isinstance(fetch_result, Exception):
                raise fetch_result
            if isinstance(status, Exception):
                raise status
        except aiohttp.ClientResponseError as e:
            if e.status == 401:
                raise ConfigEntryAuthFailed from e
            else:
                exception = e
        except asyncio.TimeoutError as e:
            exception = e
        else:
            self.fetch_fail_count = -1  # will be set to 0 by finally
            self.laststatuses_data = status
            self.laststatuses_tstamp = time.monotonic()
        finally:
            self.fetch_fail_count += 1

        if self._should_be_unavailable():
            if self.last_update_success:
                _LOGGER.info(
                    "fetch failure, going unavailable (count=%s)",
                    self.fetch_fail_count,
                    exc_info=exception,
                )
            raise exception
        else:
            ret = exception is None
            if not ret:
                _LOGGER.info(
                    "fetch failure, staying available for now (count=%s)",
                    self.fetch_fail_count,
                    exc_info=exception,
                )
            return ret
