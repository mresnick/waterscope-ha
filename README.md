# Waterscope Home Assistant Integration

**Pure HTTP authentication system for Waterscope water meter data integration with Home Assistant**

---

## Overview

This Home Assistant integration provides access to Waterscope water meter data without requiring browser automation. The implementation uses a reverse-engineered HTTP authentication flow that programmatically extracts session cookies from username/password credentials.


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