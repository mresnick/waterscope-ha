# Project Structure

Overview of the Waterscope Home Assistant integration organization.

## Directory Layout

```
waterscope-ha/
├── .kilocode/                          # Project documentation
│   ├── docs/                          # Technical deep-dive docs
│   │   ├── TECHNICAL_INVESTIGATION_FINDINGS.md
│   │   └── WATERSCOPE_AUTHENTICATION_REPRODUCTION_GUIDE.md
│   ├── code-conventions.md            # Coding standards
│   ├── project-structure.md           # This file
│   ├── development.md                 # Dev setup guide
│   ├── testing.md                     # Testing guidelines
│   └── troubleshooting.md             # Common issues
├── custom_components/waterscope/       # Main integration
│   ├── __init__.py                    # Integration setup
│   ├── config_flow.py                 # Configuration UI
│   ├── coordinator.py                 # Data management & sensors
│   ├── water_meter.py                 # API client (the complex part!)
│   ├── const.py                       # Constants
│   ├── manifest.json                  # Integration metadata
│   └── strings.json                   # UI text
├── tests/                             # Test suite
│   ├── test_standalone_auth.py        # Real auth testing
│   └── conftest.py                    # Test fixtures
└── README.md                          # Installation & usage
```

## Core Components

### `water_meter.py` - The Heart of It All
This is where the magic happens! Contains the `WaterscopeAPI` class that:

- **Hybrid Authentication**: Uses both `aiohttp` and `requests` because Azure B2C is picky
- **7-Step OAuth Flow**: Complex dance with Microsoft's authentication
- **Data Extraction**: Scrapes meter readings from HTML dashboard
- **Error Handling**: Lots of retry logic and fallbacks

### `coordinator.py` - Data Management
- **`WaterscopeDataCoordinator`**: Fetches data every 30 minutes
- **Sensor Classes**: Different sensors for various water metrics
- **Home Assistant Integration**: Proper async patterns and device info

### `config_flow.py` - User Setup
- Simple username/password input
- Basic validation (email format, etc.)
- Creates configuration entry for Home Assistant

### `const.py` - Configuration
- Domain name, default values, sensor types
- API timeouts and retry settings
- Nothing too exciting but keeps things organized

## Key Architecture Decisions

### Why Hybrid HTTP?
```python
# Problem: Azure B2C rejects aiohttp requests
# Solution: Use both libraries
async with aiohttp.ClientSession() as session:
    # Initial steps work fine with aiohttp
    pass

# But for Azure B2C, we need requests
result = await asyncio.to_thread(sync_requests_call)
```

This is the main complexity - authentication requires jumping between HTTP libraries.

### Data Flow
```
Username/Password → OAuth Dance → Session Cookies → Dashboard Scraping → Sensor Updates
```

1. User enters credentials in HA UI
2. Integration performs 7-step authentication
3. Extracts session cookies for future requests
4. Periodically scrapes dashboard for meter data
5. Updates Home Assistant sensors

### Error Handling Strategy
- **Authentication errors**: Retry with backoff, then mark unavailable
- **Network errors**: Timeout and retry on next cycle
- **Parsing errors**: Log details for debugging, return None
- **Rate limiting**: Increase polling interval automatically

## Home Assistant Integration Points

### Sensor Types Created
- **Current Meter Reading**: Main LCD display value
- **Previous Day Consumption**: Yesterday's usage
- **Billing Period**: Current billing cycle info
- **Daily Average**: Running average consumption

### Configuration
- No YAML config needed - everything through UI
- Stores username/password in config entry
- Configurable polling frequency (default 30 min)

### Device Info
- Shows up as single "Waterscope Water Meter" device
- All sensors grouped under this device
- Includes manufacturer info, model, etc.

## Security Considerations

### Credential Handling
- Passwords never logged (username masked as `user***`)
- No persistent credential storage
- Re-authentication on each data fetch
- Proper session cleanup

### Network Security
- HTTPS only
- Certificate validation
- Request timeouts to prevent hanging
- Rate limiting respect

## Performance Notes

### Resource Usage
- Minimal memory footprint (just config data)
- CPU usage spikes during auth (30 seconds every 30 minutes)
- Network: ~10 HTTP requests every 30 minutes
- No persistent connections (session per update)

### Optimization Opportunities
- Could cache authentication for shorter periods
- Batch multiple meter readings if available
- Reduce HTML parsing overhead

## Testing Strategy

### What Gets Tested
- Authentication flow with mocked responses
- Data extraction from sample HTML
- Configuration validation
- Error scenarios and recovery

### Real Testing
- Standalone script for testing auth with real credentials
- Integration testing in live Home Assistant
- Manual verification of sensor data accuracy

## Common Issues

The most frequent problems (in order):
1. **Authentication failures** - Usually credential or network issues
2. **Dashboard parsing breaks** - Waterscope changes their HTML
3. **Rate limiting** - Too frequent polling
4. **Session expiration** - Normal after 24-48 hours

## Future Improvements

### Potential Enhancements
- Support for multiple meters per account
- Historical data tracking
- Water usage alerts/automations
- HACS integration for easier installation

### Known Limitations
- Single meter support only
- No real-time data (polling based)
- Dependent on Waterscope's web interface
- Complex authentication makes it fragile

This is a hobby project that solves a specific problem: getting water meter data into Home Assistant without browser automation. The authentication complexity is the price we pay for eliminating Playwright dependencies!