#!/usr/bin/env python3
"""
Waterscope HTTP Authentication Test Suite - Unittest Framework
==============================================================

Comprehensive test for the Waterscope Home Assistant integration using Python's unittest framework.

Run with: python -m unittest tests.test_standalone_auth
Or directly: python tests/test_standalone_auth.py
"""

import unittest
import asyncio
import getpass
import sys
import os
from pathlib import Path

# Setup logging
import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Add the custom_components directory to the Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "custom_components" / "waterscope"))

try:
    from waterscope import WaterscopeAPI, authenticate_and_get_cookies
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("Attempting to handle missing const dependencies...")
    
    # Define fallback exception classes to allow testing
    class WaterscopeError(Exception):
        """Base exception for Waterscope errors."""
        pass

    class WaterscopeAPIError(WaterscopeError):
        """Exception for API-related errors."""
        pass

    class WaterscopeAuthError(WaterscopeError):
        """Exception for authentication-related errors."""
        pass
    
    # Inject the exception classes into the waterscope module namespace
    try:
        import waterscope
        waterscope.WaterscopeError = WaterscopeError
        waterscope.WaterscopeAPIError = WaterscopeAPIError
        waterscope.WaterscopeAuthError = WaterscopeAuthError
        from waterscope import WaterscopeAPI, authenticate_and_get_cookies
        print("✅ Successfully imported with fallback exception classes")
    except ImportError as e2:
        print(f"❌ Final import error: {e2}")
        print("Make sure you're running this from the correct directory with the waterscope components available.")
        sys.exit(1)


