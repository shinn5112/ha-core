"""Config flow for luxerOne integration."""
from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from luxerone.client import LuxerOneClient
from luxerone.exceptions import LuxerOneAPIException
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN, EMAIL, ID, NAME, PASS, TITLE, USER

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required("username"): str,
        vol.Required("password"): str,
    }
)


class LuxerOneHub:
    """luxerOne hub. Essentially an auth test wrapper class."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize."""
        self.title = ""
        self.name = ""
        self.user = ""
        self.email = ""

    def authenticate(self, username: str, password: str) -> bool:
        """Test if we can authenticate with the host."""
        try:
            luxerClient = LuxerOneClient(username=username, password=password)
            userDetails = luxerClient.get_user_info()
            self.name = f"{userDetails.firstName} {userDetails.lastName}"
            self.email = userDetails.email
            self.user = username.split("@")[0].lower()
            self.title = f"luxerOne for {self.name}"
            return True
        except LuxerOneAPIException:
            return False

    def __str__(self) -> str:
        """To string method..."""
        return f"name: {self.name}, user: {self.user}, email: {self.email}"


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect."""
    # If your PyPI package is not built with async, pass your methods
    # to the executor:
    # await hass.async_add_executor_job(
    #     your_validate_func, data["username"], data["password"]
    # )

    hub = LuxerOneHub(hass)
    if not await hass.async_add_executor_job(
        hub.authenticate, data["username"], data["password"]
    ):
        raise InvalidAuth

    _LOGGER.debug("Hub: %s", hub)
    return {
        TITLE: hub.title,
        ID: hub.user,
        NAME: hub.name,
        EMAIL: hub.email,
        USER: data["username"],
        PASS: data["password"],
    }


class LuxerOneConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for luxerOne."""

    VERSION = 1

    # def __init__(self) -> None:
    #     """Initialize a new LuxerOneConfigFlow."""
    #     super().__init__()
    #     self.reauth_entry = self.hass.config_entries.async_get_entry(
    #         self.context["entry_id"]
    #     )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
                await self.async_set_unique_id(info[ID].lower())
                self._abort_if_unique_id_configured()
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=info[TITLE],
                    data=info,
                    description=f"luxerOne package tracking for {info[NAME]}",
                )
        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_reauth(self, user_input: Mapping[str, Any]) -> FlowResult:
        """Reauth step."""
        return await self.async_step_reauth_confirm(user_input=user_input)

    async def async_step_reauth_confirm(
        self, user_input: Mapping[str, Any]
    ) -> FlowResult:
        """Dialog that informs the user that reauth is required."""
        if user_input is None:
            return self.async_show_form(
                step_id="reauth_confirm",
                data_schema=vol.Schema({}),
            )
        return await self.async_step_user()


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
