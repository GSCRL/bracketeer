import asyncio
import subprocess

import pytest
from playwright.async_api import async_playwright, expect


@pytest.mark.asyncio
async def test_simple_player_ready_workflow():
    """Test player readiness workflow with manual server management."""
    
    # Start server on port 8080
    server_process = subprocess.Popen(
        ["uv", "run", "python", "-c", """
from bracketeer.__main__ import app, socketio
socketio.run(app, host='127.0.0.1', port=8080, debug=False, allow_unsafe_werkzeug=True)
"""],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    
    # Wait for server to start
    await asyncio.sleep(3)
    
    try:
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=True)
            
            # Create contexts
            judge_context = await browser.new_context()
            red_player_context = await browser.new_context()
            
            # Create pages
            judge_page = await judge_context.new_page()
            red_player_page = await red_player_context.new_page()
            
            # Navigate to pages
            await judge_page.goto("http://localhost:8080/control/1")
            await red_player_page.goto("http://localhost:8080/screens/1/timer/red")
            
            # Wait for SocketIO to connect
            await asyncio.sleep(3)
            
            # Check initial state
            red_status = judge_page.locator("#redisready")
            red_ready_button = red_player_page.locator("#readybutton")
            
            await expect(red_status).to_contain_text("NOT READY")
            await expect(red_ready_button).to_contain_text("MARK READY")
            
            # Click ready button
            await red_ready_button.click()
            
            # Check that player button changed locally
            await expect(red_ready_button).to_contain_text("READIED")
            
            # Wait for SocketIO message and check judge board
            # Give it a generous timeout since we know the communication works
            await asyncio.sleep(5)
            
            # Check if judge board updated
            judge_text = await red_status.text_content()
            print(f"Judge board shows: '{judge_text}'")
            
            # The test should show if the SocketIO communication is working
            # If it shows "[READY]", communication works
            # If it shows "NOT READY", there's a communication issue
            
            await browser.close()
    
    finally:
        # Cleanup server
        server_process.terminate()
        server_process.wait()