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
SENSOR_LCD_READ = "lcd_read"
SENSOR_PREVIOUS_DAY_CONSUMPTION = "previous_day_consumption"
SENSOR_DAILY_AVERAGE_CONSUMPTION = "daily_average_consumption"
SENSOR_BILLING_READ = "billing_read"
SENSOR_CURRENT_CYCLE_TOTAL = "current_cycle_total"

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