class TestWaterscopeIntegration(unittest.TestCase):
    """Comprehensive test suite for Waterscope HTTP Authentication and Data Extraction"""

    @classmethod
    def setUpClass(cls):
        """Set up test credentials once for all tests"""
        print("\nWaterscope HTTP Authentication & Data Extraction Test")
        print("=" * 60)
        print("\nEnter your Waterscope credentials for testing:")
        
        cls.username = input("Username/Email: ").strip()
        cls.password = getpass.getpass("Password: ").strip()
        cls.invalid_username = "invalid@email.com"
        cls.invalid_password = "wrongpassword"
        
        if not cls.username or not cls.password:
            raise unittest.SkipTest("Username and password are required")
        
        # Set up event loop for async tests
        cls.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(cls.loop)

    @classmethod
    def tearDownClass(cls):
        """Clean up after all tests"""
        cls.loop.close()

    def setUp(self):
        """Set up before each test"""
        self.api = None

    def tearDown(self):
        """Clean up after each test"""
        if self.api:
            try:
                self.loop.run_until_complete(self.api.close())
            except Exception:
                pass  # Ignore cleanup errors

    def test_complete_waterscope_integration(self):
        """
        Comprehensive test covering:
        1. Authentication & Session Management
        2. Cookie Extraction & Validation  
        3. Dashboard Navigation & Data Scraping
        4. Convenience Function Testing
        5. Error Handling with Invalid Credentials
        """
        print(f"\n🧪 Waterscope Complete Integration Test")
        print("=" * 50)
        
        async def run_complete_test():
            # ================================================================
            # PHASE 1: Authentication & Session Management
            # ================================================================
            print("\n📋 PHASE 1: Authentication & Session Management")
            print("-" * 50)
            
            async with WaterscopeAPI() as api:
                self.api = api
                
                # Test authentication
                success = await api.authenticate(self.username, self.password)
                self.assertTrue(success, "Authentication should succeed with valid credentials")
                self.assertTrue(api.authenticated, "API should be marked as authenticated")
                print("✅ Authentication successful")
                print(f"   Status: {api.authenticated}")
                
                # ================================================================
                # PHASE 2: Cookie Extraction & Validation
                # ================================================================
                print("\n📋 PHASE 2: Cookie Extraction & Validation")
                print("-" * 50)
                
                # Test cookie dictionary extraction
                cookies_dict = api.get_session_cookies()
                self.assertIsInstance(cookies_dict, dict, "Should return a dictionary")
                self.assertGreater(len(cookies_dict), 0, "Should have authentication cookies")
                print(f"✅ Cookie dictionary extracted: {len(cookies_dict)} cookies")
                
                # Test cookie string format
                cookies_string = api.get_cookies_string()
                self.assertIsInstance(cookies_string, str, "Should return a string")
                self.assertGreater(len(cookies_string), 0, "Cookie string should not be empty")
                self.assertIn('; ', cookies_string, "Should have proper cookie separator")
                self.assertIn('=', cookies_string, "Should have proper key=value format")
                
                print(f"✅ Cookie string format validated: {len(cookies_string)} characters")
                print(f"   Sample: {cookies_string[:100]}...")
                
                # ================================================================
                # PHASE 3: Dashboard Navigation & Data Scraping
                # ================================================================
                print("\n📋 PHASE 3: Dashboard Navigation & Data Scraping")
                print("-" * 50)
                
                # Test comprehensive data extraction
                meter_data = await api.get_meter_data(self.username, self.password)
                
                self.assertIsNotNone(meter_data, "Dashboard data should not be None")
                self.assertEqual(meter_data.get('status'), 'success', "Data extraction should be successful")
                
                print("✅ Dashboard navigation successful")
                print(f"   Status: {meter_data.get('status', 'unknown')}")
                
                # Validate primary meter reading (critical requirement)
                meter_reading = meter_data.get('meter_reading')
                self.assertIsNotNone(meter_reading, "Meter reading should be present")
                self.assertIsInstance(meter_reading, (int, float), "Meter reading should be numeric")
                self.assertGreater(meter_reading, 0, "Meter reading should be positive")
                self.assertLess(meter_reading, 999999, "Meter reading should be within reasonable range")
                
                print(f"✅ Primary LCD Meter Reading: {meter_reading} ft³")
                print("   ✅ Reading format and range validated")
                
                # Validate additional consumption metrics (nice to have)
                consumption_metrics = {
                    'previous_day_consumption': 'Previous Day Consumption',
                    'daily_average_consumption': 'Daily Average Consumption',
                    'billing_read': 'Billing Read',
                    'current_cycle_total': 'Current Cycle Total'
                }
                
                extracted_count = 0
                for key, label in consumption_metrics.items():
                    value = meter_data.get(key)
                    if value is not None:
                        print(f"✅ {label}: {value} ft³")
                        extracted_count += 1
                
                # Validate raw meter text format
                raw_meter_text = meter_data.get('raw_meter_text')
                if raw_meter_text:
                    print(f"✅ Raw Meter Text: {raw_meter_text}")
                
                # Overall data extraction assessment
                if extracted_count >= 2:
                    print("✅ Data Extraction Quality: EXCELLENT (primary + multiple metrics)")
                elif extracted_count >= 1:
                    print("✅ Data Extraction Quality: GOOD (primary + some metrics)")
                else:
                    print("✅ Data Extraction Quality: MINIMAL (primary only, but acceptable)")
            
            # ================================================================
            # PHASE 4: Convenience Function Testing
            # ================================================================
            print("\n📋 PHASE 4: Convenience Function Testing")
            print("-" * 50)
            
            # Test standalone convenience function
            cookies = await authenticate_and_get_cookies(self.username, self.password)
            
            self.assertIsNotNone(cookies, "Convenience function should return cookies")
            self.assertIsInstance(cookies, str, "Should return a string")
            self.assertGreater(len(cookies), 0, "Should have authentication cookies")
            
            print("✅ Convenience function successful")
            print(f"   Returned cookies: {len(cookies)} characters")
            print(f"   Sample: {cookies[:100]}...")
            
            # ================================================================
            # PHASE 5: Error Handling with Invalid Credentials
            # ================================================================
            print("\n📋 PHASE 5: Error Handling Validation")
            print("-" * 50)
            
            # Test error handling with invalid credentials
            async with WaterscopeAPI() as error_api:
                # Should return False, not raise exception
                error_success = await error_api.authenticate(self.invalid_username, self.invalid_password)
                self.assertFalse(error_success, "Authentication should fail with invalid credentials")
                self.assertFalse(error_api.authenticated, "API should not be marked as authenticated")
                
                print("✅ Invalid credentials properly rejected")
                print("   Error handling working correctly")
            
            # ================================================================
            # EXTRACTED METRICS SUMMARY
            # ================================================================
            print(f"\n📊 Extracted Water Metrics:")
            print(f"   Primary Reading: {meter_reading} ft³")
            if meter_data.get('previous_day_consumption') is not None:
                print(f"   Previous Day: {meter_data.get('previous_day_consumption')} ft³")
            if meter_data.get('daily_average_consumption') is not None:
                print(f"   Daily Average: {meter_data.get('daily_average_consumption')} ft³")
            if meter_data.get('billing_read') is not None:
                print(f"   Billing Read: {meter_data.get('billing_read')} ft³")
            if meter_data.get('current_cycle_total') is not None:
                print(f"   Cycle Total: {meter_data.get('current_cycle_total')} ft³")
            
        self.loop.run_until_complete(run_complete_test())


def suite():
    """Create a test suite"""
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(TestWaterscopeIntegration)
    return suite


def main():
    """Main entry point for running tests"""
    if __name__ == '__main__':
        # Create a custom test runner with verbose output
        runner = unittest.TextTestRunner(
            verbosity=2,
            stream=sys.stdout,
            descriptions=True,
            failfast=False
        )
        
        # Run the test suite
        test_suite = suite()
        result = runner.run(test_suite)
        
        # Simple result indication
        if not result.wasSuccessful():
            print("\n❌ Test failed - please check errors above.")
        
        # Exit with appropriate code
        sys.exit(0 if result.wasSuccessful() else 1)


if __name__ == '__main__':
    main()