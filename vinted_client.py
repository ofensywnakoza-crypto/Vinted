import time
from typing import Optional
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service
import json

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "pl-PL,pl;q=0.9,en;q=0.8",
    "Referer": "https://www.vinted.pl/",
}


class VintedClient:
    def __init__(self, domain: str = "www.vinted.pl"):
        self.base_url = f"https://{domain}"
        self.driver = None
        self.cookies_set = False
        self._last_request = 0.0
        self._min_delay = 2.5

    def _init_driver(self):
        """Initialize Selenium WebDriver (real browser)."""
        if self.driver is not None:
            return

        options = webdriver.ChromeOptions()
        options.add_argument("--start-maximized")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument(f"user-agent={HEADERS['User-Agent']}")

        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=options)

    def set_cookie(self, cookie_value: str) -> None:
        """Parse and set cookies from browser string."""
        self._init_driver()
        self.driver.get(self.base_url)
        time.sleep(1)

        cookie_value = cookie_value.strip()

        if "=" in cookie_value and ";" in cookie_value:
            # Full browser cookie string
            for part in cookie_value.split(";"):
                part = part.strip()
                if "=" in part:
                    name, _, value = part.partition("=")
                    try:
                        self.driver.add_cookie({
                            "name": name.strip(),
                            "value": value.strip(),
                            "domain": ".vinted.pl",
                            "path": "/"
                        })
                    except Exception:
                        pass
        else:
            # Single _vinted_fr_session value
            try:
                self.driver.add_cookie({
                    "name": "_vinted_fr_session",
                    "value": cookie_value,
                    "domain": ".vinted.pl",
                    "path": "/"
                })
            except Exception:
                pass

        self.cookies_set = True

    def verify_auth(self) -> bool:
        user = self.get_current_user()
        return user is not None

    def _get(self, endpoint: str, params: dict = None, retries: int = 3) -> Optional[dict]:
        """Fetch API endpoint using Selenium's browser session."""
        if not self.cookies_set or self.driver is None:
            return None

        elapsed = time.time() - self._last_request
        if elapsed < self._min_delay:
            time.sleep(self._min_delay - elapsed)

        url = f"{self.base_url}{endpoint}"
        if params:
            query = "&".join(f"{k}={v}" for k, v in params.items())
            url = f"{url}?{query}"

        for attempt in range(retries):
            try:
                # execute_async_script properly waits for Promise to resolve
                script = """
                var done = arguments[arguments.length - 1];
                fetch(arguments[0], {
                    method: 'GET',
                    headers: {'Accept': 'application/json'},
                    credentials: 'include'
                })
                .then(r => r.json())
                .then(data => done({ok: true, data: data}))
                .catch(e => done({ok: false, error: e.toString()}));
                """
                self.driver.set_script_timeout(20)
                result = self.driver.execute_async_script(script, url)
                self._last_request = time.time()

                if result and result.get("ok") and isinstance(result.get("data"), dict):
                    return result["data"]
                return None

            except Exception:
                if attempt < retries - 1:
                    time.sleep(5)

        return None

    def get_current_user(self) -> Optional[dict]:
        data = self._get("/api/v2/users/current_user")
        return data.get("user") if data and "user" in data else None

    def get_user_by_id(self, user_id: int) -> Optional[dict]:
        data = self._get(f"/api/v2/users/{user_id}")
        return data.get("user") if data else None

    def get_user_items_page(self, user_id: int, page: int = 1, per_page: int = 96) -> Optional[dict]:
        return self._get(
            f"/api/v2/users/{user_id}/items",
            params={"page": page, "per_page": per_page},
        )

    def get_all_user_items(self, user_id: int) -> list[dict]:
        items: list[dict] = []
        page = 1
        while True:
            data = self.get_user_items_page(user_id, page=page)
            if not data:
                break
            batch = data.get("items", [])
            items.extend(batch)
            total_pages = data.get("pagination", {}).get("total_pages", 1)
            if page >= total_pages or not batch:
                break
            page += 1
        return items

    def search_similar(
        self,
        catalog_id: int = None,
        brand_id: int = None,
        price_from: float = None,
        price_to: float = None,
        per_page: int = 96,
    ) -> list[dict]:
        params: dict = {"per_page": per_page, "order": "newest_first"}
        if catalog_id:
            params["catalog_ids[]"] = catalog_id
        if brand_id:
            params["brand_ids[]"] = brand_id
        if price_from is not None:
            params["price_from"] = price_from
        if price_to is not None:
            params["price_to"] = price_to

        data = self._get("/api/v2/catalog/items", params=params)
        return data.get("items", []) if data else []

    def close(self):
        """Close the browser when done."""
        if self.driver:
            self.driver.quit()
            self.driver = None

