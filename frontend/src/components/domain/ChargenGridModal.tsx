import { useRef, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Copy, FileDown, Plus, Sparkles, Trash2, Upload } from 'lucide-react';
import api, { chargenImportApi, ChargenGridZeile, ImportReport, seedsApi } from '../../services/api';
import { getErrorMessage } from '../../services/errors';
import { Badge, Button, Input, Modal, useToast } from '../ui';

/**
 * Chargen-Grid (R4.2): Massenanlage und Historien-Import von Wachstumschargen.
 *
 * Drei Wege in dieselbe Prüfung und dieselbe Transaktion:
 * - Zeilen von Hand (hinzufügen/duplizieren, Sorten-Autocomplete)
 * - Einfügen aus Excel (Copy-Paste, Tab-getrennt in Spaltenreihenfolge)
 * - Datei-Upload (XLSX-Vorlage) — der Weg für die 2026-Historie
 *
 * Vor jedem Import steht der Zeilenreport (OK/WARNUNG/FEHLER je Zeile);
 * erst „Importieren" schreibt. Ein Lauf ist rückrollbar, solange keine
 * Folgebelege an den Chargen hängen.
 */

interface Props {
  open: boolean;
  onClose: () => void;
  onImported?: () => void;
}

const LEERE_ZEILE: ChargenGridZeile = {
  sorte: '', aussaat_datum: '', tray_anzahl: '', saatgut_gramm: '',
  regal_position: '', externe_chargennummer: '', notiz: '',
};

// Spaltenreihenfolge fürs Einfügen aus Excel (Tab-getrennt)
const PASTE_SPALTEN: (keyof ChargenGridZeile)[] = [
  'sorte', 'aussaat_datum', 'tray_anzahl', 'saatgut_gramm',
  'regal_position', 'externe_chargennummer', 'notiz',
];

