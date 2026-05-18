import { useRef, useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Upload, Trash, Download, Paperclip, AlertCircle } from 'lucide-react';
import { Button, Input, useToast } from '../ui';
import { attachmentsApi, AttachmentEntityType, Attachment } from '../../services/api';

interface Props {
  entityType: AttachmentEntityType;
  entityId: string;
  /** Standardwert für certificate_type (z.B. 'BIO' bei Lieferanten). */
  defaultCertificateType?: string;
  /** Kompakter Modus für eingebettete Anzeige in Edit-Modals. */
  compact?: boolean;
}

const CERT_OPTIONS = [
  { value: '', label: '— Typ wählen —' },
  { value: 'BIO', label: 'BIO-Zertifikat' },
  { value: 'ANALYSE', label: 'Labor-Analyse' },
  { value: 'DATENBLATT', label: 'Datenblatt' },
  { value: 'SONSTIGES', label: 'Sonstiges' },
];

function formatSize(b: number): string {
  if (b < 1024) return `${b} B`;
  if (b < 1024 * 1024) return `${(b / 1024).toFixed(1)} KB`;
  return `${(b / (1024 * 1024)).toFixed(1)} MB`;
}

function isExpiringSoon(validUntil: string | null): 'expired' | 'soon' | 'ok' | null {
  if (!validUntil) return null;
  const today = new Date();
  const exp = new Date(validUntil);
  const days = Math.floor((exp.getTime() - today.getTime()) / 86400000);
  if (days < 0) return 'expired';
  if (days <= 30) return 'soon';
  return 'ok';
}

export function AttachmentsPanel({ entityType, entityId, defaultCertificateType, compact }: Props) {
  const toast = useToast();
  const queryClient = useQueryClient();
  const fileInput = useRef<HTMLInputElement>(null);

  const [meta, setMeta] = useState({
    certificate_type: defaultCertificateType || '',
    bio_kontrollstelle: '',
    valid_until: '',
    notes: '',
  });

  const query = useQuery({
    queryKey: ['attachments', entityType, entityId],
    queryFn: () => attachmentsApi.list(entityType, entityId),
    enabled: !!entityId,
  });

  const invalidate = () =>
    queryClient.invalidateQueries({ queryKey: ['attachments', entityType, entityId] });

  const uploadMutation = useMutation({
    mutationFn: (file: File) =>
      attachmentsApi.upload(entityType, entityId, file, {
        certificate_type: meta.certificate_type || undefined,
        bio_kontrollstelle: meta.bio_kontrollstelle || undefined,
        valid_until: meta.valid_until || undefined,
        notes: meta.notes || undefined,
      }),
    onSuccess: () => {
      toast.success('Datei hochgeladen');
      setMeta({ certificate_type: defaultCertificateType || '', bio_kontrollstelle: '', valid_until: '', notes: '' });
      if (fileInput.current) fileInput.current.value = '';
      invalidate();
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail || 'Upload fehlgeschlagen'),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => attachmentsApi.delete(id),
    onSuccess: () => { toast.success('Datei entfernt'); invalidate(); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || 'Löschen fehlgeschlagen'),
  });

  const attachments = query.data || [];

  return (
    <div className={compact ? 'space-y-2' : 'space-y-3'}>
      <div className="flex items-center gap-2">
        <Paperclip className="w-4 h-4 text-gray-500" />
        <h4 className="font-medium text-gray-800 dark:text-gray-200">Anhänge ({attachments.length})</h4>
      </div>

      {/* Upload-Form */}
      <div className="border rounded p-3 space-y-2 dark:border-gray-700 bg-gray-50/40 dark:bg-gray-800/40">
        <div className="grid grid-cols-2 gap-2">
          <select
            value={meta.certificate_type}
            onChange={(e) => setMeta({ ...meta, certificate_type: e.target.value })}
            className="block w-full px-2 py-1.5 text-sm border border-gray-300 dark:border-gray-600 dark:bg-gray-800 rounded"
          >
            {CERT_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </select>
          <Input
            type="date"
            placeholder="Gültig bis"
            value={meta.valid_until}
            onChange={(e) => setMeta({ ...meta, valid_until: e.target.value })}
          />
        </div>
        {meta.certificate_type === 'BIO' && (
          <Input
            placeholder="Kontrollstelle (z.B. DE-ÖKO-006)"
            value={meta.bio_kontrollstelle}
            onChange={(e) => setMeta({ ...meta, bio_kontrollstelle: e.target.value })}
          />
        )}
        <Input
          placeholder="Notiz (optional)"
          value={meta.notes}
          onChange={(e) => setMeta({ ...meta, notes: e.target.value })}
        />
        <div className="flex items-center gap-2">
          <input
            ref={fileInput}
            type="file"
            className="block w-full text-sm text-gray-600 dark:text-gray-400 file:mr-3 file:py-1.5 file:px-3 file:rounded file:border-0 file:text-sm file:bg-gray-200 dark:file:bg-gray-700 file:text-gray-700 dark:file:text-gray-200 hover:file:bg-gray-300 dark:hover:file:bg-gray-600"
          />
          <Button
            size="sm"
            loading={uploadMutation.isPending}
            icon={<Upload className="w-3 h-3" />}
            onClick={() => {
              const f = fileInput.current?.files?.[0];
              if (!f) return toast.error('Bitte Datei auswählen');
              uploadMutation.mutate(f);
            }}
          >
            Hochladen
          </Button>
        </div>
      </div>

      {/* Liste */}
      {attachments.length === 0 ? (
        <p className="text-sm text-gray-500 dark:text-gray-400 italic">Noch keine Anhänge.</p>
      ) : (
        <ul className="space-y-1.5">
          {attachments.map((a: Attachment) => {
            const exp = isExpiringSoon(a.valid_until);
            return (
              <li key={a.id} className="flex items-center justify-between gap-2 border rounded p-2 text-sm dark:border-gray-700">
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2 truncate">
                    <span className="font-medium truncate">{a.filename}</span>
                    {a.certificate_type && (
                      <span className="text-xs px-1.5 py-0.5 bg-blue-100 text-blue-800 dark:bg-blue-900/40 dark:text-blue-200 rounded">
                        {a.certificate_type}
                      </span>
                    )}
                    {a.bio_kontrollstelle && (
                      <span className="text-xs text-gray-600 dark:text-gray-400">{a.bio_kontrollstelle}</span>
                    )}
                  </div>
                  <div className="flex items-center gap-3 text-xs text-gray-500 dark:text-gray-400">
                    <span>{formatSize(a.size_bytes)}</span>
                    {a.valid_until && (
                      <span className={`flex items-center gap-1 ${exp === 'expired' ? 'text-red-600 dark:text-red-400' : exp === 'soon' ? 'text-amber-600 dark:text-amber-400' : ''}`}>
                        {(exp === 'expired' || exp === 'soon') && <AlertCircle className="w-3 h-3" />}
                        gültig bis {new Date(a.valid_until).toLocaleDateString('de-DE')}
                      </span>
                    )}
                  </div>
                </div>
                <div className="flex gap-1 shrink-0">
                  <Button
                    size="sm"
                    variant="secondary"
                    icon={<Download className="w-3 h-3" />}
                    onClick={() => attachmentsApi.download(a)}
                  >
                    {compact ? '' : 'Download'}
                  </Button>
                  <Button
                    size="sm"
                    variant="danger"
                    icon={<Trash className="w-3 h-3" />}
                    loading={deleteMutation.isPending}
                    onClick={() => {
                      if (confirm(`'${a.filename}' wirklich löschen?`)) deleteMutation.mutate(a.id);
                    }}
                  />
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
