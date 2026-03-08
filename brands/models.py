from django.db import models


class BrandEntry(models.Model):
    brand = models.CharField(max_length=255, unique=True, db_index=True)
    inquire_to = models.CharField(max_length=255)
    notes = models.TextField(blank=True)
    info_received_from = models.CharField(max_length=255)
    last_changed_on = models.DateField(auto_now=True)

    class Meta:
        ordering = ["brand"]

    def __str__(self) -> str:
        return self.brand