export function ChargenGridModal({ open, onClose, onImported }: Props) {
  const toast = useToast();
  const queryClient = useQueryClient();
  const fileInput = useRef<HTMLInputElement>(null);

  const [zeilen, setZeilen] = useState<ChargenGridZeile[]>([{ ...LEERE_ZEILE }]);
  const [sammelDatum, setSammelDatum] = useState('');
  const [zielWoche, setZielWoche] = useState(new Date().toISOString().split('T')[0]);
  const [lagerbewegungen, setLagerbewegungen] = useState(true);
  const [report, setReport] = useState<ImportReport | null>(null);
  const [datei, setDatei] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);

  const { data: seeds } = useQuery({ queryKey: ['seeds'], queryFn: () => seedsApi.list() });
  const sortenNamen = (Array.isArray(seeds) ? seeds : (seeds as any)?.items ?? [])
    .map((s: { name: string }) => s.name);

  const setzeZelle = (idx: number, feld: keyof ChargenGridZeile, wert: string) => {
    setZeilen((alt) => alt.map((z, i) => (i === idx ? { ...z, [feld]: wert } : z)));
    setReport(null); // alte Prüfung gilt nach jeder Änderung nicht mehr
  };

  const zeileHinzu = (vorlage?: ChargenGridZeile) =>
    setZeilen((alt) => [...alt, { ...(vorlage ?? LEERE_ZEILE) }]);

  const zeileWeg = (idx: number) =>
    setZeilen((alt) => (alt.length > 1 ? alt.filter((_, i) => i !== idx) : alt));

  /** Einfügen aus Excel: jede Zeile Tab-getrennt in PASTE_SPALTEN-Reihenfolge. */
  const handlePaste = (e: React.ClipboardEvent) => {
    const text = e.clipboardData.getData('text');
    if (!text.includes('\t') && !text.includes('\n')) return; // normale Einzelzelle
    e.preventDefault();
    const neue = text.split(/\r?\n/).filter((l) => l.trim()).map((line) => {
      const felder = line.split('\t');
      const zeile: ChargenGridZeile = { ...LEERE_ZEILE };
      PASTE_SPALTEN.forEach((sp, i) => {
        if (felder[i] !== undefined) (zeile as any)[sp] = felder[i].trim();
      });
      return zeile;
    });
    if (neue.length) {
      setZeilen((alt) => {
        const gefuellt = alt.filter((z) => z.sorte || z.aussaat_datum);
        return [...gefuellt, ...neue];
      });
      setReport(null);
      toast.success(`${neue.length} Zeilen eingefügt`);
    }
  };

  const sammeldatumAnwenden = () => {
    if (!sammelDatum) return;
    setZeilen((alt) => alt.map((z) => ({ ...z, aussaat_datum: sammelDatum })));
    setReport(null);
  };

  const vorschlaegeLaden = async () => {
    try {
      const rows = await chargenImportApi.suggestions(zielWoche);
      if (!rows.length) {
        toast.error('Keine offenen Produktionsvorschläge in dieser Woche');
        return;
      }
      setZeilen(rows.map((r) => ({
        ...LEERE_ZEILE,
        sorte: r.sorte,
        aussaat_datum: r.aussaat_datum,
        tray_anzahl: r.tray_anzahl,
        saatgut_gramm: r.saatgut_gramm ?? '',
      })));
      setReport(null);
      toast.success(`${rows.length} Vorschläge geladen — bitte prüfen und bestätigen`);
    } catch (e) {
      toast.error(getErrorMessage(e, 'Vorschläge konnten nicht geladen werden'));
    }
  };

  const gridZeilen = () =>
    zeilen
      .filter((z) => z.sorte.trim())
      .map((z) => ({
        sorte: z.sorte,
        aussaat_datum: z.aussaat_datum || null,
        tray_anzahl: z.tray_anzahl === '' ? null : Number(z.tray_anzahl),
        saatgut_gramm: z.saatgut_gramm === '' ? null : Number(z.saatgut_gramm),
        regal_position: z.regal_position || null,
        externe_chargennummer: z.externe_chargennummer || null,
        notiz: z.notiz || null,
      }));

  const pruefen = async () => {
    setBusy(true);
    try {
      const r = datei
        ? await chargenImportApi.validate(datei)
        : await chargenImportApi.validateRows(gridZeilen());
      setReport(r);
    } catch (e) {
      toast.error(getErrorMessage(e, 'Prüfung fehlgeschlagen'));
    } finally {
      setBusy(false);
    }
  };

  const importieren = async () => {
    setBusy(true);
    try {
      const ergebnis = datei
        ? await chargenImportApi.commit(datei, lagerbewegungen)
        : await chargenImportApi.commitRows(gridZeilen(), lagerbewegungen);
      toast.success(
        `${ergebnis.created} Chargen angelegt · ${ergebnis.skipped} übersprungen`
        + (lagerbewegungen ? ` · ${ergebnis.movements} Lagerbewegungen` : '')
      );
      queryClient.invalidateQueries({ queryKey: ['growBatches'] });
      setZeilen([{ ...LEERE_ZEILE }]);
      setDatei(null);
      setReport(null);
      onImported?.();
      onClose();
    } catch (e) {
      toast.error(getErrorMessage(e, 'Import fehlgeschlagen'));
    } finally {
      setBusy(false);
    }
  };

  const templateLaden = async () => {
    try {
      const res = await api.get<Blob>('/imports/template/grow_batches', { responseType: 'blob' });
      const url = URL.createObjectURL(res.data);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'template_chargen.xlsx';
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch {
      toast.error('Vorlage konnte nicht geladen werden');
    }
  };

  const fehlerImReport = (report?.zusammenfassung.fehler ?? 0) > 0;

  return (
    <Modal open={open} onClose={onClose} title="Chargen anlegen / importieren">
      <div className="space-y-4" onPaste={handlePaste}>
        {/* Quelle: Datei ODER Grid */}
        <div className="flex flex-wrap items-center gap-2">
          <button className="btn btn-secondary btn-sm" onClick={templateLaden}>
            <FileDown className="w-4 h-4" /> Vorlage
          </button>
          <button className="btn btn-secondary btn-sm" onClick={() => fileInput.current?.click()}>
            <Upload className="w-4 h-4" /> {datei ? datei.name : 'Datei wählen'}
          </button>
          <input ref={fileInput} type="file" accept=".xlsx,.xlsm" className="hidden"
                 onChange={(e) => { setDatei(e.target.files?.[0] ?? null); setReport(null); }} />
          {datei && (
            <button className="btn btn-ghost btn-sm" onClick={() => { setDatei(null); setReport(null); }}>
              Datei verwerfen
            </button>
          )}
          <div className="flex-1" />
          <button className="btn btn-secondary btn-sm" onClick={vorschlaegeLaden} disabled={!!datei}>
            <Sparkles className="w-4 h-4" /> Vorschläge
          </button>
          <input type="date" className="input w-36" value={zielWoche}
                 onChange={(e) => setZielWoche(e.target.value)} title="Zielwoche für Vorschläge" />
        </div>

        {/* Grid — nur relevant, wenn keine Datei gewählt ist */}
        {!datei && (
          <>
            <div className="overflow-x-auto border border-gray-200 dark:border-gray-700 rounded-lg">
              <table className="table text-sm">
                <thead>
                  <tr>
                    <th className="min-w-40">Sorte</th>
                    <th>Aussaat</th>
                    <th>Kisten</th>
                    <th>Saatgut (g)</th>
                    <th>Regal</th>
                    <th>Ext. Charge</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {zeilen.map((z, i) => (
                    <tr key={i}>
                      <td>
                        <input list="sorten-liste" className="input input-sm w-full" value={z.sorte}
                               placeholder="Sorte"
                               onChange={(e) => setzeZelle(i, 'sorte', e.target.value)} />
                      </td>
                      <td>
                        <input type="date" className="input input-sm" value={z.aussaat_datum}
                               onChange={(e) => setzeZelle(i, 'aussaat_datum', e.target.value)} />
                      </td>
                      <td>
                        <input type="number" min="1" className="input input-sm w-20" value={z.tray_anzahl}
                               onChange={(e) => setzeZelle(i, 'tray_anzahl', e.target.value)} />
                      </td>
                      <td>
                        <input type="number" min="0" className="input input-sm w-24" value={z.saatgut_gramm}
                               onChange={(e) => setzeZelle(i, 'saatgut_gramm', e.target.value)} />
                      </td>
                      <td>
                        <input className="input input-sm w-20" value={z.regal_position}
                               onChange={(e) => setzeZelle(i, 'regal_position', e.target.value)} />
                      </td>
                      <td>
                        <input className="input input-sm w-24" value={z.externe_chargennummer}
                               onChange={(e) => setzeZelle(i, 'externe_chargennummer', e.target.value)} />
                      </td>
                      <td className="whitespace-nowrap">
                        <button className="p-1 text-gray-400 hover:text-minga-600" title="Zeile duplizieren"
                                onClick={() => zeileHinzu(z)}>
                          <Copy className="w-4 h-4" />
                        </button>
                        <button className="p-1 text-gray-400 hover:text-red-600" title="Zeile entfernen"
                                onClick={() => zeileWeg(i)}>
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <datalist id="sorten-liste">
                {sortenNamen.map((n: string) => <option key={n} value={n} />)}
              </datalist>
            </div>

            <div className="flex flex-wrap items-end gap-2">
              <Button variant="secondary" size="sm" icon={<Plus className="w-4 h-4" />}
                      onClick={() => zeileHinzu()}>
                Zeile
              </Button>
              <div className="w-40">
                <Input label="Datum für alle" type="date" value={sammelDatum}
                       onChange={(e) => setSammelDatum(e.target.value)} />
              </div>
              <Button variant="secondary" size="sm" onClick={sammeldatumAnwenden} disabled={!sammelDatum}>
                Übernehmen
              </Button>
              <p className="text-xs text-gray-500 dark:text-gray-400 ml-auto">
                Tipp: Zeilen aus Excel kopieren und hier einfügen
                (Sorte · Datum · Kisten · Saatgut g · Regal · Ext. Charge · Notiz)
              </p>
            </div>
          </>
        )}

        {/* Zeilenreport der Prüfung */}
        {report && (
          <div className="border border-gray-200 dark:border-gray-700 rounded-lg p-3 space-y-2 max-h-48 overflow-y-auto">
            <div className="flex gap-2 text-sm">
              <Badge variant="success">{report.zusammenfassung.ok} OK</Badge>
              {report.zusammenfassung.warnung > 0 && (
                <Badge variant="warning">{report.zusammenfassung.warnung} Warnungen</Badge>
              )}
              {report.zusammenfassung.fehler > 0 && (
                <Badge variant="danger">{report.zusammenfassung.fehler} Fehler</Badge>
              )}
            </div>
            {report.zeilen.filter((z) => z.status !== 'OK').map((z) => (
              <p key={z.zeile} className="text-sm">
                <span className={z.status === 'FEHLER' ? 'text-red-600' : 'text-amber-600'}>
                  Zeile {z.zeile}:
                </span>{' '}
                {z.meldung}
              </p>
            ))}
            {report.fehlende_sorten.length > 0 && (
              <p className="text-sm text-red-600">
                Fehlende Sorten: {report.fehlende_sorten.join(', ')} — bitte zuerst unter Saatgut anlegen.
              </p>
            )}
          </div>
        )}

        <label className="flex items-center gap-2 text-sm cursor-pointer">
          <input type="checkbox" className="rounded border-gray-300 text-minga-600"
                 checked={lagerbewegungen} onChange={(e) => setLagerbewegungen(e.target.checked)} />
          Lagerbewegungen mitbuchen (Saatgut/Substrat/Ernte mit historischem Datum —
          damit stimmt der Warenfluss rückwirkend)
        </label>

        <div className="flex justify-end gap-2">
          <button className="btn btn-secondary" onClick={onClose}>Abbrechen</button>
          <Button variant="secondary" onClick={pruefen} loading={busy}>Prüfen</Button>
          <Button onClick={importieren} loading={busy}
                  disabled={!report || fehlerImReport}
                  title={!report ? 'Erst prüfen' : fehlerImReport ? 'Fehlerzeilen zuerst beheben' : ''}>
            Importieren
          </Button>
        </div>
      </div>
    </Modal>
  );
}
