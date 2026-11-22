import { test as base, expect, type Locator, type Page } from '@playwright/test';

// Every API request is fulfilled here. These browser tests never read or mutate
// a running store's database, even if Vite is configured with a live API proxy.
const createdAt = '2026-11-20T03:00:00.000Z';
const settings = {
  wa_number: '6281200000001',
  payment_accounts: [
    { method: 'qris', name: 'QRIS Akun Tes', number: 'QRIS-TEST-ONLY' },
    { method: 'dana', name: 'DANA Rekening Tes', number: '081200000001' },
  ],
  coin_rate: 1.1,
  coin_price_idr_per_100: 110,
  coin_discount_percent: 10,
  min_topup_coins: 10000,
  announcement: 'Selamat datang di Dea Store. Pembayaran diverifikasi admin.',
  maintenance: false,
  qris_image_file_id: 'qris-test-image',
  store_name: 'Dea Store',
  logo_file_id: null,
  hero_title: 'Top Up Robux Aman & Hemat',
  hero_subtitle: 'Pilih jumlah Robux dan metode pembayaran yang kamu inginkan.',
  store_open: true,
  store_open_now: true,
  opening_hours_enabled: false,
  opens_at: '08:00',
  closes_at: '22:00',
  robux_stock: 100000,
  robux_stock_available: 100000,
  custom_robux_price_per_1000_idr: 150000,
};
const packages = [100, 500, 1000, 10000].map((robux, index) => ({
  id: `package-${robux}`, robux, price_idr: robux * 150,
  tag: index === 1 ? 'Paling populer' : null, active: true, sort: index,
}));
const orderBase = {
  user_id: 'test-user', roblox_profile: null, roblox_verified: false,
  robux: 1000, price_idr: 150000, discount_percent: 0,
  total_idr: 150000, total_coins: null, payment_method: 'dana',
  status: 'menunggu_verifikasi', note: null, reject_reason: null,
  proof_file_id: null, proof_flags: [], ai_verdict: null,
  created_at: createdAt, updated_at: createdAt, processed_at: null,
};
const orders = [
  { ...orderBase, id: 'order-a', code: 'DEA-A1B2C', roblox_username: 'MobileBuyerWithLongName123', status: 'menunggu_pembayaran' },
  { ...orderBase, id: 'order-b', code: 'DEA-D3E4F', roblox_username: 'OtherBuyer', robux: 500, total_idr: 75000 },
];
const topupBase = {
  user_id: 'test-user', coins: 10000, amount_idr: 11000,
  payment_method: 'dana', status: 'menunggu_pembayaran',
  reject_reason: null, proof_file_id: null, proof_flags: [], ai_verdict: null,
  created_at: createdAt, processed_at: null,
};
const topups = [
  { ...topupBase, id: 'topup-a', code: 'TUP-A1B2C' },
  { ...topupBase, id: 'topup-b', code: 'TUP-D3E4F', payment_method: 'qris', status: 'menunggu_verifikasi' },
];

