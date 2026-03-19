from datetime import date

from django.contrib.auth.models import Permission
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .admin import BrandEntryAdminForm
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

    def test_selected_brand_increments_search_count(self):
        self.assertEqual(self.alpha.search_count, 0)

        response = self.client.get(reverse("brands:selected_brand"), {"q": "Alpha Brand"})

        self.assertEqual(response.status_code, 200)
        self.alpha.refresh_from_db()
        self.assertEqual(self.alpha.search_count, 1)

    def test_selected_brand_does_not_increment_when_no_match(self):
        response = self.client.get(reverse("brands:selected_brand"), {"q": "Unknown Brand"})

        self.assertEqual(response.status_code, 200)
        self.alpha.refresh_from_db()
        self.assertEqual(self.alpha.search_count, 0)

    def test_healthz_returns_ok(self):
        response = self.client.get(reverse("brands:healthz"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), "ok")


class AdminAccessTests(TestCase):
    @staticmethod
    def _one_pixel_gif() -> SimpleUploadedFile:
        return SimpleUploadedFile(
            "logo.gif",
            (
                b"GIF89a\x01\x00\x01\x00\x80\x00\x00"
                b"\x00\x00\x00\xff\xff\xff!\xf9\x04\x00\x00\x00\x00\x00,"
                b"\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;"
            ),
            content_type="image/gif",
        )

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
        BrandEntry.objects.create(
            brand="Admin Visible Brand",
            inquire_to="Ops",
            notes="",
            info_received_from="",
        )

        response = self.client.get("/admin/brands/brandentry/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Search count")

    def test_staff_can_access_csv_upload_page(self):
        self._login_staff_user()

        response = self.client.get(reverse("admin:brands_brandentry_upload_csv"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Upload brands CSV")

    def test_admin_changelist_shows_top_searched_brands_panel(self):
        self._login_staff_user()
        alpha = BrandEntry.objects.create(
            brand="Alpha Ranked",
            inquire_to="Ops",
            notes="",
            info_received_from="",
        )
        beta = BrandEntry.objects.create(
            brand="Beta Ranked",
            inquire_to="Ops",
            notes="",
            info_received_from="",
        )
        BrandEntry.objects.filter(pk=alpha.pk).update(search_count=8)
        BrandEntry.objects.filter(pk=beta.pk).update(search_count=3)

        response = self.client.get(reverse("admin:brands_brandentry_changelist"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Most searched brands")
        self.assertContains(response, "Alpha Ranked")
        self.assertContains(response, "8 searches")

    def test_csv_upload_creates_and_updates_brands(self):
        self._login_staff_user()

        BrandEntry.objects.create(
            brand="Alpha Brand",
            inquire_to="Old Team",
            notes="Old note",
            info_received_from="Old source",
        )

        csv_content = (
            "brand;inquire;notes;last updated;info from;logo\n"
            "Alpha Brand;Team Alpha;Updated note;2025-01-05;Email;https://cdn.example.com/alpha.png\n"
            "Gamma Brand;Team Gamma;New note;06/01/2025;Trade Show;https://cdn.example.com/gamma.png\n"
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
        self.assertEqual(alpha.logo, "https://cdn.example.com/alpha.png")
        self.assertEqual(alpha.last_changed_on, date(2025, 1, 5))

        self.assertEqual(gamma.inquire_to, "Team Gamma")
        self.assertEqual(gamma.notes, "New note")
        self.assertEqual(gamma.info_received_from, "Trade Show")
        self.assertEqual(gamma.logo, "https://cdn.example.com/gamma.png")
        self.assertEqual(gamma.last_changed_on, date(2025, 1, 6))

    def test_csv_upload_reads_logo_from_column_f_when_logo_header_missing(self):
        self._login_staff_user()

        csv_content = (
            "brand;inquire;notes;last updated;info from;assets\n"
            "Zeta Brand;Team Zeta;Notes;2025-02-11;Call;https://cdn.example.com/zeta.png\n"
        )
        upload = SimpleUploadedFile(
            "brands_logo_column_f.csv",
            csv_content.encode("utf-8"),
            content_type="text/csv",
        )

        response = self.client.post(
            reverse("admin:brands_brandentry_upload_csv"),
            {"csv_file": upload},
        )

        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse("admin:brands_brandentry_changelist"))

        zeta = BrandEntry.objects.get(brand="Zeta Brand")
        self.assertEqual(zeta.logo, "https://cdn.example.com/zeta.png")

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

    def test_admin_form_accepts_logo_url_only(self):
        form = BrandEntryAdminForm(
            data={
                "brand": "URL Brand",
                "logo": "https://cdn.example.com/url-brand.png",
                "inquire_to": ["Europe"],
                "notes": "test",
                "info_received_from": "Email",
            }
        )

        self.assertTrue(form.is_valid())

    def test_admin_form_accepts_logo_image_only(self):
        form = BrandEntryAdminForm(
            data={
                "brand": "Image Brand",
                "logo": "",
                "inquire_to": ["USA"],
                "notes": "",
                "info_received_from": "",
            },
            files={"logo_image": self._one_pixel_gif()},
        )

        self.assertTrue(form.is_valid())

    def test_admin_form_rejects_logo_url_and_image_together(self):
        form = BrandEntryAdminForm(
            data={
                "brand": "Both Brand",
                "logo": "https://cdn.example.com/both-brand.png",
                "inquire_to": ["China"],
                "notes": "",
                "info_received_from": "",
            },
            files={"logo_image": self._one_pixel_gif()},
        )

        self.assertFalse(form.is_valid())
        self.assertIn("logo", form.errors)
        self.assertIn("logo_image", form.errors)
