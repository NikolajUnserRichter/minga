import { useState, useEffect, useMemo, useRef } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api, {
  documentTemplatesApi, type DocumentTemplate, type DocumentTypeKey,
} from '../services/api';

const TYPE_LABELS: Record<DocumentTypeKey, string> = {
  RECHNUNG: 'Rechnung',
  AUFTRAGSBESTAETIGUNG: 'Auftragsbestätigung',
  LIEFERSCHEIN: 'Lieferschein',
  VERPACKUNGSLISTE: 'Verpackungsliste',
  MAHNUNG: 'Mahnung',
};

const TEXT_FIELDS: { key: string; label: string; rows: number }[] = [
  { key: 'header_text', label: 'Briefkopf (überschreibt Firmenname + Adresse)', rows: 4 },
  { key: 'intro_text',  label: 'Anschreiben oberhalb der Tabelle',              rows: 3 },
  { key: 'outro_text',  label: 'Schlusstext unterhalb der Tabelle',             rows: 3 },
  { key: 'footer_text', label: 'Fußzeile (überschreibt Firmen-Footer)',          rows: 4 },
];

export default function DocumentTemplates() {
  const [activeType, setActiveType] = useState<DocumentTypeKey>('RECHNUNG');
  const [draft, setDraft] = useState<DocumentTemplate | null>(null);
  const [previewRefreshKey, setPreviewRefreshKey] = useState(0);
  const qc = useQueryClient();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const { data: templates, isLoading } = useQuery({
    queryKey: ['document-templates'],
    queryFn: documentTemplatesApi.listAll,
  });

  const current = useMemo(
    () => templates?.find(t => t.document_type === activeType),
    [templates, activeType],
  );

  useEffect(() => {
    if (current) setDraft({ ...current });
  }, [current?.id, current?.updated_at]);

  const isDirty = useMemo(() => {
    if (!current || !draft) return false;
    return JSON.stringify({
      texts: draft.texts, sections: draft.sections, columns: draft.columns,
      primary_color: draft.primary_color, accent_color: draft.accent_color,
    }) !== JSON.stringify({
      texts: current.texts, sections: current.sections, columns: current.columns,
      primary_color: current.primary_color, accent_color: current.accent_color,
    });
  }, [draft, current]);

  const saveMutation = useMutation({
    mutationFn: (payload: Partial<DocumentTemplate>) =>
      documentTemplatesApi.update(activeType, {
        texts: payload.texts,
        sections: payload.sections,
        columns: payload.columns,
        primary_color: payload.primary_color,
        accent_color: payload.accent_color,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['document-templates'] });
      setPreviewRefreshKey(k => k + 1);
    },
  });

  const logoMutation = useMutation({
    mutationFn: (file: File) => documentTemplatesApi.uploadLogo(activeType, file),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['document-templates'] });
      setPreviewRefreshKey(k => k + 1);
    },
  });

  const removeLogoMutation = useMutation({
    mutationFn: () => documentTemplatesApi.removeLogo(activeType),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['document-templates'] });
      setPreviewRefreshKey(k => k + 1);
    },
  });

  // PDF via authentifizierten fetch laden → Blob-URL für iframe (Basic-Auth
  // wird sonst nicht auf iframe-Subresource übertragen, würde 401 ergeben).
  const [previewBlobUrl, setPreviewBlobUrl] = useState<string | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewError, setPreviewError] = useState<string | null>(null);
  // Ref auf die aktuell im iframe verwendete URL, damit wir bei Wechsel +
  // Unmount immer die richtige URL revoken (closure-based Variable verliert
  // die Referenz, wenn der Effect-Cleanup vor dem fetch-Resolve läuft).
  const activeUrlRef = useRef<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    // 1. Sofort alte URL freigeben und iframe ausblenden — verhindert,
    //    dass nach Tab-Switch noch das PDF des vorherigen Typs angezeigt wird.
    if (activeUrlRef.current) {
      URL.revokeObjectURL(activeUrlRef.current);
      activeUrlRef.current = null;
    }
    setPreviewBlobUrl(null);
    setPreviewLoading(true);
    setPreviewError(null);
    api.get(`/document-templates/${activeType}/preview.pdf`, { responseType: 'blob' })
      .then(r => {
        if (cancelled) return;
        const url = URL.createObjectURL(r.data);
        activeUrlRef.current = url;
        setPreviewBlobUrl(url);
      })
      .catch(err => { if (!cancelled) setPreviewError(err?.message ?? 'Preview-Fehler'); })
      .finally(() => { if (!cancelled) setPreviewLoading(false); });
    return () => { cancelled = true; };
  }, [activeType, previewRefreshKey]);

  // Bei Unmount letzte URL definitiv freigeben.
  useEffect(() => () => {
    if (activeUrlRef.current) {
      URL.revokeObjectURL(activeUrlRef.current);
      activeUrlRef.current = null;
    }
  }, []);

  if (isLoading || !draft) {
    return <div className="p-6 text-gray-500">Lade Vorlagen…</div>;
  }

  return (
    <div className="p-4 max-w-[1600px] mx-auto">
      <div className="mb-4">
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Belegvorlagen</h1>
        <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
          Pro Belegart eigene Texte, Sektionen, Spalten, Farben, Logo. Live-Vorschau rechts.
        </p>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 border-b border-gray-200 dark:border-gray-700 mb-4 overflow-x-auto">
        {(Object.keys(TYPE_LABELS) as DocumentTypeKey[]).map(t => (
          <button
            key={t}
            onClick={() => setActiveType(t)}
            className={`px-4 py-2 text-sm font-medium whitespace-nowrap border-b-2 transition-colors ${
              activeType === t
                ? 'border-green-600 text-green-700 dark:text-green-400'
                : 'border-transparent text-gray-500 hover:text-gray-900 dark:hover:text-gray-100'
            }`}
          >
            {TYPE_LABELS[t]}
          </button>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* === Editor === */}
        <div className="space-y-4">
          {/* Logo */}
          <Card title="Logo">
            <div className="flex items-center gap-4">
              {draft.logo_url ? (
                <img src={draft.logo_url} alt="Logo" className="h-20 w-20 object-contain bg-white border rounded" />
              ) : (
                <div className="h-20 w-20 bg-gray-100 dark:bg-gray-700 border rounded flex items-center justify-center text-xs text-gray-400">
                  kein Logo
                </div>
              )}
              <div className="flex flex-col gap-2">
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="image/png,image/jpeg"
                  className="hidden"
                  onChange={e => {
                    const f = e.target.files?.[0];
                    if (f) logoMutation.mutate(f);
                    e.target.value = '';
                  }}
                />
                <button
                  type="button"
                  onClick={() => fileInputRef.current?.click()}
                  disabled={logoMutation.isPending}
                  className="btn btn-secondary text-sm"
                >
                  {logoMutation.isPending ? 'Lädt…' : 'Logo hochladen'}
                </button>
                {draft.logo_url && (
                  <button
                    type="button"
                    onClick={() => removeLogoMutation.mutate()}
                    className="text-xs text-red-600 hover:underline"
                  >
                    Logo entfernen
                  </button>
                )}
              </div>
            </div>
          </Card>

          {/* Texte */}
          <Card title="Texte (Platzhalter mit { } erlaubt)">
            {TEXT_FIELDS.map(f => (
              <div key={f.key} className="mb-3">
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  {f.label}
                </label>
                <textarea
                  rows={f.rows}
                  value={draft.texts[f.key] ?? ''}
                  onChange={e => setDraft({
                    ...draft,
                    texts: { ...draft.texts, [f.key]: e.target.value },
                  })}
                  className="input w-full font-mono text-sm"
                  placeholder="z.B. Sehr geehrte Damen und Herren {customer_name}, …"
                />
              </div>
            ))}
            {draft.placeholders?.length > 0 && (
              <div className="text-xs text-gray-500 dark:text-gray-400 mt-2">
                Verfügbar:&nbsp;
                {draft.placeholders.map(p => (
                  <code key={p} className="px-1 py-0.5 mr-1 bg-gray-100 dark:bg-gray-700 rounded">{p}</code>
                ))}
              </div>
            )}
          </Card>

          {/* Sektionen */}
          <Card title="Sektionen ein-/ausblenden">
            <div className="grid grid-cols-2 gap-2">
              {draft.sections.map((s, i) => (
                <label key={s.key} className="flex items-center gap-2 text-sm cursor-pointer">
                  <input
                    type="checkbox"
                    checked={s.enabled}
                    onChange={e => {
                      const next = [...draft.sections];
                      next[i] = { ...s, enabled: e.target.checked };
                      setDraft({ ...draft, sections: next });
                    }}
                  />
                  <span>{s.label}</span>
                </label>
              ))}
            </div>
          </Card>

          {/* Spalten */}
          <Card title="Spalten der Positions-Tabelle">
            <div className="grid grid-cols-2 gap-2">
              {draft.columns.map((c, i) => (
                <label key={c.key} className="flex items-center gap-2 text-sm cursor-pointer">
                  <input
                    type="checkbox"
                    checked={c.enabled}
                    onChange={e => {
                      const next = [...draft.columns];
                      next[i] = { ...c, enabled: e.target.checked };
                      setDraft({ ...draft, columns: next });
                    }}
                  />
                  <span>{c.label}</span>
                </label>
              ))}
            </div>
          </Card>

          {/* Farben */}
          <Card title="Farben">
            <div className="flex gap-4">
              <ColorField
                label="Primär"
                value={draft.primary_color}
                onChange={v => setDraft({ ...draft, primary_color: v })}
              />
              <ColorField
                label="Akzent"
                value={draft.accent_color}
                onChange={v => setDraft({ ...draft, accent_color: v })}
              />
            </div>
          </Card>

          {/* Save bar */}
          <div className="sticky bottom-0 -mx-4 px-4 py-3 bg-white/95 dark:bg-gray-900/95 border-t border-gray-200 dark:border-gray-700 flex items-center justify-between">
            <div className="text-xs text-gray-500">
              {isDirty ? 'Ungespeicherte Änderungen' : 'Synchron mit Server'}
              {saveMutation.isError && <span className="text-red-600 ml-2">Fehler beim Speichern</span>}
            </div>
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => current && setDraft({ ...current })}
                disabled={!isDirty || saveMutation.isPending}
                className="btn btn-secondary text-sm"
              >
                Zurücksetzen
              </button>
              <button
                type="button"
                onClick={() => saveMutation.mutate(draft)}
                disabled={!isDirty || saveMutation.isPending}
                className="btn btn-primary text-sm"
              >
                {saveMutation.isPending ? 'Speichere…' : 'Speichern'}
              </button>
            </div>
          </div>
        </div>

        {/* === Preview === */}
        <div className="lg:sticky lg:top-4 lg:self-start">
          <div className="bg-white dark:bg-gray-800 border rounded shadow-sm">
            <div className="flex items-center justify-between px-3 py-2 border-b border-gray-200 dark:border-gray-700">
              <span className="text-sm font-medium">Live-Vorschau (Dummy-Daten)</span>
              <button
                onClick={() => setPreviewRefreshKey(k => k + 1)}
                className="text-xs text-blue-600 hover:underline"
              >
                Neu laden
              </button>
            </div>
            {previewLoading && !previewBlobUrl && (
              <div className="flex items-center justify-center text-sm text-gray-500" style={{ height: '85vh' }}>
                Lade Vorschau…
              </div>
            )}
            {previewError && (
              <div className="flex items-center justify-center text-sm text-red-600" style={{ height: '85vh' }}>
                Fehler: {previewError}
              </div>
            )}
            {previewBlobUrl && (
              <iframe
                key={previewBlobUrl}
                src={previewBlobUrl}
                title="PDF-Vorschau"
                className="w-full"
                style={{ height: '85vh', border: 0, opacity: previewLoading ? 0.5 : 1 }}
              />
            )}
            <div className="px-3 py-2 text-xs text-gray-500 border-t border-gray-200 dark:border-gray-700">
              Vorschau zeigt gespeicherte Werte — nach „Speichern" wird automatisch aktualisiert.
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

// ---------- Helpers ----------
function Card({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="bg-white dark:bg-gray-800 border rounded shadow-sm p-4">
      <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-200 mb-3">{title}</h3>
      {children}
    </div>
  );
}

function ColorField({ label, value, onChange }: { label: string; value: string; onChange: (v: string) => void }) {
  return (
    <div className="flex flex-col">
      <span className="text-xs text-gray-600 dark:text-gray-400 mb-1">{label}</span>
      <div className="flex items-center gap-2">
        <input
          type="color"
          value={value}
          onChange={e => onChange(e.target.value)}
          className="h-9 w-12 rounded border cursor-pointer"
        />
        <input
          type="text"
          value={value}
          onChange={e => onChange(e.target.value)}
          className="input text-sm w-24 font-mono"
        />
      </div>
    </div>
  );
}
