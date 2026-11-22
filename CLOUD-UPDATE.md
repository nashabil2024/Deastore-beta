# Pembaruan Dea Store di FastAPI Cloud

Target deployment yang sudah dikonfigurasi adalah aplikasi FastAPI Cloud
`1a189d69-7cbd-44d3-8008-04cf0b9b5617`. Repository memakai workflow manual
**Deploy Dea Store to FastAPI Cloud** di `.github/workflows/deploy-fastapi-cloud.yml`.

## Memasang pembaruan ini

1. Masukkan perubahan source ke branch `main` pada repository Dea Store yang sudah ada.
   Paket pembaruan menyertakan source, tes browser, dan frontend hasil build pada
   `backend/static/`. File rahasia dan data toko tidak disertakan.
2. Pada GitHub, buka **Actions → Deploy Dea Store to FastAPI Cloud → Run workflow**,
   pilih branch `main`, lalu jalankan.
3. Workflow membangun frontend, menyalinnya ke `backend/static`, lalu mengirim aplikasi
   ke FastAPI Cloud menggunakan secret repository `FASTAPI_CLOUD_TOKEN` yang sudah ada.
   Tunggu tahap **Wait for cloud readiness** berhasil.
4. Buka `https://deastore.my.id`, muat ulang, lalu periksa halaman pemesanan dan panel admin.
   Halaman pemesanan, pelacakan, dan riwayat kini memiliki perbaikan tampilan HP.

Pengaturan database, sesi admin, metode pembayaran, dan domain tetap berasal dari aplikasi
FastAPI Cloud yang sudah ada. Pembaruan frontend ini tidak memerlukan perubahan DNS.

## Konfigurasi MongoDB Atlas pada cloud

`MONGO_URL`, `DB_NAME`, dan `SESSION_SECRET` wajib tersedia pada environment aplikasi.
Gunakan `UPLOAD_STORAGE=gridfs` agar bukti pembayaran, QRIS, dan logo tetap tersimpan
setelah redeploy. `SESSION_SECRET` harus tetap dan minimal 32 karakter; simpan sebagai secret.

URI MongoDB lama yang sudah memuat credentials tetap didukung. Alternatifnya, gunakan
URI host tanpa credentials, `MONGO_USERNAME`, lalu salah satu dari `MONGO_PASSWORD`
(secret) atau `MONGO_PASSWORD_ENV` (nama environment secret yang sudah tersimpan).
Mode credentials terpisah menggunakan `authSource=admin`. Jangan mengisi kedua sumber
password sekaligus dan jangan memasukkan nilai password ke source repository.

Pastikan Atlas IP Access List mengizinkan koneksi server hosting. Perubahan akses jaringan
harus mendapat persetujuan pemilik. Setelah deployment, periksa `/api/health` sampai HTTP
200 dengan `status=ok`; status Ready dari platform saja belum memastikan database tersambung.

## Perubahan pembeli dan admin

- Kartu riwayat pesanan/top-up di HP, serta tombol yang lebih mudah diketuk.
- Pencarian kode/username pesanan dan kode top-up di panel admin.
- Tombol **Lanjut Bayar** untuk top-up lama; transaksi tetap terbuka setelah refresh.
- Halaman pelacakan menampilkan rekening/QRIS sesuai metode transaksi yang belum dibayar.
- Salin kode pesanan, tautan pelacakan, dan nominal pembayaran.
- Informasi kekurangan/sisa saldo coin sebelum membuat pesanan.
- Pesan gagal memuat data dan tombol mencoba lagi pada riwayat dan pelacakan.

## Validasi lokal

```powershell
cd frontend
yarn install --frozen-lockfile
yarn typecheck
yarn build
cd ../tests
yarn install --frozen-lockfile
yarn playwright install chromium
# Jalankan frontend preview pada localhost:3000 di terminal lain:
# cd frontend; yarn preview --host 127.0.0.1 --port 3000
yarn playwright test --project=desktop --project=mobile
```

Tes browser memakai data simulasi dan memblokir request API yang tidak dikenali; tes ini
tidak membuat pesanan, top-up, atau approval nyata pada toko. DEPLOY.md menjelaskan opsi
alternatif menjalankan aplikasi di PC dengan Cloudflare Tunnel.
