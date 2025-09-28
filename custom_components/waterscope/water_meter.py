"""
Unified Waterscope API combining authentication and dashboard data extraction.
Pure HTTP implementation eliminating browser automation dependencies.
"""

import re
import logging
import urllib.parse
from typing import Optional, Dict, Any, Tuple
import aiohttp
import asyncio
from bs4 import BeautifulSoup
import requests
from requests.adapters import HTTPAdapter

# Handle both package and standalone imports
try:
    from .const import WaterscopeError, WaterscopeAPIError, WaterscopeAuthError
except ImportError:
    # Fallback for standalone execution
    class WaterscopeError(Exception):
        """Base exception for Waterscope errors."""
        pass

    class WaterscopeAPIError(WaterscopeError):
        """Exception for API-related errors."""
        pass

    class WaterscopeAuthError(WaterscopeError):
        """Exception for authentication-related errors."""
        pass

_LOGGER = logging.getLogger(__name__)

def _log_request_details(method: str, url: str, headers: Dict, data: Any = None, params: Dict = None):
    """Log comprehensive request details."""
    print(f"\n🔵 === {method.upper()} REQUEST ===")
    print(f"URL: {url}")
    if params:
        print(f"PARAMS: {params}")
    print("HEADERS:")
    for key, value in sorted(headers.items()):
        print(f"  {key}: {value}")
    if data:
        if isinstance(data, str):
            print(f"DATA (string): {data}")
        elif isinstance(data, dict):
            print(f"DATA (dict): {data}")
        else:
            print(f"DATA (type {type(data)}): {data}")
    print("=" * 50)

def _log_response_details(response, content: str = None):
    """Log comprehensive response details."""
    print(f"\n🔴 === RESPONSE ===")
    
    # Handle both aiohttp and requests response objects
    if hasattr(response, 'status'):
        print(f"STATUS: {response.status}")
    elif hasattr(response, 'status_code'):
        print(f"STATUS: {response.status_code}")
    
    print(f"URL: {response.url}")
    print("HEADERS:")
    for key, value in sorted(response.headers.items()):
        print(f"  {key}: {value}")
    
    if hasattr(response, 'cookies') and response.cookies:
        print("COOKIES:")
        for cookie in response.cookies:
            if hasattr(cookie, 'key'):
                print(f"  {cookie.key}")
            elif hasattr(cookie, 'name'):
                print(f"  {cookie.name}")
            else:
                print(f"  {cookie}")
    
    if content:
        print(f"CONTENT (first 500 chars):")
        print(content[:500])
        if len(content) > 500:
            print("... (truncated)")
    print("=" * 50)


