import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Building2, Save } from 'lucide-react';
import { adminApi } from '../../services/api';
import type { AppSettingResponse } from '../../services/api';
import { getErrorMessage } from '../../services/errors';
import { Button, Input, useToast } from '../ui';

/**
 * Karte „Firmendaten“ in den Einstellungen (Abschnitt F, Spec 08.10.2026).
 *
 * Liest und schreibt die Firmendaten des Mandanten über GET/PATCH
 * /admin/settings (COMPANY_*; der Router lässt nur Admins zu). Bis Oktober
 * 2026 speicherte die Karte nur im Browser (localStorage
 * 'minga_settings_company'). Was dort steht, wird einmalig als Vorschlag in
 * leere Felder übernommen und erst mit „Speichern“ auf den Server geschrieben;
 * danach ist der Browser-Eintrag gelöscht.
 *
 * Vorrang: Hat eine Belegvorlage einen eigenen Briefkopf bzw. eine eigene
 * Fußzeile, druckt das PDF nur diesen Text (pdf_service) — die Firmendaten
 * erscheinen dort dann gar nicht, also auch nicht doppelt. Die Gläubiger-ID
 * pflegt die Karte „SEPA-Lastschrift“.
 */

const FELDER = [
  { key: 'COMPANY_NAME', label: 'Firmenname' },
  { key: 'COMPANY_ADDRESS_LINE1', label: 'Straße und Hausnummer' },
  { key: 'COMPANY_ADDRESS_LINE2', label: 'PLZ und Ort' },
  { key: 'COMPANY_USTID', label: 'USt-IdNr.' },
  { key: 'COMPANY_STEUERNR', label: 'Steuernummer' },
  { key: 'COMPANY_EMAIL', label: 'E-Mail' },
  { key: 'COMPANY_PHONE', label: 'Telefon' },
  { key: 'COMPANY_WEBSITE', label: 'Website' },
  { key: 'COMPANY_BANK_NAME', label: 'Bank' },
  { key: 'COMPANY_IBAN', label: 'IBAN' },
  { key: 'COMPANY_BIC', label: 'BIC' },
] as const;

type FeldKey = (typeof FELDER)[number]['key'];
type Werte = Record<FeldKey, string>;

const ALT_SCHLUESSEL = 'minga_settings_company';
// Vorbelegung der alten Browser-Karte: Beispielwerte, nie echte Firmendaten.
const ALT_BEISPIELE = new Set([
  'Minga Greens GmbH', 'Breisacher Str. 12, 81667 München', 'DE328451962',
  'info@minga-greens.de', '+49 89 123 456 0', 'www.minga-greens.de',
]);

function leer(): Werte {
  return Object.fromEntries(FELDER.map((f) => [f.key, ''])) as Werte;
}

/** Werte der alten Browser-Karte, ohne leere Felder und ohne ihre Beispielwerte. */
function altVorschlag(): Partial<Werte> {
  let alt: Record<string, unknown>;
  try {
    alt = JSON.parse(localStorage.getItem(ALT_SCHLUESSEL) || '{}') || {};
  } catch {
    return {};
  }
  const wert = (k: string): string => {
    const v = alt[k];
    return typeof v === 'string' && v.trim() && !ALT_BEISPIELE.has(v.trim()) ? v.trim() : '';
  };
  const vorschlag: Partial<Werte> = {};
  if (wert('name')) vorschlag.COMPANY_NAME = wert('name');
  const adresse = wert('address');
  if (adresse) {
    // Die alte Karte hatte ein Feld „Straße 1, 12345 Ort“ — hier zwei Zeilen.
    const komma = adresse.lastIndexOf(',');
    if (komma > 0) {
      vorschlag.COMPANY_ADDRESS_LINE1 = adresse.slice(0, komma).trim();
      vorschlag.COMPANY_ADDRESS_LINE2 = adresse.slice(komma + 1).trim();
    } else {
      vorschlag.COMPANY_ADDRESS_LINE1 = adresse;
    }
  }
  if (wert('taxId')) vorschlag.COMPANY_USTID = wert('taxId');
  if (wert('email')) vorschlag.COMPANY_EMAIL = wert('email');
  if (wert('phone')) vorschlag.COMPANY_PHONE = wert('phone');
  if (wert('website')) vorschlag.COMPANY_WEBSITE = wert('website');
  return vorschlag;
}

/** Gespeicherte Werte des Mandanten. Nur source 'db': eine Umgebungsvariable
 *  gilt für alle Mandanten im Container und erscheint nur als Hinweis — ein
 *  Speichern übernähme sie sonst still in diesen Mandanten. */
function ausServer(data: AppSettingResponse[]): Werte {
  const werte = leer();
  for (const f of FELDER) {
    const s = data.find((x) => x.key === f.key);
    if (s && s.source === 'db') werte[f.key] = s.value || '';
  }
  return werte;
}

