import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { sepaApi, SepaMandatEingabe, Mandatsart } from '../../services/api';
import { getErrorMessage } from '../../services/errors';
import { Badge, Button, Input, Select, SelectOption, useToast } from '../ui';
import type { Zahlungsart } from '../../types';

/**
 * Zahlung / SEPA-Lastschriftmandat (B10) im Kundenformular.
 *
 * Nur für Admin und Buchhaltung eingeblendet (das Backend erzwingt es über
 * /api/v1/sepa ohnehin). Speichert NIE über salesApi.updateCustomer: das
 * Kundenformular schickt sein ganzes formData an PATCH /sales/customers,
 * den auch die Halle erreicht. Steht innerhalb des Kunden-<form> — deshalb
 * nur type="button", kein eigenes <form>.
 */
const zahlungsartOptions: SelectOption[] = [
  { value: 'UEBERWEISUNG', label: 'Überweisung' },
  { value: 'LASTSCHRIFT', label: 'SEPA-Lastschrift (Mandat)' },
];

const mandatsartOptions: SelectOption[] = [
  { value: 'CORE', label: 'Basislastschrift (CORE)' },
  { value: 'B2B', label: 'Firmenlastschrift (B2B)' },
];

export function SepaMandatKarte({ customerId, customerName, isAdmin }: {
  customerId: string;
  customerName: string;
  isAdmin: boolean;
}) {
  const toast = useToast();
  const queryClient = useQueryClient();
  const leer: SepaMandatEingabe = {
    mandatsreferenz: '', mandatsart: 'CORE', unterschrieben_am: '',
    kontoinhaber: customerName, iban: '', bic: '', bank_name: '',
  };
  const [neu, setNeu] = useState<SepaMandatEingabe>(leer);

  const { data, isLoading } = useQuery({
    queryKey: ['sepa-mandate', customerId],
    queryFn: () => sepaApi.mandate(customerId),
  });
  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ['sepa-mandate', customerId] });
    queryClient.invalidateQueries({ queryKey: ['customers'] });
  };

  const anlegen = useMutation({
    mutationFn: () => sepaApi.mandatAnlegen(customerId, {
      ...neu, bic: neu.bic || null, bank_name: neu.bank_name || null,
    }),
    onSuccess: () => { invalidate(); setNeu(leer); toast.success('Mandat angelegt'); },
    onError: (e) => toast.error(getErrorMessage(e, 'Mandat konnte nicht angelegt werden')),
  });
  const widerrufen = useMutation({
    mutationFn: (mandatId: string) => sepaApi.mandatWiderrufen(mandatId),
    onSuccess: (r) => {
      invalidate();
      toast.success('Mandat widerrufen — Zahlungsart jetzt Überweisung');
      if (r.offene_lastschriften.length > 0) {
        toast.error(`Offene Lastschriftrechnungen: ${r.offene_lastschriften.join(', ')} — nicht mehr einziehen, für Überweisung stornieren und neu ausstellen`);
      }
    },
    onError: (e) => toast.error(getErrorMessage(e, 'Widerruf fehlgeschlagen')),
  });
  const zahlungsart = useMutation({
    mutationFn: (wert: Zahlungsart) => sepaApi.setZahlungsart(customerId, wert),
    onSuccess: () => { invalidate(); toast.success('Zahlungsart gespeichert'); },
    onError: (e) => toast.error(getErrorMessage(e, 'Zahlungsart nicht gespeichert')),
  });

  if (isLoading || !data) {
    return <div className="text-sm text-gray-500">Lädt Zahlungsdaten …</div>;
  }
  const aktiv = data.mandate.find((m) => m.aktiv);
  const frueher = data.mandate.filter((m) => !m.aktiv);

  return (
    <fieldset className="border border-gray-200 dark:border-gray-700 rounded-lg p-4 space-y-3">
      <legend className="px-2 text-sm font-medium text-gray-700 dark:text-gray-300">
        Zahlung / SEPA-Lastschriftmandat
      </legend>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        <Select
          label="Zahlungsart"
          options={zahlungsartOptions}
          value={data.zahlungsart || 'UEBERWEISUNG'}
          onChange={(e) => zahlungsart.mutate(e.target.value as Zahlungsart)}
        />
        <div className="text-sm">
          <div className="text-gray-500 dark:text-gray-400">Gläubiger-ID (Firmendaten)</div>
          <div className="font-mono">{data.glaeubiger_id || '— nicht hinterlegt'}</div>
          {!data.glaeubiger_id && (
            <div className="text-xs text-gray-500">
              {isAdmin ? 'Unter Einstellungen → SEPA-Lastschrift eintragen.' : 'Bitte den Admin, sie in den Einstellungen einzutragen.'}
            </div>
          )}
        </div>
      </div>

      {aktiv ? (
        <div className="text-sm bg-gray-50 dark:bg-gray-700/50 rounded px-3 py-2 space-y-1">
          <div className="flex items-center gap-2">
            <Badge variant="success">Aktiv</Badge>
            <span className="font-medium">{aktiv.mandatsreferenz}</span>
            <span className="text-gray-500">· {aktiv.mandatsart === 'B2B' ? 'Firmenlastschrift' : 'Basislastschrift'}</span>
            <span className="text-gray-500">· unterschrieben {new Date(aktiv.unterschrieben_am).toLocaleDateString('de-DE')}</span>
          </div>
          <div>{aktiv.kontoinhaber} · <span className="font-mono">{aktiv.iban}</span>{aktiv.bic ? ` · ${aktiv.bic}` : ''}{aktiv.bank_name ? ` · ${aktiv.bank_name}` : ''}</div>
          {aktiv.letzter_einzug_am && (
            <div className="text-xs text-gray-500">Letzter Einzug: {new Date(aktiv.letzter_einzug_am).toLocaleDateString('de-DE')}</div>
          )}
          <Button
            type="button" size="sm" variant="ghost" className="text-red-600 dark:text-red-400"
            loading={widerrufen.isPending}
            onClick={() => { if (confirm('Mandat widerrufen? Der Kunde zahlt danach per Überweisung.')) widerrufen.mutate(aktiv.id); }}
          >
            Widerrufen
          </Button>
        </div>
      ) : (
        <div className="space-y-2">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
            <Input label="Mandatsreferenz" value={neu.mandatsreferenz}
              onChange={(e) => setNeu({ ...neu, mandatsreferenz: e.target.value })} />
            <Select label="Mandatsart" options={mandatsartOptions} value={neu.mandatsart}
              onChange={(e) => setNeu({ ...neu, mandatsart: e.target.value as Mandatsart })} />
            <Input label="Datum des Mandats" type="date" value={neu.unterschrieben_am}
              onChange={(e) => setNeu({ ...neu, unterschrieben_am: e.target.value })} />
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
            <Input label="Kontoinhaber" value={neu.kontoinhaber}
              onChange={(e) => setNeu({ ...neu, kontoinhaber: e.target.value })} />
            <Input label="IBAN" value={neu.iban} placeholder="DE.. .... .... .... .... .."
              onChange={(e) => setNeu({ ...neu, iban: e.target.value })} />
            <Input label="BIC (optional)" value={neu.bic || ''}
              onChange={(e) => setNeu({ ...neu, bic: e.target.value })} />
            <Input label="Bank" value={neu.bank_name || ''}
              onChange={(e) => setNeu({ ...neu, bank_name: e.target.value })} />
          </div>
          <div className="flex justify-end">
            <Button
              type="button" size="sm" variant="secondary" loading={anlegen.isPending}
              disabled={!neu.mandatsreferenz || !neu.unterschrieben_am || !neu.kontoinhaber || !neu.iban}
              onClick={() => anlegen.mutate()}
            >
              Mandat anlegen
            </Button>
          </div>
        </div>
      )}

      {frueher.length > 0 && (
        <details className="text-xs text-gray-500">
          <summary>Frühere Mandate ({frueher.length})</summary>
          {frueher.map((m) => (
            <div key={m.id}>
              {m.mandatsreferenz} · {m.iban_maskiert} · widerrufen {m.widerrufen_am ? new Date(m.widerrufen_am).toLocaleDateString('de-DE') : ''}
            </div>
          ))}
        </details>
      )}
    </fieldset>
  );
}
