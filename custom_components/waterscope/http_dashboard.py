"""Async HTTP Dashboard API for Waterscope integration."""
import logging
import re
from typing import Optional, Dict, Any
from bs4 import BeautifulSoup
import aiohttp
import asyncio

from .http_auth import WaterscopeHTTPAuthenticator
from .const import WaterscopeAPIError, WaterscopeAuthError

_LOGGER = logging.getLogger(__name__)


class WaterscopeDashboardAPI:
    """Class to handle dashboard data extraction via async HTTP."""

    def __init__(self) -> None:
        """Initialize the dashboard API."""
        self.session = None
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }

    async def authenticate_and_get_lcd_read(self, username: str, password: str) -> Optional[str]:
        """Authenticate and extract LCD read from dashboard using hybrid approach."""
        try:
            _LOGGER.debug("🔄 Starting LCD read extraction for user: %s", username[:3] + "***")
            
            # Step 1: Authenticate and get session cookies
            _LOGGER.debug("Step 1: Authenticating with WaterscopeHTTPAuthenticator...")
            async with WaterscopeHTTPAuthenticator() as auth:
                auth_result = await auth.authenticate(username, password)
                if not auth_result:
                    _LOGGER.error("❌ Authentication failed for LCD read extraction")
                    raise WaterscopeAuthError("Authentication failed")
                
                _LOGGER.debug("✅ Authentication successful, using hybrid approach for dashboard access...")
                
                # Step 2: Use requests session directly (hybrid approach)
                dashboard_url = "https://waterscope.us/Consumer/Consumer/Index"
                _LOGGER.debug("Step 2: Accessing dashboard at %s using requests session", dashboard_url)
                
                def get_dashboard_sync():
                    """Synchronous dashboard access using authenticated requests session."""
                    
                    # Define URLs inside the function
                    homepage_url = "https://waterscope.us/"
                    dashboard_url = "https://waterscope.us/Consumer/Consumer/Index"
                    
                    # First, check if we need to complete OAuth token exchange by accessing the homepage
                    _LOGGER.debug("Checking OAuth status by accessing homepage first...")
                    initial_response = auth.requests_session.get(
                        homepage_url,
                        headers=self.headers,
                        timeout=30,
                        allow_redirects=True
                    )
                    
                    _LOGGER.debug("Homepage response status: %s", initial_response.status_code)
                    _LOGGER.debug("Homepage response URL: %s", initial_response.url)
                    
                    if initial_response.status_code != 200:
                        _LOGGER.error("❌ Homepage access failed: HTTP %s", initial_response.status_code)
                        raise WaterscopeAPIError(f"Homepage access failed: HTTP {initial_response.status_code}")
                    
                    html_content = initial_response.text
                    
                    # Check if we got an OAuth token exchange form that needs to be submitted
                    if 'form id=\'auto\'' in html_content and 'action=\'https://waterscope.us/\'' in html_content:
                        _LOGGER.debug("🔄 Detected OAuth token exchange form, submitting automatically...")
                        
                        # Extract form data from the HTML
                        from bs4 import BeautifulSoup
                        soup = BeautifulSoup(html_content, 'html.parser')
                        form = soup.find('form', {'id': 'auto'})
                        
                        if form:
                            form_data = {}
                            for input_elem in form.find_all('input', {'type': 'hidden'}):
                                name = input_elem.get('name')
                                value = input_elem.get('value')
                                if name and value:
                                    form_data[name] = value
                            
                            _LOGGER.debug("Submitting OAuth token exchange with %s parameters", len(form_data))
                            
                            # Submit the form to complete OAuth flow
                            token_response = auth.requests_session.post(
                                'https://waterscope.us/',
                                data=form_data,
                                headers=self.headers,
                                timeout=30,
                                allow_redirects=True
                            )
                            
                            _LOGGER.debug("Token exchange response status: %s", token_response.status_code)
                            _LOGGER.debug("Token exchange response URL: %s", token_response.url)
                            
                            if token_response.status_code != 200:
                                _LOGGER.error("❌ Token exchange failed: HTTP %s", token_response.status_code)
                                raise WaterscopeAPIError(f"Token exchange failed: HTTP {token_response.status_code}")
                            
                            _LOGGER.debug("✅ OAuth token exchange completed successfully")
                    
                    # Now access the actual dashboard
                    _LOGGER.debug("Accessing dashboard at %s", dashboard_url)
                    dashboard_response = auth.requests_session.get(
                        dashboard_url,
                        headers=self.headers,
                        timeout=30
                    )
                    
                    _LOGGER.debug("Dashboard response status: %s", dashboard_response.status_code)
                    _LOGGER.debug("Dashboard response URL: %s", dashboard_response.url)
                    
                    if dashboard_response.status_code != 200:
                        _LOGGER.error("❌ Dashboard access failed: HTTP %s", dashboard_response.status_code)
                        raise WaterscopeAPIError(f"Dashboard access failed: HTTP {dashboard_response.status_code}")
                    
                    return dashboard_response.text
                
                # Run requests call in thread pool to maintain async compatibility
                html_content = await asyncio.to_thread(get_dashboard_sync)
                _LOGGER.debug("Retrieved dashboard HTML (%s characters)", len(html_content))
                
                # Log full HTML content for debugging
                _LOGGER.info("🔍 DASHBOARD HTML CONTENT (for debugging LCD extraction):")
                _LOGGER.info("=" * 80)
                _LOGGER.info(html_content)
                _LOGGER.info("=" * 80)
                
                # Step 3: Parse HTML and extract LCD read
                _LOGGER.debug("Step 3: Parsing HTML and extracting LCD read...")
                lcd_value = self._extract_lcd_read(html_content)
                _LOGGER.debug("LCD read extraction result: %s", lcd_value)
                
                return lcd_value
            
        except Exception as e:
            _LOGGER.error("Failed to get LCD read: %s", str(e), exc_info=True)
            raise WaterscopeAPIError(f"LCD read extraction failed: {e}") from e

    def _extract_lcd_read(self, html_content: str) -> Optional[str]:
        """Extract LCD read from dashboard HTML."""
        try:
            _LOGGER.debug("🔍 Extracting LCD read from dashboard HTML...")
            _LOGGER.debug("HTML content length: %s characters", len(html_content))
            
            # Log first 2000 characters of HTML for debugging
            _LOGGER.info("🔍 HTML SAMPLE (first 2000 chars): %s", html_content[:2000])
            
            # Check if we have the expected dashboard elements
            if 'lcd-read_NEW' in html_content:
                _LOGGER.info("✅ Found 'lcd-read_NEW' in HTML content")
            else:
                _LOGGER.warning("❌ 'lcd-read_NEW' NOT found in HTML content")
            
            if 'Consumer/Consumer/Index' in html_content or 'Consumer Portal' in html_content:
                _LOGGER.info("✅ Appears to be dashboard page")
            else:
                _LOGGER.warning("❌ Does not appear to be dashboard page")
            
            # Parse HTML with BeautifulSoup
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Method 1: Look for specific LCD read elements from actual HTML structure
            _LOGGER.debug("Method 1: Looking for LCD read elements by ID...")
            selectors = [
                '#lcd-read_NEW',           # Primary LCD read element
                '#lcd-read_NEW_1',         # Secondary LCD read element
                'span[id="lcd-read_NEW"]',
                'span[id="lcd-read_NEW_1"]'
            ]
            
            for selector in selectors:
                element = soup.select_one(selector)
                if element:
                    text = element.get_text(strip=True)
                    if text and text != 'NA' and '.' in text:
                        _LOGGER.info("✅ Found LCD read using selector '%s': %s", selector, text)
                        return text
                    _LOGGER.debug("Found element with selector '%s' but text was: '%s'", selector, text)
            
            # Method 2: Pattern matching for LCD read format (XXXXXX.XX)
            _LOGGER.debug("Method 2: Pattern matching for LCD read format...")
            # Look for patterns like "006456.29" (6 digits, dot, 2 digits)
            pattern = r'\b\d{6}\.\d{2}\b'
            matches = re.findall(pattern, html_content)
            if matches:
                # Filter out any obviously non-LCD values (like coordinates, etc.)
                for match in matches:
                    # LCD reads are typically positive numbers < 999999
                    try:
                        value = float(match)
                        if 0 < value < 999999:
                            _LOGGER.info("✅ Found LCD read using pattern matching: %s", match)
                            return match
                    except ValueError:
                        continue
            
            # Method 3: Search around "LCD Read" text in HTML
            _LOGGER.debug("Method 3: Searching around 'LCD Read' text...")
            lcd_pattern = r'LCD Read[^0-9]*(\d+(?:\.\d+)?)\s*Ft3'
            match = re.search(lcd_pattern, html_content, re.IGNORECASE)
            if match:
                value = match.group(1)
                _LOGGER.info("✅ Found LCD read around 'LCD Read' text: %s", value)
                return value
            
            # Method 4: Look for elements containing "LCD Read"
            _LOGGER.debug("Method 4: Searching elements containing 'LCD Read'...")
            lcd_elements = soup.find_all(string=re.compile(r'LCD Read', re.IGNORECASE))
            _LOGGER.debug("Found %s elements containing 'LCD Read'", len(lcd_elements))
            
            for i, element in enumerate(lcd_elements):
                _LOGGER.debug("Processing LCD element %s", i)
                parent = element.parent if element.parent else element
                # Search within parent and siblings for numeric values
                parent_text = parent.get_text() if hasattr(parent, 'get_text') else str(parent)
                _LOGGER.debug("Parent text: %s", parent_text[:100] + "..." if len(parent_text) > 100 else parent_text)
                
                # Look for numeric patterns in the parent text
                numeric_pattern = r'(\d+(?:\.\d+)?)'
                numbers = re.findall(numeric_pattern, parent_text)
                for number in numbers:
                    try:
                        value = float(number)
                        # LCD reads are reasonable water meter values
                        if 0 < value < 999999 and '.' in number:
                            _LOGGER.info("✅ Found LCD read in parent element: %s", number)
                            return number
                    except ValueError:
                        continue

            _LOGGER.warning("❌ Could not extract LCD read using any method")
            return None
            
        except Exception as e:
            _LOGGER.error("Error extracting LCD read: %s", str(e), exc_info=True)
            return None

    async def get_data(self, username: str, password: str) -> Dict[str, Any]:
        """Get complete data including LCD read."""
        try:
            _LOGGER.debug("🔄 Getting complete dashboard data for user: %s", username[:3] + "***")
            
            lcd_value = await self.authenticate_and_get_lcd_read(username, password)
            
            if lcd_value is None:
                _LOGGER.error("❌ No LCD read found in dashboard")
                raise WaterscopeAPIError("No LCD read found")
            
            _LOGGER.debug("Raw LCD value extracted: %s", lcd_value)
            
            # Convert to float for Home Assistant
            try:
                numeric_value = float(lcd_value)
                _LOGGER.debug("Converted LCD value to float: %s", numeric_value)
            except ValueError as ve:
                _LOGGER.error("❌ Invalid LCD read format: %s", lcd_value)
                raise WaterscopeAPIError(f"Invalid LCD read format: {lcd_value}") from ve
            
            result = {
                'lcd_read': numeric_value,
                'raw_lcd_text': f"{lcd_value} Ft3",
                'status': 'success',
                'timestamp': None  # Will be set by coordinator
            }
            
            _LOGGER.info("✅ Dashboard data retrieval successful: LCD read = %s Ft3", lcd_value)
            return result
            
        except Exception as e:
            _LOGGER.error("Dashboard data retrieval failed: %s", str(e), exc_info=True)
            raise WaterscopeAPIError(f"Data retrieval failed: {e}") from e

    async def close(self):
        """Close the session."""
        if self.session and not self.session.closed:
            await self.session.close()

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()

    def __enter__(self):
        """Sync context manager entry (for compatibility)."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Sync context manager exit (for compatibility)."""
        # Note: Cannot await close() in sync context
        pass