class WaterscopeAPI:
    """Unified Waterscope API for authentication and dashboard data extraction."""
    
    def __init__(self):
        self.session = None
        self.requests_session = None
        self.authenticated = False
        self._auth_cookies = {}
        
        # OAuth configuration from captured traffic
        self.oauth_config = {
            'tenant': 'metronb2c.onmicrosoft.com',
            'policy': 'B2C_1_mainsso_web', 
            'client_id': '57f60f76-c91d-404d-8f70-828b0f958a83',
            'redirect_uri': 'https://waterscope.us/',
            'response_type': 'code id_token',
            'response_mode': 'form_post',
            'scope': 'openid profile offline_access https://metronb2c.onmicrosoft.com/57f60f76-c91d-404d-8f70-828b0f958a83/read https://metronb2c.onmicrosoft.com/57f60f76-c91d-404d-8f70-828b0f958a83/write'
        }
        
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
    
    async def __aenter__(self):
        """Async context manager entry."""
        await self._setup_session()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self._cleanup()
    
    async def _setup_session(self):
        """Setup async HTTP session with browser-like configuration."""
        try:
            # Setup timeout and connection configuration
            timeout = aiohttp.ClientTimeout(total=30, connect=10)
            connector = aiohttp.TCPConnector(
                limit=100,
                limit_per_host=30,
                enable_cleanup_closed=True,
                force_close=True,  # Force connection close to match requests behavior
                use_dns_cache=False  # Disable DNS caching for more precise control
            )
            
            # Set browser-like headers
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept-Encoding': 'gzip, deflate',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Cache-Control': 'max-age=0'
            }
            
            # Force HTTP/1.1 to match working requests implementation
            self.session = aiohttp.ClientSession(
                timeout=timeout,
                connector=connector,
                headers=headers,
                cookie_jar=aiohttp.CookieJar(),
                version=aiohttp.HttpVersion11  # Critical: Force HTTP/1.1
            )
            
            _LOGGER.info("✅ Async HTTP session setup complete")
            
        except Exception as e:
            _LOGGER.error(f"Failed to setup async HTTP session: {e}")
            raise
    
    async def _cleanup(self):
        """Cleanup async session resources."""
        try:
            if self.session:
                await self.session.close()
            self.session = None
            self.authenticated = False
            self._auth_cookies = {}
            _LOGGER.info("🧹 Async HTTP session cleaned up")
        except Exception as e:
            _LOGGER.warning(f"Error during cleanup: {e}")
    
    async def authenticate(self, username: str, password: str) -> bool:
        """
        Authenticate with Waterscope using pure HTTP requests.
        
        Args:
            username: Waterscope username/email
            password: Waterscope password
            
        Returns:
            True if authentication successful
        """
        try:
            _LOGGER.info("🔐 Starting HTTP-only Waterscope authentication for user: %s", username[:3] + "***")
            _LOGGER.debug("Full authentication flow beginning...")
            
            # Step 1: Load initial login page
            _LOGGER.debug("Step 1: Loading initial login page")
            login_page_response = await self._load_login_page()
            _LOGGER.debug("Step 1 completed successfully")
            
            # Step 2: Submit username and get OAuth redirect
            _LOGGER.debug("Step 2: Submitting username")
            oauth_url = await self._submit_username(username)
            _LOGGER.debug("Step 2 completed, OAuth URL: %s", oauth_url[:50] + "...")
            
            # Step 3: Load Azure B2C login page and extract CSRF tokens
            _LOGGER.debug("Step 3: Loading OAuth page and extracting tokens")
            csrf_token, tx_state = await self._load_oauth_page(oauth_url)
            _LOGGER.debug("Step 3 completed, CSRF token: %s..., TX state: %s", csrf_token[:10], tx_state[:20] if tx_state else "None")
            
            # Step 4: Submit password to Azure B2C
            _LOGGER.debug("Step 4: Submitting password to Azure B2C")
            confirm_url = await self._submit_password(username, password, csrf_token, tx_state)
            _LOGGER.debug("Step 4 completed, confirm URL: %s", confirm_url[:50] + "...")
            
            # Step 5: Complete Azure B2C confirmation
            _LOGGER.debug("Step 5: Completing OAuth confirmation")
            auth_data = await self._complete_oauth_confirmation(confirm_url, csrf_token, tx_state)
            _LOGGER.debug("Step 5 completed, auth data keys: %s", list(auth_data.keys()) if auth_data else "None")
            
            # Step 6: Submit auth code and tokens back to Waterscope
            _LOGGER.debug("Step 6: Completing token exchange")
            success = await self._complete_token_exchange(auth_data)
            _LOGGER.debug("Step 6 completed, success: %s", success)
            
            if success:
                self.authenticated = True
                _LOGGER.info("🎉 HTTP authentication successful!")
                _LOGGER.debug("Authentication cookies available: %s", len(self._auth_cookies))
                return True
            else:
                _LOGGER.error("❌ Authentication failed in final step")
                return False
                
        except Exception as e:
            _LOGGER.error("Authentication error: %s", str(e), exc_info=True)
            _LOGGER.debug("Authentication failed at step, rolling back...")
            self.authenticated = False
            return False
    
    async def _load_login_page(self) -> aiohttp.ClientResponse:
        """Load the initial Waterscope login page."""
        _LOGGER.debug("📍 Loading initial login page...")
        
        url = "https://waterscope.us/Home/Main"
        headers = dict(self.session.headers)
        _LOGGER.debug("Login page request URL: %s", url)
        _LOGGER.debug("Login page request headers: %s", headers)
        _log_request_details("GET", url, headers)
        
        async with self.session.get(url, allow_redirects=True) as response:
            content = await response.text()
            _LOGGER.debug("Login page response status: %s", response.status)
            _LOGGER.debug("Login page response URL: %s", response.url)
            _LOGGER.debug("Login page response headers: %s", dict(response.headers))
            _LOGGER.debug("Login page content length: %s", len(content))
            _log_response_details(response, content)
            
            if response.status != 200:
                _LOGGER.error("Failed to load login page: %s", response.status)
                raise RuntimeError(f"Failed to load login page: {response.status}")
                
            _LOGGER.debug("✅ Login page loaded successfully")
            return response
    
    async def _submit_username(self, username: str) -> str:
        """Submit username and capture OAuth redirect URL."""
        _LOGGER.debug("📝 Submitting username: %s", username[:3] + "***")
        
        # Submit username form - use simple dict like original working implementation
        form_data = {'txtSearchUserName': username}
        _LOGGER.debug("🔍 Username form data: %s", form_data)
        
        url = "https://waterscope.us/Home/Main"
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'Origin': 'https://waterscope.us',
            'Referer': 'https://waterscope.us/Home/Main'
        }
        headers.update(dict(self.session.headers))
        _LOGGER.debug("Username submission headers: %s", headers)
        _log_request_details("POST", url, headers, form_data)
        
        async with self.session.post(
            url,
            data=form_data,
            headers={
                'Content-Type': 'application/x-www-form-urlencoded',
                'Origin': 'https://waterscope.us',
                'Referer': 'https://waterscope.us/Home/Main'
            },
            allow_redirects=False
        ) as response:
            
            content = await response.text()
            _LOGGER.debug("Username submission response status: %s", response.status)
            _LOGGER.debug("Username submission response headers: %s", dict(response.headers))
            _log_response_details(response, content)
            
            # Extract OAuth redirect URL from response
            if response.status in (302, 303):
                oauth_url = response.headers.get('Location')
                _LOGGER.debug("Found redirect location: %s", oauth_url)
                if oauth_url and 'b2clogin.com' in oauth_url:
                    _LOGGER.debug("✅ Username submitted, got OAuth redirect")
                    return oauth_url
            
            # Parse response for redirect information
            response_text = await response.text()
            soup = BeautifulSoup(response_text, 'html.parser')
            _LOGGER.debug("Parsing response HTML for OAuth redirect...")
            
            # Look for meta refresh or JavaScript redirects
            meta_refresh = soup.find('meta', attrs={'http-equiv': re.compile(r'refresh', re.I)})
            if meta_refresh:
                content = meta_refresh.get('content', '')
                _LOGGER.debug("Found meta refresh: %s", content)
                url_match = re.search(r'url=(.+)', content, re.I)
                if url_match:
                    oauth_url = url_match.group(1)
                    _LOGGER.debug("✅ Found OAuth redirect in meta refresh: %s", oauth_url)
                    return oauth_url
            
            # Look for form action that redirects to Azure B2C
            forms = soup.find_all('form')
            _LOGGER.debug("Found %s forms in response", len(forms))
            for i, form in enumerate(forms):
                action = form.get('action', '')
                _LOGGER.debug("Form %s action: %s", i, action)
                if 'b2clogin.com' in action:
                    _LOGGER.debug("✅ Found OAuth form action: %s", action)
                    return action
            
            _LOGGER.error("Could not find OAuth redirect URL in response")
            raise RuntimeError("Could not find OAuth redirect URL")
    
    async def _load_oauth_page(self, oauth_url: str) -> Tuple[str, str]:
        """Load Azure B2C OAuth page and extract CSRF tokens."""
        _LOGGER.info("🔗 Loading Azure B2C OAuth page...")
        
        headers = {'Referer': 'https://waterscope.us/'}
        headers.update(dict(self.session.headers))
        _log_request_details("GET", oauth_url, headers)
        
        async with self.session.get(
            oauth_url,
            headers={'Referer': 'https://waterscope.us/'},
            allow_redirects=True
        ) as response:
            
            response_text = await response.text()
            _log_response_details(response, response_text)
            
            if response.status != 200:
                raise RuntimeError(f"Failed to load OAuth page: {response.status}")
            
            # Store the current OAuth page URL for later use
            self.oauth_page_url = str(response.url)
            _LOGGER.info(f"OAuth page URL: {self.oauth_page_url}")
            
            # Extract CSRF token from cookies
            csrf_token = None
            for cookie in self.session.cookie_jar:
                if 'x-ms-cpim-csrf' in cookie.key:
                    csrf_token = cookie.value
                    break
            
            if not csrf_token:
                raise RuntimeError("Could not find CSRF token in cookies")
            
            # Extract transaction state from URL parameters
            tx_state = None
            url_params = urllib.parse.parse_qs(urllib.parse.urlparse(str(response.url)).query)
            if 'tx' in url_params:
                tx_state = url_params['tx'][0]
            
            _LOGGER.info(f"✅ Extracted CSRF token: {csrf_token[:10]}... and transaction state: {tx_state}")
            
            if not tx_state:
                _LOGGER.warning("⚠️ No transaction state found - using CSRF token as fallback")
                tx_state = csrf_token
            
            return csrf_token, tx_state
    
    async def _submit_password(self, username: str, password: str, csrf_token: str, tx_state: str) -> str:
        """Submit password to Azure B2C using hybrid approach (requests via asyncio.to_thread)."""
        _LOGGER.debug("🔑 Submitting password to Azure B2C (hybrid approach)...")
        _LOGGER.debug("Password submission for user: %s", username[:3] + "***")
        _LOGGER.debug("CSRF token: %s...", csrf_token[:10])
        _LOGGER.debug("TX state: %s", tx_state[:20] if tx_state else "None")
        
        # Use the exact URL from the OAuth page for the password submission
        referer_url = getattr(self, 'oauth_page_url', 'https://metronb2c.b2clogin.com/')
        _LOGGER.debug("Referer URL: %s", referer_url)
        
        # Extract essential cookies for Azure B2C
        essential_cookies = {}
        for cookie in self.session.cookie_jar:
            if 'x-ms-cpim' in cookie.key.lower():
                essential_cookies[cookie.key] = cookie.value
        _LOGGER.debug("Essential cookies extracted: %s", list(essential_cookies.keys()))
        
        # Use asyncio.to_thread to run synchronous requests call in async context
        _LOGGER.debug("Calling synchronous password submission via asyncio.to_thread...")
        confirm_url, updated_session = await asyncio.to_thread(
            self._submit_password_sync,
            username, password, csrf_token, tx_state, referer_url, essential_cookies
        )
        
        # Store the updated session for use in OAuth confirmation and dashboard access
        self._password_session = updated_session
        self.requests_session = updated_session
        _LOGGER.debug("Password submission completed, confirm URL: %s", confirm_url[:50] + "...")
        
        return confirm_url
    
    def _submit_password_sync(self, username: str, password: str, csrf_token: str, tx_state: str,
                             referer_url: str, essential_cookies: dict) -> tuple:
        """Synchronous Azure B2C password submission using requests."""
        
        _LOGGER.debug("🔧 Using synchronous requests for Azure B2C compatibility")
        _LOGGER.debug("Sync password submission starting for user: %s", username[:3] + "***")
        
        # Create requests session with minimal headers (matching working implementation)
        sync_session = requests.Session()
        
        # Use basic HTTPAdapter without retry strategy to avoid urllib3 version issues
        adapter = HTTPAdapter(max_retries=0)  # Disable retries completely
        sync_session.mount("http://", adapter)
        sync_session.mount("https://", adapter)
        
        # Add essential cookies
        for key, value in essential_cookies.items():
            sync_session.cookies.set(key, value)
        
        # Use the working approach 1 for Azure B2C password submission
        _LOGGER.info("🔄 Submitting password to Azure B2C")
        
        # Essential headers only (matching successful requests implementation)
        azure_headers = {
            'Accept': 'application/json, text/javascript, */*; q=0.01',
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'X-CSRF-TOKEN': csrf_token,
            'X-Requested-With': 'XMLHttpRequest',
            'Origin': 'https://metronb2c.b2clogin.com',
            'Referer': referer_url
        }
        
        url = "https://metronb2c.b2clogin.com/metronb2c.onmicrosoft.com/B2C_1_mainsso_web/SelfAsserted"
        params = {'tx': tx_state, 'p': 'B2C_1_mainsso_web'}
        data = {'request_type': 'RESPONSE', 'email': username, 'password': password}
        
        _log_request_details("POST", url, azure_headers, data, params)
        
        try:
            response = sync_session.post(
                url,
                params=params,
                data=data,
                headers=azure_headers
            )
            
            _log_response_details(response, response.text)
            _LOGGER.info(f"Password submission response: {response.status_code}")
            
            if response.status_code == 200:
                _LOGGER.info("✅ Password submitted successfully")
                # Construct confirmation URL
                confirm_url = f"https://metronb2c.b2clogin.com/metronb2c.onmicrosoft.com/B2C_1_mainsso_web/api/CombinedSigninAndSignup/confirmed"
                
                # Transfer response cookies back to main aiohttp session
                for cookie in sync_session.cookies:
                    self.session.cookie_jar.update_cookies({cookie.name: cookie.value})
                
                # Return both the confirm URL and the updated session with new cookies
                return confirm_url, sync_session
            else:
                raise RuntimeError(f"Password submission failed: {response.status_code} - {response.text[:200]}")
                
        except Exception as e:
            _LOGGER.error(f"Password submission error: {e}")
            raise RuntimeError(f"Password submission failed: {e}")
    
    async def _complete_oauth_confirmation(self, confirm_url: str, csrf_token: str, tx_state: str) -> Dict[str, str]:
        """Complete OAuth confirmation using hybrid approach (requests via asyncio.to_thread)."""
        _LOGGER.info("✅ Completing OAuth confirmation (hybrid approach)...")
        
        # Use the session with updated cookies from password submission
        password_session = getattr(self, '_password_session', None)
        if not password_session:
            # Fallback: extract essential cookies from main session
            essential_cookies = {}
            for cookie in self.session.cookie_jar:
                if 'x-ms-cpim' in cookie.key.lower():
                    essential_cookies[cookie.key] = cookie.value
            
            # Use asyncio.to_thread to run synchronous requests call in async context
            result = await asyncio.to_thread(
                self._complete_oauth_confirmation_sync,
                confirm_url, csrf_token, tx_state, essential_cookies
            )
        else:
            # Use the session that already has the updated cookies from password submission
            result = await asyncio.to_thread(
                self._complete_oauth_confirmation_with_session,
                confirm_url, csrf_token, tx_state, password_session
            )
        
        return result
    
    def _complete_oauth_confirmation_sync(self, confirm_url: str, csrf_token: str, tx_state: str,
                                        essential_cookies: dict) -> Dict[str, str]:
        """Synchronous OAuth confirmation using requests."""
        
        _LOGGER.info("🔧 Using synchronous requests for OAuth confirmation compatibility")
        
        # Create requests session with minimal headers
        sync_session = requests.Session()
        
        # Use basic HTTPAdapter without retry strategy to avoid urllib3 version issues
        adapter = HTTPAdapter(max_retries=0)  # Disable retries completely
        sync_session.mount("http://", adapter)
        sync_session.mount("https://", adapter)
        
        # Add essential cookies
        for key, value in essential_cookies.items():
            sync_session.cookies.set(key, value)
        
        # Use the working approach 1 for OAuth confirmation
        _LOGGER.info("🔄 Completing OAuth confirmation")
        
        params = {
            'rememberMe': 'false',
            'csrf_token': csrf_token,
            'state': tx_state,
            'p': 'B2C_1_mainsso_web',
            'diags': '{"pageViewId":"generated-uuid","pageId":"CombinedSigninAndSignup","trace":[]}'
        }
        
        try:
            response = sync_session.get(
                confirm_url,
                params=params,
                allow_redirects=True
            )
            
            _log_response_details(response, response.text)
            _LOGGER.info(f"OAuth confirmation response: {response.status_code}")
            
            if response.status_code == 200:
                # Parse response for form data that will be posted back to Waterscope
                soup = BeautifulSoup(response.text, 'html.parser')
                form = soup.find('form')
                
                if form:
                    # Extract form data
                    auth_data = {}
                    for input_elem in form.find_all('input'):
                        name = input_elem.get('name')
                        value = input_elem.get('value')
                        if name and value:
                            auth_data[name] = value
                    
                    if auth_data:
                        _LOGGER.info("✅ OAuth confirmation completed successfully")
                        
                        # Transfer response cookies back to main aiohttp session
                        for cookie in sync_session.cookies:
                            self.session.cookie_jar.update_cookies({cookie.name: cookie.value})
                        
                        return auth_data
                else:
                    raise RuntimeError("No form found in OAuth confirmation response")
            else:
                raise RuntimeError(f"OAuth confirmation failed: {response.status_code} - {response.text[:200]}")
                
        except Exception as e:
            _LOGGER.error(f"OAuth confirmation error: {e}")
            raise RuntimeError(f"OAuth confirmation failed: {e}")
    
    def _complete_oauth_confirmation_with_session(self, confirm_url: str, csrf_token: str, tx_state: str,
                                                 sync_session: requests.Session) -> Dict[str, str]:
        """Synchronous OAuth confirmation using existing requests session with updated cookies."""
        
        _LOGGER.info("🔧 Using existing sync session with updated cookies for OAuth confirmation")
        
        # Use the working approach 1 for OAuth confirmation with existing session
        _LOGGER.info("🔄 Completing OAuth confirmation with existing session")
        
        params = {
            'rememberMe': 'false',
            'csrf_token': csrf_token,
            'state': tx_state,
            'p': 'B2C_1_mainsso_web',
            'diags': '{"pageViewId":"generated-uuid","pageId":"CombinedSigninAndSignup","trace":[]}'
        }
        
        try:
            response = sync_session.get(
                confirm_url,
                params=params,
                allow_redirects=True
            )
            
            _log_response_details(response, response.text)
            _LOGGER.info(f"OAuth confirmation response: {response.status_code}")
            
            if response.status_code == 200:
                # Parse response for form data that will be posted back to Waterscope
                soup = BeautifulSoup(response.text, 'html.parser')
                form = soup.find('form')
                
                if form:
                    # Extract form data
                    auth_data = {}
                    for input_elem in form.find_all('input'):
                        name = input_elem.get('name')
                        value = input_elem.get('value')
                        if name and value:
                            auth_data[name] = value
                    
                    if auth_data:
                        _LOGGER.info("✅ OAuth confirmation completed successfully with existing session")
                        
                        # Transfer response cookies back to main aiohttp session
                        for cookie in sync_session.cookies:
                            self.session.cookie_jar.update_cookies({cookie.name: cookie.value})
                        
                        return auth_data
                else:
                    raise RuntimeError("No form found in OAuth confirmation response")
            else:
                raise RuntimeError(f"OAuth confirmation failed: {response.status_code} - {response.text[:200]}")
                
        except Exception as e:
            _LOGGER.error(f"OAuth confirmation error: {e}")
            raise RuntimeError(f"OAuth confirmation failed: {e}")
    
    async def _complete_token_exchange(self, auth_data: Dict[str, str]) -> bool:
        """Complete token exchange using hybrid approach (requests via asyncio.to_thread)."""
        _LOGGER.info("🔄 Completing token exchange (hybrid approach)...")
        
        # Extract all cookies for token exchange
        all_cookies = {}
        for cookie in self.session.cookie_jar:
            all_cookies[cookie.key] = cookie.value
        
        # Use asyncio.to_thread to run synchronous requests call in async context
        result = await asyncio.to_thread(
            self._complete_token_exchange_sync,
            auth_data, all_cookies
        )
        
        return result
    
    def _complete_token_exchange_sync(self, auth_data: Dict[str, str], all_cookies: dict) -> bool:
        """Synchronous token exchange using requests."""
        
        _LOGGER.info("🔧 Using synchronous requests for token exchange compatibility")
        _LOGGER.info(f"🔍 Token exchange data: {list(auth_data.keys())}")
        
        # Create requests session
        sync_session = requests.Session()
        
        # Use basic HTTPAdapter without retry strategy to avoid urllib3 version issues
        adapter = HTTPAdapter(max_retries=0)  # Disable retries completely
        sync_session.mount("http://", adapter)
        sync_session.mount("https://", adapter)
        
        # Add all cookies
        for key, value in all_cookies.items():
            sync_session.cookies.set(key, value)
        
        try:
            response = sync_session.post(
                "https://waterscope.us/",
                data=auth_data,
                headers={
                    'Content-Type': 'application/x-www-form-urlencoded',
                    'Origin': 'https://metronb2c.b2clogin.com',
                    'Referer': 'https://metronb2c.b2clogin.com/'
                },
                allow_redirects=True
            )
            
            _log_response_details(response, response.text)
            
            if response.status_code != 200:
                raise RuntimeError(f"Token exchange failed: {response.status_code}")
            
            # Check if we have authentication cookies
            auth_cookie_found = False
            for cookie in sync_session.cookies:
                if cookie.name in ['.ASPXAUTH', '.AspNet.Cookies']:
                    auth_cookie_found = True
                    self._auth_cookies[cookie.name] = cookie.value
                    # Transfer back to aiohttp session
                    self.session.cookie_jar.update_cookies({cookie.name: cookie.value})
            
            if not auth_cookie_found:
                raise RuntimeError("No authentication cookies found after token exchange")
            
            # Test access to authenticated page
            test_response = sync_session.get(
                "https://waterscope.us/Consumer/Consumer/Index#ConsumerDashboard",
                allow_redirects=False
            )
            
            _log_response_details(test_response, test_response.text)
            
            if test_response.status_code == 200:
                _LOGGER.info("✅ Token exchange completed successfully")
                
                # Transfer all final cookies back to aiohttp session
                for cookie in sync_session.cookies:
                    self.session.cookie_jar.update_cookies({cookie.name: cookie.value})
                
                # Keep the requests session for dashboard access
                self.requests_session = sync_session
                
                return True
            else:
                _LOGGER.error(f"Authentication test failed: {test_response.status_code}")
                return False
                
        except Exception as e:
            _LOGGER.error(f"Token exchange error: {e}")
            return False
    
    async def get_meter_reading(self, username: str, password: str) -> Optional[str]:
        """Extract meter reading from dashboard using hybrid approach."""
        try:
            _LOGGER.debug("🔄 Starting meter reading extraction for user: %s", username[:3] + "***")
            
            # Get all meter data
            meter_data = await self.get_meter_data(username, password)
            
            # Return just the LCD meter reading for backward compatibility
            if meter_data and 'meter_reading' in meter_data:
                return str(meter_data['meter_reading'])
            
            return None
        
        except Exception as e:
            _LOGGER.error("Failed to get meter reading: %s", str(e), exc_info=True)
            raise WaterscopeAPIError(f"Meter reading extraction failed: {e}") from e
    
    def _extract_meter_data(self, html_content: str) -> Dict[str, Optional[str]]:
        """Extract all meter data from dashboard HTML."""
        try:
            _LOGGER.debug("🔍 Extracting meter data from dashboard HTML...")
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
            
            # Initialize result dictionary
            result = {
                'meter_reading': None,
                'previous_day_consumption': None,
                'daily_average_consumption': None,
                'billing_read': None,
                'current_cycle_total': None,
                'device_name': None
            }
            
            # Extract LCD meter reading (existing functionality)
            meter_reading = self._extract_lcd_reading(soup, html_content)
            if meter_reading:
                result['meter_reading'] = meter_reading
            
            # Extract previous day consumption by finding the "Water Consumption" label
            consumption_labels = soup.find_all('label', class_='src-int_lbl-extended')
            for label in consumption_labels:
                label_text = label.get_text(strip=True)
                if 'Water' in label_text and 'Consumption' in label_text:
                    # Found the Water Consumption label, now find the associated value
                    # Look for the parent div and then find the span with the numeric value
                    parent_div = label.find_parent('div', class_='src-int_wrp-extended')
                    if parent_div:
                        # Look for spans with numeric content within this div
                        value_spans = parent_div.find_all('span')
                        for span in value_spans:
                            span_text = span.get_text(strip=True)
                            # Look for numeric patterns (e.g., "16.81")
                            numeric_match = re.search(r'^(\d+(?:\.\d+)?)$', span_text)
                            if numeric_match:
                                result['previous_day_consumption'] = numeric_match.group(1)
                                _LOGGER.info("✅ Found previous day consumption: %s", result['previous_day_consumption'])
                                break
                    break
            
            # Extract daily average consumption by finding the "Daily Average" label
            # Since the span id "last24HrUsage" is used multiple times, we need to find it by the label
            daily_avg_labels = soup.find_all('label', class_='src-int_lbl-extended')
            for label in daily_avg_labels:
                label_text = label.get_text(strip=True)
                if 'Daily' in label_text and 'Average' in label_text:
                    # Found the Daily Average label, now find the associated value
                    # Look for the parent div and then find the span with the numeric value
                    parent_div = label.find_parent('div', class_='src-int_wrp-extended')
                    if parent_div:
                        # Look for spans with numeric content within this div
                        value_spans = parent_div.find_all('span')
                        for span in value_spans:
                            span_text = span.get_text(strip=True)
                            # Look for numeric patterns (e.g., "12.53")
                            numeric_match = re.search(r'^(\d+(?:\.\d+)?)$', span_text)
                            if numeric_match:
                                result['daily_average_consumption'] = numeric_match.group(1)
                                _LOGGER.info("✅ Found daily average consumption: %s", result['daily_average_consumption'])
                                break
                    break
            
            # Extract billing read from span with id "billing-read_NEW"
            billing_read_element = soup.find('span', {'id': 'billing-read_NEW'})
            if billing_read_element:
                billing_read_text = billing_read_element.get_text(strip=True)
                if billing_read_text and billing_read_text != 'NA':
                    # Extract numeric value (remove any units or extra text)
                    numeric_match = re.search(r'(\d+(?:\.\d+)?)', billing_read_text)
                    if numeric_match:
                        result['billing_read'] = numeric_match.group(1)
                        _LOGGER.info("✅ Found billing read: %s", result['billing_read'])
            
            # Extract current cycle total by finding the "So far this cycle" label
            cycle_labels = soup.find_all('label', class_='src-int_lbl-extended')
            for label in cycle_labels:
                label_text = label.get_text(strip=True)
                if 'So far this' in label_text and 'cycle' in label_text:
                    # Found the "So far this cycle" label, now find the associated value
                    # Look for the parent div and then find the span with the numeric value
                    parent_div = label.find_parent('div', class_='src-int_wrp-extended')
                    if parent_div:
                        # Look for spans with numeric content within this div
                        value_spans = parent_div.find_all('span')
                        for span in value_spans:
                            span_text = span.get_text(strip=True)
                            # Look for numeric patterns (e.g., "213")
                            numeric_match = re.search(r'^(\d+(?:\.\d+)?)$', span_text)
                            if numeric_match:
                                result['current_cycle_total'] = numeric_match.group(1)
                                _LOGGER.info("✅ Found current cycle total: %s", result['current_cycle_total'])
                                break
                    break
            
            # Extract device/meter name - look for meter identifier or account name
            device_name = self._extract_device_name(soup, html_content)
            if device_name:
                result['device_name'] = device_name
                _LOGGER.info("✅ Found device name: %s", device_name)
            
            _LOGGER.debug("Extracted meter data: %s", result)
            return result
            
        except Exception as e:
            _LOGGER.error("Error extracting meter data: %s", str(e), exc_info=True)
            return {
                'meter_reading': None,
                'previous_day_consumption': None,
                'daily_average_consumption': None,
                'billing_read': None,
                'current_cycle_total': None,
                'device_name': None
            }
    
    def _extract_lcd_reading(self, soup: BeautifulSoup, html_content: str) -> Optional[str]:
        """Extract LCD meter reading from dashboard HTML."""
        try:
            # Use the lcd-read_NEW selector to find the LCD reading
            element = soup.select_one('#lcd-read_NEW')
            if element:
                text = element.get_text(strip=True)
                if text and text != 'NA' and '.' in text:
                    _LOGGER.info("✅ Found meter reading: %s", text)
                    return text
            
            _LOGGER.warning("❌ Could not extract meter reading")
            return None
            
        except Exception as e:
            _LOGGER.error("Error extracting LCD meter reading: %s", str(e), exc_info=True)
            return None
    
    def _extract_device_name(self, soup: BeautifulSoup, html_content: str) -> Optional[str]:
        """Extract device/meter name from dashboard HTML."""
        try:
            _LOGGER.info("🔍 Device name extraction: Starting HTML analysis")
            
            # Look for the meter information in the table structure
            # Find table containing meter information
            meter_table = soup.find('table', style=lambda value: value and 'font-size: 11px' in value)
            if meter_table:
                _LOGGER.info("🔍 Found meter table")
                
                # Look for innov8-VN LTE text and metermname spans
                innov8_span = None
                metron_span = None
                
                for span in meter_table.find_all('span'):
                    text = span.get_text(strip=True)
                    if 'innov8-VN LTE' in text:
                        innov8_span = span
                        _LOGGER.info(f"✅ Found innov8 span: '{text}'")
                    elif span.get('class') == ['metermname']:
                        metron_span = span
                        metron_text = span.get_text(strip=True)
                        _LOGGER.info(f"✅ Found metermname span: '{metron_text}'")
                
                # Combine the two parts if both found
                if innov8_span and metron_span:
                    innov8_text = innov8_span.get_text(strip=True)
                    metron_text = metron_span.get_text(strip=True)
                    # Clean up the metron text (remove extra whitespace and &nbsp;)
                    metron_text = re.sub(r'\s+', ' ', metron_text).strip()
                    device_name = f"{innov8_text} {metron_text}"
                    _LOGGER.info(f"✅ Combined device name: '{device_name}'")
                    return device_name
            
            _LOGGER.warning("❌ Device name extraction failed - no suitable patterns found")
            return None
            
        except Exception as e:
            _LOGGER.error("Error extracting device name: %s", str(e), exc_info=True)
            return None
    
    async def get_meter_data(self, username: str, password: str) -> Dict[str, Any]:
        """Get complete meter data including reading and additional consumption values."""
        try:
            _LOGGER.debug("🔄 Getting complete dashboard data for user: %s", username[:3] + "***")
            
            # Step 1: Authenticate if not already authenticated
            if not self.authenticated:
                _LOGGER.debug("Step 1: Authenticating...")
                auth_result = await self.authenticate(username, password)
                if not auth_result:
                    _LOGGER.error("❌ Authentication failed for meter data extraction")
                    raise WaterscopeAuthError("Authentication failed")
                
                _LOGGER.debug("✅ Authentication successful, using hybrid approach for dashboard access...")
            
            # Step 2: Use requests session directly (hybrid approach)
            dashboard_url = "https://waterscope.us/Consumer/Consumer/Index#ConsumerDashboard"
            _LOGGER.debug("Step 2: Accessing dashboard at %s using requests session", dashboard_url)
            
            def get_dashboard_sync():
                """Synchronous dashboard access using authenticated requests session."""
                
                # Define URLs inside the function
                homepage_url = "https://waterscope.us/"
                dashboard_url = "https://waterscope.us/Consumer/Consumer/Index#ConsumerDashboard"
                
                # First, check if we need to complete OAuth token exchange by accessing the homepage
                _LOGGER.debug("Checking OAuth status by accessing homepage first...")
                initial_response = self.requests_session.get(
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
                        token_response = self.requests_session.post(
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
                dashboard_response = self.requests_session.get(
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
            _LOGGER.info("🔍 DASHBOARD HTML CONTENT (for debugging meter data extraction):")
            _LOGGER.info("=" * 80)
            _LOGGER.info(html_content)
            _LOGGER.info("=" * 80)
            
            # Step 3: Parse HTML and extract all meter data
            _LOGGER.debug("Step 3: Parsing HTML and extracting all meter data...")
            meter_data = self._extract_meter_data(html_content)
            _LOGGER.debug("Meter data extraction result: %s", meter_data)
            
            # Validate and prepare final result
            result = {
                'status': 'success',
                'timestamp': None  # Will be set by coordinator
            }
            
            # Process LCD meter reading
            if meter_data.get('meter_reading'):
                try:
                    numeric_value = float(meter_data['meter_reading'])
                    result['meter_reading'] = numeric_value
                    result['raw_meter_text'] = f"{meter_data['meter_reading']} Ft3"
                    _LOGGER.info("✅ LCD meter reading: %s Ft3", meter_data['meter_reading'])
                except ValueError as ve:
                    _LOGGER.error("❌ Invalid meter reading format: %s", meter_data['meter_reading'])
                    raise WaterscopeAPIError(f"Invalid meter reading format: {meter_data['meter_reading']}") from ve
            else:
                _LOGGER.error("❌ No LCD meter reading found in dashboard")
                raise WaterscopeAPIError("No LCD meter reading found")
            
            # Process previous day consumption
            if meter_data.get('previous_day_consumption'):
                try:
                    numeric_value = float(meter_data['previous_day_consumption'])
                    result['previous_day_consumption'] = numeric_value
                    _LOGGER.info("✅ Previous day consumption: %s ft3", meter_data['previous_day_consumption'])
                except ValueError:
                    _LOGGER.warning("❌ Invalid previous day consumption format: %s", meter_data['previous_day_consumption'])
                    result['previous_day_consumption'] = None
            else:
                _LOGGER.warning("❌ No previous day consumption found in dashboard")
                result['previous_day_consumption'] = None
            
            # Process daily average consumption
            if meter_data.get('daily_average_consumption'):
                try:
                    numeric_value = float(meter_data['daily_average_consumption'])
                    result['daily_average_consumption'] = numeric_value
                    _LOGGER.info("✅ Daily average consumption: %s ft3", meter_data['daily_average_consumption'])
                except ValueError:
                    _LOGGER.warning("❌ Invalid daily average consumption format: %s", meter_data['daily_average_consumption'])
                    result['daily_average_consumption'] = None
            else:
                _LOGGER.warning("❌ No daily average consumption found in dashboard")
                result['daily_average_consumption'] = None
            
            # Process billing read
            if meter_data.get('billing_read'):
                try:
                    numeric_value = float(meter_data['billing_read'])
                    result['billing_read'] = numeric_value
                    _LOGGER.info("✅ Billing read: %s ft3", meter_data['billing_read'])
                except ValueError:
                    _LOGGER.warning("❌ Invalid billing read format: %s", meter_data['billing_read'])
                    result['billing_read'] = None
            else:
                _LOGGER.warning("❌ No billing read found in dashboard")
                result['billing_read'] = None
            
            # Process current cycle total
            if meter_data.get('current_cycle_total'):
                try:
                    numeric_value = float(meter_data['current_cycle_total'])
                    result['current_cycle_total'] = numeric_value
                    _LOGGER.info("✅ Current cycle total: %s ft3", meter_data['current_cycle_total'])
                except ValueError:
                    _LOGGER.warning("❌ Invalid current cycle total format: %s", meter_data['current_cycle_total'])
                    result['current_cycle_total'] = None
            else:
                _LOGGER.warning("❌ No current cycle total found in dashboard")
                result['current_cycle_total'] = None
            
            # Add device name to the result if extracted
            if meter_data.get('device_name'):
                result['device_name'] = meter_data['device_name']
                _LOGGER.info("✅ Device name extracted: %s", meter_data['device_name'])
            
            _LOGGER.info("✅ Dashboard data retrieval successful")
            return result
            
        except Exception as e:
            _LOGGER.error("Dashboard data retrieval failed: %s", str(e), exc_info=True)
            raise WaterscopeAPIError(f"Data retrieval failed: {e}") from e
    
    def get_session_cookies(self) -> Dict[str, str]:
        """Get the authentication cookies for use in subsequent requests."""
        if not self.authenticated:
            raise RuntimeError("Not authenticated - call authenticate() first")
        
        cookies = {}
        for cookie in self.session.cookie_jar:
            cookies[cookie.key] = cookie.value
        
        return cookies
    
    def get_cookies_string(self) -> str:
        """Get cookies formatted as a string for HTTP headers."""
        if not self.authenticated:
            raise RuntimeError("Not authenticated - call authenticate() first")
        
        cookie_pairs = []
        for cookie in self.session.cookie_jar:
            cookie_pairs.append(f"{cookie.key}={cookie.value}")
        
        return "; ".join(cookie_pairs)
    
    async def close(self):
        """Close the session."""
        if self.session and not self.session.closed:
            await self.session.close()

    def __enter__(self):
        """Sync context manager entry (for compatibility)."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Sync context manager exit (for compatibility)."""
        # Note: Cannot await close() in sync context
        pass


# Convenience function for simple authentication
async def authenticate_and_get_cookies(username: str, password: str) -> Optional[str]:
    """
    Authenticate with Waterscope and return session cookies.
    
    Args:
        username: Waterscope username/email
        password: Waterscope password
        
    Returns:
        Cookie string for use in HTTP requests, or None if authentication failed
    """
    try:
        async with WaterscopeAPI() as auth:
            if await auth.authenticate(username, password):
                return auth.get_cookies_string()
            return None
    except Exception as e:
        _LOGGER.error(f"Authentication failed: {e}")
        return None


if __name__ == "__main__":
    import asyncio
    import sys
    import getpass
    
    # Enable detailed logging for debugging
    logging.basicConfig(level=logging.INFO)
    
    async def main():
        if len(sys.argv) == 3:
            username, password = sys.argv[1], sys.argv[2]
        else:
            username = input("Username: ")
            password = getpass.getpass("Password: ")
        
        print("🚀 Testing unified Waterscope API...")
        print("🔍 Debug mode enabled - detailed logging active")
        
        async with WaterscopeAPI() as api:
            # Test authentication
            auth_result = await api.authenticate(username, password)
            if auth_result:
                print("✅ Authentication successful!")
                
                # Test meter reading
                meter_data = await api.get_meter_data(username, password)
                if meter_data:
                    print(f"✅ Meter reading: {meter_data['meter_reading']} Ft3")
                else:
                    print("❌ Failed to get meter reading")
            else:
                print("❌ Authentication failed")
                sys.exit(1)
    
    asyncio.run(main())