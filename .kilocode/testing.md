# Testing Guidelines

Simple testing approach for this Home Assistant integration.

## Quick Setup

```bash
# Install test dependencies
pip install pytest pytest-asyncio pytest-cov

# Run tests
pytest

# With coverage
pytest --cov=custom_components.waterscope
```

## Test Structure

```
tests/
├── test_water_meter.py     # API tests
├── test_config_flow.py     # Configuration tests
└── conftest.py             # Test fixtures
```

## Basic Test Example

```python
"""Test authentication."""
import pytest
from unittest.mock import AsyncMock, patch

from custom_components.waterscope.water_meter import WaterscopeAPI


@pytest.mark.asyncio
async def test_authentication_success():
    """Test successful authentication."""
    async with WaterscopeAPI() as api:
        with patch.object(api, '_perform_auth', return_value=True):
            result = await api.authenticate("test@example.com", "password")
            assert result is True


@pytest.mark.asyncio
async def test_authentication_failure():
    """Test authentication failure."""
    async with WaterscopeAPI() as api:
        with patch.object(api, '_perform_auth', side_effect=Exception("Failed")):
            result = await api.authenticate("bad@example.com", "badpass")
            assert result is False
```

## Test Fixtures

```python
"""Test fixtures in conftest.py"""
import pytest
from homeassistant.config_entries import ConfigEntry
from custom_components.waterscope.const import DOMAIN


@pytest.fixture
def mock_config_entry():
    """Create mock config entry."""
    return ConfigEntry(
        version=1,
        domain=DOMAIN,
        title="Waterscope",
        data={"username": "test@example.com", "password": "testpass"},
        source="user",
        entry_id="test-entry-id",
    )
```

## Real Integration Testing

For real testing with credentials:

```bash
# Set environment variables
export WATERSCOPE_USERNAME="your-email@example.com"
export WATERSCOPE_PASSWORD="your-password"

# Run integration tests
python custom_components/waterscope/water_meter.py $WATERSCOPE_USERNAME $WATERSCOPE_PASSWORD
```

## Home Assistant Testing

```yaml
# Add to configuration.yaml for debugging
logger:
  default: warning
  logs:
    custom_components.waterscope: debug
```

## What to Test

### Essential Tests
- [ ] Authentication succeeds with valid credentials
- [ ] Authentication fails with invalid credentials  
- [ ] Data extraction works from sample HTML
- [ ] Configuration flow validates input properly
- [ ] Sensors return expected values

### Nice to Have
- [ ] Network error handling
- [ ] Rate limiting scenarios
- [ ] Memory usage over time
- [ ] Performance with multiple requests

## Running Tests

```bash
# Quick test run
pytest -v

# Test specific file
pytest tests/test_water_meter.py -v

# Test with real credentials (if set)
pytest -m integration

# Skip slow tests
pytest -m "not slow"
```

Keep testing simple but cover the critical authentication and data extraction paths!