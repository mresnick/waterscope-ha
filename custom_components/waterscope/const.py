"""Constants for the Waterscope integration."""

DOMAIN = "waterscope"
DEFAULT_NAME = "Waterscope"

# Configuration keys
CONF_USERNAME = "username"
CONF_PASSWORD = "password"
CONF_POLL_FREQUENCY = "poll_frequency"
CONF_POLL_TIME_OFFSET = "poll_time_offset"
# Cookie constants removed - only username/password authentication supported

# URLs
BASE_URL = "https://waterscope.us"
LOGIN_URL = f"{BASE_URL}/Home/Main"
DASHBOARD_URL = f"{BASE_URL}/Dashboard"

# Update intervals
DEFAULT_POLL_FREQUENCY = 1440  # Default 24 hours in minutes
MIN_POLL_FREQUENCY = 60  # Minimum 1 hour in minutes
MAX_POLL_FREQUENCY = 2880  # Maximum 48 hours in minutes
DEFAULT_POLL_TIME_OFFSET = 120  # Default 2:00 AM (120 minutes from midnight)

# Sensor types
SENSOR_LCD_READ = "lcd_read"
SENSOR_PREVIOUS_DAY_CONSUMPTION = "previous_day_consumption"
SENSOR_DAILY_AVERAGE_CONSUMPTION = "daily_average_consumption"
SENSOR_BILLING_READ = "billing_read"
SENSOR_CURRENT_CYCLE_TOTAL = "current_cycle_total"

# Device info
MANUFACTURER = "Metron-Farnier LLC"
MODEL = "Water Meter"

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