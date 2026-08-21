/**
 * Excel-Upload gegen die Demo: der Upload muss als multipart/form-data ankommen.
 *
 * Hintergrund (Gernot 21.08.2026): "kommt jedes mal bei einem Upload (egal
 * welcher) eine weiße Seite". Ursache war die axios-Instanz mit dem Default
 * `Content-Type: application/json` — axios serialisiert FormData dann zu
 * `{"file":{}}`, FastAPI antwortet 422 mit einer Fehler-LISTE, und die Liste
 * landet als React-Child im Toast → Render-Crash → weiße Seite.
 *
 * Die Tests laden bewusst eine kaputte .xlsx hoch: der Server muss sie
 * erreichen und mit einer lesbaren 400 ablehnen. So bleibt die Demo-DB sauber.
 *
 * Lauf: BASE_URL=https://demo.novaerp.de DEMO_USER=anna@demo.novaerp.de \
 *       DEMO_PASS=… npx playwright test tests/e2e/import-upload.spec.ts
 */
import { test, expect, Page } from '@playwright/test';

const BASE_URL = process.env.BASE_URL || 'https://demo.novaerp.de';
const DEMO_USER = process.env.DEMO_USER || 'anna@demo.novaerp.de';
const DEMO_PASS = process.env.DEMO_PASS || '';

const XLSX_MIME = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet';

test.skip(!DEMO_PASS, 'DEMO_PASS nicht gesetzt — Upload-Test nur gegen die Demo lauffähig');

test.describe.configure({ mode: 'serial' });

async function login(page: Page) {
  await page.goto(`${BASE_URL}/dashboard`);
  const userField = page.getByRole('textbox', { name: /Username or email|Benutzername/i });
  const onLoginPage = await userField
    .waitFor({ state: 'visible', timeout: 10_000 })
    .then(() => true)
    .catch(() => false);
  if (onLoginPage) {
    await userField.fill(DEMO_USER);
    await page.getByRole('textbox', { name: /^(Password|Passwort)$/i }).fill(DEMO_PASS);
    await page.getByRole('button', { name: /Sign In|Anmelden/i }).click();
  }
  await page.waitForURL((u) => u.hostname === new URL(BASE_URL).hostname, { timeout: 20_000 });
  await expect(page.getByText('Dashboard').first()).toBeVisible({ timeout: 20_000 });
}

async function nav(page: Page, linkName: string | RegExp) {
  await page.getByRole('link', { name: linkName }).first().click();
}

/** Weiße-Seite-Detektor: Body muss sichtbaren Text enthalten. */
async function expectNotBlank(page: Page) {
  const text = (await page.locator('body').innerText()).trim();
  expect(text.length, 'Seite ist leer (weißer Bildschirm)').toBeGreaterThan(20);
}

/** Lädt eine unlesbare .xlsx hoch und gibt die Server-Antwort zurück. */
async function uploadKaputteDatei(page: Page, entity: string) {
  const response = page.waitForResponse(
    (r) => r.url().includes(`/api/v1/imports/${entity}`) && r.request().method() === 'POST',
    { timeout: 30_000 }
  );
  await page.locator('input[type=file]').first().setInputFiles({
    name: 'kaputt.xlsx',
    mimeType: XLSX_MIME,
    buffer: Buffer.from('das ist keine echte xlsx'),
  });
  return response;
}

test('Bestellungen: Historie-Upload geht als multipart raus (Ex-Bug: weiße Seite)', async ({ page }) => {
  await login(page);
  await nav(page, 'Bestellungen');

  const res = await uploadKaputteDatei(page, 'order_history');

  const contentType = res.request().headers()['content-type'] || '';
  expect(contentType, 'Upload wurde nicht als multipart/form-data gesendet').toContain(
    'multipart/form-data'
  );
  // 400 = Datei erreicht den Endpoint und wird inhaltlich abgelehnt.
  // 422 hieße: der Body kam gar nicht als Datei an.
  expect(res.status(), 'Server hat den Upload nicht als Datei erhalten').toBe(400);

  await expect(page.getByRole('alert').first()).toBeVisible({ timeout: 10_000 });
  await expectNotBlank(page);
});

test('Produktion: Chargen-Upload geht als multipart raus', async ({ page }) => {
  await login(page);
  await nav(page, 'Wachstumschargen');

  const res = await uploadKaputteDatei(page, 'grow_batches');

  expect(res.request().headers()['content-type'] || '').toContain('multipart/form-data');
  expect(res.status()).toBe(400);
  await expectNotBlank(page);
});

test('Bestellungen: Template-Download liefert eine XLSX', async ({ page }) => {
  await login(page);
  await nav(page, 'Bestellungen');

  const download = page.waitForEvent('download', { timeout: 30_000 });
  await page.getByRole('button', { name: 'Template' }).first().click();
  const file = await download;

  expect(file.suggestedFilename()).toBe('template_order_history.xlsx');
  await expectNotBlank(page);
});
