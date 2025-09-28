# Development Setup

Quick setup guide for developing this Home Assistant integration.

## Prerequisites

- Python 3.8+
- Home Assistant for testing
- Git

## Quick Setup

```bash
# Clone and setup
git clone <repository-url>
cd waterscope-ha

# Create virtual environment
python -m venv venv
# Windows: venv\Scripts\activate
# macOS/Linux: source venv/bin/activate

# Install dependencies
pip install homeassistant>=2023.1.0
pip install requests beautifulsoup4 aiohttp

# Development tools
pip install black flake8 pytest pytest-asyncio
```

## Development Environment

### Option 1: Full Home Assistant
```bash
# Create HA config directory
mkdir ha-dev
cd ha-dev
hass --config . --script ensure_config

# Link integration
# Windows (as Admin): mklink /D custom_components\waterscope ..\..\custom_components\waterscope
# macOS/Linux: ln -s $(pwd)/../custom_components/waterscope custom_components/waterscope
```

### Option 2: Quick Testing
```bash
# Test authentication directly
python custom_components/waterscope/water_meter.py username@example.com password
```

## VS Code Setup

Create `.vscode/settings.json`:
```json
{
  "python.defaultInterpreterPath": "./venv/bin/python",
  "python.formatting.provider": "black",
  "editor.formatOnSave": true
}
```

Create `.vscode/launch.json`:
```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "Test Auth",
      "type": "python",
      "request": "launch",
      "program": "${workspaceFolder}/custom_components/waterscope/water_meter.py",
      "args": ["username@example.com", "password"],
      "console": "integratedTerminal"
    }
  ]
}
```

## Development Workflow

```bash
# Format code
black .

# Basic checks
flake8 custom_components/

# Run tests
pytest

# Test with real credentials
export WATERSCOPE_USERNAME="your-email@example.com"
export WATERSCOPE_PASSWORD="your-password"
python custom_components/waterscope/water_meter.py $WATERSCOPE_USERNAME $WATERSCOPE_PASSWORD
```

## Home Assistant Integration Testing

```yaml
# configuration.yaml - Enable debug logging
logger:
  default: warning
  logs:
    custom_components.waterscope: debug
```

```bash
# Start HA with integration
cd ha-dev
hass --config . --debug

# Watch logs
tail -f home-assistant.log | grep waterscope
```

## Common Development Tasks

### Add New Sensor
1. Add sensor class in `coordinator.py`
2. Update data extraction in `water_meter.py`
3. Test with real data
4. Add basic test

### Modify Authentication
1. Update flow in `water_meter.py`
2. Test with real credentials
3. Check error handling

### Debug Issues
```python
# Add temporary debug in water_meter.py
_LOGGER.debug("HTML content: %s", html_content[:500])

# Or use debugger
import pdb; pdb.set_trace()
```

## Testing with Real Service

```bash
# Environment variables for testing
export WATERSCOPE_USERNAME="your-email@example.com"
export WATERSCOPE_PASSWORD="your-password"

# Test authentication
python custom_components/waterscope/water_meter.py $WATERSCOPE_USERNAME $WATERSCOPE_PASSWORD

# Test in Home Assistant
# 1. Install integration
# 2. Configure with real credentials
# 3. Check entities appear
# 4. Verify data updates
```

## Troubleshooting

### Import Errors
```bash
# Check Python environment
python -c "import homeassistant; print('HA OK')"

# Check integration imports
python -c "from custom_components.waterscope import water_meter; print('Integration OK')"
```

### Authentication Issues
```bash
# Test connectivity
curl -I https://waterscope.us/Home/Main

# Check credentials manually
# Login to waterscope.us in browser with same credentials
```

### Home Assistant Issues
```bash
# Check manifest syntax
python -c "import json; print(json.load(open('custom_components/waterscope/manifest.json')))"

# Restart HA completely after changes
```

Keep it simple - focus on getting authentication working and data flowing!