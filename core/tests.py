from unittest.mock import patch
from urllib.error import URLError

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


class CitySuggestionsTests(TestCase):
    """The nearby-city endpoint must stay opt-in, private, and offline-tolerant."""

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="geo-user",
            email="geo@example.com",
            password="pass12345",
            full_name="Geo User",
        )
        self.client.force_login(self.user)
        self.url = reverse("core:cities")
        self.coords = {"lat": "6.9165", "lon": "122.0590"}

    def test_anonymous_user_is_redirected(self):
        self.client.logout()
        response = self.client.get(self.url, self.coords)
        self.assertEqual(response.status_code, 302)

    def test_invalid_coordinates_are_rejected(self):
        for params in ({}, {"lat": "abc", "lon": "0"}, {"lat": "91", "lon": "0"}):
            with self.subTest(params=params):
                response = self.client.get(self.url, params)
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.json()["cities"], [])

    def test_only_get_is_allowed(self):
        response = self.client.post(self.url, self.coords)
        self.assertEqual(response.status_code, 405)

    @patch("core.views.cache")
    def test_returns_city_and_area_labels(self, mock_cache):
        mock_cache.get.return_value = None
        payload = {
            "address": {
                "city": "Zamboanga City",
                "village": "Campo Islam",
                "state": "Zamboanga del Sur",  # too broad to use as a city
                "country": "Philippines",
            }
        }
        with patch("core.views._fetch_reverse", return_value=payload):
            response = self.client.get(self.url, self.coords)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"cities": ["Zamboanga City", "Campo Islam"]})
        mock_cache.set.assert_called_once()

    @patch("core.views.cache")
    def test_cached_result_skips_upstream(self, mock_cache):
        mock_cache.get.return_value = ["Cached City"]
        with patch("core.views._fetch_reverse") as fetch:
            response = self.client.get(self.url, self.coords)

        self.assertEqual(response.json(), {"cities": ["Cached City"]})
        fetch.assert_not_called()

    @patch("core.views.cache")
    def test_upstream_failure_is_graceful(self, mock_cache):
        mock_cache.get.return_value = None
        with patch("core.views._fetch_reverse", side_effect=URLError("offline")):
            response = self.client.get(self.url, self.coords)

        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json()["cities"], [])
