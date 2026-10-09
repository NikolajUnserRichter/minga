import { useState } from 'react';
import { useQuery, keepPreviousData } from '@tanstack/react-query';
import { AlertCircle, CalendarX, FileText } from 'lucide-react';
import { PageHeader, FilterBar } from '../components/common/Layout';
import { OrderDocumentsModal } from '../components/domain/OrderDocumentsModal';
import {
  Badge, Button, Combobox, EmptyState, Input, OrderStatusBadge, Pagination, Table, useToast,
  type ComboboxOption, type Column,
} from '../components/ui';
import { salesApi } from '../services/api';
import { belegstatusApi } from '../services/belegstatusApi';
import {
  LUECKEN_TEXT, datumKurz, heuteBerlin, lieferscheinZelle, rechnungZelle, versandZelle, vorgabeVon, zahlungZelle,
  type BelegstatusZeile, type Zelle,
} from '../services/belegstatus';
import { getErrorMessage } from '../services/errors';
import { Order } from '../types';

/**
 * Belegstatus (Paket 4, Abschnitt C; Gernot 08.10.2026, B2): je Bestellung
 * Lieferschein erstellt, Rechnung erstellt, Rechnung versendet, bezahlt.
 * Filter Zeitraum (Liefertag), Kunde und „nur unvollständige“. Rechte wie die
 * Rechnungen (Admin, Vertrieb, Buchhaltung); die Halle sieht die Seite nicht.
 */

const SEITE = 50;
const ZEITRAUM_FALSCH = '„von“ liegt nach „bis“';

const TON_KLASSE: Record<Zelle['ton'], string> = {
  ok: 'text-emerald-700 dark:text-emerald-300',
  luecke: 'text-red-700 dark:text-red-300 font-medium',
  neutral: 'text-gray-500 dark:text-gray-400',
};

function ZellenText({ zelle }: { zelle: Zelle }) {
  return (
    <span className={`whitespace-nowrap ${TON_KLASSE[zelle.ton]}`}>
      <span aria-hidden="true">{zelle.zeichen}</span>
      {zelle.text && <span className="ml-1">{zelle.text}</span>}
    </span>
  );
}

