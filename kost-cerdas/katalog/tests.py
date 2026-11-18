import csv
import os
import tempfile
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import httpx
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase
from google.genai._interactions import APITimeoutError, BadRequestError
from google.genai.errors import APIError

from .fuzzy import score_kos
from .models import Kos
from .services import GeminiUnavailable, explain_dashboard


class FuzzyScoringTests(TestCase):
    def test_favorable_kos_scores_above_over_budget_distant_kos(self):
        favorable = SimpleNamespace(
            harga=Decimal("650"), jarak_km=Decimal("0.8"), rating=Decimal("4.8"), ac=True
        )
        less_suitable = SimpleNamespace(
            harga=Decimal("1450"), jarak_km=Decimal("4.2"), rating=Decimal("3.1"), ac=False
        )
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
        with patch.dict(
            os.environ,
            {"GEMINI_API_KEY": "test-only-key", "GEMINI_MODEL": "gemini-3.5-flash-lite"},
        ):
            result = explain_dashboard("Jumlah kos: 30")

        self.assertEqual(result, "Ringkasan grafik.")
        client_class.assert_called_once_with(api_key="test-only-key")
        call = client.interactions.create.call_args
        self.assertEqual(call.kwargs["model"], "gemini-3.5-flash-lite")
        self.assertFalse(call.kwargs["store"])

    @patch("google.genai.Client")
    def test_default_model_is_flash_lite_when_not_configured(self, client_class):
        client = client_class.return_value
        client.interactions.create.return_value = SimpleNamespace(output_text="Ringkasan grafik.")
        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-only-key"}, clear=True):
            explain_dashboard("Jumlah kos: 30")

        self.assertEqual(
            client.interactions.create.call_args.kwargs["model"],
            "gemini-3.5-flash-lite",
        )

    @patch("google.genai.Client")
    def test_legacy_api_error_is_classified_and_logs_only_safe_status(self, client_class):
        client = client_class.return_value
        client.interactions.create.side_effect = APIError(
            403, {"error": {"message": "do-not-log-provider-response"}}
        )
        with patch.dict(
            os.environ,
            {"GEMINI_API_KEY": "test-only-key", "GEMINI_MODEL": "gemini-3.5-flash-lite"},
        ):
            with self.assertLogs("katalog.services", level="WARNING") as captured:
                with self.assertRaises(GeminiUnavailable) as raised:
                    explain_dashboard("Jumlah kos: 30")

        self.assertIn("Akses Gemini ditolak", str(raised.exception))
        self.assertIn("status_code=403", captured.output[0])
        self.assertNotIn("test-only-key", captured.output[0])
        self.assertNotIn("do-not-log-provider-response", captured.output[0])

    @patch("google.genai.Client")
    def test_interactions_bad_request_is_classified_without_logging_provider_text(self, client_class):
        client = client_class.return_value
        response = httpx.Response(
            400,
            request=httpx.Request("POST", "https://example.invalid"),
        )
        client.interactions.create.side_effect = BadRequestError(
            "API_KEY_INVALID: synthetic detail",
            response=response,
            body={"message": "do-not-log-provider-response"},
        )
        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-only-key"}):
            with self.assertLogs("katalog.services", level="WARNING") as captured:
                with self.assertRaises(GeminiUnavailable) as raised:
                    explain_dashboard("Jumlah kos: 30")

        self.assertIn("API key Gemini tidak valid", str(raised.exception))
        self.assertIn("status_code=400", captured.output[0])
        self.assertNotIn("API_KEY_INVALID", captured.output[0])
        self.assertNotIn("synthetic detail", captured.output[0])
        self.assertNotIn("do-not-log-provider-response", captured.output[0])

    @patch("google.genai.Client")
    def test_interactions_timeout_has_specific_message_and_safe_log(self, client_class):
        client = client_class.return_value
        request = httpx.Request("POST", "https://example.invalid")
        client.interactions.create.side_effect = APITimeoutError(request)
        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-only-key"}):
            with self.assertLogs("katalog.services", level="WARNING") as captured:
                with self.assertRaises(GeminiUnavailable) as raised:
                    explain_dashboard("Jumlah kos: 30")

        self.assertIn("melewati batas waktu", str(raised.exception))
        self.assertIn("timed out", captured.output[0])

    @patch("google.genai.Client")
    def test_httpx_timeout_has_specific_user_message_and_safe_log(self, client_class):
        client = client_class.return_value
        client.interactions.create.side_effect = httpx.TimeoutException("synthetic timeout detail")
        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-only-key"}):
            with self.assertLogs("katalog.services", level="WARNING") as captured:
                with self.assertRaises(GeminiUnavailable) as raised:
                    explain_dashboard("Jumlah kos: 30")

        self.assertIn("melewati batas waktu", str(raised.exception))
        self.assertIn("timed out", captured.output[0])
        self.assertNotIn("synthetic timeout detail", captured.output[0])

    def test_missing_key_returns_safe_configuration_message(self):
        with patch.dict(os.environ, {"GEMINI_API_KEY": ""}):
            with self.assertRaises(GeminiUnavailable):
                explain_dashboard("Jumlah kos: 30")


class GeminiDashboardViewTests(TestCase):
    def test_loading_indicator_and_script_render_and_blank_key_disables_button(self):
        with patch.dict(os.environ, {"GEMINI_API_KEY": "   "}):
            response = self.client.get("/", secure=True)

        self.assertContains(response, 'id="gemini-loading-status"')
        self.assertContains(response, 'aria-busy="false"')
        self.assertRegex(
            response.content.decode("utf-8"),
            r'<script src="/static/katalog/dashboard\.[^\"]+\.js" defer></script>',
        )
        self.assertContains(response, 'type="submit" disabled')
        self.assertNotIn("X-Frame-Options", response.headers)

    def test_admin_keeps_default_frame_protection(self):
        response = self.client.get("/admin/", secure=True)
        self.assertEqual(response.headers.get("X-Frame-Options"), "DENY")


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
