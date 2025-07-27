#!/usr/bin/env python3
"""
Test script to verify user isolation in Redis NavigationManager
"""

import sys
import os
sys.path.append('src')

def test_user_isolation():
    print("=== Testing User Isolation in NavigationManager ===")
    
    try:
        from src.core.navigation.navigation_manager import NavigationManager
        
        # Test 1: Different users should have different Redis keys
        user1_nav = NavigationManager(user_id="user1@example.com")
        user2_nav = NavigationManager(user_id="user2@example.com")
        
        print(f"User1 Redis key: {user1_nav.redis_key}")
        print(f"User2 Redis key: {user2_nav.redis_key}")
        
        assert user1_nav.redis_key != user2_nav.redis_key, "❌ Users have same Redis key!"
        print("✅ Users have different Redis keys")
        
        # Test 2: Users should have isolated navigation states
        user1_nav.start_new_search("is:unread", 10)
        user1_nav.set_next_page_token("user1_token")
        
        user2_nav.start_new_search("is:important", 5)  
        user2_nav.set_next_page_token("user2_token")
        
        user1_state = user1_nav.get_navigation_info()
        user2_state = user2_nav.get_navigation_info()
        
        print(f"User1 state: {user1_state}")
        print(f"User2 state: {user2_state}")
        
        assert user1_state["query"] != user2_state["query"], "❌ Users share same query!"
        print("✅ Users have isolated queries")
        
        # Test 3: Navigation actions should not affect other users
        user1_nav.navigate_next()
        user1_after = user1_nav.get_navigation_info()
        user2_unchanged = user2_nav.get_navigation_info()
        
        assert user1_after["current_page"] == 2, "❌ User1 navigation failed"
        assert user2_unchanged["current_page"] == 1, "❌ User2 was affected by User1 navigation"
        print("✅ Navigation actions are isolated per user")
        
        # Test 4: New instances should load existing user data
        user1_new_instance = NavigationManager(user_id="user1@example.com")
        user1_loaded_state = user1_new_instance.get_navigation_info()
        
        assert user1_loaded_state["current_page"] == user1_after["current_page"], "❌ User state not persisted"
        print("✅ User state persists across instances")
        
        # Test 5: Check Redis keys are properly namespaced
        expected_user1_key = "gmail_assistant:navigation:user1@example.com"
        expected_user2_key = "gmail_assistant:navigation:user2@example.com"
        
        assert user1_nav.redis_key == expected_user1_key, f"❌ Wrong key format: {user1_nav.redis_key}"
        assert user2_nav.redis_key == expected_user2_key, f"❌ Wrong key format: {user2_nav.redis_key}"
        print("✅ Redis keys are properly namespaced")
        
        # Test 6: Test data cleanup
        cleared1 = user1_nav.clear_user_data()
        cleared2 = user2_nav.clear_user_data()
        
        assert cleared1, "❌ Failed to clear user1 data"
        assert cleared2, "❌ Failed to clear user2 data"
        print("✅ User data cleanup works")
        
        print("\n🎉 ALL USER ISOLATION TESTS PASSED!")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_user_isolation()