export default function Belegstatus() {
  const toast = useToast();
  const [von, setVon] = useState(() => vorgabeVon(heuteBerlin()));
  const [bis, setBis] = useState('');
  const [kundeId, setKundeId] = useState('');
  const [nurUnvollstaendig, setNurUnvollstaendig] = useState(false);
  const [seite, setSeite] = useState(1);
  const [belegeOrder, setBelegeOrder] = useState<Order | null>(null);
  const [oeffnet, setOeffnet] = useState<string | null>(null);

  // min/max sperren nur den Kalender, per Tastatur geht „von“ nach „bis“: Dann
  // fragt die Seite den Server nicht (er antwortete 422), die Filter bleiben bedienbar
  const zeitraumFalsch = von !== '' && bis !== '' && von > bis;
  const filter = { von, bis, kunde_id: kundeId, nur_unvollstaendig: nurUnvollstaendig, page: seite, page_size: SEITE };
  const statusQuery = useQuery({
    queryKey: ['belegstatus', filter],
    queryFn: () => belegstatusApi.liste(filter),
    placeholderData: keepPreviousData,
    enabled: !zeitraumFalsch,
  });

  const kundenQuery = useQuery({
    queryKey: ['customers', 'belegstatus'],
    queryFn: () => salesApi.listCustomers({ page_size: 500 }),
  });
  const kundenOptionen: ComboboxOption[] = [
    { value: '', label: 'Alle Kunden' },
    ...(kundenQuery.data?.items ?? [])
      .map((k) => ({ value: k.id, label: k.name }))
      .sort((a, b) => a.label.localeCompare(b.label, 'de')),
  ];

  // Jeder Filterwechsel beginnt wieder auf Seite 1
  const neu = <T,>(setzen: (wert: T) => void) => (wert: T) => { setzen(wert); setSeite(1); };

  const belegeOeffnen = async (z: BelegstatusZeile) => {
    setOeffnet(z.order_id);
    try {
      setBelegeOrder(await salesApi.getOrder(z.order_id));
    } catch (e) {
      toast.error(getErrorMessage(e, 'Bestellung konnte nicht geladen werden'));
    } finally {
      setOeffnet(null);
    }
  };
  const belegeSchliessen = () => {
    setBelegeOrder(null);
    if (!zeitraumFalsch) void statusQuery.refetch(); // Rechnung angelegt oder versendet: Zeile neu
  };

  // Fehler stehen in der Karte unter den Filtern, nie statt der Filter
  const fehlerStatus = (statusQuery.error as { response?: { status?: number } } | null)?.response?.status;
  const keineBerechtigung = fehlerStatus === 403;
  const fehlerText = keineBerechtigung
    ? 'Den Belegstatus sehen Admin, Vertrieb und Buchhaltung.'
    : fehlerStatus
      ? getErrorMessage(statusQuery.error, `Der Server antwortet mit Fehler ${fehlerStatus}.`)
      : 'Bitte prüfe die Verbindung zum Server und versuche es erneut.';
  // Bei ungültigem Zeitraum keine Zahlen der vorigen Abfrage (keepPreviousData)
  const daten = zeitraumFalsch ? undefined : statusQuery.data;
  const spalten: Column<BelegstatusZeile>[] = [
    {
      key: 'order_number',
      header: 'Bestellung',
      render: (z) => (
        <div className="space-y-1">
          <div className="font-medium text-gray-900 dark:text-white">{z.order_number}</div>
          <OrderStatusBadge status={z.order_status} />
        </div>
      ),
    },
    {
      key: 'customer_name',
      header: 'Kunde',
      render: (z) => (
        <div>
          <div>{z.customer_name}</div>
          {z.abrechnung === 'MONATLICH' && <div className="text-xs text-gray-500">Monatsrechnung</div>}
        </div>
      ),
    },
    { key: 'liefertag', header: 'Liefertag', render: (z) => datumKurz(z.liefertag) },
    { key: 'lieferschein', header: 'Lieferschein', render: (z) => <ZellenText zelle={lieferscheinZelle(z)} /> },
    { key: 'rechnung', header: 'Rechnung', render: (z) => <ZellenText zelle={rechnungZelle(z)} /> },
    { key: 'versand', header: 'Versendet', render: (z) => <ZellenText zelle={versandZelle(z)} /> },
    { key: 'zahlung', header: 'Bezahlt', render: (z) => <ZellenText zelle={zahlungZelle(z)} /> },
    {
      key: 'luecken',
      header: 'Lücke',
      render: (z) => (
        <div className="flex flex-wrap gap-1">
          {z.luecken.map((l) => <Badge key={l} variant="danger" size="sm">{LUECKEN_TEXT[l]}</Badge>)}
        </div>
      ),
    },
    {
      key: 'aktion',
      header: '',
      align: 'right',
      render: (z) => (
        <Button size="sm" variant="secondary" icon={<FileText className="w-4 h-4" />}
          loading={oeffnet === z.order_id} onClick={() => void belegeOeffnen(z)}>
          Belege
        </Button>
      ),
    },
  ];

  return (
    <div className="space-y-6">
      <PageHeader
        title="Belegstatus"
        subtitle="Je Bestellung: Lieferschein, Rechnung, Versand und Zahlung"
      />

      <FilterBar>
        <Input type="date" label="Liefertag von" value={von} max={bis || undefined}
          onChange={(e) => neu(setVon)(e.target.value)} />
        <Input type="date" label="bis" value={bis} min={von || undefined}
          error={zeitraumFalsch ? ZEITRAUM_FALSCH : undefined}
          onChange={(e) => neu(setBis)(e.target.value)} />
        <Combobox label="Kunde" options={kundenOptionen} value={kundeId} onChange={neu(setKundeId)}
          placeholder="Alle Kunden" />
        <label className="flex items-center gap-2 text-sm text-gray-700 dark:text-gray-300 self-end pb-2">
          <input type="checkbox" checked={nurUnvollstaendig}
            onChange={(e) => neu(setNurUnvollstaendig)(e.target.checked)} />
          Nur unvollständige{daten ? ` (${daten.unvollstaendig})` : ''}
        </label>
      </FilterBar>

      <p className="text-sm text-gray-500 dark:text-gray-400">
        Unvollständig: geliefert, aber ohne Rechnung, nur mit Rechnungsentwurf oder Rechnung nicht versendet —
        bei Monatskunden ab dem 1. des Folgemonats. „extern (DATEV)“: vor NovaERP abgerechnet (Status Fakturiert).
        Stornierte Bestellungen fehlen.
      </p>

      <div className="card overflow-hidden">
        {zeitraumFalsch ? (
          <EmptyState
            icon={<CalendarX className="w-16 h-16" />}
            title="Zeitraum ungültig"
            description="„Liefertag von“ liegt nach „bis“ — bitte eines der beiden Daten ändern."
          />
        ) : statusQuery.isError ? (
          <EmptyState
            icon={<AlertCircle className="w-16 h-16 text-red-400" />}
            title={keineBerechtigung ? 'Keine Berechtigung für den Belegstatus' : 'Belegstatus konnte nicht geladen werden'}
            description={fehlerText}
            action={keineBerechtigung ? undefined : (
              <Button variant="secondary" loading={statusQuery.isFetching} onClick={() => void statusQuery.refetch()}>
                Erneut versuchen
              </Button>
            )}
          />
        ) : (
          <>
            <Table
              columns={spalten}
              data={daten?.items ?? []}
              keyExtractor={(z) => z.order_id}
              loading={statusQuery.isLoading}
              emptyMessage={nurUnvollstaendig ? 'Keine unvollständigen Bestellungen im Zeitraum' : 'Keine Bestellungen im Zeitraum'}
            />
            {daten && daten.total > SEITE && (
              <Pagination
                currentPage={seite}
                totalPages={Math.ceil(daten.total / SEITE)}
                totalItems={daten.total}
                itemsPerPage={SEITE}
                onPageChange={setSeite}
              />
            )}
          </>
        )}
      </div>

      <OrderDocumentsModal open={!!belegeOrder} onClose={belegeSchliessen} order={belegeOrder} />
    </div>
  );
}
