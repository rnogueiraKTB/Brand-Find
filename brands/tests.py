from datetime import date

from django.contrib.auth.models import Permission
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
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
        self.assertNotContains(response, "dropdown-item")
        self.assertNotContains(response, "No brands found for this search.")

    def test_live_search_no_match_shows_empty_message(self):
        response = self.client.get(reverse("brands:live_search"), {"q": "zzzz-not-found"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No brands found for this search.")
        self.assertNotContains(response, "dropdown-item")

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
    def _login_staff_user(self):
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
        return user

    def test_admin_redirects_anonymous_user(self):
        response = self.client.get("/admin/brands/brandentry/")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/admin/login/", response.url)

    def test_staff_user_with_permissions_can_access_admin(self):
        self._login_staff_user()

        response = self.client.get("/admin/brands/brandentry/")
        self.assertEqual(response.status_code, 200)

    def test_staff_can_access_csv_upload_page(self):
        self._login_staff_user()

        response = self.client.get(reverse("admin:brands_brandentry_upload_csv"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Upload brands CSV")

    def test_csv_upload_creates_and_updates_brands(self):
        self._login_staff_user()

        BrandEntry.objects.create(
            brand="Alpha Brand",
            inquire_to="Old Team",
            notes="Old note",
            info_received_from="Old source",
        )

        csv_content = (
            "brand;inquire;notes;last updated;info from\n"
            "Alpha Brand;Team Alpha;Updated note;2025-01-05;Email\n"
            "Gamma Brand;Team Gamma;New note;06/01/2025;Trade Show\n"
        )
        upload = SimpleUploadedFile("brands.csv", csv_content.encode("utf-8"), content_type="text/csv")

        response = self.client.post(
            reverse("admin:brands_brandentry_upload_csv"),
            {"csv_file": upload},
        )

        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse("admin:brands_brandentry_changelist"))

        alpha = BrandEntry.objects.get(brand="Alpha Brand")
        gamma = BrandEntry.objects.get(brand="Gamma Brand")

        self.assertEqual(alpha.inquire_to, "Team Alpha")
        self.assertEqual(alpha.notes, "Updated note")
        self.assertEqual(alpha.info_received_from, "Email")
        self.assertEqual(alpha.last_changed_on, date(2025, 1, 5))

        self.assertEqual(gamma.inquire_to, "Team Gamma")
        self.assertEqual(gamma.notes, "New note")
        self.assertEqual(gamma.info_received_from, "Trade Show")
        self.assertEqual(gamma.last_changed_on, date(2025, 1, 6))

    def test_csv_upload_allows_missing_notes_column(self):
        self._login_staff_user()

        csv_content = (
            "brand;inquire;last updated;info from\n"
            "Delta Brand;Team Delta;2025-02-01;Call\n"
        )
        upload = SimpleUploadedFile("brands_no_notes.csv", csv_content.encode("utf-8"), content_type="text/csv")

        response = self.client.post(
            reverse("admin:brands_brandentry_upload_csv"),
            {"csv_file": upload},
        )

        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse("admin:brands_brandentry_changelist"))

        delta = BrandEntry.objects.get(brand="Delta Brand")
        self.assertEqual(delta.inquire_to, "Team Delta")
        self.assertEqual(delta.notes, "")
        self.assertEqual(delta.info_received_from, "Call")
        self.assertEqual(delta.last_changed_on, date(2025, 2, 1))

    def test_csv_upload_allows_missing_info_from_column(self):
        self._login_staff_user()

        csv_content = (
            "brand;inquire;last updated\n"
            "Epsilon Brand;Team Epsilon;2025-02-10\n"
        )
        upload = SimpleUploadedFile(
            "brands_no_info_from.csv",
            csv_content.encode("utf-8"),
            content_type="text/csv",
        )

        response = self.client.post(
            reverse("admin:brands_brandentry_upload_csv"),
            {"csv_file": upload},
        )

        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse("admin:brands_brandentry_changelist"))

        epsilon = BrandEntry.objects.get(brand="Epsilon Brand")
        self.assertEqual(epsilon.inquire_to, "Team Epsilon")
        self.assertEqual(epsilon.notes, "")
        self.assertEqual(epsilon.info_received_from, "")
        self.assertEqual(epsilon.last_changed_on, date(2025, 2, 10))
