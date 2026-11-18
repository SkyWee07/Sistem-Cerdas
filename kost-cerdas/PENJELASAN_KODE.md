# Panduan Pertanggungjawaban Kode — Kost Cerdas

Panduan ini menjelaskan implementasi aplikasi Django Kost Cerdas yang disimpan di GitHub pada `SkyWee07/Sistem-Cerdas/tree/main/kost-cerdas` (snapshot GitHub: commit `d2cb487`). Situs aktif: https://kostcerdas-kvehqc3l.manus.space. Dataset berasal dari `https://github.com/SkyWee07/Sistem-Cerdas/blob/main/kos_madiun.csv`.

Tujuannya bukan menghafal kode, melainkan memahami **masukan → proses → keluaran**, alasan setiap bagian dibuat, dan batasannya. Angka harga pada CSV dan aplikasi adalah **ribu rupiah per bulan**; contohnya nilai `900` berarti Rp900.000 per bulan.

## 1. Gambaran arsitektur

Aplikasi memakai Django untuk menerima permintaan HTTP dan merender halaman, MySQL/SQLite untuk menyimpan catatan kos, Matplotlib untuk membuat grafik PNG, fungsi fuzzy buatan sendiri untuk memberi skor kecocokan, serta Gemini untuk memberi uraian teks ketika pengguna meminta penjelasan. Gemini tidak menghitung grafik dan tidak melatih model: ia menerima ringkasan angka yang dihitung aplikasi, lalu menyusun penjelasan dalam bahasa Indonesia.

Alur umumnya:

1. `entrypoint.sh` menjalankan migrasi database, mengimpor CSV hanya bila tabel masih kosong, lalu menyalakan Gunicorn.
2. `kostcerdas/urls.py` memilih endpoint proyek; untuk halaman aplikasi, permintaan diteruskan ke `katalog/urls.py`.
3. Fungsi view membaca data model `Kos` dari database, memanggil perhitungan yang diperlukan, lalu mengirim context ke template HTML.
4. Template menghasilkan halaman; grafik yang dibuat Matplotlib dimasukkan sebagai data URI PNG langsung ke HTML.
5. Penjelasan Gemini hanya diminta jika tombol “Jelaskan grafik” ditekan.

| URL | View/fungsi | Kegunaan |
|---|---|---|
| `/` | `dashboard` | Statistik, dua grafik, sampel data, tombol Gemini |
| `/kos/` | `kos_list` | Pencarian, filter, pengurutan katalog |
| `/kos/<id>/` | `kos_detail` | Detail satu catatan kos |
| `/rekomendasi/` | `recommendations` | Form kriteria dan hasil peringkat fuzzy |
| `/admin/` | Django Admin | Pengelolaan data dengan akun admin Django |
| `/health/` | `health` | Pemeriksaan bahwa server merespons |
| `/manus-routes.json` | `manus_routes` | Manifest daftar halaman untuk platform hosting |

## 2. Model, database, dan migrasi

### `katalog/models.py` — `Kos`

`Kos` adalah model Django yang menggambarkan satu baris data kos. Django menerjemahkan model ini menjadi tabel database.

| Anggota | Fungsi dan aturan |
|---|---|
| `nama` | Nama kos, teks maksimum 120 karakter, harus unik agar tidak ada dua record dengan nama sama. |
| `jarak_km` | Jarak dari kampus dengan dua angka desimal; tidak boleh negatif. |
| `harga` | Harga bulanan dalam ribu rupiah, dua angka desimal; tidak boleh negatif. |
| `ac` | Boolean: tersedia/tidak tersedia AC. |
| `rating` | Nilai desimal 0–5. |
| `Meta.ordering` | Hasil query default diurutkan berdasarkan nama. |
| `Meta.verbose_name` | Label model di Django Admin ditampilkan sebagai “Kos” dan “Data kos”. |
| `__str__(self)` | Mengembalikan `self.nama`. Ini membuat record mudah dikenali di admin, shell, dan log Django tanpa menampilkan representasi object yang panjang. |

### `katalog/migrations/0001_initial.py`

Ini adalah migrasi awal yang membuat tabel `Kos` dengan lima field di atas, primary key otomatis, validator, label, dan pengurutan. Berkas migrasi adalah catatan perubahan skema; jangan menggantinya dengan edit manual tabel karena Django perlu tahu riwayat skemanya.