type MockApi = { unexpected: string[] };
const test = base.extend<{ mockApi: MockApi }>({
  mockApi: async ({ page }, use) => {
    const unexpected: string[] = [];
    await page.route('**/api/**', async (route) => {
      const request = route.request();
      const url = new URL(request.url());
      const path = url.pathname.replace(/^\/api/, '').replace(/\/$/, '') || '/';
      const respond = (body: unknown, status = 200) => route.fulfill({ status, json: body });
      if (path === '/roblox/lookup' && request.method() === 'POST') {
        const { username } = request.postDataJSON() as { username: string };
        await respond({ status: 'found', profile: { username, display_name: username, user_id: 12345, avatar_url: null } });
        return;
      }
      if (request.method() !== 'GET') {
        unexpected.push(`${request.method()} ${path}`);
        await respond({ detail: 'Mutation blocked by isolated browser test' }, 405);
        return;
      }
      if (path === '/auth/me') {
        await respond({ user: { id: 'test-user', username: 'AdminMobileTest', role: 'admin', coins: 25000, created_at: createdAt } });
      } else if (path === '/settings') {
        await respond(settings);
      } else if (path === '/packages') {
        await respond(packages);
      } else if (path === '/orders/mine') {
        await respond(orders);
      } else if (path === '/topups/mine') {
        await respond(topups);
      } else if (path === '/admin/orders') {
        const status = url.searchParams.get('status');
        await respond(orders.filter((order) => !status || status === 'all' || (status === 'pending' ? ['menunggu_pembayaran', 'menunggu_verifikasi', 'diproses'].includes(order.status) : order.status === status)));
      } else if (path === '/admin/topups') {
        const status = url.searchParams.get('status');
        await respond(topups.filter((topup) => !status || status === 'all' || (status === 'pending' ? ['menunggu_pembayaran', 'menunggu_verifikasi'].includes(topup.status) : topup.status === status)));
      } else if (path === '/admin/stats') {
        await respond({ orders_pending: 2, orders_today: 2, topups_pending: 2, users_count: 25, revenue_idr: 125000000, robux_sold: 1000000, coin_circulation: 10000 });
      } else if (path === '/admin/logs' || path === '/admin/users') {
        await respond([]);
      } else if (path === '/admin/notification-status') {
        await respond({ configured: false, missing: [] });
      } else if (path.startsWith('/admin/orders/')) {
        const order = orders.find((item) => item.id === path.split('/').pop());
        await respond(order ?? { detail: 'Not found' }, order ? 200 : 404);
      } else if (path.startsWith('/orders/')) {
        const order = orders.find((item) => item.code === decodeURIComponent(path.split('/').pop() ?? ''));
        await respond(order ?? { detail: 'Not found' }, order ? 200 : 404);
      } else if (path.startsWith('/files/')) {
        await route.fulfill({ contentType: 'image/svg+xml', body: '<svg xmlns="http://www.w3.org/2000/svg" width="192" height="192"><rect width="192" height="192" fill="white"/><text x="20" y="96">QRIS TEST</text></svg>' });
      } else {
        unexpected.push(`${request.method()} ${path}`);
        await respond({ detail: 'Unmocked API request' }, 404);
      }
    });
    await use({ unexpected });
    expect(unexpected, 'All API requests must stay inside the read-only test fixtures').toEqual([]);
  },
});

async function noPageOverflow(page: Page) {
  await page.evaluate(async () => { await document.fonts.ready; });
  const measurements = await page.evaluate(() => {
    const width = document.documentElement.clientWidth;
    return {
      overflow: Math.max(document.documentElement.scrollWidth, document.body.scrollWidth) - width,
      offenders: Array.from(document.querySelectorAll('main *')).filter((element) => {
        const box = element.getBoundingClientRect();
        return box.width > 0 && (box.left < -1 || box.right > width + 1);
      }).slice(0, 8).map((element) => `${element.tagName} ${element.getAttribute('data-testid') ?? element.className}`),
    };
  });
  expect(measurements.overflow, `Page exceeds viewport; candidates: ${measurements.offenders.join('; ')}`).toBeLessThanOrEqual(1);
}

async function tapTarget(locator: Locator) {
  const bounds = await locator.boundingBox();
  expect(bounds, 'The primary action should have a visible tap target').not.toBeNull();
  expect(bounds!.height).toBeGreaterThanOrEqual(44);
  expect(bounds!.width).toBeGreaterThanOrEqual(44);
}

for (const width of [320, 375, 390, 1440]) {
  test(`Home and checkout fit a ${width}px viewport with a long buyer name`, async ({ page, mockApi }) => {
    void mockApi;
    await page.setViewportSize({ width, height: 900 });
    await page.goto('/');
    await expect(page.getByTestId('package-grid')).toBeVisible();
    await expect(page.getByTestId('package-grid').getByRole('button').first()).toBeVisible();
    await noPageOverflow(page);
    await page.goto('/order?robux=1000');
    await page.getByTestId('input-roblox-username').fill(orders[0].roblox_username);
    await expect(page.getByTestId('roblox-profile-card')).toBeVisible();
    await page.getByTestId('custom-robux-input').fill('1234');
    await page.getByTestId('payment-method-card-dana').click();
    await expect(page.getByTestId('order-summary')).toContainText(orders[0].roblox_username);
    await expect(page.getByTestId('btn-submit-order')).toBeEnabled();
    await noPageOverflow(page);
  });
}

