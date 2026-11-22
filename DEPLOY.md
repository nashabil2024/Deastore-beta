# Menjalankan Dea Store gratis dengan domain sendiri

Paket ini menjalankan aplikasi dan MongoDB di PC Windows milikmu. Cloudflare Tunnel
menghubungkannya ke `deastore.my.id` tanpa IP publik, buka port router, kartu, atau
tagihan hosting. PC, Docker Desktop, dan internet harus terus menyala; saat PC tidur,
mati, atau internet putus, toko tidak bisa dibuka.

## 1. Pasang Docker Desktop

Unduh Docker Desktop dari situs resmi: <https://www.docker.com/products/docker-desktop/>.
Pilih penggunaan personal atau usaha kecil yang sesuai, lalu jalankan Docker Desktop.
Jika pemasangan meminta restart Windows, lakukan restart dan buka Docker Desktop lagi.
Pastikan statusnya menunjukkan Docker berjalan.

## 2. Buat Cloudflare Tunnel

1. Masuk ke <https://dash.cloudflare.com/> dengan akun yang mengelola `deastore.my.id`.
   Pastikan domain muncul di daftar **Domains**. Domain yang baru ditambahkan bisa berstatus
   **Pending** sampai nameserver diganti di registrar.
2. Buka **Networking → Tunnels**, pilih **Create a tunnel**, lalu beri nama `dea-store`.
3. Pilih metode Docker. Setelah Tunnel dibuat, buka **Configure → Published application routes**
   (atau **Routes → Add route**), lalu isi:
   - Hostname: `deastore.my.id`
   - Service: `http://app:10000`
4. Simpan. Salin token Tunnel dari layar instalasi/configurasi dan simpan sendiri.
   Jangan kirim token itu lewat chat atau unggah ke GitHub.

Jika Cloudflare meminta penggantian record lama, ubah hanya record A/AAAA untuk nama utama
`deastore.my.id` agar menunjuk ke Tunnel. Jangan hapus record untuk `www` atau subdomain lain,
maupun record MX/TXT, kecuali memang ingin mengganti layanan tersebut juga.

Sebelum mengganti nameserver di registrar, periksa semua record yang diimpor Cloudflare dan
pastikan rute Tunnel sudah siap. Di halaman **Overview**, Cloudflare menampilkan dua nameserver
baru yang harus dipasang pada registrar; nilai itu khusus untuk domainmu. Nameserver lama tetap
aktif sampai registrar menyimpan perubahan. Propagasi biasanya 1–2 jam, tetapi bisa sampai 24 jam.

## 3. Siapkan aplikasi

Di folder paket ini, salin `.env.example` menjadi `.env`. Isi nilai berikut:

- `SESSION_SECRET`: string acak minimal 32 karakter.
- `ADMIN_USERNAME`: nama login admin yang kamu inginkan.
- `ADMIN_PASSWORD`: kata sandi unik minimal 12 karakter.
- `CLOUDFLARE_TUNNEL_TOKEN`: token Tunnel dari Cloudflare.

Biarkan `EMERGENT_LLM_KEY` kosong. File `.env` berisi rahasia; jangan dibagikan.

## 4. Jalankan toko

Buka PowerShell pada folder paket, lalu jalankan:

```powershell
docker compose up -d --build
```

Saat pertama kali, Docker mengunduh komponen lalu membangun aplikasi. Tunggu sampai selesai,
kemudian buka <https://deastore.my.id>.

Masuk ke `/admin` memakai nama dan kata sandi dari `.env`. Toko awalnya dalam mode perawatan
dan metode pembayaran belum diisi. Masukkan nomor WhatsApp, rekening/e-wallet, dan QRIS
yang benar, lalu matikan mode perawatan sebelum menerima pesanan.

## Setelah berjalan

- Aktifkan **Start Docker Desktop when you sign in** di pengaturan Docker Desktop.
- Jangan matikan atau tidurkan PC bila toko harus tetap bisa dibuka.
- Database dan bukti pembayaran tersimpan di volume lokal Docker (`mongo_data` dan `uploads`).
  Cadangkan secara berkala; menghapus volume akan menghapus data toko.
- Pembaruan kode: jalankan `docker compose up -d --build` dari folder ini.
- Matikan sementara: jalankan `docker compose down`. Jangan tambahkan `-v` kecuali memang
  ingin menghapus database dan file yang tersimpan.
