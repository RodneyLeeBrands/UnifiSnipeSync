# snipe.py
import requests
from ratelimiter import RateLimiter
from time import sleep

class Snipe:
    def __init__(self, api_url, api_key, rate_limit, timeout=30):
        self.api_url = api_url
        self.api_key = api_key
        self.timeout = timeout
        self.headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        self.rate_limiter = RateLimiter(max_calls=rate_limit, period=60)

    def fetch_paginated_results(self, url, params=None):
        results = []
        page = 1

        while True:
            with self.rate_limiter:
                params = params or {}
                params["offset"] = (page - 1) * 500
                params["limit"] = 500
                response = requests.get(url, headers=self.headers, params=params, timeout=self.timeout)

                data = response.json()

                if data.get("status") == "error" and data.get("messages") == "Too Many Requests":
                    sleep(60)
                    self.rate_limiter.clear()
                    continue

                response.raise_for_status()
                results.extend(data["rows"])

                if data["total"] <= len(results):
                    break

                page += 1

        return results


    def get_all_hardware(self, params=None):
        url = f"{self.api_url}/hardware"
        return self.fetch_paginated_results(url, params)

    def get_all_models(self, params=None):
        url = f"{self.api_url}/models"
        return self.fetch_paginated_results(url, params)

    def create_hardware(self, data):
        url = f"{self.api_url}/hardware"
        response = requests.post(url, headers=self.headers, json=data, timeout=self.timeout)
        response.raise_for_status()
        return response

    def update_hardware(self, device_id, data):
        url = f"{self.api_url}/hardware/{device_id}"
        response = requests.patch(url, headers=self.headers, json=data, timeout=self.timeout)
        response.raise_for_status()
        return response

    def create_model(self, data):
        url = f"{self.api_url}/models"
        response = requests.post(url, headers=self.headers, json=data, timeout=self.timeout)
        response.raise_for_status()
        return response