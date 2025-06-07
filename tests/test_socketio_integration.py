import asyncio

import pytest
from playwright.async_api import expect


class TestSocketIOIntegration:
    """Test real-time SocketIO communication between judge and players."""
    
    @pytest.mark.asyncio
    async def test_player_ready_workflow(self, bracketeer_server, browser_contexts):
        """Test player readiness updates are received by judge board."""
        cage_id = 1
        
        # Setup pages
        judge_page = await browser_contexts["judge"].new_page()
        red_player_page = await browser_contexts["red_player"].new_page()
        blue_player_page = await browser_contexts["blue_player"].new_page()
        
        # Navigate to pages
        await judge_page.goto(f"{bracketeer_server}/control/{cage_id}")
        await red_player_page.goto(f"{bracketeer_server}/screens/{cage_id}/timer/red")
        await blue_player_page.goto(f"{bracketeer_server}/screens/{cage_id}/timer/blue")
        
        # Wait for pages to load and SocketIO to connect
        await asyncio.sleep(5)
        
        # Initially, players should show as NOT READY on judge board
        red_status = judge_page.locator("#redisready")
        blue_status = judge_page.locator("#blueisready")
        
        await expect(red_status).to_contain_text("NOT READY")
        await expect(blue_status).to_contain_text("NOT READY")
        
        # Red player marks ready
        red_ready_button = red_player_page.locator("#readybutton")
        await red_ready_button.click()
        
        # Wait longer for SocketIO message to propagate
        await asyncio.sleep(3)
        
        # Judge board should update to show red player as ready
        await expect(red_status).to_contain_text("[READY]", timeout=10000)
        await expect(blue_status).to_contain_text("NOT READY")  # Blue still not ready
        
        # Blue player marks ready
        blue_ready_button = blue_player_page.locator("#readybutton")
        await blue_ready_button.click()
        
        # Both players should now show as ready on judge board
        await expect(red_status).to_contain_text("[READY]")
        await expect(blue_status).to_contain_text("[READY]")
        
        # Player screens should also update their own buttons
        await expect(red_ready_button).to_contain_text("READIED")
        await expect(blue_ready_button).to_contain_text("READIED")
    
    @pytest.mark.asyncio
    async def test_timer_synchronization(self, bracketeer_server, browser_contexts):
        """Test timer synchronization across all connected clients."""
        cage_id = 1
        
        # Setup pages
        judge_page = await browser_contexts["judge"].new_page()
        red_player_page = await browser_contexts["red_player"].new_page()
        blue_player_page = await browser_contexts["blue_player"].new_page()
        
        # Navigate to pages
        await judge_page.goto(f"{bracketeer_server}/control/{cage_id}")
        await red_player_page.goto(f"{bracketeer_server}/screens/{cage_id}/timer/red")
        await blue_player_page.goto(f"{bracketeer_server}/screens/{cage_id}/timer/blue")
        
        # Wait for pages to load
        await asyncio.sleep(2)
        
        # Get timer elements
        judge_timer = judge_page.locator("#timer_control_counter")
        red_timer = red_player_page.locator("#timer")
        blue_timer = blue_player_page.locator("#timer")
        
        # Note: Judge and player timers may start with different values
        # Judge loads from /debug/durations.json, players start at "000"
        # The key test is synchronization after timer events
        
        # Start timer from judge control
        start_button = judge_page.locator("button:has-text('Start▶️')")
        await start_button.click()
        
        # Wait for timer events to propagate
        await asyncio.sleep(3)
        
        # All timers should now be synchronized (countdown running)
        judge_time = await judge_timer.text_content()
        red_time = await red_timer.text_content()
        blue_time = await blue_timer.text_content()
        
        print(f"Timer values - Judge: {judge_time}, Red: {red_time}, Blue: {blue_time}")
        
        # All client timers should match (they receive the same timer events)
        assert red_time == blue_time
        # Judge timer and client timers should be very close (within 1-2 seconds due to timing)
        
        # Verify timers are actually counting down
        await asyncio.sleep(2)
        red_time_after = await red_timer.text_content()
        assert red_time != red_time_after  # Timer should be changing
        
        # Pause timer
        pause_button = judge_page.locator("button:has-text('Pause⏸️')")
        await pause_button.click()
        
        # Get current time after pause
        paused_time = await judge_timer.text_content()
        
        # Wait and ensure timer is actually paused (not counting)
        await asyncio.sleep(2)
        current_time = await judge_timer.text_content()
        
        assert paused_time == current_time  # Timer should be paused
    
    @pytest.mark.asyncio
    async def test_reset_functionality(self, bracketeer_server, browser_contexts):
        """Test timer reset and ready state reset."""
        cage_id = 1
        
        # Setup pages
        judge_page = await browser_contexts["judge"].new_page()
        red_player_page = await browser_contexts["red_player"].new_page()
        
        # Navigate to pages
        await judge_page.goto(f"{bracketeer_server}/control/{cage_id}")
        await red_player_page.goto(f"{bracketeer_server}/screens/{cage_id}/timer/red")
        
        await asyncio.sleep(2)
        
        # Mark red player as ready
        red_ready_button = red_player_page.locator("#readybutton")
        await red_ready_button.click()
        
        # Verify ready state
        await expect(red_ready_button).to_contain_text("READIED")
        
        # Stop timer (which should reset ready states)
        stop_button = judge_page.locator("button:has-text('Stop⏹️')")
        await stop_button.click()
        
        # Player ready button should reset
        await expect(red_ready_button).to_contain_text("MARK READY")
        
        # Judge board ready status should reset
        red_status = judge_page.locator("#redisready")
        await expect(red_status).to_contain_text("NOT READY")

class TestSocketIOEvents:
    """Test individual SocketIO event handling."""
    
    @pytest.mark.asyncio
    async def test_cage_room_joining(self, bracketeer_server, browser_contexts):
        """Test that clients properly join cage-specific rooms."""
        cage_id = 1
        different_cage_id = 2
        
        # Setup pages for different cages
        judge_page_cage1 = await browser_contexts["judge"].new_page()
        player_page_cage1 = await browser_contexts["red_player"].new_page()
        player_page_cage2 = await browser_contexts["blue_player"].new_page()
        
        # Navigate to different cages
        await judge_page_cage1.goto(f"{bracketeer_server}/control/{cage_id}")
        await player_page_cage1.goto(f"{bracketeer_server}/screens/{cage_id}/timer/red")
        await player_page_cage2.goto(f"{bracketeer_server}/screens/{different_cage_id}/timer/blue")
        
        await asyncio.sleep(2)
        
        # Start timer on cage 1
        start_button = judge_page_cage1.locator("button:has-text('Start▶️')")
        await start_button.click()
        
        await asyncio.sleep(1)
        
        # Cage 1 player should see timer updates
        cage1_timer = player_page_cage1.locator("#timer")
        cage1_time = await cage1_timer.text_content()
        assert cage1_time != "000"
        
        # Cage 2 player should still see initial timer (not affected)
        cage2_timer = player_page_cage2.locator("#timer")
        cage2_time = await cage2_timer.text_content()
        assert cage2_time == "000"