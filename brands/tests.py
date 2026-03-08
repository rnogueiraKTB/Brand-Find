from datetime import date

from django.contrib.auth.models import Permission
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import BrandEntry


class BrandEntryModelTests(TestCase):
    def test_last_changed_on_updates_automatically(self):
        entry = BrandEntry.objects.create(
            brand="Alpha",
            inquire_to="Support Team",
            notes="Initial note",
            info_received_from="Operations",
        )

        self.assertIsInstance(entry.last_changed_on, date)
        entry.last_changed_on = date(2000, 1, 1)
        entry.notes = "Updated note"
        entry.save()

        self.assertEqual(entry.last_changed_on, timezone.localdate())


class BrandViewsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.alpha = BrandEntry.objects.create(
            brand="Alpha Brand",
            inquire_to="Team Alpha",
            notes="Alpha details",
            info_received_from="Email",
        )
        BrandEntry.objects.create(
            brand="Beta Brand",
            inquire_to="Team Beta",
            notes="Beta details",
            info_received_from="Meeting",
        )

    def test_home_is_public(self):
        response = self.client.get(reverse("brands:home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Brand Lookup")

    def test_live_search_matches_case_insensitive(self):
        response = self.client.get(reverse("brands:live_search"), {"q": "alpha"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Alpha Brand")

    def test_live_search_empty_query_returns_no_results(self):
        response = self.client.get(reverse("brands:live_search"), {"q": "   "})
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "result-item")

    def test_live_search_limits_to_ten_sorted_results(self):
        for index in range(15):
            BrandEntry.objects.create(
                brand=f"Brand {index:02d}",
                inquire_to="Ops",
                notes="Generated",
                info_received_from="Seed script",
            )

        response = self.client.get(reverse("brands:live_search"), {"q": "Brand"})
        self.assertEqual(response.status_code, 200)
        results = list(response.context["results"])

        self.assertEqual(len(results), 10)
        self.assertEqual([result.brand for result in results], sorted(result.brand for result in results))

    def test_brand_detail_returns_200_for_valid_id(self):
        response = self.client.get(reverse("brands:brand_detail", kwargs={"pk": self.alpha.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Info received from")

    def test_brand_detail_returns_404_for_invalid_id(self):
        response = self.client.get(reverse("brands:brand_detail", kwargs={"pk": 999999}))
        self.assertEqual(response.status_code, 404)

    def test_healthz_returns_ok(self):
        response = self.client.get(reverse("brands:healthz"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), "ok")


class AdminAccessTests(TestCase):
    def test_admin_redirects_anonymous_user(self):
        response = self.client.get("/admin/brands/brandentry/")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/admin/login/", response.url)

    def test_staff_user_with_permissions_can_access_admin(self):
        user_model = get_user_model()
        user = user_model.objects.create_user(
            username="staffuser",
            password="testpassword123",
            email="staff@example.com",
            is_staff=True,
        )
        permissions = Permission.objects.filter(
            codename__in=["view_brandentry", "add_brandentry", "change_brandentry"]
        )
        user.user_permissions.add(*permissions)

        self.client.login(username="staffuser", password="testpassword123")

        response = self.client.get("/admin/brands/brandentry/")
        self.assertEqual(response.status_code, 200)