test('Admin can find a mobile order by username or code and open its details', async ({ page, mockApi }) => {
  void mockApi;
  await page.setViewportSize({ width: 320, height: 850 });
  await page.goto('/admin');
  await expect(page.getByTestId('stat-revenue')).toBeVisible();
  const tabListBounds = await page.getByRole('tablist').boundingBox();
  for (const tab of await page.getByRole('tab').all()) {
    await tapTarget(tab);
    const bounds = await tab.boundingBox();
    expect(bounds!.y + bounds!.height).toBeLessThanOrEqual(tabListBounds!.y + tabListBounds!.height + 1);
  }
  await noPageOverflow(page);
  await page.getByTestId('admin-tab-orders').click();
  const cards = page.getByTestId('admin-orders-mobile');
  await expect(cards.locator('article')).toHaveCount(2);
  await page.screenshot({ path: test.info().outputPath('admin-orders-mobile.png'), fullPage: true });
  await page.getByTestId('admin-orders-search').fill('mobilebuyer');
  await expect(cards.locator('article')).toHaveCount(1);
  await expect(cards).toContainText('DEA-A1B2C');
  await expect(cards).not.toContainText('DEA-D3E4F');
  const detail = page.getByTestId('admin-order-mobile-detail-DEA-A1B2C');
  await tapTarget(detail);
  await detail.click();
  await expect(page.getByTestId('admin-order-dialog')).toContainText(orders[0].roblox_username);
  await noPageOverflow(page);
  await page.keyboard.press('Escape');
  await expect(page.getByTestId('admin-order-dialog')).not.toBeVisible();
  await page.getByTestId('admin-orders-search').fill('dea-d3e4f');
  await expect(cards.locator('article')).toHaveCount(1);
  await expect(cards).toContainText('OtherBuyer');
  await page.getByTestId('admin-orders-search').fill('no-such-order');
  await expect(cards.locator('article')).toHaveCount(0);
  await expect(page.getByText('Tidak ada pesanan yang cocok.', { exact: false })).toBeVisible();
});

test('Admin top-up search filters mobile cards and opens the matching request', async ({ page, mockApi }) => {
  void mockApi;
  await page.setViewportSize({ width: 375, height: 850 });
  await page.goto('/admin');
  await page.getByTestId('admin-tab-topups').click();
  const cards = page.getByTestId('admin-topups-mobile');
  await expect(cards.locator('article')).toHaveCount(2);
  await page.getByTestId('admin-topups-search').fill('tup-a1b2c');
  await expect(cards.locator('article')).toHaveCount(1);
  await expect(cards).toContainText('DANA');
  const detail = page.getByTestId('admin-topup-mobile-detail-TUP-A1B2C');
  await tapTarget(detail);
  await detail.click();
  await expect(page.getByTestId('admin-topup-dialog')).toContainText('TUP-A1B2C');
  await noPageOverflow(page);
});

test('A buyer resumes an old DANA top-up and keeps its payment instructions after reload', async ({ page, mockApi }) => {
  void mockApi;
  await page.setViewportSize({ width: 320, height: 850 });
  await page.goto('/dashboard');
  // The creation form initially selects QRIS. Opening an older DANA request
  // must use the transaction's method instead of that unrelated form state.
  await expect(page.getByTestId('topup-method-select')).toHaveValue('qris');
  const resume = page.getByTestId('topup-open-mobile-TUP-A1B2C');
  await expect(resume).toBeVisible();
  await tapTarget(resume);
  await resume.click();
  await expect(page).toHaveURL(/\/dashboard\?topup=topup-a$/);
  const instructions = page.getByTestId('topup-instructions');
  await expect(instructions).toContainText('DANA Rekening Tes');
  await expect(instructions).toContainText('081200000001');
  await expect(instructions.getByAltText('QRIS Dea Store')).toHaveCount(0);
  await expect(instructions).not.toContainText('QRIS-TEST-ONLY');
  await page.reload();
  await expect(page.getByTestId('active-topup-panel')).toContainText('TUP-A1B2C');
  await expect(instructions).toContainText('DANA Rekening Tes');
  await expect(instructions).toContainText('081200000001');
  await expect(instructions.getByAltText('QRIS Dea Store')).toHaveCount(0);
  await noPageOverflow(page);
  await tapTarget(page.getByTestId('topup-wa-button'));
});

