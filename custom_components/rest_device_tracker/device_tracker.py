"""
Demo platform for the Device tracker component.

For more details about this platform, please refer to the documentation
https://home-assistant.io/components/demo/
"""
from datetime import timedelta
import logging
import json

import voluptuous as vol
from requests.auth import HTTPBasicAuth, HTTPDigestAuth

from homeassistant.components.device_tracker import PLATFORM_SCHEMA
from homeassistant.components.device_tracker import DOMAIN
from homeassistant.components.sensor.rest import RestData
from homeassistant.const import (
    CONF_PAYLOAD, CONF_NAME, CONF_VALUE_TEMPLATE, CONF_METHOD, CONF_RESOURCE,
    CONF_VERIFY_SSL, CONF_USERNAME, CONF_PASSWORD, ATTR_BATTERY_LEVEL,
    CONF_HEADERS, CONF_AUTHENTICATION, HTTP_BASIC_AUTHENTICATION, 
    CONF_SCAN_INTERVAL, HTTP_DIGEST_AUTHENTICATION, CONF_DEVICE_CLASS, 
    CONF_FORCE_UPDATE)
import homeassistant.helpers.config_validation as cv
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers.event import async_track_time_interval

from homeassistant.helpers.entity import Entity


__version__ = '0.1.9'
#from flatten_json import flatten # FIXME: Add dependency

#######################
#for debug only

def flatten_json(y):
    out = {}

    def flatten(x, name=''):
        if type(x) is dict:
            for a in x:
                flatten(x[a], name + a + '_')
        elif type(x) is list:
            i = 0
            for a in x:
                flatten(a, name + str(i) + '_')
                i += 1
        else:
            out[name[:-1]] = x

    flatten(y)
    return out

####################


_LOGGER = logging.getLogger(__name__)

ATTR_ADDRESS = 'address'
ATTR_CATEGORY = 'category'
ATTR_GEOFENCE = 'geofence'
ATTR_MOTION = 'motion'
ATTR_SPEED = 'speed'
ATTR_TRACKER = 'tracker'

DEFAULT_METHOD = 'GET'
DEFAULT_NAME = 'REST Tracker'
DEFAULT_VERIFY_SSL = True
DEFAULT_FORCE_UPDATE = False

DEFAULT_SCAN_INTERVAL = timedelta(seconds=30)
SCAN_INTERVAL = DEFAULT_SCAN_INTERVAL

CONF_JSON_ATTRS = 'json_attributes'
METHODS = ['POST', 'GET']

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_RESOURCE): cv.url,
    vol.Optional(CONF_AUTHENTICATION):
        vol.In([HTTP_BASIC_AUTHENTICATION, HTTP_DIGEST_AUTHENTICATION]),
    vol.Optional(CONF_JSON_ATTRS, default=[]): cv.ensure_list_csv,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_USERNAME): cv.string,
    vol.Optional(CONF_PASSWORD): cv.string,
    vol.Optional(CONF_VERIFY_SSL, default=DEFAULT_VERIFY_SSL): cv.boolean,
    vol.Optional(CONF_FORCE_UPDATE, default=DEFAULT_FORCE_UPDATE): cv.boolean,
})

async def async_setup_scanner(hass, config, async_see, discovery_info=None):
    """Validate the configuration and return a Traccar scanner."""
    method = 'GET'
    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)
    json_attrs = config.get(CONF_JSON_ATTRS)
    force_update = config.get(CONF_FORCE_UPDATE)
    headers = None
    payload = None    
    
    if username and password:
        if config.get(CONF_AUTHENTICATION) == HTTP_DIGEST_AUTHENTICATION:
            auth = HTTPDigestAuth(username, password)
        else:
            auth = HTTPBasicAuth(username, password)
    else:
        auth = None
        
    rest = RestData(method, config.get(CONF_RESOURCE), auth, headers, payload, 
                    config.get(CONF_VERIFY_SSL))
        
    scanner = RestDeviceTracker(
        hass, rest, async_see, config.get(CONF_NAME),
        config.get(CONF_SCAN_INTERVAL, SCAN_INTERVAL),
        config.get(CONF_JSON_ATTRS), config.get(CONF_FORCE_UPDATE))

    return await scanner.async_init()
  
class RestDeviceTracker(Entity):
    """Representation of a REST device tracker."""

    def __init__(self, hass, rest, async_see, name, scan_interval, json_attrs, 
                 force_update=False):
        """Initialize a REST binary sensor."""
        self._hass = hass
        self._rest = rest
        self._name = name
        self._scan_interval = scan_interval
        self._json_attrs = {}
        self._force_update = force_update
        self._attributes = None
        self._async_see = async_see
        
        for d in json_attrs:
            for key, value in d.items():
                self._json_attrs[key] = value
                _LOGGER.debug( key + ' is ' + value)
        
    async def async_init(self):
        """Further initialize connection to REST."""
        _LOGGER.debug('Init device data.')
        self._rest.update()
        if self._rest.data:
            await self._async_update()
            async_track_time_interval(self._hass,
                                      self._async_update,
                                      self._scan_interval)
            return True
        else:
            return False

    async def _async_update(self, now=None):
        """Update info from rest."""
        _LOGGER.debug('Updating device data.')
        self._rest.update()
        value = flatten_json(json.loads(self._rest.data))
        value = self._rest.data
        if self._json_attrs:
            self._attributes = {}
            if self._rest.data:
                try:
                    json_dict = flatten_json(json.loads(self._rest.data))
                    for k,v in json_dict.items():
                        _LOGGER.debug(k+' : '+str(v))
                    if isinstance(json_dict, dict):
                        attrs = {k: json_dict[v] for k,v in self._json_attrs.items()
                                 if v in json_dict}
                        self._attributes = attrs
                    else:
                        _LOGGER.warning("JSON result was not a dictionary")
                except ValueError:
                    _LOGGER.warning("REST result could not be parsed as JSON")
                    _LOGGER.debug("Erroneous JSON: %s", value)
            else:
                _LOGGER.warning("Empty reply found when expecting JSON data")
            self._attributes[ATTR_TRACKER] = self._name

            await self._async_see(
                dev_id=self._name,
                gps=(self._attributes['latitude'], self._attributes['longitude']),
                attributes=self._attributes)
