import logging
import os

import httpx
from google import genai
from google.genai.errors import APIError
from google.genai._interactions import (
    APIConnectionError as InteractionsAPIConnectionError,
    APIError as InteractionsAPIError,
    APITimeoutError as InteractionsAPITimeoutError,
)


logger = logging.getLogger(__name__)


class GeminiUnavailable(Exception):
    """Raised when Gemini cannot provide the requested chart explanation."""


def _api_error_message(status_code, provider_message=""):
    """Return a user-safe Indonesian message for a Gemini API status code."""
    safe_provider_message = provider_message.lower()
    invalid_key_markers = ("api_key_invalid", "invalid api key", "api key not valid")
    if status_code == 400 and any(marker in safe_provider_message for marker in invalid_key_markers):
        return "API key Gemini tidak valid. Periksa key pada konfigurasi deployment."

    messages = {
        400: "Permintaan Gemini ditolak. Periksa nama model dan konfigurasi permintaan.",
        401: "Autentikasi Gemini ditolak. Periksa API key pada konfigurasi deployment.",
        402: "Kredit atau billing Google Gemini perlu diperiksa.",
        403: "Akses Gemini ditolak. Periksa izin, verifikasi proyek, dan kuota akun Google.",
        404: "Model Gemini tidak ditemukan atau belum tersedia untuk proyek ini.",
        429: "Batas kuota atau laju permintaan Gemini tercapai. Coba lagi nanti.",
    }
    if status_code >= 500:
        return "Layanan Gemini sedang mengalami gangguan. Coba lagi beberapa saat."
    return messages.get(
        status_code,
        "Penjelasan Gemini gagal dibuat. Periksa log server untuk kode status yang aman.",
    )


def explain_dashboard(summary):
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        logger.warning("Gemini request skipped because GEMINI_API_KEY is not configured")
        raise GeminiUnavailable("API Gemini belum dikonfigurasi di lingkungan server.")

    prompt = (
        "Jelaskan dashboard grafik data kos berikut dalam bahasa Indonesia yang ringkas dan mudah "
        "dipahami mahasiswa. Gunakan hanya angka yang diberikan. Bedakan korelasi dari sebab-akibat, "
        "sebutkan keterbatasan karena jumlah data kecil, dan jangan mengarang lokasi atau fasilitas. "
        "Tulis 2–3 paragraf dengan satu temuan utama dan satu saran membaca grafik.\n\n"
        f"Ringkasan data yang menjadi dasar grafik Matplotlib:\n{summary}"
    )
    model = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite").strip() or "gemini-3.5-flash-lite"

    try:
        client = genai.Client(api_key=api_key)
        response = client.interactions.create(
            model=model,
            input=prompt,
            store=False,
            generation_config={"max_output_tokens": 500},
        )
        text = getattr(response, "output_text", "")
        if not text or not text.strip():
            logger.warning("Gemini returned no explanation text (model=%s)", model)
            raise GeminiUnavailable("Gemini tidak mengembalikan teks penjelasan.")
        return text.strip()
    except GeminiUnavailable:
        raise
    except (httpx.TimeoutException, InteractionsAPITimeoutError) as exc:
        logger.warning("Gemini request timed out (exception_type=%s)", type(exc).__name__)
        raise GeminiUnavailable(
            "Permintaan ke Gemini melewati batas waktu. Coba lagi beberapa saat."
        ) from exc
    except (InteractionsAPIConnectionError, httpx.RequestError) as exc:
        logger.warning("Gemini network request failed (exception_type=%s)", type(exc).__name__)
        raise GeminiUnavailable(
            "Gemini tidak dapat dijangkau. Periksa koneksi layanan dan coba lagi."
        ) from exc
    except (APIError, InteractionsAPIError) as exc:
        status_value = getattr(exc, "status_code", getattr(exc, "code", 0))
        try:
            status_code = int(status_value)
        except (TypeError, ValueError):
            status_code = 0
        logger.warning(
            "Gemini API request failed (status_code=%s, model=%s)",
            status_code or "unknown",
            model,
        )
        provider_message = getattr(exc, "message", "")
        if not isinstance(provider_message, str):
            provider_message = ""
        raise GeminiUnavailable(_api_error_message(status_code, provider_message)) from exc
    except Exception as exc:
        # Do not log the exception text or traceback: provider errors can contain sensitive request details.
        logger.error(
            "Unexpected Gemini integration failure (model=%s, exception_type=%s)",
            model,
            type(exc).__name__,
        )
        raise GeminiUnavailable(
            "Terjadi kesalahan internal saat meminta penjelasan Gemini. Periksa log server."
        ) from exc