test('Checkout explains an insufficient coin balance and allows an affordable amount', async ({ page, mockApi }) => {
  void mockApi;
  await page.setViewportSize({ width: 320, height: 850 });
  await page.goto('/order?robux=1000');
  await page.getByTestId('input-roblox-username').fill('MobileBuyer');
  await page.getByTestId('payment-method-card-coin').click();
  await expect(page.getByTestId('order-coin-balance')).toContainText('Kurang');
  await expect(page.getByTestId('btn-submit-order')).toBeDisabled();
  await expect(page.getByRole('link', { name: 'Top-Up Coin', exact: true })).toHaveAttribute('href', '/dashboard');
  await page.getByTestId('custom-robux-input').fill('100');
  await expect(page.getByTestId('order-coin-balance')).toContainText('Sisa setelah bayar');
  await expect(page.getByTestId('btn-submit-order')).toBeEnabled();
  await noPageOverflow(page);
});

test('An unpaid order offers the exact amount and code for copying', async ({ page, mockApi, context }) => {
  void mockApi;
  await context.grantPermissions(['clipboard-read', 'clipboard-write']);
  await page.goto('/track?code=DEA-A1B2C');
  await page.getByRole('button', { name: 'Salin nominal pembayaran', exact: true }).click();
  await expect.poll(() => page.evaluate(() => navigator.clipboard.readText())).toBe('150000');
  await page.getByRole('button', { name: 'Salin kode pesanan', exact: true }).click();
  await expect.poll(() => page.evaluate(() => navigator.clipboard.readText())).toBe('DEA-A1B2C');
});

test('Tracking submits with Enter, updates the URL and shows the unpaid order account', async ({ page, mockApi }) => {
  void mockApi;
  await page.setViewportSize({ width: 390, height: 850 });
  await page.goto('/track');
  await page.getByTestId('track-code-input').fill('dea-a1b2c');
  await page.getByTestId('track-code-input').press('Enter');
  await expect(page).toHaveURL(/\/track\?code=DEA-A1B2C$/);
  const result = page.getByTestId('track-result');
  await expect(result).toContainText(orders[0].roblox_username);
  await expect(result).toContainText('DANA Rekening Tes');
  await expect(result).toContainText('081200000001');
  await expect(result.getByAltText('QRIS Dea Store')).toHaveCount(0);
  await noPageOverflow(page);
  await page.reload();
  await expect(result).toContainText('DEA-A1B2C');
  await expect(result).toContainText('081200000001');
});

test('My Orders exposes readable mobile cards and a working tracking link', async ({ page, mockApi }) => {
  void mockApi;
  await page.setViewportSize({ width: 375, height: 850 });
  await page.goto('/orders');
  const card = page.locator('main article').filter({ hasText: 'DEA-A1B2C' });
  await expect(card).toBeVisible();
  await expect(card).toContainText(orders[0].roblox_username);
  await expect(card).toContainText('DANA');
  // Select the actual href rather than the visible label so the test also
  // verifies that each card preserves its own order code in navigation.
  const trackingLink = card.locator('a[href="/track?code=DEA-A1B2C"]').first();
  await expect(trackingLink).toBeVisible();
  await noPageOverflow(page);
  await trackingLink.click();
  await expect(page).toHaveURL(/\/track\?code=DEA-A1B2C$/);
  await expect(page.getByTestId('track-result')).toContainText('DEA-A1B2C');
});