### `settings.database_from_environment()`

Fungsi di `kostcerdas/settings.py` memilih database dari `DATABASE_URL`:

- Jika kosong, memakai SQLite lokal di `db.sqlite3`.
- Jika skema `mysql://` atau `mysql+pymysql://`, mengurai host, port, nama database, username, password, dan parameter URL; mengaktifkan PyMySQL sebagai driver kompatibel MySQL.
- Opsi MySQL menetapkan `utf8mb4`, koneksi persisten 60 detik, dan pemeriksaan kesehatan koneksi. Parameter `ssl=true` (atau nilai setara) mengaktifkan TLS.
- Jika skema `sqlite://`, memakai SQLite pada path yang disebut URL.
- Skema lain ditolak dengan `RuntimeError`, sehingga salah konfigurasi tidak diam-diam memilih database lain.

Fungsi ini hanya **membuat konfigurasi koneksi**; migrasi tabel dilakukan oleh `manage.py migrate`.

## 3. Impor dataset CSV

### `katalog/management/commands/import_kos.py`

Perintah ini membuat perintah terminal Django `python manage.py import_kos`.

#### `Command.add_arguments(self, parser)`

Mendaftarkan dua argumen:

- `--path`: lokasi CSV. Default-nya file proyek `data/kos_madiun.csv`; argumen ini berguna untuk menguji atau mengimpor file lain.
- `--if-empty`: jika dipakai dan database sudah memiliki setidaknya satu record kos, impor dilewati. Opsi ini penting saat startup container supaya perubahan data yang telah dikelola tidak ditimpa oleh impor ulang.

#### `Command.handle(self, *args, **options)`

Inilah proses utama impor:

1. Bila `--if-empty` aktif dan `Kos.objects.exists()` benar, tampilkan peringatan dan berhenti.
2. Pastikan file yang diminta benar-benar ada; jika tidak, lempar `CommandError` dengan path yang dicari.
3. Buka CSV sebagai UTF-8 (mendukung BOM lewat `utf-8-sig`) dan `newline=""`, lalu baca header dengan `csv.DictReader`.
4. Pastikan kolom `nama`, `jarak_km`, `harga`, `ac`, dan `rating` tersedia.
5. Untuk setiap baris, rapikan nama dan status AC, lalu konversi angka ke `Decimal` agar nilai uang/jarak/rating tidak langsung dibulatkan menjadi float.
6. Tolak nama kosong, angka yang tidak valid, status AC di luar `ya/tidak/true/false/1/0`, jarak/harga negatif, atau rating di luar 0–5. Pesan error menyebut nomor baris CSV.
7. Terjemahkan nilai AC menjadi boolean dan simpan baris dengan `Kos.objects.create(...)`.
8. Seluruh loop berada di dalam `transaction.atomic()`. Jika satu baris gagal, transaksi dibatalkan sehingga impor tidak meninggalkan setengah dataset.
9. Tangani `csv.Error` sebagai `CommandError`, lalu tampilkan jumlah record yang berhasil dibuat.

Nama bersifat unik di database. Jika file berisi nama duplikat, database akan menolak record duplikat; transaksi mencegah impor parsial. Untuk impor awal biasa digunakan `--if-empty`.

## 4. View Django: logika permintaan dan halaman

### Fungsi pembantu di `katalog/views.py`

#### `_safe_float(value, default, low, high)`

Mencoba mengubah input query string menjadi angka `float`. Jika input tidak dapat dibaca, fungsi mengembalikan `default`; jika bisa, nilainya dibatasi di antara `low` dan `high`. Ini mencegah kriteria rekomendasi berada di luar rentang yang diharapkan.

#### `_dashboard_summary(rows)`

Membuat paragraf teks ringkas dari data database untuk dikirim ke Gemini. Jika tidak ada baris, hasilnya adalah pesan “belum ada data”. Jika ada, fungsi menghitung jumlah kos, minimum/maksimum/rata-rata harga, rata-rata jarak dan rating, serta rata-rata harga dan jumlah record untuk kelompok ber-AC/tanpa AC. Ini bukan prompt yang berisi seluruh database; yang dikirim adalah ringkasan angka.

### View halaman

#### `dashboard(request)`

