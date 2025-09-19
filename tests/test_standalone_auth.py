#!/usr/bin/env python3
"""
Standalone test for Waterscope HTTP authentication implementation.
This test doesn't require Home Assistant dependencies.
"""

import asyncio
import logging
import sys
import getpass
from typing import Optional

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Add the waterscope directory to path and import directly
sys.path.insert(0, 'custom_components/waterscope')

try:
    from http_auth import WaterscopeHTTPAuthenticator, authenticate_and_get_cookies
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("Make sure you're running this from the correct directory with the waterscope components available.")
    sys.exit(1)

class StandaloneAuthTest:
    """Standalone test for HTTP authentication functionality."""
    
    def __init__(self, username: str, password: str):
        self.username = username
        self.password = password
        self.test_results = []
    
    async def run_tests(self):
        """Run authentication tests."""
        print("🧪 Starting Waterscope HTTP Authentication Test")
        print("=" * 50)
        
        # Test 1: Basic authentication flow
        await self._test_basic_authentication()
        
        # Test 2: Cookie extraction and format
        await self._test_cookie_extraction()
        
        # Test 3: Convenience function
        await self._test_convenience_function()
        
        # Test 4: Error handling
        await self._test_error_handling()
        
        # Print summary
        self._print_test_summary()
    
    async def _test_basic_authentication(self):
        """Test basic authentication flow."""
        print("\n🔐 Test 1: Basic Authentication Flow")
        print("-" * 40)
        
        try:
            async with WaterscopeHTTPAuthenticator() as auth:
                result = await auth.authenticate(self.username, self.password)
                
                if result:
                    print("✅ Authentication successful")
                    print(f"   Authenticated: {auth.authenticated}")
                    self.test_results.append(("Basic Authentication", True, ""))
                else:
                    print("❌ Authentication failed")
                    self.test_results.append(("Basic Authentication", False, "Authentication returned False"))
                    
        except Exception as e:
            print(f"❌ Authentication error: {e}")
            self.test_results.append(("Basic Authentication", False, str(e)))
    
    async def _test_cookie_extraction(self):
        """Test cookie extraction and formatting."""
        print("\n🍪 Test 2: Cookie Extraction")
        print("-" * 40)
        
        try:
            async with WaterscopeHTTPAuthenticator() as auth:
                if await auth.authenticate(self.username, self.password):
                    # Test cookie dictionary
                    cookies_dict = auth.get_session_cookies()
                    print(f"✅ Cookie dictionary extracted: {len(cookies_dict)} cookies")
                    
                    # Check for required cookies
                    required_cookies = ['.ASPXAUTH', '.AspNet.Cookies', 'ASP.NET_SessionId']
                    found_cookies = []
                    for cookie_name in required_cookies:
                        if cookie_name in cookies_dict:
                            found_cookies.append(cookie_name)
                    
                    print(f"   Required cookies found: {found_cookies}")
                    
                    # Test cookie string format
                    cookies_string = auth.get_cookies_string()
                    print(f"✅ Cookie string format: {len(cookies_string)} characters")
                    print(f"   Sample: {cookies_string[:100]}...")
                    
                    # Validate cookie string format
                    if '; ' in cookies_string and '=' in cookies_string:
                        print("✅ Cookie string format is valid")
                        self.test_results.append(("Cookie Extraction", True, ""))
                    else:
                        print("❌ Invalid cookie string format")
                        self.test_results.append(("Cookie Extraction", False, "Invalid format"))
                else:
                    print("❌ Cannot test cookies - authentication failed")
                    self.test_results.append(("Cookie Extraction", False, "Auth failed"))
                    
        except Exception as e:
            print(f"❌ Cookie extraction error: {e}")
            self.test_results.append(("Cookie Extraction", False, str(e)))
    
    async def _test_convenience_function(self):
        """Test the convenience function."""
        print("\n🚀 Test 3: Convenience Function")
        print("-" * 40)
        
        try:
            cookies = await authenticate_and_get_cookies(self.username, self.password)
            
            if cookies:
                print("✅ Convenience function successful")
                print(f"   Returned cookies: {len(cookies)} characters")
                print(f"   Sample: {cookies[:100]}...")
                self.test_results.append(("Convenience Function", True, ""))
            else:
                print("❌ Convenience function failed")
                self.test_results.append(("Convenience Function", False, "No cookies returned"))
                
        except Exception as e:
            print(f"❌ Convenience function error: {e}")
            self.test_results.append(("Convenience Function", False, str(e)))
    
    async def _test_error_handling(self):
        """Test error handling with invalid credentials."""
        print("\n⚠️  Test 4: Error Handling")
        print("-" * 40)
        
        try:
            # Test with invalid username
            async with WaterscopeHTTPAuthenticator() as auth:
                result = await auth.authenticate("invalid@email.com", "wrongpassword")
                
                if not result:
                    print("✅ Invalid credentials properly rejected")
                    self.test_results.append(("Error Handling", True, ""))
                else:
                    print("❌ Invalid credentials were accepted (unexpected)")
                    self.test_results.append(("Error Handling", False, "Invalid creds accepted"))
                    
        except Exception as e:
            print(f"✅ Exception properly raised for invalid credentials: {type(e).__name__}")
            self.test_results.append(("Error Handling", True, ""))
    
    def _print_test_summary(self):
        """Print test summary."""
        print("\n" + "=" * 50)
        print("📋 TEST SUMMARY")
        print("=" * 50)
        
        passed = 0
        failed = 0
        
        for test_name, success, error in self.test_results:
            status = "✅ PASS" if success else "❌ FAIL"
            print(f"{status:<10} {test_name}")
            if not success and error:
                print(f"           Error: {error}")
            
            if success:
                passed += 1
            else:
                failed += 1
        
        print("-" * 50)
        print(f"Total Tests: {len(self.test_results)}")
        print(f"Passed: {passed}")
        print(f"Failed: {failed}")
        
        if failed == 0:
            print("\n🎉 ALL TESTS PASSED! HTTP authentication is working correctly.")
        else:
            print(f"\n⚠️  {failed} test(s) failed. Please review and fix issues.")
        
        return failed == 0

async def main():
    """Main test runner."""
    print("Waterscope HTTP Authentication Standalone Test")
    print("Version: 1.0")
    print()
    
    # Get credentials
    if len(sys.argv) == 3:
        username, password = sys.argv[1], sys.argv[2]
    else:
        print("Enter your Waterscope credentials for testing:")
        username = input("Username/Email: ").strip()
        password = getpass.getpass("Password: ").strip()
    
    if not username or not password:
        print("❌ Username and password are required")
        sys.exit(1)
    
    # Run tests
    test_suite = StandaloneAuthTest(username, password)
    success = await test_suite.run_tests()
    
    print("\n" + "=" * 50)
    if success:
        print("✅ HTTP AUTHENTICATION VALIDATION SUCCESSFUL")
        print("The implementation is working correctly!")
    else:
        print("❌ HTTP AUTHENTICATION VALIDATION FAILED") 
        print("Please check the errors above.")
    
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    asyncio.run(main())