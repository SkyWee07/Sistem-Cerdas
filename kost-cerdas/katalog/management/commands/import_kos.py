import csv
from decimal import Decimal, InvalidOperation
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from katalog.models import Kos


class Command(BaseCommand):
    help = "Impor kos_madiun.csv ke database; data lama tidak ditimpa."

    def add_arguments(self, parser):
        parser.add_argument(
            "--path",
            default=str(Path(__file__).resolve().parents[3] / "data" / "kos_madiun.csv"),
            help="Path CSV dengan kolom nama, jarak_km, harga, ac, rating.",
        )
        parser.add_argument(
            "--if-empty",
            action="store_true",
            help="Lewati impor bila database sudah berisi data kos.",
        )

    def handle(self, *args, **options):
        if options["if_empty"] and Kos.objects.exists():
            self.stdout.write(self.style.WARNING("Data kos sudah ada; impor awal dilewati agar perubahan tersimpan."))
            return

        csv_path = Path(options["path"])
        if not csv_path.is_file():
            raise CommandError(f"File CSV tidak ditemukan: {csv_path}")

        created = 0
        try:
            with csv_path.open("r", newline="", encoding="utf-8-sig") as source:
                reader = csv.DictReader(source)
                required = {"nama", "jarak_km", "harga", "ac", "rating"}
                if not reader.fieldnames or not required.issubset(set(reader.fieldnames)):
                    raise CommandError("CSV wajib memiliki kolom nama, jarak_km, harga, ac, dan rating.")

                with transaction.atomic():
                    for line_number, row in enumerate(reader, start=2):
                        try:
                            nama = (row["nama"] or "").strip()
                            jarak = Decimal((row["jarak_km"] or "").strip())
                            harga = Decimal((row["harga"] or "").strip())
                            rating = Decimal((row["rating"] or "").strip())
                            ac_value = (row["ac"] or "").strip().lower()
                        except (InvalidOperation, AttributeError, TypeError) as exc:
                            raise CommandError(f"Nilai angka tidak valid pada baris {line_number}.") from exc

                        if not nama:
                            raise CommandError(f"Nama kos kosong pada baris {line_number}.")
                        if ac_value not in {"ya", "tidak", "true", "false", "1", "0"}:
                            raise CommandError(f"Nilai AC tidak valid pada baris {line_number}; gunakan ya/tidak.")
                        ac = ac_value in {"ya", "true", "1"}
                        if jarak < 0 or harga < 0 or not Decimal("0") <= rating <= Decimal("5"):
                            raise CommandError(f"Nilai di luar rentang pada baris {line_number}.")
                        Kos.objects.create(
                            nama=nama,
                            jarak_km=jarak,
                            harga=harga,
                            ac=ac,
                            rating=rating,
                        )
                        created += 1
        except csv.Error as exc:
            raise CommandError(f"CSV tidak dapat dibaca: {exc}") from exc

        self.stdout.write(self.style.SUCCESS(f"Berhasil mengimpor {created} data kos dari {csv_path.name}."))
