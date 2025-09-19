"""Sensor platform for Waterscope integration."""
import logging
from datetime import timedelta
from typing import Optional, Any, Dict

from homeassistant.components.sensor import (
    SensorEntity,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .http_dashboard import WaterscopeDashboardAPI
from .const import (
    DOMAIN,
    DEFAULT_NAME,
    SENSOR_LCD_READ,
    UPDATE_INTERVAL,
    MANUFACTURER,
    MODEL,
    WaterscopeAPIError,
)
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Waterscope sensors from a config entry."""
    _LOGGER.info("🚀 Setting up Waterscope sensors...")
    _LOGGER.debug("Config entry ID: %s", config_entry.entry_id)
    _LOGGER.debug("Config entry data: %s", {k: "***" if k == CONF_PASSWORD else v for k, v in config_entry.data.items()})
    
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    _LOGGER.debug("Retrieved coordinator: %s", type(coordinator).__name__)
    
    entities = [
        WaterscopeLCDReadSensor(coordinator, config_entry),
    ]
    _LOGGER.debug("Created %s sensor entities", len(entities))
    
    _LOGGER.debug("Adding entities with update_before_add=True...")
    async_add_entities(entities, update_before_add=True)
    _LOGGER.info("✅ Waterscope sensors setup complete")


class WaterscopeDataCoordinator(DataUpdateCoordinator):
    """Class to manage fetching data from the Waterscope dashboard API."""

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize the data coordinator."""
        self.config_entry = config_entry
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=UPDATE_INTERVAL),
        )

    async def _async_update_data(self) -> Dict[str, Any]:
        """Update data via dashboard API."""
        try:
            _LOGGER.debug("🔄 Starting data update for Waterscope...")
            # Use username/password authentication with dashboard API
            username = self.config_entry.data[CONF_USERNAME]
            password = self.config_entry.data[CONF_PASSWORD]
            
            _LOGGER.debug("Updating data for user: %s", username[:3] + "***")
            
            async with WaterscopeDashboardAPI() as dashboard_api:
                _LOGGER.debug("Created dashboard API instance, fetching data...")
                data = await dashboard_api.get_data(username, password)
                
                if not data:
                    _LOGGER.error("❌ Failed to fetch data from dashboard API - no data returned")
                    raise UpdateFailed("Failed to fetch data from dashboard API")
                
                _LOGGER.debug("✅ Raw data retrieved: %s", data)
                
                # Extract LCD read value
                lcd_value = data.get('lcd_read')
                _LOGGER.debug("Extracted LCD value: %s", lcd_value)
                
                result = {
                    SENSOR_LCD_READ: lcd_value,
                    'raw_data': data,
                    'data_source': 'dashboard_api'
                }
                
                _LOGGER.info("✅ Data update successful - LCD read: %s", lcd_value)
                return result
                
        except Exception as error:
            _LOGGER.error("❌ Data update failed: %s", str(error), exc_info=True)
            raise UpdateFailed(f"Failed to update data: {error}") from error


class WaterscopeSensorBase(CoordinatorEntity, SensorEntity):
    """Base representation of a Waterscope sensor."""

    def __init__(
        self,
        coordinator: WaterscopeDataCoordinator,
        config_entry: ConfigEntry,
        sensor_type: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._config_entry = config_entry
        self._sensor_type = sensor_type
        self._attr_unique_id = f"{config_entry.entry_id}_{sensor_type}"
        
    @property
    def device_info(self) -> Dict[str, Any]:
        """Return device information about this Waterscope device."""
        return {
            "identifiers": {(DOMAIN, self._config_entry.entry_id)},
            "name": DEFAULT_NAME,
            "manufacturer": MANUFACTURER,
            "model": MODEL,
            "sw_version": "1.0.0",
        }

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.last_update_success


class WaterscopeLCDReadSensor(WaterscopeSensorBase):
    """Representation of LCD read sensor."""

    def __init__(
        self,
        coordinator: WaterscopeDataCoordinator,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the LCD read sensor."""
        super().__init__(coordinator, config_entry, SENSOR_LCD_READ)
        self._attr_name = "LCD Read"
        self._attr_native_unit_of_measurement = "ft³"
        self._attr_device_class = SensorDeviceClass.WATER
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        self._attr_icon = "mdi:water-gauge"

    @property
    def native_value(self) -> Optional[float]:
        """Return the native value of the sensor."""
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.get(SENSOR_LCD_READ)

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return the state attributes."""
        attributes = {
            "integration": DOMAIN,
            "last_updated": getattr(self.coordinator, 'last_update_success_time', None),
            "description": "LCD meter read from dashboard",
        }
        
        if self.coordinator.data:
            # Add data source information
            data_source = self.coordinator.data.get('data_source', 'unknown')
            attributes["data_source"] = data_source
            
            # Add raw data information
            if self.coordinator.data.get('raw_data'):
                raw_data = self.coordinator.data['raw_data']
                attributes["raw_lcd_text"] = raw_data.get('raw_lcd_text')
                attributes["api_status"] = raw_data.get('status')
        
        return attributes