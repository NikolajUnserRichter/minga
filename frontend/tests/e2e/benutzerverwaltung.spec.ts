/**
 * Abnahme Benutzerverwaltung (Paket 4, B8), ohne Backend und ohne Keycloak.
 *
 * Läuft gegen einen lokalen Vite-Dev-Server mit VITE_AUTH_DISABLED=true. Der
 * Dev-Nutzer aus AuthContext.tsx hat alle Rollen und sieht die Seite deshalb
 * als Administrator. Alle Aufrufe an /api/v1/users beantwortet eine kleine
 * Attrappe im Browser. Sie folgt dem Backend-Vertrag (backend/app/schemas/user.py,
 * backend/app/api/v1/users.py). Andere API-Aufrufe enden mit 404.
 *
 * Lauf (aus frontend/):
 *   VITE_AUTH_DISABLED=true VITE_API_URL=http://localhost:5179 \
 *     ./node_modules/.bin/vite --port 5179 --strictPort &
 *   until curl -sf http://localhost:5179/ >/dev/null; do sleep 1; done
 *   U2_ABNAHME_URL=http://localhost:5179 ./node_modules/.bin/playwright test \
 *     tests/e2e/benutzerverwaltung.spec.ts --retries=0
 *
 * VITE_API_URL zeigt auf den Dev-Server selbst. So bleiben alle Aufrufe auf
 * demselben Origin, und die Attrappe braucht keine CORS-Header.
 */
import { test, expect, Page } from '@playwright/test';

const BASE = process.env.U2_ABNAHME_URL || '';
test.skip(!BASE, 'U2_ABNAHME_URL nicht gesetzt: nur gegen lokalen Dev-Server mit VITE_AUTH_DISABLED=true');

type Rolle = 'admin' | 'sales' | 'production_planner' | 'production_staff' | 'accounting';

interface Benutzer {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  role: Rolle | null;
  roles: Rolle[];
  enabled: boolean;
  created_at: string | null;
  is_self: boolean;
}

interface Aufruf {
  methode: string;
  pfad: string;
  body: unknown;
}

const ID_ICH = '11111111-1111-4111-8111-111111111111';
const ID_GERNOT = '22222222-2222-4222-8222-222222222222';
const ID_OHNE = '33333333-3333-4333-8333-333333333333';
const ID_NEU = '44444444-4444-4444-8444-444444444444';
const ID_MEHR = '55555555-5555-4555-8555-555555555555';

function startBestand(): Benutzer[] {
  return [
    { id: ID_ICH, email: 'admin@minga-greens.de', first_name: 'Admin', last_name: 'Minga',
      role: 'admin', roles: ['admin'], enabled: true, created_at: '2026-09-02T08:00:00Z', is_self: true },
    { id: ID_GERNOT, email: 'gernot@example.org', first_name: 'Gernot', last_name: 'Kleinberger',
      role: 'admin', roles: ['admin'], enabled: true, created_at: '2026-09-02T08:05:00Z', is_self: false },
    { id: ID_OHNE, email: 'ohne@example.org', first_name: 'Ohne', last_name: 'Rolle',
      role: null, roles: [], enabled: true, created_at: null, is_self: false },
    { id: ID_MEHR, email: 'mehr@example.org', first_name: 'Mehr', last_name: 'Rollen',
      role: 'sales', roles: ['sales', 'accounting'], enabled: true, created_at: null, is_self: false },
  ];
}

const TEMP_ANLAGE = 'Einmal-Test-1234!';
const TEMP_RESET = 'Neu-Test-5678!';
const ERLAUBT_PATCH = ['first_name', 'last_name', 'role', 'enabled'];
const DEMO_SPERRE = 'In der Demo können Benutzer nicht geändert werden.';

