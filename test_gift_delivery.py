"""
Test script for Gift Delivery System

This script helps test the scheduled gift delivery functionality.
"""

import requests
import json
from datetime import datetime, timedelta
import time

# Configuration
BASE_URL = "http://localhost:8000"


def print_section(title):
    """Print a formatted section header"""
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def test_health_check():
    """Test if the server is running"""
    print_section("Health Check")
    
    try:
        response = requests.get(f"{BASE_URL}/health")
        response.raise_for_status()
        data = response.json()
        
        print("✅ Server is running")
        print(f"   Gemini API: {'✓' if data.get('gemini_api_key_configured') else '✗'}")
        print(f"   Supabase: {'✓' if data.get('supabase_configured') else '✗'}")
        return True
    except Exception as e:
        print(f"❌ Server health check failed: {e}")
        return False


def test_scheduler_status():
    """Test the gift scheduler status endpoint"""
    print_section("Gift Scheduler Status")
    
    try:
        response = requests.get(f"{BASE_URL}/api/gifts/scheduler/status")
        response.raise_for_status()
        data = response.json()
        
        print(f"✅ Scheduler Status Retrieved")
        print(f"   Running: {data.get('running')}")
        print(f"   Check Interval: {data.get('check_interval')}s")
        print(f"   Processed Gifts: {data.get('processed_gifts_count')}")
        print(f"   Message: {data.get('message')}")
        return True
    except Exception as e:
        print(f"❌ Failed to get scheduler status: {e}")
        return False


def test_upcoming_deliveries(hours=24):
    """Test upcoming deliveries endpoint"""
    print_section(f"Upcoming Deliveries (Next {hours} hours)")
    
    try:
        response = requests.get(f"{BASE_URL}/api/gifts/upcoming?hours={hours}")
        response.raise_for_status()
        data = response.json()
        
        print(f"✅ Upcoming Deliveries Retrieved")
        print(f"   Count: {data.get('count')}")
        print(f"   Time Window: {data.get('hours')} hours")
        
        if data.get('gifts'):
            print("\n   Gifts:")
            for i, gift in enumerate(data['gifts'][:5], 1):  # Show first 5
                gift_id = gift.get('id', 'N/A')[:8]
                delivery_time = gift.get('delivery_time', 'N/A')
                status = gift.get('status', 'N/A')
                print(f"   {i}. ID: {gift_id}... | Status: {status} | Delivery: {delivery_time}")
        else:
            print("   No upcoming deliveries")
        
        return True
    except Exception as e:
        print(f"❌ Failed to get upcoming deliveries: {e}")
        return False


def simulate_gift_delivery_test():
    """
    Simulate a gift delivery test
    
    Note: This requires manual setup in your Supabase database:
    1. Create a gift with delivery_time set to now + 2 minutes
    2. Set status to 'completed'
    3. Watch the logs for delivery
    """
    print_section("Gift Delivery Simulation Test")
    
    print("""
    To test the gift delivery system:
    
    1. In your Supabase SQL Editor, run:
    
       -- Create a test gift (adjust to_user_id and from_user_id as needed)
       INSERT INTO gifts (
         from_user_id,
         to_user_id,
         delivery_email,
         status,
         occasion,
         relationship,
         delivery_time,
         child_name,
         age_group,
         checked
       ) VALUES (
         'YOUR_FROM_USER_ID'::UUID,
         'YOUR_TO_USER_ID'::UUID,
         'recipient@example.com',
         'completed',
         'Birthday',
         'Parent',
         NOW() + INTERVAL '2 minutes',  -- Delivers in 2 minutes
         'Test Child',
         '7-10',
         FALSE
       );
    
    2. Watch the backend logs for:
       - "📦 Found 1 gifts ready for delivery"
       - "🎁 Delivering gift..."
       - "✅ Successfully delivered gift"
    
    3. On the frontend (if logged in as recipient):
       - Check browser console for "🎁 Received gift update"
       - Notification badge should appear
       - Click notification to mark as read
    
    4. The scheduler checks every 60 seconds, so delivery may take up to 1 minute
       after the delivery_time is reached.
    """)
    
    return True


def run_all_tests():
    """Run all tests"""
    print("\n")
    print("╔" + "=" * 58 + "╗")
    print("║" + " " * 10 + "GIFT DELIVERY SYSTEM TEST SUITE" + " " * 16 + "║")
    print("╚" + "=" * 58 + "╝")
    
    tests = [
        ("Health Check", test_health_check),
        ("Scheduler Status", test_scheduler_status),
        ("Upcoming Deliveries", lambda: test_upcoming_deliveries(24)),
        ("Delivery Simulation Guide", simulate_gift_delivery_test),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"\n❌ Test '{test_name}' crashed: {e}")
            results.append((test_name, False))
        
        time.sleep(0.5)  # Small delay between tests
    
    # Print summary
    print_section("Test Summary")
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"   {status} - {test_name}")
    
    print(f"\n   Total: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n   🎉 All tests passed!")
    else:
        print(f"\n   ⚠️  {total - passed} test(s) failed")
    
    print("\n" + "=" * 60 + "\n")


if __name__ == "__main__":
    run_all_tests()

