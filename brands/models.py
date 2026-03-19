from django.db import models


class BrandEntry(models.Model):
    brand = models.CharField(max_length=255, unique=True, db_index=True)
    logo = models.URLField(max_length=500, blank=True, null=True)
    logo_image = models.ImageField(upload_to="brand_logos/", blank=True, null=True)
    inquire_to = models.CharField(max_length=255)
    notes = models.TextField(blank=True)
    info_received_from = models.CharField(max_length=255, blank=True)
    search_count = models.PositiveIntegerField(default=0, editable=False, db_index=True)
    last_changed_on = models.DateField(auto_now=True)

    class Meta:
        ordering = ["brand"]
        constraints = [
            models.CheckConstraint(
                condition=~(
                    (
                        models.Q(logo__isnull=False)
                        & ~models.Q(logo="")
                    )
                    & (
                        models.Q(logo_image__isnull=False)
                        & ~models.Q(logo_image="")
                    )
                ),
                name="brandentry_only_one_logo_source",
            )
        ]

    def __str__(self) -> str:
        return self.brand

    @property
    def logo_source(self) -> str:
        if self.logo:
            return self.logo
        if self.logo_image:
            return self.logo_image.url
        return ""
