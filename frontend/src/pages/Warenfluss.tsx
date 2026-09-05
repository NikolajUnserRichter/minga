import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { FileDown, FileText } from 'lucide-react';
import { reportsApi, WarenflussZeile } from '../services/api';
import { PageHeader } from '../components/common/Layout';
import { Badge, EmptyState, Modal, PageLoader, Select, Input, useToast } from '../components/ui';

/**
 * Warenfluss-Auswertung (Zertifizierungsnachweis): je Sorte/Artikel
 * Anfangsbestand → Zugang → Verbrauch → Sollbestand Ende, mit Drilldown
 * auf die Einzelbewegungen und Export als CSV/PDF.
 */

const MATERIALARTEN = [
  { value: 'SAATGUT', label: 'Saatgut' },
  { value: 'SUBSTRAT', label: 'Substrate' },
  { value: 'VERPACKUNG', label: 'Verpackungen' },
  { value: 'FERTIGWARE', label: 'Fertige Erzeugnisse' },
];

const BEWEGUNGS_LABEL: Record<string, string> = {
  EINGANG: 'Wareneingang', PRODUKTION: 'Verbrauch (Aussaat)', ERNTE: 'Ernte',
  VERLUST: 'Ausschuss/Verlust', KORREKTUR: 'Inventurkorrektur',
  AUSGANG: 'Verkauf/Lieferung', RUECKGABE: 'Retoure', UMLAGERUNG: 'Umlagerung',
};

function heute(): string { return new Date().toISOString().split('T')[0]; }
function jahresanfang(): string { return `${new Date().getFullYear()}-01-01`; }

