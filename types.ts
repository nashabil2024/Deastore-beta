// Hand-written mirrors of the backend Pydantic models — when you change a model in
// backend/models/*.py, change its interface HERE in the same edit. Nothing infers
// across the Python boundary.

export type UserRole = "user" | "admin";

export interface SessionUser {
  id: string;
  username: string;
  role: UserRole;
  coins: number;
  created_at: string;
}

export interface RobloxProfile {
  username: string;
  display_name: string | null;
  user_id: number | null;
  avatar_url: string | null;
}

export interface LookupResult {
  status: "found" | "not_found" | "unavailable";
  profile: RobloxProfile | null;
}

export interface Package {
  id: string;
  robux: number;
  price_idr: number;
  tag: string | null;
  active: boolean;
  sort: number;
}

export interface FakeFlag {
  kind: "exact" | "similar";
  ref_type: string | null;
  ref_code: string | null;
}

export interface AiVerdict {
  ai_status: "pending" | "done" | "unavailable";
  looks_like_payment_proof: boolean | null;
  detected_amount: number | null;
  detected_method: string | null;
  edited_signs: string | null;
  risk: "low" | "medium" | "high" | null;
  notes: string | null;
}

export type OrderStatus =
  | "menunggu_pembayaran"
  | "menunggu_verifikasi"
  | "diproses"
  | "selesai"
  | "ditolak";

export interface Order {
  id: string;
  code: string;
  user_id: string | null;
  roblox_username: string;
  roblox_profile: RobloxProfile | null;
  roblox_verified: boolean;
  robux: number;
  price_idr: number;
  discount_percent: number;
  total_idr: number;
  voucher_code?: string | null;
  promo_discount_idr?: number;
  total_coins: number | null;
  payment_method: string;
  status: OrderStatus;
  note: string | null;
  reject_reason: string | null;
  proof_file_id: string | null;
  proof_flags: FakeFlag[];
  ai_verdict: AiVerdict | null;
  created_at: string;
  updated_at: string;
  processed_at: string | null;
}

export type TopupStatus =
  | "menunggu_pembayaran"
  | "menunggu_verifikasi"
  | "disetujui"
  | "ditolak";

export interface CoinTopup {
  id: string;
  code: string;
  user_id: string;
  coins: number;
  amount_idr: number;
  payment_method: string;
  status: TopupStatus;
  reject_reason: string | null;
  proof_file_id: string | null;
  proof_flags: FakeFlag[];
  ai_verdict: AiVerdict | null;
  created_at: string;
  processed_at: string | null;
}

export interface PaymentAccount {
  method: string;
  name: string;
  number: string;
}

export interface StoreSettings {
  wa_number: string;
  payment_accounts: PaymentAccount[];
  /** Compatibility value for older screens: IDR per one coin. */
  coin_rate: number;
  coin_price_idr_per_100: number;
  coin_discount_percent: number;
  min_topup_coins: number;
  announcement: string | null;
  maintenance: boolean;
  qris_image_file_id: string | null;
  store_name: string;
  logo_file_id: string | null;
  hero_title: string;
  hero_subtitle: string;
  store_open: boolean;
  store_open_now: boolean;
  opening_hours_enabled: boolean;
  opens_at: string;
  closes_at: string;
  robux_stock: number | null;
  robux_stock_available: number | null;
  custom_robux_price_per_1000_idr: number;
}

export interface AdminStats {
  orders_pending: number;
  orders_today: number;
  topups_pending: number;
  users_count: number;
  revenue_idr: number;
  robux_sold: number;
  coin_circulation: number;
}

export interface AdminUser {
  id: string;
  username: string;
  role: UserRole;
  coins: number;
  created_at: string;
}

export interface AdminLog {
  id: string;
  admin_username: string;
  action: string;
  target: string;
  detail: string | null;
  created_at: string;
}
