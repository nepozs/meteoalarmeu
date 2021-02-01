"""Binary Sensor for MeteoAlarmEU."""

import logging
from datetime import timedelta

import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.template import (
    forgiving_as_timestamp as as_timestamp,
    timestamp_local,
)
from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    DEVICE_CLASS_SAFETY,
    PLATFORM_SCHEMA,
)
from homeassistant.const import ATTR_ATTRIBUTION, CONF_NAME

from meteoalarm_rssapi import (
    MeteoAlarm,
    MeteoAlarmException,
    MeteoAlarmUnrecognizedRegionError,
    awareness_types,
)

import voluptuous as vol


_LOGGER = logging.getLogger(__name__)

ATTRIBUTION = "Information provided by meteoalarm.eu"
CONF_COUNTRY = "country"
CONF_REGION = "region"
CONF_AWARENESS_TYPES = "awareness_types"
DEFAULT_NAME = "meteoalarmeu"
DEFAULT_AWARENESS_TYPES = awareness_types

SCAN_INTERVAL = timedelta(minutes=30)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_COUNTRY): cv.string,
        vol.Required(CONF_REGION): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_AWARENESS_TYPES, default=DEFAULT_AWARENESS_TYPES): vol.All(
            cv.ensure_list, [vol.In(DEFAULT_AWARENESS_TYPES)]
        ),
    },
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the MeteoAlarmEU binary sensor platform."""
    country = config[CONF_COUNTRY]
    region = config[CONF_REGION]
    name = config[CONF_NAME]
    awareness_types = config[CONF_AWARENESS_TYPES]

    try:
        api = MeteoAlarm(country, region)
    except MeteoAlarmUnrecognizedRegionError:
        _LOGGER.error("Wrong region name (check 'meteoalarm.eu' for the EXACT name)")
    except (KeyError, MeteoAlarmException):
        _LOGGER.error("Wrong country code or region name")
        return

    _LOGGER.info(
        "A binary_sensor was created for country {} and region {}".format(
            country, region
        )
    )
    add_entities([MeteoAlarmBinarySensor(api, name, awareness_types)], True)


class MeteoAlarmBinarySensor(BinarySensorEntity):
    """Representation of a MeteoAlarmEU binary sensor."""

    def __init__(self, api, name, awareness_types):
        """Initialize the MeteoAlarmEU binary sensor."""
        self._name = name
        self._attributes = {}
        self._awareness_types = awareness_types
        self._state = None
        self._api = api
        self._available = True

    @property
    def name(self):
        """Return the name of the binary sensor."""
        return self._name

    @property
    def is_on(self):
        """Return the status of the binary sensor."""
        return self._state

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        self._attributes[ATTR_ATTRIBUTION] = ATTRIBUTION
        return self._attributes

    @property
    def device_class(self):
        """Return the device class of this binary sensor."""
        return DEVICE_CLASS_SAFETY

    @property
    def available(self):
        """Return true if the device is available."""
        return self._available

    def update(self):
        """Update device state."""
        try:
            msgs = self._api.alerts()
            alert = [m for m in msgs if m["awareness_type"] in self._awareness_types]
        except (KeyError, MeteoAlarmException):
            _LOGGER.error("Bad response from meteoalarm.eu")
            self._available = False
            return
        if not self._available:
            _LOGGER.info("meteoalarm.eu server is now OK")
        self._available = True
        if alert:
            alarm = alert[0]
            try:
                # change to local date/time (drop the seconds)
                alarm["from"] = timestamp_local(as_timestamp(alarm["from"]))[:-3]
                alarm["until"] = timestamp_local(as_timestamp(alarm["until"]))[:-3]
                alarm["published"] = timestamp_local(as_timestamp(alarm["published"]))
            except ValueError:
                _LOGGER.error("Not possible to convert to local time")
            self._attributes = alarm
            self._state = True
        else:
            self._attributes = {}
            self._state = False