export default function Warenfluss() {
  const toast = useToast();
  const [materialType, setMaterialType] = useState('SAATGUT');
  const [von, setVon] = useState(jahresanfang());
  const [bis, setBis] = useState(heute());
  const [drilldown, setDrilldown] = useState<string | null>(null);

  const { data: report, isLoading } = useQuery({
    queryKey: ['material-flow', materialType, von, bis],
    queryFn: () => reportsApi.materialFlow({ material_type: materialType, von, bis }),
  });

  const { data: details } = useQuery({
    queryKey: ['material-flow-details', materialType, von, bis, drilldown],
    queryFn: () => reportsApi.materialFlowDetails({
      material_type: materialType, von, bis, schluessel: drilldown || undefined,
    }),
    enabled: !!drilldown,
  });

  const schnellwahl = (art: 'monat' | 'quartal' | 'jahr') => {
    const jetzt = new Date();
    if (art === 'monat') {
      setVon(new Date(jetzt.getFullYear(), jetzt.getMonth(), 1).toISOString().split('T')[0]);
    } else if (art === 'quartal') {
      const q = Math.floor(jetzt.getMonth() / 3) * 3;
      setVon(new Date(jetzt.getFullYear(), q, 1).toISOString().split('T')[0]);
    } else {
      setVon(jahresanfang());
    }
    setBis(heute());
  };

  const einheit = materialType === 'SAATGUT' ? 'g' : 'Stk';
  const zahl = (v: number) => Number(v).toLocaleString('de-DE');

  return (
    <div className="space-y-6">
      <PageHeader
        title="Warenfluss"
        subtitle="Lückenloser Materialfluss je Sorte — der Nachweis für Audit und Zertifizierung"
        actions={
          <div className="flex gap-2">
            <button className="btn btn-secondary btn-sm"
              onClick={() => reportsApi.exportMaterialFlow({ material_type: materialType, format: 'csv', von, bis })
                .catch(() => toast.error('Export fehlgeschlagen'))}>
              <FileDown className="w-4 h-4" /> CSV
            </button>
            <button className="btn btn-secondary btn-sm"
              onClick={() => reportsApi.exportMaterialFlow({ material_type: materialType, format: 'pdf', von, bis })
                .catch(() => toast.error('Export fehlgeschlagen'))}>
              <FileText className="w-4 h-4" /> PDF-Nachweis
            </button>
          </div>
        }
      />

      <div className="card">
        <div className="card-body flex flex-wrap items-end gap-3">
          <div className="w-48">
            <Select label="Material" value={materialType}
              onChange={(e) => setMaterialType(e.target.value)} options={MATERIALARTEN} />
          </div>
          <div className="w-40">
            <Input label="Von" type="date" value={von} onChange={(e) => setVon(e.target.value)} />
          </div>
          <div className="w-40">
            <Input label="Bis" type="date" value={bis} onChange={(e) => setBis(e.target.value)} />
          </div>
          <div className="flex gap-1 pb-1">
            <button className="btn btn-ghost btn-sm" onClick={() => schnellwahl('monat')}>Monat</button>
            <button className="btn btn-ghost btn-sm" onClick={() => schnellwahl('quartal')}>Quartal</button>
            <button className="btn btn-ghost btn-sm" onClick={() => schnellwahl('jahr')}>Jahr</button>
          </div>
        </div>
      </div>

      {isLoading ? <PageLoader /> : (
        <div className="card overflow-x-auto">
          {(report?.zeilen ?? []).length === 0 ? (
            <EmptyState
              title="Keine Bewegungen im Zeitraum"
              description="Wareneingänge, Aussaaten und importierte Historie erscheinen hier automatisch."
            />
          ) : (
            <table className="table">
              <thead>
                <tr>
                  <th>Sorte/Artikel</th>
                  <th className="text-right">Anfangsbestand</th>
                  <th className="text-right">Zugang</th>
                  <th className="text-right">Verbrauch</th>
                  <th className="text-right">Ausschuss/Sonst.</th>
                  <th className="text-right">Korrektur</th>
                  <th className="text-right">Sollbestand Ende</th>
                </tr>
              </thead>
              <tbody>
                {report!.zeilen.map((z: WarenflussZeile) => (
                  <tr key={z.schluessel} className="cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-700/50"
                      onClick={() => setDrilldown(z.schluessel)}>
                    <td className="font-medium">{z.schluessel}</td>
                    <td className="text-right">{zahl(z.anfangsbestand)} {einheit}</td>
                    <td className="text-right text-green-700 dark:text-green-400">{zahl(z.zugang)} {einheit}</td>
                    <td className="text-right text-amber-700 dark:text-amber-400">{zahl(z.verbrauch)} {einheit}</td>
                    <td className="text-right">{zahl(z.sonstiges)} {einheit}</td>
                    <td className="text-right">{zahl(z.korrektur)} {einheit}</td>
                    <td className="text-right font-semibold">{zahl(z.endbestand)} {einheit}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {/* Drilldown: die Einzelbewegungen hinter der Zeile */}
      <Modal open={!!drilldown} onClose={() => setDrilldown(null)}
             title={`Bewegungen: ${drilldown ?? ''}`}>
        <div className="space-y-2 max-h-96 overflow-y-auto">
          {(details ?? []).map((d, i) => (
            <div key={i} className="flex items-center justify-between p-2 rounded bg-gray-50 dark:bg-gray-700/40 text-sm">
              <div>
                <span className="font-medium">{BEWEGUNGS_LABEL[d.movement_type] || d.movement_type}</span>
                <span className="text-gray-500 dark:text-gray-400"> · {new Date(d.datum).toLocaleDateString('de-DE')}</span>
                {d.grund && <p className="text-gray-500 dark:text-gray-400">{d.grund}</p>}
              </div>
              <div className="flex items-center gap-2">
                {d.aus_import && <Badge variant="info" size="sm">Import</Badge>}
                <span className={Number(d.menge) < 0 ? 'text-amber-700 dark:text-amber-400' : 'text-green-700 dark:text-green-400'}>
                  {zahl(d.menge)} {d.einheit}
                </span>
              </div>
            </div>
          ))}
          {(details ?? []).length === 0 && (
            <p className="text-sm text-gray-500 dark:text-gray-400 italic">Keine Bewegungen im Zeitraum.</p>
          )}
        </div>
      </Modal>
    </div>
  );
}