/** Hängt die Attrappe ein und liefert das Protokoll der Aufrufe. */
async function attrappe(
  page: Page,
  opts: { listeFehler?: { status: number; detail: string }; demo?: boolean } = {},
) {
  const db = startBestand();
  const aufrufe: Aufruf[] = [];

  // Zuerst registriert = zuletzt geprüft: alles Übrige unter /api/v1 → 404.
  await page.route('**/api/v1/**', (route) =>
    route.fulfill({ status: 404, contentType: 'application/json', body: JSON.stringify({ detail: 'nicht gemockt' }) }),
  );

  await page.route('**/api/v1/users**', async (route) => {
    const req = route.request();
    const pfad = new URL(req.url()).pathname.replace(/^.*\/api\/v1/, '');
    const methode = req.method();
    const roh = req.postData();
    const body = roh ? JSON.parse(roh) : null;
    aufrufe.push({ methode, pfad, body });
    const json = (status: number, daten: unknown) =>
      route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(daten) });

    const teile = pfad.split('/').filter(Boolean); // ['users', id?, aktion?]
    const ziel = teile[1] ? db.find((b) => b.id === teile[1]) : undefined;

    if (methode === 'GET' && teile.length === 1) {
      if (opts.listeFehler) return json(opts.listeFehler.status, { detail: opts.listeFehler.detail });
      return json(200, { items: db, total: db.length, schreibgeschuetzt: !!opts.demo });
    }
    // backend/app/api/v1/users.py, _mandant_schreiben: im Mandanten demo ist jedes Schreiben gesperrt, Lesen nicht.
    if (opts.demo && methode !== 'GET') return json(403, { detail: DEMO_SPERRE });
    if (methode === 'POST' && teile.length === 1) {
      const unbekannt = Object.keys(body).filter((k) => !['email', 'first_name', 'last_name', 'role'].includes(k));
      if (unbekannt.length) return json(422, { detail: [{ loc: ['body', unbekannt[0]], msg: 'Extra inputs are not permitted' }] });
      if (db.some((b) => b.email === body.email)) return json(409, { detail: 'Diese E-Mail-Adresse ist bereits vergeben.' });
      const neu: Benutzer = { id: ID_NEU, email: body.email, first_name: body.first_name, last_name: body.last_name,
        role: body.role, roles: [body.role], enabled: true, created_at: '2026-10-08T12:00:00Z', is_self: false };
      db.push(neu);
      return json(201, { ...neu, temporary_password: TEMP_ANLAGE });
    }
    if (!ziel) return json(404, { detail: 'Benutzer nicht gefunden.' });
    if (methode === 'PATCH' && teile.length === 2) {
      const unbekannt = Object.keys(body).filter((k) => !ERLAUBT_PATCH.includes(k));
      if (unbekannt.length) return json(422, { detail: [{ loc: ['body', unbekannt[0]], msg: 'Extra inputs are not permitted' }] });
      if (ziel.is_self && body.enabled === false) return json(409, { detail: 'Das eigene Konto kann nicht deaktiviert werden.' });
      if (body.first_name !== undefined) ziel.first_name = body.first_name;
      if (body.last_name !== undefined) ziel.last_name = body.last_name;
      if (body.enabled !== undefined) ziel.enabled = body.enabled;
      if (body.role !== undefined) { ziel.role = body.role; ziel.roles = [body.role]; }
      return json(200, ziel);
    }
    if (methode === 'POST' && teile[2] === 'reset-password') {
      return json(200, { user: ziel, temporary_password: TEMP_RESET });
    }
    return json(405, { detail: 'Nicht im Vertrag' });
  });

  return aufrufe;
}

const karte = (page: Page, email: string) => page.locator('.card', { hasText: email });