export function FirmendatenKarte() {
  const toast = useToast();
  const queryClient = useQueryClient();
  const { data, error } = useQuery({ queryKey: ['admin-settings'], queryFn: () => adminApi.listSettings() });
  const [werte, setWerte] = useState<Werte | null>(null);
  const [vorschlag, setVorschlag] = useState<FeldKey[]>([]);

  useEffect(() => {
    // Nur beim ersten Laden befüllen: andere Karten speichern ebenfalls über
    // /admin/settings und laden die Liste neu — ungespeicherte Eingaben hier
    // gehen dabei nicht verloren.
    if (!data || werte !== null) return;
    const start = ausServer(data);
    const alt = altVorschlag();
    const uebernommen = FELDER.map((f) => f.key).filter((k) => !start[k] && alt[k]);
    for (const k of uebernommen) start[k] = alt[k] as string;
    setWerte(start);
    setVorschlag(uebernommen);
  }, [data, werte]);

  const speichern = useMutation({
    mutationFn: (w: Werte) =>
      adminApi.updateSettings(Object.fromEntries(FELDER.map((f) => [f.key, w[f.key].trim() || null]))),
    onSuccess: async () => {
      localStorage.removeItem(ALT_SCHLUESSEL);
      setVorschlag([]);
      toast.success('Firmendaten gespeichert');
      // Der Server normalisiert (IBAN, BIC, Rand-Leerzeichen): gespeicherten Stand
      // zeigen. Scheitert nur dieses Nachladen, ist trotzdem gespeichert.
      try {
        const frisch = await adminApi.listSettings();
        queryClient.setQueryData(['admin-settings'], frisch);
        setWerte(ausServer(frisch));
      } catch {
        toast.error('Gespeichert, aber der neue Stand ließ sich nicht laden — bitte die Seite neu laden.');
      }
    },
    onError: (e) => toast.error(getErrorMessage(e, 'Speichern fehlgeschlagen')),
  });

  const verwerfen = () => {
    localStorage.removeItem(ALT_SCHLUESSEL);
    setVorschlag([]);
    if (data) setWerte(ausServer(data));
  };

  if (!data || werte === null) {
    // Ein Ladefehler zählt nur ohne Daten: scheitert ein Nachladen im
    // Hintergrund, bleiben Karte und ungespeicherte Eingaben stehen.
    return (
      <div className="card lg:col-span-2">
        <div className={`card-body text-sm ${!data && error ? 'text-red-600 dark:text-red-400' : 'text-gray-500'}`}>
          {!data && error
            ? `Firmendaten ließen sich nicht laden: ${getErrorMessage(error, 'unbekannter Fehler')}`
            : 'Lädt Firmendaten…'}
        </div>
      </div>
    );
  }

  const umgebung = (key: FeldKey): string | undefined => {
    const s = data.find((x) => x.key === key);
    return s && s.source === 'env' && s.value ? `Vorgabe des Servers: ${s.value}` : undefined;
  };

  return (
    <div className="card lg:col-span-2">
      <div className="card-header">
        <h3 className="card-title flex items-center gap-2">
          <Building2 className="w-5 h-5 text-minga-600 dark:text-minga-400" />
          Firmendaten
        </h3>
        <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
          Gespeichert für alle Benutzer dieses Arbeitsbereichs. Verwendet für Grußformel und Betreff
          der Beleg-Mails und für Belege, deren Belegvorlage keinen eigenen Briefkopf bzw. keine
          eigene Fußzeile hat. Steht dort ein eigener Text, druckt der Beleg nur diesen — nichts
          erscheint doppelt. Briefkopf und Fußzeile pflegen Sie unter{' '}
          <Link to="/admin/templates" className="underline">Belegvorlagen</Link>, die
          Gläubiger-ID unter „SEPA-Lastschrift“.
        </p>
      </div>
      <div className="card-body space-y-4">
        {vorschlag.length > 0 && (
          <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800 dark:border-amber-800 dark:bg-amber-900/20 dark:text-amber-300">
            <p>
              Diese Angaben waren bisher nur in diesem Browser gespeichert, noch nicht auf dem
              Server: {vorschlag.map((k) => FELDER.find((f) => f.key === k)?.label).join(', ')}.
              Bitte prüfen und mit „Speichern“ übernehmen.
            </p>
            <button type="button" className="mt-2 underline" onClick={verwerfen}>
              Vorschlag verwerfen
            </button>
          </div>
        )}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {FELDER.map((f) => (
            <Input
              key={f.key}
              label={f.label}
              type={f.key === 'COMPANY_EMAIL' ? 'email' : 'text'}
              value={werte[f.key]}
              hint={umgebung(f.key)}
              onChange={(e) => setWerte({ ...werte, [f.key]: e.target.value })}
            />
          ))}
        </div>
        <div className="flex justify-end">
          <Button
            icon={<Save className="w-4 h-4" />}
            loading={speichern.isPending}
            onClick={() => speichern.mutate(werte)}
          >
            Speichern
          </Button>
        </div>
      </div>
    </div>
  );
}
