"""
Lightweight HTTP-based Waterscope API for Home Assistant.
Uses manually provided session cookies instead of browser automation.
"""

import logging
import re
import json
import asyncio
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from bs4 import BeautifulSoup

_LOGGER = logging.getLogger(__name__)

class WaterscopeHTTPAPIError(Exception):
    """Base exception for Waterscope HTTP API errors."""
    pass

class WaterscopeAuthError(WaterscopeHTTPAPIError):
    """Authentication error."""
    pass

class WaterscopeHTTPAPI:
    """Waterscope API using HTTP requests with session cookies."""
    
    def __init__(self, session_cookies: str, csrf_token: Optional[str] = None):
        """
        Initialize the HTTP API client.
        
        Args:
            session_cookies: Session cookies as a string (e.g., "cookie1=value1; cookie2=value2")
            csrf_token: Optional CSRF token if required
        """
        self.session_cookies = session_cookies
        self.csrf_token = csrf_token
        self.session = None
        self.authenticated = False
        self._last_data = None
        
    def __enter__(self):
        """Context manager entry."""
        self._setup_session()
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self._cleanup()
        
    async def __aenter__(self):
        """Async context manager entry."""
        self._setup_session()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        self._cleanup()
    
    def _setup_session(self):
        """Setup HTTP session with cookies and headers."""
        try:
            self.session = requests.Session()
            
            # Use basic HTTPAdapter without retry strategy to avoid urllib3 version issues
            adapter = HTTPAdapter(max_retries=0)  # Disable retries completely
            self.session.mount("http://", adapter)
            self.session.mount("https://", adapter)
            
            # Set headers to mimic a real browser
            self.session.headers.update({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Cache-Control': 'max-age=0'
            })
            
            # Parse and set cookies
            self._set_cookies()
            
            # Add CSRF token to headers if provided
            if self.csrf_token:
                self.session.headers.update({
                    'X-CSRF-Token': self.csrf_token,
                    'X-Requested-With': 'XMLHttpRequest'
                })
            
            _LOGGER.info("✅ HTTP session setup complete")
            
        except Exception as e:
            _LOGGER.error(f"Failed to setup HTTP session: {e}")
            raise WaterscopeHTTPAPIError(f"Session setup failed: {e}")
    
    def _set_cookies(self):
        """Parse and set session cookies."""
        try:
            if not self.session_cookies:
                raise WaterscopeHTTPAPIError("No session cookies provided")
            
            # Parse cookie string
            cookie_pairs = [cookie.strip() for cookie in self.session_cookies.split(';')]
            
            for pair in cookie_pairs:
                if '=' in pair:
                    name, value = pair.split('=', 1)
                    self.session.cookies.set(name.strip(), value.strip(), domain='waterscope.us')
            
            _LOGGER.info(f"✅ Set {len(cookie_pairs)} cookies")
            
        except Exception as e:
            _LOGGER.error(f"Failed to set cookies: {e}")
            raise WaterscopeHTTPAPIError(f"Cookie setup failed: {e}")
    
    def _cleanup(self):
        """Cleanup session resources."""
        try:
            if self.session:
                self.session.close()
            self.session = None
            self.authenticated = False
            _LOGGER.info("🧹 HTTP session cleaned up")
        except Exception as e:
            _LOGGER.warning(f"Error during cleanup: {e}")
    
    async def verify_authentication(self) -> bool:
        """
        Verify that the provided cookies are valid by checking dashboard access.
        
        Returns:
            True if authentication is valid
        """
        try:
            _LOGGER.debug("🔐 Verifying session authentication...")
            _LOGGER.debug("Session cookies length: %s", len(self.session_cookies) if self.session_cookies else 0)
            
            # Try to access the dashboard using asyncio.to_thread to avoid blocking
            _LOGGER.debug("Requesting dashboard page for authentication verification...")
            response = await asyncio.to_thread(
                self.session.get,
                "https://waterscope.us/Dashboard",
                timeout=30,
                allow_redirects=True
            )
            
            _LOGGER.debug("Authentication verification response: %s", response.status_code)
            _LOGGER.debug("Authentication verification URL: %s", response.url)
            _LOGGER.debug("Response headers: %s", dict(response.headers))
            
            # Check if we got redirected to login page
            if "Home/Main" in response.url or "login" in response.url.lower():
                _LOGGER.error("❌ Redirected to login page - cookies are invalid or expired")
                _LOGGER.debug("Final URL indicates login redirect: %s", response.url)
                self.authenticated = False
                return False
            
            # Check for successful dashboard page indicators
            if response.status_code == 200:
                _LOGGER.debug("Got 200 response, checking dashboard content...")
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Look for dashboard indicators
                dashboard_indicators = [
                    soup.find('a', href=lambda x: x and 'Dashboard' in x),
                    soup.find(text=re.compile(r'dashboard', re.I)),
                    soup.find('div', class_=re.compile(r'meter|reading|usage', re.I)),
                    soup.find('canvas'),  # Charts
                    soup.find('table')    # Data tables
                ]
                
                _LOGGER.debug("Dashboard indicators found: %s", [bool(indicator) for indicator in dashboard_indicators])
                
                if any(indicator for indicator in dashboard_indicators):
                    _LOGGER.info("🎉 Authentication verification successful!")
                    self.authenticated = True
                    return True
            
            _LOGGER.error("❌ Dashboard page doesn't contain expected content")
            _LOGGER.debug("Page content sample (first 500 chars): %s", response.text[:500])
            self.authenticated = False
            return False
            
        except Exception as e:
            _LOGGER.error("Authentication verification error: %s", str(e), exc_info=True)
            self.authenticated = False
            return False
    
    async def get_data(self) -> Optional[Dict[str, Any]]:
        """
        Fetch comprehensive water usage data from Waterscope.
        
        Returns:
            Dictionary containing water usage data
        """
        try:
            _LOGGER.debug("📊 Fetching Waterscope data...")
            
            # First verify authentication
            _LOGGER.debug("Verifying authentication before data fetch...")
            if not await self.verify_authentication():
                _LOGGER.error("❌ Authentication failed - cookies may be expired")
                raise WaterscopeAuthError("Authentication failed - cookies may be expired")
            
            _LOGGER.debug("✅ Authentication verified, fetching dashboard page...")
            
            # Fetch dashboard page using asyncio.to_thread to avoid blocking
            response = await asyncio.to_thread(
                self.session.get,
                "https://waterscope.us/Dashboard",
                timeout=30
            )
            
            _LOGGER.debug("Dashboard fetch response: %s", response.status_code)
            _LOGGER.debug("Dashboard fetch URL: %s", response.url)
            
            if response.status_code != 200:
                _LOGGER.error("❌ Dashboard request failed with status %s", response.status_code)
                raise WaterscopeHTTPAPIError(f"Dashboard request failed with status {response.status_code}")
            
            _LOGGER.debug("✅ Dashboard page fetched successfully, parsing HTML...")
            
            # Parse the HTML content
            soup = BeautifulSoup(response.text, 'html.parser')
            _LOGGER.debug("HTML parsed, extracting data...")
            
            # Extract data using the same patterns as the Playwright version
            raw_data = self._extract_data_from_html(soup, response.text)
            _LOGGER.debug("Raw data extracted: %s", raw_data.keys())
            
            # Process the extracted data
            _LOGGER.debug("Processing extracted data...")
            processed_data = await self._process_extracted_data(raw_data)
            _LOGGER.debug("Data processing complete: %s", processed_data.keys())
            
            self._last_data = processed_data
            _LOGGER.info("✅ Data fetched and processed successfully")
            return processed_data
            
        except WaterscopeAuthError:
            _LOGGER.error("Authentication error during data fetch")
            raise
        except Exception as e:
            _LOGGER.error("Data fetch error: %s", str(e), exc_info=True)
            raise WaterscopeHTTPAPIError(f"Failed to fetch data: {e}")
    
    def _extract_data_from_html(self, soup: BeautifulSoup, page_text: str) -> Dict[str, Any]:
        """Extract data from HTML using BeautifulSoup (mimicking the Playwright extraction)."""
        result = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'status': 'connected',
            'url': 'https://waterscope.us/Dashboard',
            'readings': {},
            'billing': {},
            'usage': {},
            'errors': []
        }
        
        try:
            # Look for current meter reading
            meter_selectors = [
                '[class*="meter"]',
                '[class*="reading"]', 
                '[class*="current"]',
                '[id*="meter"]',
                '[id*="reading"]'
            ]
            
            for selector_pattern in meter_selectors:
                # Convert CSS selector to BeautifulSoup find parameters
                if 'class*=' in selector_pattern:
                    class_pattern = selector_pattern.split('class*="')[1].split('"')[0]
                    elements = soup.find_all(attrs={'class': re.compile(class_pattern, re.I)})
                elif 'id*=' in selector_pattern:
                    id_pattern = selector_pattern.split('id*="')[1].split('"')[0]
                    elements = soup.find_all(attrs={'id': re.compile(id_pattern, re.I)})
                else:
                    continue
                
                for element in elements:
                    text = element.get_text(strip=True) if element else ''
                    numbers = re.findall(r'[\d,]+\.?\d*', text)
                    if numbers:
                        result['readings']['raw_text'] = text
                        result['readings']['extracted_numbers'] = numbers
                        break
                        
                if result['readings']:
                    break
            
            # Look for billing period information
            billing_keywords = ['billing', 'period', 'cycle']
            for keyword in billing_keywords:
                elements = soup.find_all(text=re.compile(keyword, re.I))
                for element in elements:
                    if hasattr(element, 'parent'):
                        parent_text = element.parent.get_text(strip=True)
                        if any(kw in parent_text.lower() for kw in billing_keywords):
                            result['billing']['period_text'] = parent_text
                            break
                if result['billing']:
                    break
            
            # Look for usage charts or data
            charts = soup.find_all(['canvas', 'svg'])
            if charts:
                result['usage']['charts_found'] = len(charts)
                result['usage']['chart_types'] = [chart.name for chart in charts]
            
            # Look for tables with data
            tables = soup.find_all('table')
            if tables:
                result['usage']['tables_found'] = len(tables)
                result['usage']['table_data'] = []
                
                for idx, table in enumerate(tables):
                    rows = table.find_all('tr')
                    if rows:
                        table_data = []
                        for row in rows:
                            cells = row.find_all(['td', 'th'])
                            cell_data = [cell.get_text(strip=True) for cell in cells]
                            if cell_data:  # Only add non-empty rows
                                table_data.append(cell_data)
                        
                        if table_data:
                            result['usage']['table_data'].append({
                                'table_index': idx,
                                'rows': table_data
                            })
            
            # Store page text for pattern analysis
            result['page_text'] = soup.get_text()
            
        except Exception as error:
            result['errors'].append(f'HTML extraction error: {str(error)}')
            _LOGGER.warning(f"Error during HTML extraction: {error}")
        
        return result
    
    async def _process_extracted_data(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process and clean the extracted data (same logic as Playwright version)."""
        processed = {
            'timestamp': raw_data.get('timestamp'),
            'status': 'success',
            'current_reading': None,
            'daily_usage': None,
            'billing_period': None,
            'usage_history': [],
            'raw_data': raw_data
        }
        
        try:
            # Extract current reading from various sources
            if 'readings' in raw_data and 'extracted_numbers' in raw_data['readings']:
                numbers = raw_data['readings']['extracted_numbers']
                if numbers:
                    # Try to find the largest number (likely the meter reading)
                    numeric_values = []
                    for num_str in numbers:
                        try:
                            # Remove commas and convert to float
                            clean_num = float(num_str.replace(',', ''))
                            numeric_values.append(clean_num)
                        except ValueError:
                            continue
                    
                    if numeric_values:
                        processed['current_reading'] = max(numeric_values)
            
            # Extract usage data from tables
            if 'usage' in raw_data and 'table_data' in raw_data['usage']:
                for table in raw_data['usage']['table_data']:
                    for row in table['rows']:
                        if len(row) >= 2:
                            # Look for date/usage patterns
                            date_patterns = [
                                r'\d{1,2}[/-]\d{1,2}[/-]\d{2,4}',
                                r'\d{4}-\d{2}-\d{2}',
                                r'[A-Za-z]{3}\s+\d{1,2}'
                            ]
                            
                            for cell in row:
                                for pattern in date_patterns:
                                    if re.search(pattern, cell):
                                        # Found a potential date row
                                        usage_row = {
                                            'date': cell,
                                            'values': [c for c in row if c != cell and re.search(r'\d+\.?\d*', c)]
                                        }
                                        if usage_row['values']:
                                            processed['usage_history'].append(usage_row)
                                        break
            
            # Extract billing period
            if 'billing' in raw_data and 'period_text' in raw_data['billing']:
                processed['billing_period'] = raw_data['billing']['period_text']
            
            # Analyze page text for additional insights
            page_text = raw_data.get('page_text', '')
            
            # Look for daily usage patterns
            daily_usage_patterns = [
                r'daily.*?(\d+\.?\d*)\s*gallons?',
                r'(\d+\.?\d*)\s*gallons?.*?today',
                r'usage.*?(\d+\.?\d*)\s*gal'
            ]
            
            for pattern in daily_usage_patterns:
                match = re.search(pattern, page_text.lower())
                if match:
                    try:
                        processed['daily_usage'] = float(match.group(1))
                        break
                    except (ValueError, IndexError):
                        continue
                        
        except Exception as e:
            _LOGGER.warning(f"Error processing extracted data: {e}")
            processed['status'] = 'partial'
        
        return processed
    
    async def get_health_status(self) -> Dict[str, Any]:
        """Get health status of the API service."""
        return {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'session_available': self.session is not None,
            'authenticated': self.authenticated,
            'last_data_timestamp': self._last_data.get('timestamp') if self._last_data else None,
            'status': 'healthy' if self.authenticated else 'not_authenticated'
        }

# Convenience function for testing
async def test_waterscope_http_api(session_cookies: str, csrf_token: Optional[str] = None) -> bool:
    """
    Test function for Waterscope HTTP API.
    
    Args:
        session_cookies: Session cookies string
        csrf_token: Optional CSRF token
        
    Returns:
        True if authentication and data fetch successful
    """
    async with WaterscopeHTTPAPI(session_cookies, csrf_token) as api:
        if await api.verify_authentication():
            data = await api.get_data()
            return data is not None
        return False