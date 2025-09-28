# Troubleshooting

Common issues and quick solutions for the Waterscope integration.

## Authentication Problems

### Authentication Always Fails
```
Error: Authentication failed: Invalid credentials
```

**Solutions:**
1. **Check credentials** - Login to waterscope.us manually with same username/password
2. **Network issues** - Test: `ping waterscope.us`
3. **Account locked** - Check email for suspension notices
4. **Enable debug logging**:
   ```yaml
   # configuration.yaml
   logger:
     default: warning
     logs:
       custom_components.waterscope: debug
   ```

### Works Initially Then Stops
**Cause:** Session expiration or password changed

**Solutions:**
1. Integration should auto-retry (normal after 24-48 hours)
2. If password changed: Settings → Integrations → Waterscope → Configure
3. If rate limited: Increase polling interval or wait 1 hour

## No Sensor Data

### Sensors Show "Unavailable"
1. **Check authentication** - See above
2. **Dashboard changes** - Waterscope may have changed their HTML
3. **Debug data extraction**:
   ```python
   # Add to water_meter.py temporarily
   _LOGGER.debug("Dashboard HTML: %s", html_content[:500])
   ```

### Some Sensors Missing
**Cause:** HTML element IDs changed

**Check:** Look for elements like `lcd-read_NEW`, `previous-day-consumption` in debug logs

## Integration Issues

### Integration Won't Load
1. **Check file structure**:
   ```bash
   ls custom_components/waterscope/
   # Should have: __init__.py, manifest.json, etc.
   ```

2. **Validate manifest**:
   ```bash
   python -c "import json; print(json.load(open('custom_components/waterscope/manifest.json')))"
   ```

3. **Test imports**:
   ```bash
   python -c "from custom_components.waterscope import water_meter"
   ```

### Setup Fails
```
Error: Unknown error occurred
```

1. Check Home Assistant logs: `/config/home-assistant.log`
2. Restart Home Assistant completely
3. Try removing and re-adding integration

## Performance Issues

### Slow Authentication
- **Increase timeouts** if on slow network
- **Check for multiple rapid attempts** (rate limiting)

### High CPU/Memory
- **Increase polling interval** (default 30 min → 60 min)
- **Check for memory leaks** in logs

## Quick Diagnostics

### Test Authentication
```bash
# Direct test
python custom_components/waterscope/water_meter.py username@example.com password

# With environment variables
export WATERSCOPE_USERNAME="username@example.com"
export WATERSCOPE_PASSWORD="password"
python custom_components/waterscope/water_meter.py $WATERSCOPE_USERNAME $WATERSCOPE_PASSWORD
```

### Check Network
```bash
curl -I https://waterscope.us/Home/Main
nslookup waterscope.us
nslookup metronb2c.b2clogin.com
```

### Monitor Logs
```bash
# Real-time monitoring
tail -f /config/home-assistant.log | grep waterscope

# Search for errors
grep -i error /config/home-assistant.log | grep waterscope
```

## Common Error Messages

| Error | Meaning | Solution |
|-------|---------|----------|
| "Invalid credentials" | Wrong username/password | Verify credentials |
| "Connection timeout" | Network issue | Check connectivity |
| "Could not find LCD reading" | Dashboard changed | Check debug logs |
| "Rate limited" | Too many requests | Increase poll interval |
| "Unknown error" | Various issues | Check HA logs |

## Getting Help

### Information to Collect
1. **Home Assistant version**: Settings → System → About
2. **Integration version**: Check `manifest.json`
3. **Error logs**: With debug logging enabled
4. **Timeline**: When did it stop working?

### Sanitize Logs Before Sharing
```bash
# Remove sensitive data
sed 's/password=[^&]*/password=***MASKED***/g' home-assistant.log
sed 's/username=[^&]*/username=***MASKED***/g' home-assistant.log
```

## Quick Fixes

1. **Restart Integration**: Settings → Integrations → Waterscope → Reload
2. **Restart Home Assistant**: Settings → System → Restart
3. **Re-add Integration**: Remove and add integration again
4. **Clear Browser Cache**: If using HA web interface
5. **Check Credentials**: Login to waterscope.us manually

Most issues are authentication-related or due to Waterscope changing their website. Start with checking credentials and enabling debug logging!