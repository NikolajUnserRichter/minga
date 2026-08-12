/**
 * Browser-Smoke gegen die Demo (demo.novaerp.de) mit Keycloak-Login.
 *
 * Prüft genau die Seiten, die in den letzten Releases angefasst wurden —
 * insbesondere die Ex-Weiße-Seite-Bugs (Verpackung, Abonnements) und die
 * neuen Seiten (Tagesplan, Dienstplan).
 *
 * Lauf: BASE_URL=https://demo.novaerp.de DEMO_USER=anna@demo.novaerp.de \
 *       DEMO_PASS=demo1234 npx playwright test tests/e2e/smoke-demo.spec.ts
 */
import { test, expect, Page } from '@playwright/test';

const BASE_URL = process.env.BASE_URL || 'https://demo.novaerp.de';
const DEMO_USER = process.env.DEMO_USER || 'anna@demo.novaerp.de';
const DEMO_PASS = process.env.DEMO_PASS || '';

test.skip(!DEMO_PASS, 'DEMO_PASS nicht gesetzt — Smoke nur gegen die Demo lauffähig');

test.describe.configure({ mode: 'serial' });

async function login(page: Page) {
  await page.goto(`${BASE_URL}/dashboard`);
  // Keycloak-Redirect abwarten und einloggen (falls nicht schon eingeloggt)
  const userField = page.getByRole('textbox', { name: /Username or email|Benutzername/i });
  // isVisible() wartet NICHT — explizit auf das Login-Formular warten
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


/** SPA-Navigation über die Sidebar — vermeidet Keycloak-Redirect-Roundtrips. */
async function nav(page: Page, linkName: string | RegExp) {
  await page.getByRole('link', { name: linkName }).first().click();
}

/** Weiße-Seite-Detektor: Body muss sichtbaren Text enthalten. */
async function expectNotBlank(page: Page) {
  const text = (await page.locator('body').innerText()).trim();
  expect(text.length, 'Seite ist leer (weißer Bildschirm)').toBeGreaterThan(20);
}

test('Login + Dashboard rendert (KW-Header, Wochenkarte)', async ({ page }) => {
  await login(page);
  await expect(page.getByText(/Übersicht KW/)).toBeVisible();
  await expect(page.getByText('Ernte diese Woche')).toBeVisible();
  await expectNotBlank(page);
});

test('Lager → Verpackung-Tab rendert (Ex-Bug 1: weiße Seite)', async ({ page }) => {
  await login(page);
  await nav(page, 'Lager');
  await page.getByRole('tab', { name: /Verpackung/ }).first().click();
  // Tabelle ODER Empty-State — Hauptsache kein Crash
  await expect(
    page.getByText(/Kein Verpackungsmaterial|Artikelnr\./).first()
  ).toBeVisible({ timeout: 10_000 });
  await expectNotBlank(page);
});

test('Abonnements rendert (Ex-Bug 5: weiße Seite)', async ({ page }) => {
  await login(page);
  await nav(page, /Abo/);
  await expect(page.getByText(/Abo|Abonnement/i).first()).toBeVisible({ timeout: 10_000 });
  await expectNotBlank(page);
});

test('Bestellungen + Filter "Offen" (Ex-Bug 6: HTTP 422)', async ({ page }) => {
  await login(page);
  await nav(page, 'Bestellungen');
  await page.locator('select').first().selectOption('OFFEN');
  await expect(page.getByText(/konnten nicht geladen werden/)).toHaveCount(0);
  await expectNotBlank(page);
});

test('Tagesplan zeigt Sektionen + Im Dienst', async ({ page }) => {
  await login(page);
  await nav(page, 'Tagesplan');
  for (const s of ['Im Dienst', 'Aussaat', 'Ernte', 'Verpacken', 'Ausliefern']) {
    await expect(page.getByText(s).first()).toBeVisible({ timeout: 10_000 });
  }
  await expectNotBlank(page);
});

test('Dienstplan: Woche rendert + Schicht anlegen', async ({ page }) => {
  await login(page);
  await nav(page, 'Dienstplan');
  await expect(page.getByText(/^KW \d+/).first()).toBeVisible({ timeout: 10_000 });

  // Schicht auf dem ersten Tag anlegen
  await page.getByTitle('Schicht hinzufügen').first().click();
  await page.getByLabel('Mitarbeiter').fill(`Smoke Tester ${Date.now()}`);
  await page.getByLabel('Aufgabe (optional)').fill('Smoke-Test');
  await page.getByRole('button', { name: 'Anlegen' }).click();
  await expect(page.getByText('Smoke-Test').first()).toBeVisible({ timeout: 10_000 });
});

test('Produktion: Aussaat-Modal öffnet (Substrat/Abweichung-Felder)', async ({ page }) => {
  await login(page);
  await nav(page, 'Wachstumschargen');
  await page.getByRole('button', { name: /Neue Aussaat/ }).click();
  await expect(page.getByText('Saatgut').first()).toBeVisible({ timeout: 10_000 });
  await expectNotBlank(page);
});

test('Kunden: Checkbox "Preise auf Lieferschein" vorhanden', async ({ page }) => {
  await login(page);
  await nav(page, 'Kunden');
  await page.getByRole('button', { name: /Neuer Kunde|Anlegen|Erstellen/i }).first().click();
  await expect(page.getByText('Preise auf Lieferschein andrucken')).toBeVisible({ timeout: 10_000 });
});
