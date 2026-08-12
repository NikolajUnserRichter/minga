import { useRef, useState } from 'react';
import { Upload, FileDown } from 'lucide-react';
import { Button, useToast } from '../ui';
import api from '../../services/api';

type Entity = 'customers' | 'suppliers' | 'seeds' | 'products' | 'locations' | 'order_history' | 'grow_batches';

interface Props {
  entity: Entity;
  label?: string;
  /** Wort für den zweiten Counter im Toast (Default: "aktualisiert"). Für Historien-Import: "übersprungen". */
  secondaryLabel?: string;
  onImported?: () => void;
}

/**
 * Excel-Import-Button: lädt eine .xlsx hoch und zeigt das Importergebnis (created/updated/errors).
 * Plus separater Download-Button für ein leeres Template mit Header-Zeile.
 */
export function ExcelImport({ entity, label = 'Excel-Import', secondaryLabel = 'aktualisiert', onImported }: Props) {
  const toast = useToast();
  const fileInput = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);

  const handleDownload = async () => {
    try {
      // Über die geteilte axios-Instanz: hängt den Bearer-Token an (raw fetch → 401)
      const res = await api.get<Blob>(`/imports/template/${entity}`, { responseType: 'blob' });
      const url = URL.createObjectURL(res.data);
      const a = document.createElement('a');
      a.href = url;
      a.download = `template_${entity}.xlsx`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch (e) {
      toast.error('Template-Download fehlgeschlagen');
    }
  };

  const handleUpload = async (file: File) => {
    setBusy(true);
    try {
      const form = new FormData();
      form.append('file', file);
      let data: any;
      try {
        const res = await api.post(`/imports/${entity}`, form);
        data = res.data;
      } catch (err: any) {
        toast.error(err?.response?.data?.detail || 'Import fehlgeschlagen');
        return;
      }
      const created = data.created || 0;
      const updated = data.updated || 0;
      const errors: string[] = data.errors || [];
      const summary = `${created} angelegt · ${updated} ${secondaryLabel}${errors.length ? ` · ${errors.length} Fehler` : ''}`;
      if (errors.length) {
        toast.error(`${summary}\n${errors.slice(0, 3).join('\n')}${errors.length > 3 ? '\n…' : ''}`);
      } else {
        toast.success(summary);
      }
      onImported?.();
    } catch (e: any) {
      toast.error(e?.message || 'Upload fehlgeschlagen');
    } finally {
      setBusy(false);
      if (fileInput.current) fileInput.current.value = '';
    }
  };

  return (
    <div className="inline-flex gap-2">
      <Button
        type="button"
        variant="secondary"
        size="sm"
        icon={<FileDown className="w-4 h-4" />}
        onClick={handleDownload}
      >
        Template
      </Button>
      <Button
        type="button"
        variant="secondary"
        size="sm"
        loading={busy}
        icon={<Upload className="w-4 h-4" />}
        onClick={() => fileInput.current?.click()}
      >
        {label}
      </Button>
      <input
        ref={fileInput}
        type="file"
        accept=".xlsx,.xlsm"
        className="hidden"
        onChange={(e) => {
          const f = e.target.files?.[0];
          if (f) handleUpload(f);
        }}
      />
    </div>
  );
}
