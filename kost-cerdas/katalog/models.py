from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class Kos(models.Model):
    nama = models.CharField("Nama kos", max_length=120, unique=True)
    jarak_km = models.DecimalField(
        "Jarak dari kampus (km)", max_digits=5, decimal_places=2,
        validators=[MinValueValidator(0)],
    )
    harga = models.DecimalField(
        "Harga per bulan (ribu rupiah)", max_digits=10, decimal_places=2,
        validators=[MinValueValidator(0)],
    )
    ac = models.BooleanField("Memiliki AC", default=False)
    rating = models.DecimalField(
        "Rating", max_digits=3, decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(5)],
    )

    class Meta:
        ordering = ["nama"]
        verbose_name = "Kos"
        verbose_name_plural = "Data kos"

    def __str__(self):
        return self.nama
