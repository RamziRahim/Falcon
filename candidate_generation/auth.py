"""
Falcon - Candidate Generation Authentication
Module: auth.py
Version: 1.1.0
"""

from typing import Tuple
from playwright.sync_api import sync_playwright, Browser, Page
from config import (HEADLESS,SCREENER_LOGIN_URL,SCREENER_TIMEOUT,)
from common.logger import get_logger
from config import FALCON_VERSION

logger = get_logger("auth")

class AuthenticationError(Exception):
    pass

def login(username:str,password:str)->Tuple[object,Browser,Page]:
    logger.info("Starting browser")
    p=sync_playwright().start()
    browser=p.chromium.launch(headless=HEADLESS)
    page=browser.new_page()
    page.goto(SCREENER_LOGIN_URL,wait_until="domcontentloaded",timeout=SCREENER_TIMEOUT)
    page.fill("input[name='username']",username)
    page.fill("input[name='password']",password)
    page.click("button[type='submit']")
    page.wait_for_timeout(5000)
    page.wait_for_load_state("domcontentloaded")
    if "/login" in page.url.lower():
        browser.close(); p.stop()
        raise AuthenticationError("Login failed")
    logger.info("Login successful")
    return p,browser,page

def validate_session(page:Page)->bool:
    return "/login" not in page.url.lower()

def logout(playwright,browser:Browser)->None:
    logger.info("Closing browser")
    try:
        browser.close()
    finally:
        playwright.stop()
