# SignLens — Website Deteksi Bahasa Isyarat

Website Flask yang mengadaptasi aplikasi Python OpenCV + MediaPipe Gesture Recognizer. Mendukung isyarat bawaan model, pola custom, simpan foto, dan galeri.

## 1. Kebutuhan

- Python 3.11 (disarankan)
- File model `gesture_recognizer.task`
- Webcam
- Browser modern
- Koneksi internet untuk deployment

**Model tidak disertakan dalam ZIP ini.** Salin file `gesture_recognizer.task` yang sudah diberikan guru ke folder utama proyek, sejajar dengan `app.py`. Pastikan file tersebut memang model MediaPipe Gesture Recognizer yang sesuai.

## 2. Menjalankan di komputer sendiri

Buka terminal pada folder proyek.

### Windows

```powershell
py -3.11 -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
python app.py
```

### macOS / Linux

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
python app.py
```

Buka `http://127.0.0.1:5000` di browser. Izinkan akses kamera.

Jika instalasi MediaPipe gagal, pastikan versi Python dan sistem operasi/arsitektur didukung oleh wheel MediaPipe. Python 3.11 64-bit umumnya pilihan aman untuk konfigurasi ini.

## 3. Cara menggunakan

1. Klik **Mulai Kamera**, lalu izinkan akses webcam.
2. Arahkan tangan ke kamera dengan pencahayaan cukup.
3. Hasil deteksi muncul di panel kanan.
4. Tombol **Simpan Foto** aktif hanya ketika hasil deteksi dikenali.
5. Foto yang tersimpan muncul pada bagian Galeri Foto.
6. Klik **Berhenti** untuk mematikan kamera.

## 4. Menambah isyarat custom

Edit dictionary `POLA_CUSTOM` di `app.py`.

Urutan pola: `(jempol, telunjuk, tengah, manis, kelingking)`.
- `1` = terbuka
- `0` = tertutup

Contoh:

```python
POLA_CUSTOM = {
    (1, 0, 0, 0, 1): "Telepon",
    (0, 1, 0, 0, 1): "Rock",
    (0, 1, 1, 1, 0): "Tiga",
    (0, 1, 1, 1, 1): "Empat",
    (0, 0, 0, 0, 1): "Kelingking",
}
```

Catatan: fungsi deteksi jari ini adalah pendekatan sederhana dari kode awal. Hasil dapat dipengaruhi orientasi tangan, sisi tangan, dan sudut kamera. Uji pola custom pada kondisi penggunaan sebenarnya.

## 5. Deployment internet menggunakan Render

File `render.yaml` sudah disediakan sebagai contoh konfigurasi Render Blueprint. Konfigurasi tersebut menggunakan persistent disk 1 GB pada paket berbayar yang mendukung disk. Paket hosting, harga, dan dukungan disk dapat berubah; periksa paket Render terbaru sebelum memilih.

### Langkah deployment

1. Buat repository GitHub baru.
2. Upload seluruh isi folder proyek ke repository.
3. Upload `gesture_recognizer.task` ke folder utama repository jika ukuran dan kebijakan GitHub mengizinkan. Jika terlalu besar atau ingin privat, simpan model pada penyimpanan privat dan unduh saat build menggunakan mekanisme secret yang aman. Jangan memasukkan token/URL bertanda tangan ke kode publik.
4. Di Render, pilih **New → Blueprint** dan hubungkan repository.
5. Periksa konfigurasi `render.yaml`, lalu deploy.
6. Tunggu proses build dan start selesai.
7. Buka URL HTTPS dari Render dan izinkan akses kamera.

**Penting:** persistent disk membutuhkan jenis paket Render yang mendukung disk. Jika paket yang dipilih tidak mendukung disk, gunakan layanan object storage (misalnya S3-compatible) atau layanan hosting lain dengan persistent volume. Tanpa penyimpanan persisten, foto lokal dapat hilang saat instance diganti atau deploy ulang.

### Jika model tidak ingin disimpan di GitHub

Jangan membuat repository publik berisi model jika lisensi atau ukuran file tidak memungkinkan. Pilihan yang lebih baik:
- Simpan model di object storage privat.
- Buat mekanisme pengunduhan saat build/deploy.
- Simpan kredensial sebagai environment secret pada hosting.
- Jangan pernah menaruh access key di `app.py`, JavaScript, atau repository publik.

## 6. Catatan produksi dan keamanan

- Browser hanya mengizinkan akses webcam pada HTTPS atau `localhost`.
- Frame webcam dikirim ke server untuk diproses. Aplikasi ini tidak menyimpan frame secara otomatis; foto hanya disimpan ketika pengguna menekan tombol simpan dan isyarat dikenali.
- Satu proses Gunicorn dengan satu worker dipakai karena objek MediaPipe recognizer dibuat satu kali dan dilindungi lock. Ini contoh awal, bukan konfigurasi untuk trafik besar.
- Setiap frame dikirim sebagai permintaan HTTP. Deteksi dibatasi sekitar 3 kali per detik per browser untuk mengurangi beban server.
- Aplikasi contoh ini belum memiliki login, kuota pengguna, pembatasan request per IP, atau kebijakan retensi foto. Tambahkan perlindungan tersebut sebelum dibuka untuk publik.
- Foto galeri dapat diakses oleh siapa pun yang dapat membuka URL aplikasi. Jangan menyimpan foto pribadi/sensitif dalam konfigurasi publik ini.
- Untuk penggunaan kelas atau banyak pengguna, pertimbangkan autentikasi, pembatasan ukuran/kuota, object storage privat, dan penghapusan foto berkala.
- Performa bergantung CPU server dan jumlah pengguna bersamaan. Untuk penggunaan publik skala besar, lakukan load test dan pertimbangkan pemrosesan di browser atau worker terpisah.
- Jangan jalankan Flask dengan `debug=True` di server publik.

## 7. Endpoint API

| Method | Endpoint | Fungsi |
|---|---|---|
| GET | `/` | Halaman website |
| GET | `/api/health` | Status aplikasi/model |
| POST | `/api/detect` | Kirim gambar untuk deteksi |
| POST | `/api/save` | Simpan gambar yang dikenali |
| GET | `/api/gallery` | Daftar foto terbaru |
| GET | `/photos/<filename>` | Menampilkan foto |

## 8. Struktur folder

```text
gesture-website/
├── app.py
├── gesture_recognizer.task   # salin sendiri
├── requirements.txt
├── Procfile
├── render.yaml
├── README.md
├── templates/
│   └── index.html
├── static/
│   ├── style.css
│   └── app.js
└── hasil_capture/
```

## 9. Troubleshooting singkat

- **Model tidak ditemukan:** pastikan `gesture_recognizer.task` berada di lokasi `MODEL_PATH`.
- **Kamera tidak muncul:** izinkan kamera, tutup aplikasi lain yang memakai kamera, dan gunakan HTTPS saat online.
- **Tidak ada isyarat dikenali:** pastikan tangan terlihat utuh, pencahayaan cukup, dan model yang digunakan benar.
- **Website lambat:** kurangi resolusi kamera atau naikkan interval deteksi pada `DETECT_INTERVAL_MS` di `static/app.js`.
- **Foto hilang setelah deploy:** pastikan `UPLOAD_DIR` mengarah ke persistent disk/volume yang benar.
- **Server kehabisan memori:** gunakan instance dengan RAM memadai dan batasi ukuran gambar serta jumlah request.