test.describe('Benutzerverwaltung (B8)', () => {
  test('zeigt die Antwort des Servers und räumt die alte Attrappe weg', async ({ page }) => {
    await page.addInitScript(() => {
      localStorage.setItem('minga-mock-users', JSON.stringify([
        { id: '1', name: 'Max Mustermann', email: 'max@minga-greens.de', role: 'ADMIN' },
      ]));
    });
    const aufrufe = await attrappe(page);
    await page.goto(`${BASE}/users`);

    await expect(karte(page, 'gernot@example.org')).toBeVisible();
    await expect(page.getByText('Max Mustermann')).toHaveCount(0);
    await expect.poll(() => page.evaluate(() => localStorage.getItem('minga-mock-users'))).toBeNull();
    expect(aufrufe.some((a) => a.methode === 'GET' && a.pfad === '/users')).toBe(true);

    // Benutzer ohne Rolle fallen auf
    await expect(karte(page, 'ohne@example.org').getByText('Keine Rolle')).toBeVisible();
    await expect(page.getByText('Ein aktiver Benutzer hat keine Rolle')).toBeVisible();
  });

  test('Anlegen schickt genau die vier Felder und zeigt das Einmalpasswort einmal', async ({ page }) => {
    const aufrufe = await attrappe(page);
    await page.goto(`${BASE}/users`);

    await page.getByRole('button', { name: 'Neuer Benutzer' }).click();
    const dialog = page.getByRole('dialog');
    // Vorbelegt: Mitarbeiter-Login
    await expect(dialog.locator('input[type=radio][value="production_staff"]')).toBeChecked();
    await expect(dialog.getByText('Darf Rechnungen anlegen, finalisieren und versenden.').first()).toBeVisible();

    await dialog.getByLabel('Vorname').fill('Mia');
    // Esc verwirft das halb ausgefüllte Formular nicht
    await page.keyboard.press('Escape');
    await expect(dialog.getByLabel('Vorname')).toHaveValue('Mia');
    await dialog.getByLabel('Nachname').fill('Mitarbeiterin');
    await dialog.getByLabel('E-Mail').fill('Mia@Example.org');
    await dialog.getByRole('button', { name: 'Anlegen' }).click();

    await expect(page.getByTestId('einmalpasswort')).toHaveText(TEMP_ANLAGE);
    await expect(page.getByText('Anmeldename: mia@example.org')).toBeVisible();
    // Ein versehentliches Esc verwirft das Einmalpasswort nicht
    await page.keyboard.press('Escape');
    await expect(page.getByTestId('einmalpasswort')).toHaveText(TEMP_ANLAGE);
    const anlage = aufrufe.find((a) => a.methode === 'POST' && a.pfad === '/users');
    expect(anlage?.body).toEqual({
      email: 'mia@example.org', first_name: 'Mia', last_name: 'Mitarbeiterin', role: 'production_staff',
    });

    await page.getByRole('button', { name: 'Passwort ist notiert' }).click();
    await expect(page.getByText(TEMP_ANLAGE)).toHaveCount(0);
    await expect(karte(page, 'mia@example.org')).toBeVisible();
  });

  test('Serverfehler erscheinen im Klartext', async ({ page }) => {
    await attrappe(page);
    await page.goto(`${BASE}/users`);

    await page.getByRole('button', { name: 'Neuer Benutzer' }).click();
    const dialog = page.getByRole('dialog');
    await dialog.getByLabel('Vorname').fill('Doppelt');
    await dialog.getByLabel('Nachname').fill('Angelegt');
    await dialog.getByLabel('E-Mail').fill('gernot@example.org');
    await dialog.getByRole('button', { name: 'Anlegen' }).click();

    await expect(page.getByText('Diese E-Mail-Adresse ist bereits vergeben.')).toBeVisible();
    await expect(page.getByTestId('einmalpasswort')).toHaveCount(0);
  });

  test('Deaktivieren fragt nach, löscht nie und lässt sich rückgängig machen', async ({ page }) => {
    const aufrufe = await attrappe(page);
    await page.goto(`${BASE}/users`);

    await karte(page, 'gernot@example.org').getByRole('button', { name: 'Deaktivieren', exact: true }).click();
    const dialog = page.getByRole('dialog');
    await expect(dialog.getByText('Benutzer deaktivieren?')).toBeVisible();
    expect(aufrufe.filter((a) => a.methode === 'PATCH')).toHaveLength(0);

    await dialog.getByRole('button', { name: 'Deaktivieren', exact: true }).click();
    await expect(karte(page, 'gernot@example.org').getByText('Deaktiviert')).toBeVisible();
    const patch = aufrufe.filter((a) => a.methode === 'PATCH');
    expect(patch).toHaveLength(1);
    expect(patch[0].pfad).toBe(`/users/${ID_GERNOT}`);
    expect(patch[0].body).toEqual({ enabled: false });
    expect(aufrufe.some((a) => a.methode === 'DELETE')).toBe(false);

    await karte(page, 'gernot@example.org').getByRole('button', { name: 'Aktivieren', exact: true }).click();
    await expect(karte(page, 'gernot@example.org').getByRole('button', { name: 'Deaktivieren', exact: true })).toBeVisible();
    expect(aufrufe.filter((a) => a.methode === 'PATCH')[1].body).toEqual({ enabled: true });
  });

  test('das eigene Konto ist vor Aussperren geschützt', async ({ page }) => {
    const aufrufe = await attrappe(page);
    await page.goto(`${BASE}/users`);

    const eigene = karte(page, 'admin@minga-greens.de');
    await expect(eigene.getByText('(Sie)')).toBeVisible();
    await expect(eigene.getByRole('button', { name: 'Deaktivieren', exact: true })).toHaveCount(0);

    await eigene.getByRole('button', { name: 'Bearbeiten' }).click();
    const dialog = page.getByRole('dialog');
    await expect(dialog.locator('input[type=radio][value="production_staff"]')).toBeDisabled();
    await expect(dialog.getByLabel('E-Mail')).toBeDisabled();
    await dialog.getByLabel('Vorname').fill('Chefin');
    await dialog.getByRole('button', { name: 'Speichern' }).click();

    await expect(eigene.getByText('Chefin Minga')).toBeVisible();
    const patch = aufrufe.find((a) => a.methode === 'PATCH');
    expect(patch?.pfad).toBe(`/users/${ID_ICH}`);
    expect(patch?.body).toEqual({ first_name: 'Chefin' });
  });

  test('Rolle ändern schickt nur die Rolle', async ({ page }) => {
    const aufrufe = await attrappe(page);
    await page.goto(`${BASE}/users`);

    await karte(page, 'ohne@example.org').getByRole('button', { name: 'Bearbeiten' }).click();
    const dialog = page.getByRole('dialog');
    await dialog.locator('input[type=radio][value="accounting"]').check();
    await dialog.getByRole('button', { name: 'Speichern' }).click();

    await expect(karte(page, 'ohne@example.org').getByText('Buchhaltung')).toBeVisible();
    expect(aufrufe.find((a) => a.methode === 'PATCH')?.body).toEqual({ role: 'accounting' });
  });

  test('mehrere Rollen: Umbenennen behält sie, die höchste wählen stuft darauf zurück', async ({ page }) => {
    const aufrufe = await attrappe(page);
    await page.goto(`${BASE}/users`);
    const mehr = karte(page, 'mehr@example.org');
    await expect(mehr.getByText('Buchhaltung')).toBeVisible();

    await mehr.getByRole('button', { name: 'Bearbeiten' }).click();
    let dialog = page.getByRole('dialog');
    await expect(dialog.locator('input[type=radio]:checked')).toHaveCount(0);
    await dialog.getByLabel('Nachname').fill('Umbenannt');
    await dialog.getByRole('button', { name: 'Speichern' }).click();
    await expect(mehr.getByText('Mehr Umbenannt')).toBeVisible();
    await expect(mehr.getByText('Buchhaltung')).toBeVisible();

    await mehr.getByRole('button', { name: 'Bearbeiten' }).click();
    dialog = page.getByRole('dialog');
    await dialog.locator('input[type=radio][value="sales"]').check();
    await dialog.getByRole('button', { name: 'Speichern' }).click();
    await expect(mehr.getByText('Buchhaltung')).toHaveCount(0);
    await expect(mehr.getByText('Vertrieb')).toBeVisible();

    const patch = aufrufe.filter((a) => a.methode === 'PATCH');
    expect(patch.map((a) => a.body)).toEqual([{ last_name: 'Umbenannt' }, { role: 'sales' }]);
  });

  test('Passwort zurücksetzen fragt nach und zeigt das neue Einmalpasswort', async ({ page }) => {
    const aufrufe = await attrappe(page);
    await page.goto(`${BASE}/users`);

    await karte(page, 'gernot@example.org').getByRole('button', { name: 'Passwort zurücksetzen' }).click();
    expect(aufrufe.filter((a) => a.pfad.endsWith('/reset-password'))).toHaveLength(0);
    await page.getByRole('dialog').getByRole('button', { name: 'Zurücksetzen' }).click();

    await expect(page.getByTestId('einmalpasswort')).toHaveText(TEMP_RESET);
    await expect(page.getByText('Anmeldename: gernot@example.org')).toBeVisible();
    expect(aufrufe.filter((a) => a.methode === 'POST' && a.pfad === `/users/${ID_GERNOT}/reset-password`)).toHaveLength(1);
  });

  test('ein Ladefehler erscheint als Fehler, nicht als leere Liste', async ({ page }) => {
    await attrappe(page, { listeFehler: { status: 503, detail: 'Benutzerverwaltung derzeit nicht verfügbar: Zeitüberschreitung' } });
    await page.goto(`${BASE}/users`);

    await expect(page.getByText('Benutzer konnten nicht geladen werden')).toBeVisible();
    await expect(page.getByText('Benutzerverwaltung derzeit nicht verfügbar: Zeitüberschreitung')).toBeVisible();
    await expect(page.getByText('Keine Benutzer gefunden')).toHaveCount(0);
    await expect(page.getByRole('button', { name: 'Neuer Benutzer' })).toHaveCount(0);
  });

  test('Demo: Liste lesbar, ohne Schreibknöpfe', async ({ page }) => {
    const aufrufe = await attrappe(page, { demo: true });
    await page.goto(`${BASE}/users`);
    await expect(karte(page, 'gernot@example.org')).toBeVisible();

    // E-M6: Die Liste meldet schreibgeschuetzt; die Seite bietet nichts Schreibendes an.
    await expect(page.getByText('In der Demo können Benutzer nur angesehen werden.')).toBeVisible();
    await expect(page.getByRole('button', { name: 'Neuer Benutzer' })).toHaveCount(0);
    for (const knopf of ['Bearbeiten', 'Passwort zurücksetzen', 'Deaktivieren', 'Aktivieren']) {
      await expect(page.getByRole('button', { name: knopf, exact: true })).toHaveCount(0);
    }
    await expect(page.getByText('Ein aktiver Benutzer hat keine Rolle')).toHaveCount(0);
    expect(aufrufe.filter((a) => a.methode !== 'GET')).toHaveLength(0);
  });
});
