"""The Waterscope integration."""
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DOMAIN
from .coordinator import WaterscopeDataCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Waterscope from a config entry."""
    _LOGGER.info("🚀 Setting up Waterscope integration...")
    _LOGGER.debug("Config entry ID: %s", entry.entry_id)
    _LOGGER.debug("Config entry title: %s", entry.title)
    _LOGGER.debug("Config entry data keys: %s", list(entry.data.keys()))
    
    # Initialize data coordinator (it will handle API creation based on config)
    _LOGGER.debug("Creating WaterscopeDataCoordinator...")
    coordinator = WaterscopeDataCoordinator(hass, entry)
    _LOGGER.debug("✅ Data coordinator created successfully")
    
    # Fetch initial data so we have data when the entities are created
    try:
        _LOGGER.debug("Performing initial data refresh...")
        await coordinator.async_config_entry_first_refresh()
        _LOGGER.debug("✅ Initial data refresh completed successfully")
    except Exception as err:
        _LOGGER.error("❌ Error fetching initial data: %s", str(err), exc_info=True)
        raise ConfigEntryNotReady(f"Failed to fetch initial data: {err}") from err

    # Store coordinator in hass data
    _LOGGER.debug("Storing coordinator in hass data...")
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator
    _LOGGER.debug("✅ Coordinator stored successfully")

    # Set up platforms
    _LOGGER.debug("Setting up platforms: %s", PLATFORMS)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    
    # Set up options update listener
    entry.async_on_unload(entry.add_update_listener(async_update_options))
    _LOGGER.info("✅ Waterscope integration setup complete")

    return True


async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Update options."""
    _LOGGER.info("🔄 Updating Waterscope configuration options...")
    coordinator = hass.data[DOMAIN][entry.entry_id]
    
    # Update coordinator with new settings
    if hasattr(coordinator, 'async_config_entry_updated'):
        await coordinator.async_config_entry_updated(hass, entry)
    
    _LOGGER.info("✅ Configuration options updated successfully")


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.info("🧹 Unloading Waterscope integration...")
    _LOGGER.debug("Unloading entry ID: %s", entry.entry_id)
    
    # Unload platforms
    _LOGGER.debug("Unloading platforms: %s", PLATFORMS)
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    _LOGGER.debug("Platform unload result: %s", unload_ok)
    
    if unload_ok:
        # Clean up stored data
        _LOGGER.debug("Cleaning up stored data...")
        hass.data[DOMAIN].pop(entry.entry_id)
        _LOGGER.info("✅ Waterscope integration unloaded successfully")
    else:
        _LOGGER.warning("⚠️ Failed to unload some platforms")

    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    _LOGGER.info("🔄 Reloading Waterscope integration...")
    _LOGGER.debug("Reloading entry ID: %s", entry.entry_id)
    
    _LOGGER.debug("Step 1: Unloading current entry...")
    await async_unload_entry(hass, entry)
    
    _LOGGER.debug("Step 2: Setting up entry again...")
    await async_setup_entry(hass, entry)
    
    _LOGGER.info("✅ Waterscope integration reload complete")