- Mengambil seluruh record `Kos` dari database.
- Menghitung jumlah, rata-rata, minimum/maksimum harga, rata-rata jarak/rating dan jumlah kos ber-AC.
- Meminta `price_distance_chart` dan `average_price_by_ac_chart` membuat dua gambar jika data tersedia.
- Jika metode request `POST` dan field `action` berisi `explain`, memanggil `explain_dashboard(summary)`. Error aman dari `GeminiUnavailable` ditangkap lalu ditampilkan sebagai notifikasi; halaman utama tetap bekerja.
- Menyusun context, termasuk status apakah key Gemini tersedia, sumber data, dan lima record sampel, kemudian merender `katalog/dashboard.html`.

Dengan demikian, kunjungan biasa `GET /` tidak memanggil Gemini. API baru digunakan setelah tombol ditekan.

#### `kos_list(request)`

Dibatasi oleh decorator `@require_GET`, sehingga hanya melayani GET. Fungsi ini membaca parameter URL:

- `q`: mencari nama dengan `nama__icontains` (pencarian tidak peka huruf besar/kecil).
- `ac=ya` atau `ac=tidak`: memilih kos dengan/tanpa AC.
- `maks_harga`: membatasi harga maksimum. Jika nilainya tidak numerik, filter harga diabaikan.
- `urut`: memilih kolom urut dari whitelist `nama`, `harga`, `-harga`, `jarak_km`, `-jarak_km`, atau `-rating`. Nilai lain kembali ke urutan nama. Whitelist mencegah query memilih field arbitrer.

Kemudian view merender katalog beserta parameter yang sudah diproses dan jumlah hasil.

#### `kos_detail(request, pk)`

Juga GET-only. Mengambil satu record berdasarkan primary key (`pk`). `get_object_or_404` mengembalikan halaman 404 yang benar jika ID tidak ada, bukan menimbulkan error server. Context-nya hanya berisi record tersebut.

#### `recommendations(request)`

Membaca preferensi dari query string: anggaran (`budget`, default 1100 ribu), jarak maksimum (`jarak`, default 2,5 km), rating minimum (`rating`, default 3,8), dan kebutuhan AC (`ac=ya`). Nilai numerik dibatasi masing-masing ke 100–10.000, 0,1–20, dan 1–5. Fungsi menghitung `score_kos(...)` untuk setiap record, memasangkan hasil dengan object kos, mengurutkan skor dari tertinggi ke terendah, lalu menampilkan hasil pada template rekomendasi.

## 5. Grafik Matplotlib

Semua fungsi grafik berada di `katalog/charts.py`. Backend `Agg` dipilih karena aplikasi berjalan di server tanpa layar desktop; font DejaVu Sans dipasang untuk konsistensi render. Warna `INK`, `GREEN`, `GOLD`, dan `GRID` menjadi konstanta gaya grafik.

#### `_as_data_uri(figure)`

Menyimpan figure sebagai PNG ke `BytesIO` di memori, bukan file permanen. Byte gambar diubah menjadi Base64 dan dibungkus sebagai URI `data:image/png;base64,...`, sehingga template dapat langsung memakai hasilnya sebagai `src` gambar. `figure.clear()` membersihkan figure setelah selesai agar memori tidak tertahan.

#### `price_distance_chart(rows)`

Membuat scatter plot: sumbu X jarak dari kampus, sumbu Y harga per bulan. Setiap titik adalah satu kos; hijau berarti ber-AC, emas berarti tanpa AC. Fungsi menambahkan judul, label sumbu, grid horizontal dan gaya sumbu, lalu menyerahkan figure ke `_as_data_uri`.

#### `average_price_by_ac_chart(rows)`

Membagi data menjadi kelompok tanpa AC dan dengan AC. Kelompok kosong tidak digambar. Untuk kelompok yang ada, fungsi menghitung mean harga, membuat bar chart dan menambahkan anotasi berisi nilai rata-rata serta jumlah kos. Hasil akhirnya juga data URI PNG.

Grafik menunjukkan **deskripsi dataset**, bukan bukti bahwa jarak atau AC menyebabkan harga tertentu. Data yang tersedia kecil dan tidak semua faktor harga tercatat.

## 6. Fuzzy logic: dari kriteria ke skor

