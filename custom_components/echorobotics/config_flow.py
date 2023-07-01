"""Config flow for echorobotics integration."""
from __future__ import annotations

import logging
import re
from typing import Any

import aiohttp

import echoroboticsapi
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError, ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_create_clientsession
import homeassistant.helpers.config_validation as cv

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


STEP_REAUTH_DATA_SCHEMA = vol.Schema(
    {
        vol.Required("user_token"): str,
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """

    api = echoroboticsapi.Api(
        websession=async_create_clientsession(
            hass,
            cookies=echoroboticsapi.create_cookies(
                user_id=data["user_id"], user_token=data["user_token"]
            ),
        ),
        robot_ids=[data["robot_id"]],
    )
    try:
        statuses = await api.last_statuses()
    except aiohttp.ClientResponseError as e:
        if e.status == 401:
            raise InvalidAuth from e
        else:
            raise CannotConnect(e) from e
    except Exception as exc:
        raise CannotConnect(exc) from exc

    if not statuses:
        raise EmptyResponse()
    if len(statuses.statuses_info) != 1:
        _LOGGER.error(f"no statuses in {statuses}")
        raise EmptyResponse()

    if statuses.statuses_info[0].robot != data["robot_id"]:
        data["robot_id"] = statuses.statuses_info[0].robot

    return data


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for echorobotics."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""

        def get_default(key: str) -> str | None:
            if user_input:
                return user_input.get(key, None)
            return None
        user_data_schema = vol.Schema(
            {
                vol.Required("user_id", default=get_default("user_id")): str,
                vol.Required("user_token", default=get_default("user_token")): str,
                vol.Required("robot_id", default=get_default("robot_id")): str,
            }
        )

        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=user_data_schema
            )

        errors = {}
        if await self.is_duplicate(user_input):
            return self.async_abort(reason="already_configured")

        try:
            user_input = await validate_input(self.hass, user_input)
        except CannotConnect:
            errors["base"] = "cannot_connect"
        except EmptyResponse:
            errors["base"] = "empty_response"
        except InvalidAuth:
            errors["base"] = "invalid_auth"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            return self.async_create_entry(
                title=user_input["robot_id"], data=user_input
            )

        return self.async_show_form(
            step_id="user", data_schema=user_data_schema, errors=errors
        )

    async def is_duplicate(self, user_input) -> bool:
        """Check if current device is already configured."""
        for other_robot in self._async_current_entries():
            if other_robot.data["robot_id"] == user_input["robot_id"]:
                return True
        return False

    async def async_step_reauth(self, user_input: dict[str, Any]) -> FlowResult:
        """Handle reauthorization."""

        existing_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        errors = {}
        if user_input is not None:
            user_input["user_id"] = existing_entry.data["user_id"]
            user_input["robot_id"] = existing_entry.data["robot_id"]
            try:
                user_input = await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except EmptyResponse:
                errors["base"] = "empty_response"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                self.hass.config_entries.async_update_entry(
                    existing_entry,
                    data={
                        **existing_entry.data,
                        "user_token": user_input["user_token"],
                    }
                )
                await self.hass.config_entries.async_reload(existing_entry.entry_id)
                return self.async_abort(reason="reauth_successful")

        return self.async_show_form(
            step_id="reauth", data_schema=STEP_REAUTH_DATA_SCHEMA, errors=errors
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""

class InvalidAuth(HomeAssistantError):
    """Error to indicate auth fail"""

class EmptyResponse(HomeAssistantError):
    """Error to indicate we didn't find the robot."""
