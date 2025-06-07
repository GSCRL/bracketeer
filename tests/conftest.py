import asyncio
import subprocess

import pytest_asyncio
from playwright.async_api import async_playwright


@pytest_asyncio.fixture(scope="session")
async def bracketeer_server():
    """Start Bracketeer server for testing."""
    # Start the server in background
    process = subprocess.Popen(
        ["uv", "run", "bracketeer/__main__.py"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    
    # Wait for server to start
    await asyncio.sleep(5)
    
    yield "http://localhost"
    
    # Cleanup
    process.terminate()
    process.wait()

@pytest_asyncio.fixture
async def browser_contexts():
    """Create multiple browser contexts for multi-user testing."""
    async with async_playwright() as playwright_instance:
        browser = await playwright_instance.chromium.launch(headless=True)
        
        # Create separate contexts for judge and players
        judge_context = await browser.new_context()
        red_player_context = await browser.new_context()
        blue_player_context = await browser.new_context()
        
        yield {
            "judge": judge_context,
            "red_player": red_player_context,
            "blue_player": blue_player_context
        }
        
        # Cleanup
        await judge_context.close()
        await red_player_context.close()
        await blue_player_context.close()
        await browser.close()