# Dea Store

## Transfer bank Indonesia

Admin dapat menambahkan rekening dari berbagai bank di **Admin → Pengaturan → Rekening & E-Wallet**. Pilih bank yang tersedia, atau pilih **Transfer Bank (pilih rekening)** dan tambahkan satu baris per rekening bank. Nama bank, pemilik, dan nomor rekening akan ditampilkan kepada pelanggan.

## Notifikasi transaksi

Panel admin memeriksa pesanan baru setiap 15 detik dan top-up setiap 20 detik. Klik **Aktifkan Notifikasi** di panel admin untuk mengizinkan notifikasi desktop saat halaman admin terbuka.

Pesan WhatsApp otomatis memerlukan akun WhatsApp Business Cloud API, template Utility `deastore_admin_alert` yang disetujui dengan empat parameter teks (kode, jenis transaksi, detail, total), serta nilai server `WHATSAPP_CLOUD_API_TOKEN`, `WHATSAPP_PHONE_NUMBER_ID`, `WHATSAPP_NOTIFY_TO`, dan `WHATSAPP_TEMPLATE_NAME`. Contoh isi template: `Transaksi baru {{1}}. {{2}} — {{3}}. Total {{4}}. Buka panel admin untuk memproses.` Isi variabel server pada `.env` lokal lalu mulai ulang aplikasi. Jangan bagikan token melalui chat. Pesan pemberitahuan bisnis harus memakai template yang disetujui Meta.

Toko top-up Robux dengan frontend React/Vite dan backend FastAPI/MongoDB.

## Deploy gratis dengan domain sendiri

Target deployment saat ini adalah FastAPI Cloud. Lihat [CLOUD-UPDATE.md](CLOUD-UPDATE.md)
untuk memasang pembaruan pada aplikasi dan domain yang sudah dikonfigurasi.
Lihat [DEPLOY.md](DEPLOY.md) bila ingin memakai opsi alternatif Docker Desktop
dan Cloudflare Tunnel di PC Windows; pada opsi tersebut PC harus tetap menyala.
File `.env` yang berisi nilai rahasia tidak disertakan. Gunakan `.env.example` hanya
sebagai daftar nama pengaturan; jangan mengunggah nilai rahasia ke GitHub.

Saat pertama kali dijalankan, aplikasi membuat akun admin dari `ADMIN_USERNAME` dan
`ADMIN_PASSWORD`, paket awal, serta toko dalam mode pengaturan. Metode pembayaran
dimulai kosong. Isi nomor WhatsApp, rekening/e-wallet, dan QRIS milikmu lewat panel
admin sebelum menerima pesanan nyata.


## Fitur Member Club (pembaruan)

Pembaruan ini menambahkan halaman `/member` untuk pelanggan yang sudah login:

- **Live Order Tracking** tetap memakai halaman `/track` dan riwayat pesanan yang sudah ada.
- **Voucher & Promo Code** dikelola melalui Panel Admin → Komunitas. Pelanggan dapat melihat voucher di Member Club dan memasukkan kode pada formulir pesanan. Voucher dapat berupa persentase atau potongan rupiah, dengan minimum transaksi dan batas pemakaian.
- **Referral System** memakai link `/register?ref=KODE`. Bonus 100 DeaPoints diberikan kepada pengundang setelah pesanan pertama teman yang diundang selesai.
- **Giveaway Center** dikelola melalui Panel Admin → Komunitas; pelanggan login dapat mendaftar giveaway.
- **DeaPoints** bertambah setelah pesanan Robux berstatus selesai, sebesar 1 poin per Rp10.000 transaksi (minimal 1 poin).
- **Member Club** memiliki level Bronze (0–1.499), Silver (1.500–4.999; bonus poin 10%), dan Gold (5.000+; bonus poin 25%).
- **Notifikasi otomatis** muncul pada halaman Member Club untuk perubahan pesanan, top-up coin, poin, referral, dan keikutsertaan giveaway.

Database lama tidak dihapus atau di-reset. Koleksi baru dibuat otomatis saat fitur pertama kali dipakai. Sebelum deploy ke produksi, uji alur voucher/referral/giveaway pada staging dan pastikan backup MongoDB tersedia.