Semua fungsi fuzzy ada di `katalog/fuzzy.py`. Ini sistem inferensi berbasis aturan, bukan model machine-learning yang dilatih. Tidak diperlukan dataset pelatihan; input kos berasal dari database, sedangkan aturan dan batas keanggotaan ditentukan eksplisit dalam kode.

#### `_clamp(value, low=0.0, high=1.0)`

Mengubah nilai menjadi float lalu membatasinya pada interval tertentu; default-nya 0–1. Dipakai untuk menjaga derajat keanggotaan/rating fit agar tetap valid.

#### `trapezoid(value, a, b, c, d)`

Menghitung derajat keanggotaan fungsi trapesium: 0 di luar rentang, naik linier dari `a` ke `b`, bernilai 1 di bagian datar `b`–`c`, lalu turun linier dari `c` ke `d`. Kasus `a == b` dan `c == d` memungkinkan bentuk “bahu” di sisi kiri/kanan. Keluaran berada pada 0–1.

#### `triangle(value, a, b, c)`

Fungsi segitiga dibuat dengan memanggil `trapezoid(value, a, b, b, c)`: naik menuju puncak di `b`, lalu turun sampai nol di `c`.

#### `_min(*values)`

Mengembalikan nilai terkecil; dalam aturan fuzzy, operasi minimum adalah operator AND. Jika tidak menerima input, hasilnya 0.

#### `score_kos(kos, budget_ribu, max_distance_km, min_rating, require_ac=False)`

Ini fungsi inti rekomendasi. Input-nya satu object `Kos` dan preferensi pengguna; hasilnya dictionary berisi `score` 0–100, `label`, dan daftar `notes`.

1. Mengubah harga, jarak, dan rating kos menjadi float. Anggaran dan jarak preferensi dibatasi minimal 1 dan 0,1 agar pembagian tidak nol; rating target dibatasi 1–5.
2. Membentuk rasio `harga/anggaran` dan `jarak/jarak_maksimum`. Rasio di bawah 1 umumnya berarti masih di dalam preferensi.
3. Menghitung `rating_fit` dan membatasi hasilnya 0–1.
4. Mengubah rasio menjadi derajat keanggotaan linguistik berikut:

| Kriteria | Himpunan dan parameter |
|---|---|
| Harga | `hemat`: trapesium (0, 0, 0,65, 0,95); `sesuai`: segitiga (0,72, 1, 1,28); `mahal`: trapesium (1,02, 1,25, 2,2, 2,2) |
| Jarak | `dekat`: trapesium (0, 0, 0,38, 0,72); `sedang`: segitiga (0,45, 0,85, 1,2); `jauh`: trapesium (1, 1,3, 2,5, 2,5) |
| Rating fit | `rendah`: trapesium (0, 0, 0,2, 0,45); `cukup`: segitiga (0,3, 0,55, 0,78); `tinggi`: trapesium (0,65, 0,82, 1, 1) |

5. Jika AC diwajibkan tetapi kos tidak punya AC, `ac_fit` menjadi 0,1; selain itu 1. Ini **penalti kuat**, bukan filter yang membuang kos sepenuhnya.
6. Menjalankan 11 aturan. Contoh: harga hemat + jarak dekat + rating tinggi menghasilkan “sangat”; harga hemat + jarak sedang + rating cukup menghasilkan “baik”; harga mahal + jarak jauh + rating rendah menghasilkan “rendah”. Setiap aturan juga mempertimbangkan `ac_fit`; kekuatan aturan adalah minimum derajat keanggotaan syarat-syaratnya.
7. Membuat himpunan keluaran di titik 0–100: `rendah`, `cukup`, `baik`, dan `sangat`. Hasil tiap aturan dipotong (clipping) sesuai kekuatan aturannya; semua hasil digabung memakai maksimum.
8. Menghitung centroid/pusat massa, yaitu jumlah `skor × keanggotaan` dibagi jumlah keanggotaan. Jika tidak ada aturan aktif, fallback-nya 25. Skor dibulatkan satu desimal.
9. Mengubah angka menjadi label: ≥82 “Sangat cocok”; ≥65 “Cocok”; ≥45 “Cukup cocok”; sisanya “Kurang sesuai”.
10. Membuat catatan alasan berdasarkan perbandingan langsung terhadap anggaran, jarak, rating, dan AC bila diwajibkan.

