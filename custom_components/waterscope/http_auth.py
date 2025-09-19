"""
Pure HTTP implementation of Waterscope authentication flow.
Reverse engineered from network traffic analysis to eliminate browser automation.
"""

import re
import logging
import urllib.parse
from typing import Optional, Dict, Any, Tuple
from datetime import datetime, timezone
import aiohttp
import asyncio
from bs4 import BeautifulSoup
import json
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

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

class WaterscopeHTTPAuthenticator:
    """Pure HTTP implementation of Waterscope OAuth authentication flow."""
    
    def __init__(self):
        self.session = None
        self.requests_session = None  # Expose requests session for dashboard access
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
            
            # Extract transaction state from URL or page - multiple approaches
            tx_state = None
            
            # Method 1: From URL parameters
            url_params = urllib.parse.parse_qs(urllib.parse.urlparse(str(response.url)).query)
            if 'tx' in url_params:
                tx_state = url_params['tx'][0]
            
            # Method 2: From state parameter (common in OAuth flows)
            if not tx_state and 'state' in url_params:
                tx_state = url_params['state'][0]
            
            # Method 3: Look for tx parameter in page content
            if not tx_state:
                tx_match = re.search(r'tx=([^&\s"\']+)', response_text)
                if tx_match:
                    tx_state = tx_match.group(1)
            
            # Method 4: Look for StateProperties in page content
            if not tx_state:
                state_match = re.search(r'StateProperties=([^&\s"\']+)', response_text)
                if state_match:
                    tx_state = state_match.group(1)
            
            # Method 5: Extract from form inputs
            if not tx_state:
                soup = BeautifulSoup(response_text, 'html.parser')
                tx_input = soup.find('input', {'name': 'tx'})
                if tx_input:
                    tx_state = tx_input.get('value')
            
            # Method 6: Use state parameter as backup
            if not tx_state and 'state' in url_params:
                # Extract just the transaction part from the state
                state_value = url_params['state'][0]
                # Azure B2C often embeds transaction info in the state
                tx_state = state_value
            
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
        
        # Store the updated session for use in OAuth confirmation
        self._password_session = updated_session
        # Also expose it as requests_session for dashboard access
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
        
        # Multiple approaches to try for Azure B2C password submission
        approaches = [
            {
                'url': "https://metronb2c.b2clogin.com/metronb2c.onmicrosoft.com/B2C_1_mainsso_web/SelfAsserted",
                'params': {'tx': tx_state, 'p': 'B2C_1_mainsso_web'},
                'data': {'request_type': 'RESPONSE', 'email': username, 'password': password}
            },
            {
                'url': "https://metronb2c.b2clogin.com/metronb2c.onmicrosoft.com/B2C_1_mainsso_web/SelfAsserted",
                'params': {'tx': f'StateProperties={tx_state}', 'p': 'B2C_1_mainsso_web'},
                'data': {'request_type': 'RESPONSE', 'email': username, 'password': password}
            },
            {
                'url': "https://metronb2c.b2clogin.com/metronb2c.onmicrosoft.com/B2C_1_mainsso_web/SelfAsserted",
                'params': {'tx': tx_state, 'p': 'B2C_1_mainsso_web'},
                'data': {'signInName': username, 'password': password, 'request_type': 'RESPONSE'}
            }
        ]
        
        for i, approach in enumerate(approaches, 1):
            _LOGGER.info(f"🔄 Trying sync approach {i}: {approach['url']}")
            
            # Essential headers only (matching successful requests implementation)
            azure_headers = {
                'Accept': 'application/json, text/javascript, */*; q=0.01',
                'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                'X-CSRF-TOKEN': csrf_token,
                'X-Requested-With': 'XMLHttpRequest',
                'Origin': 'https://metronb2c.b2clogin.com',
                'Referer': referer_url
            }
            
            _log_request_details("POST", approach['url'], azure_headers, approach['data'], approach['params'])
            
            try:
                response = sync_session.post(
                    approach['url'],
                    params=approach['params'],
                    data=approach['data'],
                    headers=azure_headers
                )
                
                _log_response_details(response, response.text)
                _LOGGER.info(f"Sync approach {i} response: {response.status_code}")
                
                if response.status_code == 200:
                    _LOGGER.info(f"✅ Password submitted successfully with sync approach {i}")
                    # Construct confirmation URL
                    confirm_url = f"https://metronb2c.b2clogin.com/metronb2c.onmicrosoft.com/B2C_1_mainsso_web/api/CombinedSigninAndSignup/confirmed"
                    
                    # Transfer response cookies back to main aiohttp session
                    for cookie in sync_session.cookies:
                        self.session.cookie_jar.update_cookies({cookie.name: cookie.value})
                    
                    # Return both the confirm URL and the updated session with new cookies
                    return confirm_url, sync_session
                else:
                    _LOGGER.warning(f"Sync approach {i} failed: {response.status_code} - {response.text[:200]}")
                    
            except Exception as e:
                _LOGGER.error(f"Sync approach {i} error: {e}")
                continue
        
        # If all approaches failed
        raise RuntimeError(f"All sync password submission approaches failed")
    
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
        
        # The tx_state might be the full OAuth state parameter, let's try different formats
        approaches = [
            # Approach 1: Use state parameter directly
            {
                'rememberMe': 'false',
                'csrf_token': csrf_token,
                'state': tx_state,
                'p': 'B2C_1_mainsso_web',
                'diags': '{"pageViewId":"generated-uuid","pageId":"CombinedSigninAndSignup","trace":[]}'
            },
            # Approach 2: Traditional tx parameter
            {
                'rememberMe': 'false',
                'csrf_token': csrf_token,
                'tx': f'StateProperties={tx_state}',
                'p': 'B2C_1_mainsso_web',
                'diags': '{"pageViewId":"generated-uuid","pageId":"CombinedSigninAndSignup","trace":[]}'
            },
            # Approach 3: Just the csrf_token and basic params
            {
                'rememberMe': 'false',
                'csrf_token': csrf_token,
                'p': 'B2C_1_mainsso_web'
            }
        ]
        
        for i, params in enumerate(approaches, 1):
            _LOGGER.info(f"🔄 Trying sync confirmation approach {i}")
            
            try:
                response = sync_session.get(
                    confirm_url,
                    params=params,
                    allow_redirects=True
                )
                
                _log_response_details(response, response.text)
                _LOGGER.info(f"Sync confirmation approach {i} response: {response.status_code}")
                
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
                            _LOGGER.info(f"✅ OAuth confirmation completed with sync approach {i}")
                            
                            # Transfer response cookies back to main aiohttp session
                            for cookie in sync_session.cookies:
                                self.session.cookie_jar.update_cookies({cookie.name: cookie.value})
                            
                            return auth_data
                    else:
                        _LOGGER.warning(f"Sync approach {i}: No form found in response")
                else:
                    _LOGGER.warning(f"Sync approach {i} failed: {response.status_code} - {response.text[:200]}")
                    
            except Exception as e:
                _LOGGER.error(f"Sync confirmation approach {i} error: {e}")
                continue
        
        # If all approaches failed
        raise RuntimeError(f"All sync OAuth confirmation approaches failed")
    
    def _complete_oauth_confirmation_with_session(self, confirm_url: str, csrf_token: str, tx_state: str,
                                                 sync_session: requests.Session) -> Dict[str, str]:
        """Synchronous OAuth confirmation using existing requests session with updated cookies."""
        
        _LOGGER.info("🔧 Using existing sync session with updated cookies for OAuth confirmation")
        
        # The tx_state might be the full OAuth state parameter, let's try different formats
        approaches = [
            # Approach 1: Use state parameter directly
            {
                'rememberMe': 'false',
                'csrf_token': csrf_token,
                'state': tx_state,
                'p': 'B2C_1_mainsso_web',
                'diags': '{"pageViewId":"generated-uuid","pageId":"CombinedSigninAndSignup","trace":[]}'
            },
            # Approach 2: Traditional tx parameter
            {
                'rememberMe': 'false',
                'csrf_token': csrf_token,
                'tx': f'StateProperties={tx_state}',
                'p': 'B2C_1_mainsso_web',
                'diags': '{"pageViewId":"generated-uuid","pageId":"CombinedSigninAndSignup","trace":[]}'
            },
            # Approach 3: Just the csrf_token and basic params
            {
                'rememberMe': 'false',
                'csrf_token': csrf_token,
                'p': 'B2C_1_mainsso_web'
            }
        ]
        
        for i, params in enumerate(approaches, 1):
            _LOGGER.info(f"🔄 Trying existing session confirmation approach {i}")
            
            try:
                response = sync_session.get(
                    confirm_url,
                    params=params,
                    allow_redirects=True
                )
                
                _log_response_details(response, response.text)
                _LOGGER.info(f"Existing session confirmation approach {i} response: {response.status_code}")
                
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
                            _LOGGER.info(f"✅ OAuth confirmation completed with existing session approach {i}")
                            
                            # Transfer response cookies back to main aiohttp session
                            for cookie in sync_session.cookies:
                                self.session.cookie_jar.update_cookies({cookie.name: cookie.value})
                            
                            return auth_data
                    else:
                        _LOGGER.warning(f"Existing session approach {i}: No form found in response")
                else:
                    _LOGGER.warning(f"Existing session approach {i} failed: {response.status_code} - {response.text[:200]}")
                    
            except Exception as e:
                _LOGGER.error(f"Existing session confirmation approach {i} error: {e}")
                continue
        
        # If all approaches failed
        raise RuntimeError(f"All existing session OAuth confirmation approaches failed")
    
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
                "https://waterscope.us/Consumer/Consumer/Index",
                allow_redirects=False
            )
            
            _log_response_details(test_response, test_response.text)
            
            if test_response.status_code == 200:
                _LOGGER.info("✅ Token exchange completed successfully")
                
                # Transfer all final cookies back to aiohttp session
                for cookie in sync_session.cookies:
                    self.session.cookie_jar.update_cookies({cookie.name: cookie.value})
                
                return True
            else:
                _LOGGER.error(f"Authentication test failed: {test_response.status_code}")
                return False
                
        except Exception as e:
            _LOGGER.error(f"Token exchange error: {e}")
            return False
    
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
        async with WaterscopeHTTPAuthenticator() as auth:
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
        
        print("🚀 Testing HTTP-only authentication...")
        print("🔍 Debug mode enabled - detailed logging active")
        
        cookies = await authenticate_and_get_cookies(username, password)
        
        if cookies:
            print("✅ Authentication successful!")
            print("🍪 Session cookies:", cookies[:100] + "..." if len(cookies) > 100 else cookies)
        else:
            print("❌ Authentication failed")
            sys.exit(1)
    
    asyncio.run(main())