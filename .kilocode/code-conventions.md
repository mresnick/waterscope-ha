# Code Conventions

This document outlines the coding standards and conventions for the Waterscope Home Assistant integration project.

## Python Standards

### Base Standards
- **Python Version**: Minimum Python 3.8+ (Home Assistant requirement)
- **PEP 8**: Follow Python Enhancement Proposal 8 for style guidelines
- **Type Hints**: Use type hints for all function signatures and class attributes
- **Docstrings**: Use Google-style docstrings for all public functions and classes

### Code Formatting

#### Black Formatter
- **Line Length**: 88 characters (Black default)
- **String Quotes**: Double quotes preferred by Black
- **Automatic Formatting**: Use Black for consistent code formatting

```python
# Example of properly formatted code
async def authenticate_user(
    username: str, password: str, timeout: int = 30
) -> bool:
    """Authenticate user with Waterscope service.
    
    Args:
        username: User email address
        password: User password
        timeout: Request timeout in seconds
        
    Returns:
        True if authentication successful, False otherwise
        
    Raises:
        AuthenticationError: When credentials are invalid
        ConnectionError: When service is unreachable
    """
    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            result = await self._perform_auth(session, username, password)
            return result.success
    except Exception as exc:
        _LOGGER.error("Authentication failed: %s", exc)
        raise AuthenticationError("Invalid credentials") from exc
```

### Home Assistant Specific Conventions

#### Import Organization
```python
"""Home Assistant integration for Waterscope."""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, Optional

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import WaterscopeDataCoordinator
```

#### Logging
- Use module-level logger: `_LOGGER = logging.getLogger(__name__)`
- Sensitive data protection: Mask credentials in logs
- Log levels:
  - `DEBUG`: Detailed development information
  - `INFO`: Important operational events
  - `WARNING`: Unexpected but recoverable issues
  - `ERROR`: Serious problems that affect functionality

```python
_LOGGER = logging.getLogger(__name__)

# Good - Masked sensitive data
_LOGGER.info("Authenticating user: %s", username[:3] + "***")

# Bad - Exposing sensitive data
_LOGGER.info("Authenticating with password: %s", password)
```

#### Async/Await Patterns
- Use `async`/`await` for all I/O operations
- Wrap blocking calls with `asyncio.to_thread()`
- Proper resource cleanup with context managers

```python
# Good - Non-blocking pattern
async def fetch_data(self) -> Dict[str, Any]:
    """Fetch data from API."""
    async with aiohttp.ClientSession() as session:
        async with session.get(self.api_url) as response:
            return await response.json()

# Good - Blocking call wrapped
async def sync_operation(self) -> str:
    """Perform synchronous operation safely."""
    return await asyncio.to_thread(self._blocking_function)
```

#### Entity Conventions
- Inherit from appropriate base classes (`SensorEntity`, `CoordinatorEntity`)
- Use proper device info structure
- Implement required properties consistently

```python
class WaterscopeSensor(CoordinatorEntity, SensorEntity):
    """Base Waterscope sensor."""

    def __init__(
        self,
        coordinator: WaterscopeDataCoordinator,
        entry: ConfigEntry,
        sensor_type: str,
    ) -> None:
        """Initialize sensor."""
        super().__init__(coordinator)
        self._entry = entry
        self._sensor_type = sensor_type
        self._attr_unique_id = f"{entry.entry_id}_{sensor_type}"
        self._attr_name = f"Waterscope {sensor_type.replace('_', ' ').title()}"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry.entry_id)},
            name="Waterscope Water Meter",
            manufacturer=MANUFACTURER,
            model="Water Meter",
            sw_version="1.0",
        )
```

## Error Handling

### Exception Patterns
- Use specific exception types
- Preserve exception chains with `raise ... from`
- Handle expected failures gracefully

```python
async def fetch_meter_data(self) -> Dict[str, Any]:
    """Fetch meter data with proper error handling."""
    try:
        data = await self._api_call()
        return self._parse_data(data)
    except aiohttp.ClientError as exc:
        _LOGGER.warning("Network error fetching data: %s", exc)
        raise UpdateFailed("Network connection failed") from exc
    except ValueError as exc:
        _LOGGER.error("Invalid data format: %s", exc)
        raise UpdateFailed("Data parsing failed") from exc
    except Exception as exc:
        _LOGGER.exception("Unexpected error: %s", exc)
        raise UpdateFailed("Unknown error occurred") from exc
```

### Validation Patterns
```python
def validate_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """Validate configuration input."""
    errors = {}
    
    username = config.get("username", "").strip()
    if not username or "@" not in username:
        errors["username"] = "invalid_email"
    
    password = config.get("password", "").strip()
    if not password or len(password) < 8:
        errors["password"] = "invalid_password"
    
    if errors:
        raise vol.Invalid("Configuration validation failed", errors)
    
    return {"username": username, "password": password}
```

## Testing Conventions

### Test Structure
- Use `pytest` for all tests
- Test file naming: `test_*.py`
- Mock external dependencies
- Test both success and failure scenarios

