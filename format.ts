// Formatting + label helpers (id-ID).

export function formatIDR(n: number): string {
  return new Intl.NumberFormat("id-ID", {
    style: "currency",
    currency: "IDR",
    maximumFractionDigits: 0,
  }).format(n);
}

export function formatNumber(n: number): string {
  return new Intl.NumberFormat("id-ID").format(n);
}

export function formatDateTime(iso: string): string {
  return new Date(iso).toLocaleString("id-ID", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export const PAYMENT_LABELS: Record<string, string> = {
  qris: "QRIS",
  dana: "DANA",
  gopay: "GoPay",
  ovo: "OVO",
  shopeepay: "ShopeePay",
  bca: "Bank BCA",
  mandiri: "Bank Mandiri",
  bri: "Bank BRI",
  bank_transfer: "Transfer Bank (pilih rekening)",
  bank_other: "Bank lainnya",
  bni: "Bank BNI",
  btn: "Bank BTN",
  bsi: "Bank Syariah Indonesia",
  cimb: "CIMB Niaga",
  danamon: "Bank Danamon",
  permata: "Bank Permata",
  maybank: "Maybank Indonesia",
  ocbc: "OCBC Indonesia",
  panin: "Bank Panin",
  mega: "Bank Mega",
  sinarmas: "Bank Sinarmas",
  jenius: "Jenius / BTPN",
  jago: "Bank Jago",
  blu: "blu by BCA Digital",
  seabank: "SeaBank",
  allo: "Allo Bank",
  neo: "Bank Neo Commerce",
  bank_dki: "Bank DKI",
  bjb: "Bank BJB",
  jateng: "Bank Jateng",
  jatim: "Bank Jatim",
  bali: "Bank BPD Bali",
  diy: "Bank BPD DIY",
  sumut: "Bank Sumut",
  sumselbabel: "Bank Sumsel Babel",
  kalbar: "Bank Kalbar",
  kalsel: "Bank Kalsel",
  kaltimtara: "Bank Kaltimtara",
  sulselbar: "Bank Sulselbar",
  nagari: "Bank Nagari",
  ntb: "Bank NTB Syariah",
  ntt: "Bank NTT",
  maluku: "Bank Maluku Malut",
  malut: "Bank Maluku Utara",
  bengkulu: "Bank Bengkulu",
  papua: "Bank Papua",
  coin: "Saldo Coin",
};

export const EWALLET_METHODS = ["dana", "gopay", "ovo", "shopeepay"] as const;

export const BANK_METHODS = [
  "bca", "bri", "bni", "mandiri", "btn", "bsi", "cimb", "danamon", "permata",
  "maybank", "ocbc", "panin", "mega", "sinarmas", "jenius", "jago", "blu", "seabank",
  "allo", "neo", "bank_dki", "bjb", "jateng", "jatim", "bali", "diy", "sumut",
  "sumselbabel", "kalbar", "kalsel", "kaltimtara", "sulselbar", "nagari", "ntb", "ntt",
  "maluku", "malut", "bengkulu", "papua",
] as const;

export const MANUAL_METHODS = ["qris", ...EWALLET_METHODS, ...BANK_METHODS] as const;

export function waLink(waNumber: string, text: string): string {
  return `https://wa.me/${waNumber.replace(/[^0-9]/g, "")}?text=${encodeURIComponent(text)}`;
}

export function orderWaText(code: string, roblox: string, robux: number, total: string, method: string): string {
  return [
    "Halo Dea Store, saya ingin konfirmasi pesanan:",
    `Kode Pesanan: ${code}`,
    `Username Roblox: ${roblox}`,
    `Jumlah Robux: ${formatNumber(robux)}`,
    `Total: ${total}`,
    `Metode Bayar: ${PAYMENT_LABELS[method] ?? method}`,
    "Bukti pembayaran sudah saya upload di website. Mohon dicek ya, terima kasih!",
  ].join("\n");
}

export function topupWaText(code: string, coins: number, total: string, method: string): string {
  return [
    "Halo Dea Store, saya ingin konfirmasi top-up Saldo Coin:",
    `Kode Top-Up: ${code}`,
    `Jumlah Coin: ${formatNumber(coins)}`,
    `Total: ${total}`,
    `Metode Bayar: ${PAYMENT_LABELS[method] ?? method}`,
    "Bukti pembayaran sudah saya upload di website. Mohon dicek ya, terima kasih!",
  ].join("\n");
}

export function fileUrl(fileId: string, code?: string): string {
  return `/api/files/${fileId}${code ? `?code=${encodeURIComponent(code)}` : ""}`;
}
