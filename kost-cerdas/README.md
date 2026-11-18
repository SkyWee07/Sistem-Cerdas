# Kost Cerdas

Aplikasi web individu berbasis Django untuk membaca data kos Madiun. Aplikasi menyimpan data dalam database, membuat grafik dengan Matplotlib, memberi peringkat kecocokan memakai fuzzy logic, dan menyediakan penjelasan grafik melalui Gemini.

## Dataset

Aplikasi memakai file asli `data/kos_madiun.csv`, yang disalin tanpa perubahan dari [SkyWee07/Sistem-Cerdas](https://github.com/SkyWee07/Sistem-Cerdas/blob/main/kos_madiun.csv). CSV berisi 30 baris data dengan kolom `nama`, `jarak_km`, `harga`, `ac`, dan `rating`. Nilai `harga` mengikuti contoh sumber dan dinyatakan dalam ribu rupiah per bulan.

Repositori sumber tidak memuat berkas atau metadata lisensi. Cantumkan tautan sumber saat mempresentasikan proyek dan konfirmasikan izin redistribusi dengan pemilik repositori atau dosen sebelum mempublikasikan ulang datanya.

## Fitur

- Dashboard statistik dan grafik Matplotlib untuk hubungan harga–jarak serta rata-rata harga menurut ketersediaan AC.
- Katalog kos dengan pencarian nama, filter AC/harga, urutan, dan halaman detail.
- Rekomendasi fuzzy Mamdani dari anggaran, jarak maksimal, rating minimal, dan kebutuhan AC. Sistem menggabungkan membership function, aturan, agregasi, lalu centroid; tidak membutuhkan dataset pelatihan.
- Tombol Gemini untuk menjelaskan ringkasan angka yang menjadi dasar grafik. Data agregat dikirim dari server, bukan API key atau kode browser.
- Django Admin untuk mengelola baris database; buat akun admin secara lokal dengan `createsuperuser` bila diperlukan.

## Menjalankan secara lokal

Gunakan Python 3.12 atau lebih baru. Buat dan aktifkan virtual environment, lalu pasang dependensi:

```bash
python -m venv .venv
# Linux/macOS
source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Salin `.env.example` menjadi `.env`. Untuk penggunaan Gemini lokal, isi `GEMINI_API_KEY` di `.env` secara lokal dan jangan unggah `.env` ke GitHub. Biarkan `DATABASE_URL` kosong untuk memakai SQLite lokal. Setelah itu jalankan:

```bash
python manage.py migrate
python manage.py import_kos --if-empty
python manage.py runserver 0.0.0.0:3000
```

Buka `http://127.0.0.1:3000/`. Perintah impor berhenti tanpa mengubah baris yang sudah ada ketika `--if-empty` digunakan. Untuk mengelola data lewat admin, buat akun dengan `python manage.py createsuperuser`, lalu kunjungi `/admin/`.

## Database dan impor CSV

Saat `DATABASE_URL` menunjuk ke MySQL, Django memakai database tersebut dan TLS bila parameter URL menyatakan `ssl=true`. Jika `DATABASE_URL` tidak tersedia, aplikasi menggunakan `db.sqlite3` untuk pengembangan lokal. Skema dibuat dengan migrasi Django. Impor awal hanya dilakukan ketika tabel kos masih kosong, sehingga proses startup tidak menimpa perubahan data berikutnya.

Format yang didukung importer: `nama`, `jarak_km`, `harga`, `ac`, dan `rating`. Baris tanpa nama, nilai numerik tidak valid, status AC selain ya/tidak, atau nilai jarak/harga/rating di luar batas akan ditolak.

## Konfigurasi Gemini

Sediakan `GEMINI_API_KEY` sebagai protected environment secret di server atau sebagai variabel lokal di `.env`. Secara default, aplikasi menggunakan model `gemini-3.5-flash-lite`; model dapat diganti melalui `GEMINI_MODEL`. Aplikasi memakai Google Gen AI SDK dan Interactions API. Model dan endpoint yang tersedia dapat berubah; periksa [daftar model Gemini](https://aistudio.google.com/docs/models) sebelum mengganti konfigurasi. Tombol penjelasan baru memanggil API ketika ditekan.

Kegagalan Gemini dicatat di log server dengan kode status, nama model, atau jenis exception saja. API key, isi respons provider, teks exception, dan ringkasan data tidak dicatat. Pesan pada halaman membedakan kesalahan autentikasi, izin/kuota, model yang tidak tersedia, timeout, jaringan, dan gangguan server.

## Pemeriksaan dasar

```bash
python manage.py check
python manage.py test
```

## Deployment

Proyek menyertakan `Dockerfile` dan `entrypoint.sh`. Container memasang dependensi, mengumpulkan static files, menjalankan migrasi, mengimpor CSV hanya jika database kosong, kemudian menjalankan Gunicorn pada `0.0.0.0:$PORT` (default 3000). Atur `DATABASE_URL` ke database persisten dan `GEMINI_API_KEY` sebagai protected server secret pada environment deployment. Health endpoint publik yang tidak memerlukan login adalah `/health/`.

Untuk produksi, set `DEBUG=false`, batasi `ALLOWED_HOSTS` ke domain aplikasi, dan aktifkan `SECURE_SSL_REDIRECT=true`. `SECURE_HSTS_SECONDS` dimulai dari 3600 detik; naikkan hanya setelah HTTPS berfungsi end-to-end. Biarkan `SECURE_HSTS_INCLUDE_SUBDOMAINS=false` dan `SECURE_HSTS_PRELOAD=false` sampai semua subdomain benar-benar hanya melayani HTTPS dan keputusan preload sudah ditinjau. Django mempercayai `X-Forwarded-Proto: https` dari reverse proxy; pastikan proxy mengatur header itu dengan benar agar redirect tidak berulang. Jalankan `python manage.py check --deploy` sebelum rilis.

Jangan taruh API key pada JavaScript, template, README, atau repository. Database pengembangan dan deployment dapat memakai database yang sama pada platform ini; perlakukan migrasi dan impor sebagai perubahan data sungguhan.

## Struktur

- `kostcerdas/`: pengaturan, URL, WSGI/ASGI Django.
- `katalog/`: model database, importer CSV, grafik Matplotlib, algoritma fuzzy, integrasi Gemini, views dan admin.
- `templates/katalog/`: halaman dashboard, katalog, detail, dan rekomendasi.
- `static/katalog/site.css`: tampilan responsif.
- `data/kos_madiun.csv`: dataset asli dari repositori.
