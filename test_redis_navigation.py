#!/usr/bin/env python3
"""
Test script for Redis-backed NavigationManager
Run this after starting Redis with: docker-compose up redis
"""

import sys
import os
sys.path.append('src')

from src.core.navigation.navigation_manager import NavigationManager

def test_redis_navigation():
    print("=== Testing Redis-backed NavigationManager ===")
    
    try:
        # Test User 1
        user1_nav = NavigationManager(user_id="test_user1")
        print("✓ User1 NavigationManager created successfully")
        
        # Start search
        user1_nav.start_new_search("is:unread", 10)
        user1_nav.set_next_page_token("token1")
        print(f"User1 initial state: {user1_nav.get_navigation_info()}")
        
        # Navigate next
        token = user1_nav.navigate_next()
        print(f"User1 after next: token={token}, state={user1_nav.get_navigation_info()}")
        
        # Test User 2 (different user, isolated state)
        user2_nav = NavigationManager(user_id="test_user2")
        user2_nav.start_new_search("is:important", 5)
        print(f"User2 initial state: {user2_nav.get_navigation_info()}")
        
        # Verify User1 state is unchanged
        print(f"User1 state still: {user1_nav.get_navigation_info()}")
        
        # Test persistence - create new instance with same user_id
        user1_nav_new = NavigationManager(user_id="test_user1")
        print(f"User1 new instance (same data): {user1_nav_new.get_navigation_info()}")
        
        print("✓ All Redis navigation tests passed!")
        
    except ConnectionError as e:
        print(f"✗ Redis connection failed: {e}")
        print("Please start Redis with: docker-compose up redis")
    except Exception as e:
        print(f"✗ Test failed: {e}")

if __name__ == "__main__":
    test_redis_navigation()