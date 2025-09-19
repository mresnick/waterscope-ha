"""Streamlined configuration flow for Waterscope integration."""
import logging
from typing import Any, Dict, Optional

import voluptuous as vol
from homeassistant import config_entries, core, exceptions
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv

from .const import (
    DOMAIN,
    DEFAULT_NAME,
    WaterscopeError,
    WaterscopeAPIError,
    WaterscopeAuthError
)

_LOGGER = logging.getLogger(__name__)

# Configuration schema for username/password authentication (simplified)
STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
    }
)


class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate there is invalid auth."""


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


async def validate_user_input(hass: core.HomeAssistant, data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate the username/password input format only.
    
    This ultra-lightweight validation only checks that we have proper credentials.
    The actual authentication and data retrieval will happen after integration setup
    during the coordinator's initial data fetch and regular polling cycle.
    """
    try:
        _LOGGER.info("🔍 Validating user credentials format for Waterscope integration...")
        _LOGGER.debug("Validating credentials for user: %s", data[CONF_USERNAME][:3] + "***")
        
        # Basic validation - check that we have username and password
        username = data.get(CONF_USERNAME, "").strip()
        password = data.get(CONF_PASSWORD, "").strip()
        
        if not username:
            _LOGGER.error("❌ Username is required")
            raise InvalidAuth("Username is required")
            
        if not password:
            _LOGGER.error("❌ Password is required")
            raise InvalidAuth("Password is required")
            
        # Basic email format check for username
        if "@" not in username or "." not in username:
            _LOGGER.error("❌ Username should be a valid email address")
            raise InvalidAuth("Username should be a valid email address")
                    
        _LOGGER.info("✅ Credential format validation successful")
        _LOGGER.debug("Credentials will be validated during first data fetch")
        
    except InvalidAuth:
        _LOGGER.error("Invalid credentials format provided")
        raise
    except Exception as err:
        _LOGGER.error("Credential validation error: %s", str(err), exc_info=True)
        raise CannotConnect from err

    # Return info that you want to store in the config entry.
    _LOGGER.debug("Format validation completed, credentials will be stored securely")
    return {"title": f"{DEFAULT_NAME}"}


class WaterscopeConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Waterscope."""

    VERSION = 1

    async def async_step_user(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Handle the initial step - username/password authentication."""
        errors: Dict[str, str] = {}
        
        if user_input is not None:
            _LOGGER.info("🔧 Processing Waterscope configuration for user: %s", user_input[CONF_USERNAME][:3] + "***")
            try:
                _LOGGER.debug("Starting user input validation...")
                info = await validate_user_input(self.hass, user_input)
                _LOGGER.debug("User input validation completed successfully")
                
                _LOGGER.debug("Setting unique ID: %s", user_input[CONF_USERNAME])
                await self.async_set_unique_id(user_input[CONF_USERNAME])
                self._abort_if_unique_id_configured()
                
                # Store username/password credentials securely for polling cycle
                _LOGGER.info("✅ Creating Waterscope config entry for user: %s", user_input[CONF_USERNAME][:3] + "***")
                _LOGGER.debug("Credentials validated and will be stored securely for regular data polling")
                return self.async_create_entry(title=info["title"], data=user_input)
                
            except CannotConnect:
                _LOGGER.warning("⚠️ Cannot connect to Waterscope service")
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                _LOGGER.warning("⚠️ Invalid authentication credentials")
                errors["base"] = "invalid_auth"
            except Exception as e:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception during config: %s", str(e))
                errors["base"] = "unknown"

        _LOGGER.debug("Showing config form (errors: %s)", errors)
        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
            description_placeholders={
                "login_url": "https://waterscope.us/Home/Main"
            }
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> "WaterscopeOptionsFlowHandler":
        """Create the options flow."""
        return WaterscopeOptionsFlowHandler(config_entry)


class WaterscopeOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow for Waterscope."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        # For now, no options to configure
        # Future options could include update interval, units, etc.
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({}),
        )