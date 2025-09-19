"""Constants for the Waterscope integration."""

DOMAIN = "waterscope"
DEFAULT_NAME = "Waterscope"

# Configuration keys
CONF_USERNAME = "username"
CONF_PASSWORD = "password"
# Cookie constants removed - only username/password authentication supported

# URLs
BASE_URL = "https://waterscope.us"
LOGIN_URL = f"{BASE_URL}/Home/Main"
DASHBOARD_URL = f"{BASE_URL}/Dashboard"

# Update intervals
UPDATE_INTERVAL = 86400  # 24 hours (daily) in seconds

# Sensor types
SENSOR_CYCLE_USAGE = "cycle_usage"
SENSOR_CURRENT_READING = "current_reading"
SENSOR_DAILY_USAGE = "daily_usage"
SENSOR_LCD_READ = "lcd_read"

# Device info
MANUFACTURER = "Waterscope"
MODEL = "Water Usage Monitor"

# Authentication modes
AUTH_MODE_COOKIES = "cookies"
AUTH_MODE_HTTP = "http"

# API Errors
class WaterscopeError(Exception):
    """Base exception for Waterscope integration."""
    pass

class WaterscopeAuthError(WaterscopeError):
    """Authentication error."""
    pass

class WaterscopeAPIError(WaterscopeError):
    """API communication error."""
    pass