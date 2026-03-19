import csv
from datetime import date, datetime
from io import StringIO
import re

from django import forms
from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import UploadedFile
from django.core.validators import URLValidator
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.urls import path, reverse
from django.utils.dateparse import parse_date

from .models import BrandEntry

INQUIRE_TO_CHOICES = (
    ("Europe", "Europe"),
    ("USA", "USA"),
    ("China", "China"),
    ("Decline", "Decline"),
)


class BrandEntryAdminForm(forms.ModelForm):
    inquire_to = forms.MultipleChoiceField(
        label="Inquire to",
        choices=INQUIRE_TO_CHOICES,
        widget=forms.CheckboxSelectMultiple,
        required=True,
        help_text="Select one or more destinations.",
    )

    class Meta:
        model = BrandEntry
        fields = "__all__"

    @staticmethod
    def _parse_inquire_to(value: str) -> list[str]:
        if not value:
            return []

        valid_options = {choice for choice, _ in INQUIRE_TO_CHOICES}
        tokens = [
            token.strip()
            for token in re.split(r"[,;/|]+", value)
            if token and token.strip()
        ]

        normalized: list[str] = []
        for token in tokens:
            for option in valid_options:
                if token.lower() == option.lower() and option not in normalized:
                    normalized.append(option)
                    break

        return normalized

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.initial["inquire_to"] = self._parse_inquire_to(self.instance.inquire_to)
        self.fields["logo"].help_text = "Logo URL (use URL or image upload, not both)."
        self.fields["logo_image"].help_text = "Upload a logo image (use URL or image upload, not both)."

    def clean_inquire_to(self) -> str:
        values = self.cleaned_data.get("inquire_to", [])
        return ", ".join(values)

    def clean(self):
        cleaned_data = super().clean()
        logo_url = (cleaned_data.get("logo") or "").strip()
        logo_image = cleaned_data.get("logo_image")

        if logo_url and logo_image:
            error_message = "Provide only one logo source: URL or image upload."
            self.add_error("logo", error_message)
            self.add_error("logo_image", error_message)

        return cleaned_data


class BrandCsvUploadForm(forms.Form):
    csv_file = forms.FileField(
        label="CSV file",
        help_text=(
            "Use headers: brand; inquire; last updated "
            "(notes, info from and logo optional; logo defaults to column F)"
        ),
    )