Urutan daftar ditentukan skor, bukan label. Skor adalah alat pembanding sesuai aturan yang ditulis, bukan probabilitas keberhasilan atau jaminan mutu kos.

## 7. Integrasi Gemini

### `GeminiUnavailable`

Exception khusus yang menandakan penjelasan AI tidak bisa dibuat. View menangkap exception ini untuk menampilkan pesan yang aman tanpa merusak dashboard.

### `explain_dashboard(summary)`

1. Membaca `GEMINI_API_KEY` dari environment server. Jika kosong, langsung mengangkat `GeminiUnavailable` dengan pesan konfigurasi.
2. Menyusun prompt berbahasa Indonesia yang meminta ringkasan singkat, memakai angka yang diberikan saja, membedakan korelasi dengan sebab-akibat, serta menyebut keterbatasan jumlah data.
3. Membaca `GEMINI_MODEL` atau memakai default `gemini-4-carbon`.
4. Membuat Google Gen AI client di server dan mengirim permintaan Interactions API dengan `store=False` dan batas keluaran 500 token.
5. Mengembalikan `output_text` setelah di-trim. Output kosong dianggap error.
6. Error provider/koneksi/model dibungkus menjadi pesan umum; detail exception asli tidak ditampilkan karena dapat berisi URL atau detail sensitif.

Key tidak dimasukkan ke HTML, JavaScript, maupun query browser. Pengujian memakai mock, sehingga suite tes tidak mengirim permintaan sungguhan ke Gemini.

## 8. Format dan halaman HTML

Template tidak menjalankan fungsi Python bebas; template memakai variabel context dan tag Django.

| Template | Tanggung jawab |
|---|---|
| `base.html` | Kerangka bersama, bahasa Indonesia, CSS, header/navigasi, area konten, footer. Memuat tag `static` dan `katalog_tags`. |
| `dashboard.html` | Memperlihatkan metrik, gambar grafik, sumber data, sampel tabel, form POST CSRF-protected untuk meminta penjelasan, dan kondisi error/hasil AI. |
| `kos_list.html` | Form GET untuk pencarian, filter AC/harga dan urutan; mempertahankan nilai pilihan dan menampilkan hasil atau pesan kosong. |
| `kos_detail.html` | Profil satu kos, harga, jarak, rating, AC, dan tautan ke rekomendasi/katalog. |
| `recommendations.html` | Form preferensi GET, skor, label, progress bar, alasan tiap hasil, dan uraian metode centroid. |

### `katalog/templatetags/katalog_tags.py` — `ribu(value)`

Filter template ini mencoba mengubah angka ke format ribuan tanpa desimal dan mengganti pemisah ribuan koma menjadi titik. Contoh `1250` menjadi `1.250`, cocok dengan konvensi tampilan Indonesia. Jika nilainya bukan angka, nilai awal dikembalikan agar halaman tidak gagal.

### `static/katalog/site.css`

CSS mendefinisikan token warna/typography pada `:root`, komponen (kartu, tabel, form, skor), status hover/focus, serta breakpoint responsif 900 px dan 680 px. Media query `prefers-reduced-motion` mengurangi animasi bagi pengguna yang meminta gerak minimal. CSS tidak melakukan perhitungan data.

## 9. Routing proyek dan endpoint utilitas

### `katalog/urls.py`

Menghubungkan pola URL halaman ke view: root ke dashboard, `kos/` ke katalog, `kos/<int:pk>/` ke detail, dan `rekomendasi/` ke rekomendasi. Nama route (`dashboard`, `kos_list`, dan seterusnya) dipakai template lewat `{% url %}` sehingga tidak perlu menulis URL berulang secara manual.

### `kostcerdas/urls.py`

#### `manus_routes(_request)`

Membuka `public/manus-routes.json` dan mengembalikannya sebagai `FileResponse` dengan content type JSON. `_request` tidak dipakai karena isi manifest tetap.

#### `health(_request)`

Mengembalikan teks `ok` dengan tipe `text/plain`, tanpa autentikasi. Ini endpoint kesiapan layanan untuk platform deployment.

File `public/manus-routes.json` mencantumkan lima halaman yang dapat dikunjungi; tidak berisi API key atau data record.

