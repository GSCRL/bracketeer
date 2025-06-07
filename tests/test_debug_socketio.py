import asyncio

import pytest
from playwright.async_api import expect


class TestDebugSocketIO:
    """Debug SocketIO connectivity issues."""
    
    @pytest.mark.asyncio
    async def test_pages_load_correctly(self, bracketeer_server, browser_contexts):
        """Test that all pages load without errors."""
        cage_id = 1
        
        # Setup pages
        judge_page = await browser_contexts["judge"].new_page()
        red_player_page = await browser_contexts["red_player"].new_page()
        
        # Navigate to pages
        await judge_page.goto(f"{bracketeer_server}/control/{cage_id}")
        await red_player_page.goto(f"{bracketeer_server}/screens/{cage_id}/timer/red")
        
        # Wait for pages to load
        await asyncio.sleep(3)
        
        # Check that pages loaded successfully
        judge_title = await judge_page.title()
        red_title = await red_player_page.title()
        
        print(f"Judge page title: {judge_title}")
        print(f"Red player page title: {red_title}")
        
        # Check for key elements
        ready_button = red_player_page.locator("#readybutton")
        judge_red_status = judge_page.locator("#redisready")
        
        await expect(ready_button).to_be_visible()
        await expect(judge_red_status).to_be_visible()
        
        # Print initial button text
        ready_text = await ready_button.text_content()
        judge_text = await judge_red_status.text_content()
        
        print(f"Ready button text: {ready_text}")
        print(f"Judge status text: {judge_text}")
    
    @pytest.mark.asyncio 
    async def test_socket_connection(self, bracketeer_server, browser_contexts):
        """Test SocketIO connection by checking console logs."""
        cage_id = 1
        
        # Setup page with console logging
        red_player_page = await browser_contexts["red_player"].new_page()
        
        # Listen for console logs
        console_logs = []
        red_player_page.on("console", lambda msg: console_logs.append(f"{msg.type}: {msg.text}"))
        
        # Navigate to page
        await red_player_page.goto(f"{bracketeer_server}/screens/{cage_id}/timer/red")
        
        # Wait for page load and socket connection
        await asyncio.sleep(5)
        
        # Check if SocketIO connected
        socket_connected = await red_player_page.evaluate("typeof socket !== 'undefined' && socket.connected")
        print(f"Socket connected: {socket_connected}")
        
        # Print console logs for debugging
        print("Console logs:")
        for log in console_logs:
            print(f"  {log}")
        
        # Try to emit a test event
        await red_player_page.evaluate("""
            if (typeof socket !== 'undefined') {
                socket.emit('test_event', {message: 'test from playwright'});
                console.log('Test event emitted');
            } else {
                console.log('Socket not available');
            }
        """)
        
        await asyncio.sleep(2)
    
    @pytest.mark.asyncio
    async def test_manual_ready_click(self, bracketeer_server, browser_contexts):
        """Test clicking ready button manually and checking immediate feedback."""
        cage_id = 1
        
        # Setup pages
        judge_page = await browser_contexts["judge"].new_page()
        red_player_page = await browser_contexts["red_player"].new_page()
        
        # Navigate to pages
        await judge_page.goto(f"{bracketeer_server}/control/{cage_id}")
        await red_player_page.goto(f"{bracketeer_server}/screens/{cage_id}/timer/red")
        
        # Wait for pages to load
        await asyncio.sleep(3)
        
        # Get initial state
        ready_button = red_player_page.locator("#readybutton")
        initial_text = await ready_button.text_content()
        print(f"Initial ready button text: {initial_text}")
        
        # Click ready button
        await ready_button.click()
        
        # Check if button text changed locally (should happen immediately)
        await asyncio.sleep(1)
        after_click_text = await ready_button.text_content()
        print(f"After click ready button text: {after_click_text}")
        
        # Check judge board after longer wait
        await asyncio.sleep(3)
        judge_status = judge_page.locator("#redisready")
        judge_text = await judge_status.text_content()
        print(f"Judge status after click: {judge_text}")
        
        # The button should change locally even if SocketIO fails
        assert after_click_text != initial_text, "Button should change locally after click"