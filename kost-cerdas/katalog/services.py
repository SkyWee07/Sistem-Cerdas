import os


class GeminiUnavailable(Exception):
    """Raised when Gemini cannot provide the requested chart explanation."""


def explain_dashboard(summary):
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise GeminiUnavailable("API Gemini belum dikonfigurasi di lingkungan server.")

    prompt = (
        "Jelaskan dashboard grafik data kos berikut dalam bahasa Indonesia yang ringkas dan mudah "
        "dipahami mahasiswa. Gunakan hanya angka yang diberikan. Bedakan korelasi dari sebab-akibat, "
        "sebutkan keterbatasan karena jumlah data kecil, dan jangan mengarang lokasi atau fasilitas. "
        "Tulis 2–3 paragraf dengan satu temuan utama dan satu saran membaca grafik.\n\n"
        f"Ringkasan data yang menjadi dasar grafik Matplotlib:\n{summary}"
    )
    model = os.getenv("GEMINI_MODEL", "gemini-4-carbon").strip() or "gemini-4-carbon"
    try:
        from google import genai

        client = genai.Client(api_key=api_key)
        response = client.interactions.create(
            model=model,
            input=prompt,
            store=False,
            generation_config={"max_output_tokens": 500},
        )
        text = getattr(response, "output_text", "")
        if not text or not text.strip():
            raise GeminiUnavailable("Gemini tidak mengembalikan teks penjelasan.")
        return text.strip()
    except GeminiUnavailable:
        raise
    except Exception as exc:
        # Do not expose provider request details, which can contain credential-bearing URLs.
        raise GeminiUnavailable(
            "Penjelasan AI belum dapat dibuat. Periksa API key, koneksi, dan ketersediaan model Gemini."
        ) from exc