## 10. Konfigurasi, peluncur, dan deployment

### `manage.py`

Jika file dijalankan langsung (`__name__ == "__main__"`), menetapkan modul settings `kostcerdas.settings`, lalu meneruskan argumen terminal ke `execute_from_command_line`. Karena itu perintah `migrate`, `test`, `import_kos`, `runserver`, dan `createsuperuser` menggunakan entry point yang sama.

### `kostcerdas/wsgi.py` dan `kostcerdas/asgi.py`

Keduanya menetapkan lokasi settings dan meminta Django membuat application object. WSGI dipakai Gunicorn pada deployment saat ini; ASGI tersedia untuk server yang mendukung interface asynchronous.

### `kostcerdas/settings.py`

- `BASE_DIR` mencari root proyek; `load_dotenv` membaca `.env` lokal.
- `SECRET_KEY` memakai environment `DJANGO_SECRET_KEY`, atau menghasilkan key acak bila belum disetel. Untuk server jangka panjang sebaiknya sediakan key stabil sebagai secret; key baru pada restart dapat membatalkan sesi admin lama.
- `DEBUG` mengubah string env menjadi boolean. `ALLOWED_HOSTS` dan `CSRF_TRUSTED_ORIGINS` dibaca dari environment; origin Manus ditambahkan untuk situs ter-host.
- Cookie CSRF/session memakai `Lax` ketika DEBUG, tetapi `SameSite=None; Secure` di HTTPS production agar dapat bekerja di konteks iframe lintas situs. `SECURE_PROXY_SSL_HEADER` membaca skema HTTPS dari reverse proxy.
- `INSTALLED_APPS`, `MIDDLEWARE`, `TEMPLATES`, WSGI/ASGI menunjuk komponen Django dan aplikasi katalog.
- Bahasa diatur ke Indonesia, timezone `Asia/Jakarta`, dan static files dikompresi/di-hash lewat WhiteNoise.

### `entrypoint.sh`

Urutan startup produksi: `migrate --noinput` membuat atau memperbarui skema; `import_kos --if-empty` mengisi database hanya bila kosong; `exec gunicorn` menjalankan aplikasi WSGI pada `0.0.0.0:$PORT` (default 3000), dengan dua worker default dan timeout 60 detik. `exec` membuat Gunicorn menjadi proses utama container agar sinyal shutdown diteruskan dengan benar.

### `Dockerfile`

Memakai Python 3.12 slim, mengatur mode Python non-buffered dan Matplotlib headless, memasang font DejaVu, memasang dependencies dari `requirements.txt`, menyalin source, menjalankan `chmod 755` untuk `entrypoint.sh`, mengumpulkan static files, mendeklarasikan port 3000, lalu menjalankan script entrypoint. `chmod` eksplisit ditambahkan setelah publikasi pertama mendapati izin eksekusi script tidak terbawa di image.

### `requirements.txt`

- Django: web framework, ORM, template, admin, command, dan test client.
- Gunicorn: server WSGI production.
- Matplotlib: grafik.
- PyMySQL: koneksi MySQL.
- WhiteNoise: penyajian static files dari aplikasi.
- python-dotenv: membaca `.env` lokal.
- google-genai: SDK resmi Google Gen AI.

`.env.example` memberi contoh `DEBUG`, host, trusted origins, database, key Gemini (kosong), dan model. File `.env` asli tidak boleh masuk Git. Di deployment, key Gemini disimpan sebagai protected secret.

## 11. Administrasi dan tes

### `katalog/admin.py` — `KosAdmin`

`@admin.register(Kos)` mendaftarkan model di Django Admin. `list_display` menentukan kolom tabel, `list_filter` memberi filter AC, `search_fields` mencari nama, dan `ordering` mengurutkan nama. Class ini mengatur tampilan admin, bukan mekanisme autentikasi; login ditangani Django Admin.

### `katalog/apps.py` — `KatalogConfig`

Mendaftarkan aplikasi dengan nama `katalog`, memilih tipe primary key default `BigAutoField`, dan memberi label “Data Kos” pada admin.

### `katalog/tests.py`

Lima test method memverifikasi bagian inti:

