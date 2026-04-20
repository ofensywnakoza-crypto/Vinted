import requests
import time
from typing import Optional

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
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        self._last_request = 0.0
        self._min_delay = 2.5  # seconds between requests — safe rate
        self.user_id: Optional[int] = None

    # ------------------------------------------------------------------ #
    # Auth
    # ------------------------------------------------------------------ #

    def set_cookie(self, cookie_value: str) -> None:
        """Accept either a single _vinted_fr_session value or a full browser cookie string."""
        domain = self.base_url.replace("https://", ".")
        cookie_value = cookie_value.strip()

        if "=" in cookie_value and ";" in cookie_value:
            # Full browser cookie string, e.g. "foo=bar; _vinted_fr_session=eyJ..."
            for part in cookie_value.split(";"):
                part = part.strip()
                if "=" in part:
                    name, _, value = part.partition("=")
                    self.session.cookies.set(name.strip(), value.strip(), domain=domain, path="/")
        else:
            # Single _vinted_fr_session value
            self.session.cookies.set("_vinted_fr_session", cookie_value, domain=domain, path="/")

    def verify_auth(self) -> bool:
        user = self.get_current_user()
        return user is not None

    # ------------------------------------------------------------------ #
    # Internal HTTP
    # ------------------------------------------------------------------ #

    def _get(self, endpoint: str, params: dict = None, retries: int = 3) -> Optional[dict]:
        elapsed = time.time() - self._last_request
        if elapsed < self._min_delay:
            time.sleep(self._min_delay - elapsed)

        url = f"{self.base_url}{endpoint}"
        for attempt in range(retries):
            try:
                resp = self.session.get(url, params=params, timeout=15)
                self._last_request = time.time()
                if resp.status_code == 200:
                    return resp.json()
                if resp.status_code == 429:
                    wait = 30 * (attempt + 1)
                    time.sleep(wait)
                    continue
                return None
            except requests.RequestException:
                if attempt < retries - 1:
                    time.sleep(5)
        return None

    # ------------------------------------------------------------------ #
    # User
    # ------------------------------------------------------------------ #

    def get_current_user(self) -> Optional[dict]:
        data = self._get("/api/v2/users/current_user")
        if data and "user" in data:
            self.user_id = data["user"]["id"]
            return data["user"]
        return None

    def get_user_by_id(self, user_id: int) -> Optional[dict]:
        data = self._get(f"/api/v2/users/{user_id}")
        return data.get("user") if data else None

    # ------------------------------------------------------------------ #
    # Items
    # ------------------------------------------------------------------ #

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