```python
"""Tests for Waterscope authentication."""
import pytest
from unittest.mock import AsyncMock, patch

from custom_components.waterscope.water_meter import WaterscopeAPI


@pytest.fixture
async def api_client():
    """Create API client for testing."""
    async with WaterscopeAPI() as client:
        yield client


async def test_successful_authentication(api_client):
    """Test successful authentication flow."""
    with patch.object(api_client, '_perform_auth') as mock_auth:
        mock_auth.return_value = True
        
        result = await api_client.authenticate("user@example.com", "password123")
        
        assert result is True
        mock_auth.assert_called_once()


async def test_authentication_failure(api_client):
    """Test authentication failure handling."""
    with patch.object(api_client, '_perform_auth') as mock_auth:
        mock_auth.side_effect = AuthenticationError("Invalid credentials")
        
        result = await api_client.authenticate("bad@example.com", "badpass")
        
        assert result is False
```

## File Organization

### Module Structure
```
custom_components/waterscope/
├── __init__.py          # Integration setup
├── config_flow.py       # Configuration flow
├── const.py            # Constants and configuration
├── coordinator.py      # Data update coordinator  
├── water_meter.py      # Core API implementation
├── manifest.json       # Integration metadata
└── strings.json        # UI strings
```

### Import Dependencies
- Group imports: standard library, third-party, local
- Use absolute imports for local modules
- Avoid circular imports

## Documentation

### Docstring Format (Google Style)
```python
async def get_meter_reading(
    self, username: str, password: str, retry_count: int = 3
) -> Optional[float]:
    """Get current meter reading from Waterscope dashboard.
    
    Authenticates with the Waterscope service and extracts the current
    meter reading value from the dashboard.
    
    Args:
        username: User email address for authentication
        password: User password for authentication  
        retry_count: Number of retry attempts on failure
        
    Returns:
        Current meter reading in cubic feet, or None if unavailable
        
    Raises:
        AuthenticationError: When credentials are invalid
        ConnectionError: When service is unreachable
        DataParseError: When meter data cannot be extracted
        
    Example:
        >>> api = WaterscopeAPI()
        >>> reading = await api.get_meter_reading("user@example.com", "pass123")
        >>> print(f"Current reading: {reading} ft³")
    """
```

### Comments
- Use comments sparingly for complex logic
- Prefer self-documenting code
- Explain "why" not "what"

```python
# Good - Explains reasoning
# Azure B2C requires specific request format that aiohttp cannot provide
result = await asyncio.to_thread(self._sync_b2c_request, credentials)

# Bad - States the obvious  
# Call the function with parameters
result = await some_function(param1, param2)
```

## Performance Guidelines

### Resource Management
- Use context managers for resource cleanup
- Close sessions and connections explicitly
- Limit concurrent operations

```python
# Good - Proper resource management
async with aiohttp.ClientSession() as session:
    async with session.get(url) as response:
        data = await response.json()
        return self._process_data(data)

# Good - Controlled concurrency
async def fetch_multiple_readings(self, meters: List[str]) -> Dict[str, float]:
    """Fetch readings for multiple meters with concurrency control."""
    semaphore = asyncio.Semaphore(5)  # Limit to 5 concurrent requests
    
    async def fetch_single(meter_id: str) -> Tuple[str, float]:
        async with semaphore:
            reading = await self._fetch_reading(meter_id)
            return meter_id, reading
    
    tasks = [fetch_single(meter) for meter in meters]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    return {meter_id: reading for meter_id, reading in results 
            if not isinstance(reading, Exception)}
```

## Security Considerations

### Credential Handling
- Never log passwords or sensitive tokens
- Use secure storage for credentials
- Implement proper session cleanup

```python
# Good - Masked logging
_LOGGER.debug("Authentication attempt for user: %s", username[:3] + "***")

# Good - Secure cleanup
async def cleanup_session(self) -> None:
    """Clean up session and clear sensitive data."""
    if self.session:
        await self.session.close()
    
    # Clear any cached credentials
    self._credentials = None
    self._session_cookies.clear()
```

### Input Validation
- Validate all external inputs
- Sanitize data before processing
- Use type hints for early detection

```python
def validate_username(username: str) -> str:
    """Validate and sanitize username input."""
    if not isinstance(username, str):
        raise TypeError("Username must be a string")
    
    username = username.strip().lower()
    
    if not username:
        raise ValueError("Username cannot be empty")
    
    if "@" not in username or len(username) > 255:
        raise ValueError("Invalid email format")
    
    return username
```

## Commit and PR Guidelines

### Commit Messages
- Use conventional commit format: `type(scope): description`
- Types: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`
- Keep first line under 72 characters
- Include detailed description for complex changes

```
feat(auth): implement hybrid HTTP authentication flow

- Combine aiohttp and requests for Azure B2C compatibility
- Add comprehensive error handling and retry logic
- Support session cookie extraction and management

Resolves: #123
```

### Pull Request Requirements
- All tests must pass
- Code coverage must not decrease
- Documentation updated for new features
- Code review by at least one maintainer
- Black formatting applied
- Type hints present for new code

This document should be reviewed and updated as the project evolves to maintain code quality and consistency across all contributions.