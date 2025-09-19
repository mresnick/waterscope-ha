# Waterscope Home Assistant Integration

**Pure HTTP authentication system for Waterscope water meter data integration with Home Assistant**

---

## Overview

This Home Assistant integration provides access to Waterscope water meter data without requiring browser automation. The implementation uses a reverse-engineered HTTP authentication flow that programmatically extracts session cookies from username/password credentials.

### Key Features

- ✅ **No Browser Automation** - Pure HTTP implementation eliminates Playwright/Selenium dependencies
- ✅ **Real-Time Water Data** - Access to current usage, daily consumption, and billing information
- ✅ **Production Ready** - Comprehensive error handling and session management
- ✅ **Home Assistant Native** - Full integration with HA config flow and entity system

---

## Installation

### HACS Installation (Recommended)

1. Add this repository to HACS as a custom repository
2. Install "Waterscope" from HACS
3. Restart Home Assistant

### Manual Installation

1. Copy the `custom_components/waterscope` folder to your Home Assistant `config/custom_components/` directory
2. Restart Home Assistant

---

## Configuration

1. Go to **Settings** → **Devices & Services** → **Add Integration**
2. Search for "Waterscope" and select it
3. Enter your Waterscope credentials:
   - **Username**: Your Waterscope account email
   - **Password**: Your Waterscope account password
4. The integration will automatically authenticate and set up your water meter sensors

---

## Available Sensors

The integration creates the following entities:

- **Water Usage (Last 24 Hours)** - Current 24-hour water consumption in gallons
- **Current Meter Reading** - Latest meter reading value
- **Daily Usage** - Today's water consumption
- **Billing Period** - Current billing cycle information

---

## Authentication Method

This integration uses a sophisticated HTTP-only authentication system that:

1. **Authenticates with Waterscope** using your username/password
2. **Handles Azure B2C OAuth flow** with proper CSRF token management
3. **Extracts session cookies** programmatically
4. **Accesses dashboard data** via authenticated HTTP requests

The authentication process eliminates the need for browser automation while maintaining full access to your water usage data.

---

## Technical Architecture

### Core Components

- **`waterscope.py`** - Unified API providing both authentication and dashboard data extraction via `WaterscopeAPI`
- **`sensor.py`** - Home Assistant sensor entities and data coordinator
- **`config_flow.py`** - Integration configuration interface
- **`const.py`** - Constants, URLs, and exception definitions

### Authentication Flow

```
Username/Password → Azure B2C OAuth → Session Cookies → Dashboard Access → Data Extraction
```

The implementation handles the complete 7-step OAuth authentication process using a hybrid approach via the unified `WaterscopeAPI`:

1. Load initial login page
2. Submit username and capture OAuth redirect
3. Load Azure B2C page and extract CSRF tokens
4. Submit password to Azure B2C (hybrid aiohttp/requests via asyncio.to_thread)
5. Complete OAuth confirmation using authenticated session
6. Exchange tokens with Waterscope
7. Validate session and extract dashboard data

All authentication and data extraction functionality is consolidated into a single `WaterscopeAPI` class that provides both `authenticate()` and `get_meter_data()` methods.

---

## Testing

### Validation Script

Test your authentication with the included validation script:

```bash
python tests/test_standalone_auth.py
```

This will:
- Authenticate with your credentials
- Access the Waterscope dashboard
- Extract real water usage data
- Verify the complete authentication flow

### Expected Results

A successful test will show:
- ✅ Authentication successful
- ✅ Dashboard access (HTTP 200)
- ✅ Water usage data extracted (e.g., "16.81 gallons")

---

## Troubleshooting

### Common Issues

**Authentication Fails**
- Verify your Waterscope credentials are correct
- Check that your account has dashboard access
- Ensure you can log in via the Waterscope website

**No Data Available**
- Confirm your water meter is properly connected to Waterscope
- Check that data appears on the Waterscope dashboard
- Verify the integration is using the correct consumer dashboard URL

**Integration Not Loading**
- Restart Home Assistant after installation
- Check the Home Assistant logs for error messages
- Ensure all required Python packages are installed

### Debug Logging

Enable debug logging in Home Assistant:

```yaml
logger:
  default: info
  logs:
    custom_components.waterscope: debug
```

---

## Security Considerations

- **Credentials**: Stored securely using Home Assistant's credential storage system
- **Session Management**: Automatic session cleanup and proper cookie handling
- **Rate Limiting**: Built-in retry strategies and backoff mechanisms
- **Error Handling**: Comprehensive error handling prevents credential exposure

---

## Development

### Project Structure

```
custom_components/waterscope/
├── __init__.py              # Integration setup and coordinator management
├── config_flow.py           # Configuration interface and validation
├── const.py                # Constants, URLs, and exception definitions
├── waterscope.py           # Unified API (WaterscopeAPI) - authentication and data extraction
├── sensor.py               # Home Assistant sensors and data coordinator
├── manifest.json           # Integration metadata
└── strings.json            # UI text and translations

tests/
└── test_standalone_auth.py       # Authentication flow tests
```

### Authentication Implementation Details

For detailed technical information about the authentication flow, see:
- **[`WATERSCOPE_AUTHENTICATION_REPRODUCTION_GUIDE.md`](WATERSCOPE_AUTHENTICATION_REPRODUCTION_GUIDE.md)** - Complete reproduction guide

---

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Submit a pull request

---

## License

This project is licensed under the MIT License - see the LICENSE file for details.

---

## Acknowledgments

- Home Assistant community for integration standards and best practices
- Waterscope for providing the water meter data service
- Azure B2C documentation for OAuth implementation guidance

---

## Support

For issues and questions:

1. Check the [troubleshooting section](#troubleshooting) above
2. Review the authentication reproduction guide for technical details
3. Open an issue on GitHub with debug logs and error details

---

**Successfully tested with real Waterscope credentials - extracting live water usage data (16.81 gallons) via pure HTTP authentication!** 🚀