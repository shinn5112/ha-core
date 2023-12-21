"""luxerOne sensors."""
import logging
from typing import Any

from luxerone.client import LuxerOneClient
from luxerone.exceptions import LuxerOneAPIException, TokenExpiredException
from luxerone.package import Package

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import generate_entity_id
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, ENTITY_ID_FORMAT, EVENT_DOMAIN, ID, NAME, PASS, USER

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up luxerOne package sensor entities based on a config entry."""
    luxerOneClient = hass.data[DOMAIN][config_entry.entry_id]
    async_add_entities(
        [
            LuxerOnePackageSensor(hass, luxerOneClient, config_entry),
        ],
        True,
    )


class LuxerOnePackageSensor(SensorEntity):
    """Detects the number of packages that are available and their attributes."""

    _attr_icon = "mdi:package"
    _attr_has_entity_name = True
    _attr_unit_of_measurement_ = "packages"

    def __init__(
        self,
        hass: HomeAssistant,
        luxerOne_client: LuxerOneClient,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize a LuxerOnePackageSensor."""
        super().__init__()
        self._luxerOne_client = luxerOne_client
        self._hass = hass
        self._config_entry = config_entry
        self._attr_unique_id = self._config_entry.data[ID]
        self._attr_name = "Packages " + self._config_entry.data[NAME]
        self.entity_id = generate_entity_id(
            ENTITY_ID_FORMAT, name=self._attr_name, hass=hass
        )
        self._attr_extra_state_attributes = {}
        _LOGGER.debug(
            "Created new LuxerOnePackageSensor with id %s", self._attr_unique_id
        )

    def _request_new_token(self) -> None:
        _LOGGER.debug("Token expired for %s, requesting a new one", self.entity_id)
        self._luxerOne_client.login(
            self._config_entry.data[USER], self._config_entry.data[PASS]
        )

    def _get_pending_packages(self) -> list[Package]:
        return self._luxerOne_client.get_pending_packages()

    async def async_update(self, **kwargs: Any) -> None:
        """Perform an async update of the package data."""
        # save the current package codes, will be used later.
        _LOGGER.debug("update requested for %s", {self.entity_id})
        try:
            old_codes = self._attr_extra_state_attributes["package_codes"]
        except KeyError:
            old_codes = []

        packages: list[Package] = []
        # package codes will be called out separate from the data for easy use.
        package_codes: list[str] = []
        package_data: dict[str, Any] = {}
        try:
            try:
                packages = await self._hass.async_add_executor_job(
                    self._get_pending_packages
                )
            except TokenExpiredException:
                await self._hass.async_add_executor_job(self._request_new_token)
                packages = await self._hass.async_add_executor_job(
                    self._get_pending_packages
                )
            for package in packages:
                package_datum = {}
                package_codes.append(package.accessCode)
                package_datum["carrier"] = package.carrier.carrier
                package_datum["labels"] = package.labels
                package_datum["locker"] = package.locker.lockerNumber
                package_datum["locker_type"] = package.locker.lockerType
                package_datum["location"] = package.location.locationAddress
                package_datum["access_code"] = package.accessCode
                package_datum["perishable"] = package.isPerishable
                package_datum["charge"] = package.charge
                package_datum["hold_until"] = package.holdUntil
                package_datum["picked_up"] = package.pickedup
                package_data[package.id] = package_datum

            # add an explicit entry in the attributes for the package codes so the user doesn't
            # have to look for them
            package_data["package_codes"] = package_codes
            self._attr_native_value = len(packages)
            self._attr_extra_state_attributes = package_data
            self.async_write_ha_state()
            _LOGGER.debug(
                "%d packages detected for %s",
                len(package_codes),
                self._config_entry.data[NAME],
            )

            if package_codes != old_codes:
                event_data = {
                    "entity_id": self.entity_id,
                    "device_id": self.entity_id,
                    "type": "new_package_detected",
                }
                self.hass.bus.async_fire(EVENT_DOMAIN, event_data)

        except LuxerOneAPIException as err:
            _LOGGER.error(
                "Was unable to login to luxerOne for %s because %s",
                {self.entity_id},
                err,
            )
