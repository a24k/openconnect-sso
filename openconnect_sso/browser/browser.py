import json
import structlog
from logging import CRITICAL

from urllib.parse import urlparse
from selenium import webdriver
from selenium.webdriver import DesiredCapabilities
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from webdriver_manager.utils import ChromeType
from selenium.webdriver.common.proxy import Proxy, ProxyType
from ..config import DisplayMode

from openconnect_sso import config

logger = structlog.get_logger()


class Browser:
    def __init__(self, proxy=None, display_mode=DisplayMode.SHOWN):
        self.cfg = config.load()
        self.proxy = proxy
        self.display_mode = display_mode
        self.cookies = {}

    def __enter__(self):
        chrome_options = Options()
        capabilities = DesiredCapabilities.CHROME

        if self.display_mode == DisplayMode.HIDDEN:
            chrome_options.add_argument("headless")
            chrome_options.add_argument("no-sandbox")
            chrome_options.add_argument('--disable-dev-shm-usage')

        if self.proxy:
            proxy = Proxy()
            proxy.proxy_type = ProxyType.MANUAL
            parsed = urlparse(self.proxy)
            if parsed.scheme.startswith("socks5"):
                proxy.socks_proxy = f"{parsed.hostname}:{parsed.port}"
            elif parsed.scheme.startswith("http"):
                proxy.http_proxy = f"{parsed.hostname}:{parsed.port}"
            elif parsed.scheme.startswith("ssl"):
                proxy.ssl_proxy = f"{parsed.hostname}:{parsed.port}"
            else:
                raise ValueError("Unsupported proxy type", parsed.scheme)

            proxy.add_to_capabilities(capabilities)

        self.driver = webdriver.Chrome(
            ChromeDriverManager(chrome_type=ChromeType.CHROMIUM, log_level=CRITICAL).install(),
            options=chrome_options,
            desired_capabilities=capabilities
        )
        return self

    def authenticate_at(self, url, credentials, login_final_url):
        self.driver.get(url)

        if credentials:
            for url_pattern, rules in self.cfg.auto_fill_rules.items():
                script = f"""
// ==UserScript==
// @include {url_pattern}
// ==/UserScript==

{get_selectors(rules, credentials)}
"""
                self.driver.execute_script(script)

        logger.info("Waiting for browser")
        WebDriverWait(self.driver, 90, poll_frequency=1).until(lambda driver:
                self.find_cookies()
                and
                self.driver.execute_script(script) == None
                and
                driver.current_url == login_final_url
                )
        logger.info("Browser exited")

    def find_cookies(self):
        for cookie in self.driver.get_cookies():
            logger.debug(f"Cookie found: {cookie['name']}")
            self.cookies[cookie["name"]] = cookie["value"]
        return True

    def get_cookie(self, cookie_name):
        return self.cookies[cookie_name]

    def __exit__(self, exc_type, exc_value, t):
        self.driver.close()
        return True

def get_selectors(rules, credentials):
    statements = []
    for rule in rules:
        selector = json.dumps(rule.selector)
        if rule.action == "stop":
            statements.append(
                f"""var elem = document.querySelector({selector}); if (elem) {{ return; }}"""
            )
        elif rule.fill:
            value = json.dumps(getattr(credentials, rule.fill, None))
            if value:
                statements.append(
                    f"""var elem = document.querySelector({selector}); if (elem) {{ elem.dispatchEvent(new Event("focus")); elem.value = {value}; elem.dispatchEvent(new Event("blur")); }}"""
                )
            else:
                logger.warning(
                    "Credential info not available",
                    type=rule.fill,
                    possibilities=dir(credentials),
                )
        elif rule.action == "click":
            statements.append(
                f"""var elem = document.querySelector({selector}); if (elem) {{ elem.dispatchEvent(new Event("focus")); elem.click(); }}"""
            )
    return "\n".join(statements)
