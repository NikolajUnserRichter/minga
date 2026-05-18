import { useRef, useState } from 'react';
import { Upload, FileDown } from 'lucide-react';
import { Button, useToast } from '../ui';

type Entity = 'customers' | 'suppliers' | 'seeds' | 'products' | 'locations';

interface Props {
  entity: Entity;
  label?: string;
  onImported?: () => void;
}

const API_URL = import.meta.env.VITE_API_URL ?? (import.meta.env.DEV ? 'http://localhost:8000' : '');

/**
 * Excel-Import-Button: lädt eine .xlsx hoch und zeigt das Importergebnis (created/updated/errors).
 * Plus separater Download-Button für ein leeres Template mit Header-Zeile.
 */
export function ExcelImport({ entity, label = 'Excel-Import', onImported }: Props) {
  const toast = useToast();
  const fileInput = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);

  const handleDownload = async () => {
    try {
      const res = await fetch(`${API_URL}/api/v1/imports/template/${entity}`, {
        credentials: 'include',
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
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
      const res = await fetch(`${API_URL}/api/v1/imports/${entity}`, {
        method: 'POST',
        body: form,
        credentials: 'include',
      });
      const data = await res.json();
      if (!res.ok) {
        toast.error(data?.detail || 'Import fehlgeschlagen');
        return;
      }
      const created = data.created || 0;
      const updated = data.updated || 0;
      const errors: string[] = data.errors || [];
      const summary = `${created} angelegt · ${updated} aktualisiert${errors.length ? ` · ${errors.length} Fehler` : ''}`;
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
