import csv
import os
import tempfile
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from django.core.management import call_command
from django.test import SimpleTestCase, TestCase

from .fuzzy import score_kos
from .models import Kos
from .services import GeminiUnavailable, explain_dashboard


class FuzzyScoringTests(TestCase):
    def test_favorable_kos_scores_above_over_budget_distant_kos(self):
        favorable = SimpleNamespace(harga=Decimal("650"), jarak_km=Decimal("0.8"), rating=Decimal("4.8"), ac=True)
        less_suitable = SimpleNamespace(harga=Decimal("1450"), jarak_km=Decimal("4.2"), rating=Decimal("3.1"), ac=False)
        preferred = score_kos(favorable, 1100, 2.5, 3.8, True)
        other = score_kos(less_suitable, 1100, 2.5, 3.8, True)
        self.assertGreater(preferred["score"], other["score"])
        self.assertIn("score", preferred)
        self.assertTrue(preferred["label"])


class GeminiServiceTests(SimpleTestCase):
    @patch("google.genai.Client")
    def test_explanation_uses_server_key_and_non_stored_interaction(self, client_class):
        client = client_class.return_value
        client.interactions.create.return_value = SimpleNamespace(output_text="Ringkasan grafik.")
        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-only-key", "GEMINI_MODEL": "gemini-4-carbon"}):
            result = explain_dashboard("Jumlah kos: 30")

        self.assertEqual(result, "Ringkasan grafik.")
        client_class.assert_called_once_with(api_key="test-only-key")
        call = client.interactions.create.call_args
        self.assertEqual(call.kwargs["model"], "gemini-4-carbon")
        self.assertFalse(call.kwargs["store"])

    def test_missing_key_returns_safe_configuration_message(self):
        with patch.dict(os.environ, {"GEMINI_API_KEY": ""}):
            with self.assertRaises(GeminiUnavailable):
                explain_dashboard("Jumlah kos: 30")


class ImportKosCommandTests(TestCase):
    def test_imports_repository_csv_shape(self):
        contents = [
            {"nama": "Kos Uji", "jarak_km": "1.2", "harga": "900", "ac": "ya", "rating": "4.2"},
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "kos.csv"
            with path.open("w", newline="", encoding="utf-8") as output:
                writer = csv.DictWriter(output, fieldnames=contents[0].keys())
                writer.writeheader()
                writer.writerows(contents)
            call_command("import_kos", path=str(path), if_empty=True, verbosity=0)
        kos = Kos.objects.get(nama="Kos Uji")
        self.assertEqual(kos.harga, Decimal("900"))
        self.assertTrue(kos.ac)

    def test_if_empty_does_not_overwrite_existing_records(self):
        Kos.objects.create(nama="Tetap", jarak_km="1.00", harga="700", ac=False, rating="4.0")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "empty.csv"
            path.write_text("nama,jarak_km,harga,ac,rating\n", encoding="utf-8")
            call_command("import_kos", path=str(path), if_empty=True, verbosity=0)
        self.assertEqual(Kos.objects.count(), 1)
        self.assertEqual(Kos.objects.get().nama, "Tetap")