| Test | Yang dibuktikan |
|---|---|
| `test_favorable_kos_scores_above_over_budget_distant_kos` | Kos murah/dekat/ber-rating tinggi menghasilkan skor lebih tinggi daripada contoh mahal/jauh/rating rendah. |
| `test_explanation_uses_server_key_and_non_stored_interaction` | Client Gemini menerima key dari server, model yang dipilih dipakai, output dikembalikan, dan `store=False`; client di-mock sehingga tidak ada request berbayar. |
| `test_missing_key_returns_safe_configuration_message` | Key kosong menghasilkan exception aman, bukan crash tersembunyi. |
| `test_imports_repository_csv_shape` | Bentuk CSV sumber dapat dibaca dan nilai tersimpan sebagai Decimal/boolean yang benar. |
| `test_if_empty_does_not_overwrite_existing_records` | Opsi `--if-empty` mempertahankan record yang sudah ada. |

Tes bukan bukti bahwa setiap kemungkinan input diuji. Suite tidak memanggil API Gemini live; itu disengaja agar tes deterministik dan tidak menggunakan kuota API.

## 12. Fungsi-fungsi yang ditulis

Sebagai indeks ringkas, seluruh fungsi Python khusus aplikasi yang utama adalah: `Kos.__str__`; `Command.add_arguments`, `Command.handle`; `_as_data_uri`, `price_distance_chart`, `average_price_by_ac_chart`; `_clamp`, `trapezoid`, `triangle`, `_min`, `score_kos`; `explain_dashboard`; `_safe_float`, `_dashboard_summary`, `dashboard`, `kos_list`, `kos_detail`, `recommendations`; `ribu`; `manus_routes`, `health`; dan `database_from_environment`. File WSGI/ASGI serta `manage.py` membuat application/command entry point; tidak menambahkan fungsi bisnis lain.

## 13. Batasan yang layak disebut saat presentasi

1. Dataset hanya 30 kos dan lima atribut; hasil tidak mewakili semua kos Madiun dan tidak memuat faktor seperti ukuran kamar, listrik, atau kontrak.
2. Aturan fuzzy dan membership function ditentukan manual. Ini sistem inferensi berbasis aturan, bukan model belajar dari data. Ubah parameter/rule dapat mengubah peringkat.
3. Skor fuzzy adalah alat bantu perbandingan, bukan probabilitas atau jaminan kualitas.
4. Grafik korelasional/deskriptif, bukan kesimpulan sebab-akibat.
5. Penjelasan Gemini bergantung pada API, key, ketersediaan model, dan kuota. Ringkasan angka tetap tersedia saat AI gagal.
6. Import startup hanya mengisi tabel kosong; pengelolaan rutin dilakukan lewat admin atau perubahan data yang disengaja, bukan menimpa otomatis dari CSV.
7. Repositori dataset sumber tidak mencantumkan lisensi. Cantumkan sumber dan minta arahan/izin sebelum redistribusi lebih lanjut.
8. Folder `kost-cerdas/` di GitHub adalah snapshot untuk version control. Ia tidak otomatis tersinkron dengan repositori kanonis Manus; perubahan baru perlu disalin/commit ke GitHub secara terpisah.

### Jawaban singkat yang bisa dipakai saat ditanya dosen

- **Bagaimana data masuk?** CSV divalidasi oleh management command, diubah ke tipe Decimal/boolean, lalu ditulis ke tabel `Kos` dalam transaksi.
- **Bagaimana dashboard dibuat?** View mengambil record dari ORM, menghitung statistik, fungsi Matplotlib membuat PNG di memori, template menampilkan angka dan gambar.
- **Apa peran fuzzy?** Mengubah rasio harga/jarak dan rating menjadi derajat keanggotaan, menerapkan aturan Mamdani, menggabungkan output, lalu defuzzifikasi centroid ke skor 0–100.
- **Apa peran Gemini?** Mengubah ringkasan statistik menjadi penjelasan bahasa Indonesia hanya saat diminta; ia tidak mengubah database atau menghitung skor fuzzy.
- **Bagaimana keamanan key?** Key dibaca dari environment server dan tidak dikirim ke browser; file `.env` lokal diabaikan Git.
- **Bagaimana deployment menyimpan data?** Database memakai `DATABASE_URL` persisten; filesystem container bersifat sementara. Startup menjalankan migrasi dan impor awal yang tidak menimpa data.