@admin.register(BrandEntry)
class BrandEntryAdmin(admin.ModelAdmin):
    form = BrandEntryAdminForm
    list_display = ("brand", "search_count", "logo", "inquire_to", "info_received_from", "last_changed_on")
    search_fields = ("brand", "inquire_to", "info_received_from", "notes")
    ordering = ("-search_count", "brand")
    readonly_fields = ("search_count", "last_changed_on")
    change_list_template = "admin/brands/brandentry/change_list.html"

    def changelist_view(self, request: HttpRequest, extra_context=None):
        top_searched_brands = list(
            self.model.objects.filter(search_count__gt=0).order_by("-search_count", "brand")[:10]
        )
        extra_context = {
            **(extra_context or {}),
            "top_searched_brands": top_searched_brands,
        }
        return super().changelist_view(request, extra_context=extra_context)

    @staticmethod
    def _normalize_header(header: str) -> str:
        return " ".join(header.strip().lower().replace("_", " ").split())

    @classmethod
    def _resolve_columns(cls, headers: list[str]) -> dict[str, str]:
        aliases = {
            "brand": {"brand", "marca"},
            "inquire_to": {"inquire", "inquire to", "inquireto", "inquire_to"},
            "notes": {"notes", "note", "notas"},
            "last_changed_on": {
                "last updated",
                "last update",
                "last changed on",
                "last_changed_on",
                "lastupdated",
            },
            "info_received_from": {
                "info from",
                "info received from",
                "info_received_from",
                "info",
            },
            "logo": {"logo", "logo url", "logo_url", "url logo", "logo link"},
        }

        normalized_lookup = {cls._normalize_header(name): name for name in headers if name}
        resolved: dict[str, str] = {}

        for logical_name, options in aliases.items():
            for alias in options:
                source_name = normalized_lookup.get(alias)
                if source_name:
                    resolved[logical_name] = source_name
                    break

        # If no logo header alias is found, assume the URL is in column F.
        if "logo" not in resolved and len(headers) >= 6:
            fallback_logo_column = headers[5]
            if fallback_logo_column:
                resolved["logo"] = fallback_logo_column

        required = {"brand", "inquire_to", "last_changed_on"}
        missing = sorted(required - set(resolved))
        if missing:
            raise ValueError(
                "Missing required columns. Expected headers: "
                "brand; inquire; last updated "
                "(notes, info from and logo optional; logo defaults to column F)"
            )

        return resolved

    @staticmethod
    def _parse_last_updated(value: str) -> date | None:
        cleaned = value.strip()
        if not cleaned:
            return None

        parsed = parse_date(cleaned)
        if parsed is not None:
            return parsed

        for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d"):
            try:
                return datetime.strptime(cleaned, fmt).date()
            except ValueError:
                continue

        raise ValueError(f"Invalid date format: {value}")

    @staticmethod
    def _parse_logo_url(value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            return ""

        validator = URLValidator(schemes=["http", "https"])
        try:
            validator(cleaned)
        except ValidationError as exc:
            raise ValueError(f"Invalid logo URL: {value}") from exc

        return cleaned

    @classmethod
    def _import_rows_from_csv(cls, uploaded_file: UploadedFile) -> dict[str, int | list[str]]:
        try:
            raw_text = uploaded_file.read().decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise ValueError("CSV must be encoded in UTF-8.") from exc
        if not raw_text.strip():
            raise ValueError("The uploaded file is empty.")

        sample = raw_text[:4096]
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=";,")
            delimiter = dialect.delimiter
        except csv.Error:
            delimiter = ";"

        reader = csv.DictReader(StringIO(raw_text), delimiter=delimiter)
        if not reader.fieldnames:
            raise ValueError("Could not detect CSV headers.")

        columns = cls._resolve_columns(reader.fieldnames)
        created = 0
        updated = 0
        skipped = 0
        errors: list[str] = []

        for line_no, row in enumerate(reader, start=2):
            if not row or not any((value or "").strip() for value in row.values()):
                skipped += 1
                continue

            brand = (row.get(columns["brand"]) or "").strip()
            inquire_to = (row.get(columns["inquire_to"]) or "").strip()
            notes_column = columns.get("notes")
            notes = (row.get(notes_column) or "").strip() if notes_column else ""
            info_from_column = columns.get("info_received_from")
            info_from = (row.get(info_from_column) or "").strip() if info_from_column else ""
            logo_column = columns.get("logo")
            logo_raw = (row.get(logo_column) or "").strip() if logo_column else ""
            last_updated_raw = row.get(columns["last_changed_on"]) or ""

            if not brand or not inquire_to:
                skipped += 1
                errors.append(
                    f"Line {line_no}: skipped because brand and inquire are required."
                )
                continue

            try:
                logo = cls._parse_logo_url(logo_raw)
            except ValueError as exc:
                errors.append(f"Line {line_no}: {exc}")
                logo = ""

            defaults = {
                "inquire_to": inquire_to,
                "notes": notes,
                "info_received_from": info_from,
            }
            if logo_column:
                defaults["logo"] = logo
                if logo:
                    # CSV logo URL takes precedence and clears uploaded image.
                    defaults["logo_image"] = None

            brand_entry, was_created = BrandEntry.objects.update_or_create(
                brand=brand,
                defaults=defaults,
            )

            try:
                parsed_last_updated = cls._parse_last_updated(last_updated_raw)
            except ValueError as exc:
                errors.append(f"Line {line_no}: {exc}")
                parsed_last_updated = None

            if parsed_last_updated is not None:
                BrandEntry.objects.filter(pk=brand_entry.pk).update(last_changed_on=parsed_last_updated)

            if was_created:
                created += 1
            else:
                updated += 1

        return {
            "created": created,
            "updated": updated,
            "skipped": skipped,
            "errors": errors,
        }

    def get_urls(self):
        custom_urls = [
            path(
                "upload-csv/",
                self.admin_site.admin_view(self.upload_csv_view),
                name="brands_brandentry_upload_csv",
            )
        ]
        return custom_urls + super().get_urls()

    def upload_csv_view(self, request: HttpRequest) -> HttpResponse:
        if not self.has_change_permission(request):
            raise PermissionDenied

        changelist_url = reverse("admin:brands_brandentry_changelist")

        if request.method == "POST":
            form = BrandCsvUploadForm(request.POST, request.FILES)
            if form.is_valid():
                try:
                    summary = self._import_rows_from_csv(form.cleaned_data["csv_file"])
                except ValueError as exc:
                    self.message_user(request, str(exc), level=messages.ERROR)
                else:
                    for error in summary["errors"]:
                        self.message_user(request, error, level=messages.WARNING)
                    self.message_user(
                        request,
                        (
                            f"Upload complete. Created: {summary['created']} | "
                            f"Updated: {summary['updated']} | Skipped: {summary['skipped']}"
                        ),
                        level=messages.SUCCESS,
                    )
                    return redirect(changelist_url)
        else:
            form = BrandCsvUploadForm()

        context = {
            **self.admin_site.each_context(request),
            "opts": self.model._meta,
            "form": form,
            "title": "Upload brands CSV",
            "changelist_url": changelist_url,
        }
        return render(request, "admin/brands/brandentry/upload_csv.html", context)
