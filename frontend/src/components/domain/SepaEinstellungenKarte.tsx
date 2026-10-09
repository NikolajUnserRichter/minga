import { useEffect, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { adminApi } from '../../services/api';
import { getErrorMessage } from '../../services/errors';
import { Button, Input, useToast } from '../ui';

/**
 * SEPA-Lastschrift in den Firmeneinstellungen (B10): Gläubiger-ID und
 * Vorabankündigungsfrist. Speichert über PATCH /admin/settings; das Backend
 * prüft Format und Prüfziffer (422 mit Klartext).
 */
export function SepaEinstellungenKarte() {
  const toast = useToast();
  const queryClient = useQueryClient();
  const { data } = useQuery({ queryKey: ['admin-settings'], queryFn: () => adminApi.listSettings() });
  const [gid, setGid] = useState('');
  const [frist, setFrist] = useState('');

  useEffect(() => {
    if (!data) return;
    // Nur den gespeicherten Wert des Mandanten vorbelegen: list_settings zeigt
    // ohne DB-Wert die Umgebungsvariable (gilt für alle Mandanten im
    // Container) — ein Speichern übernähme sie sonst still in jeden Mandanten.
    const gespeichert = (key: string) => {
      const s = data.find((x) => x.key === key);
      return s && s.source === 'db' ? s.value || '' : '';
    };
    setGid(gespeichert('COMPANY_SEPA_GLAEUBIGER_ID'));
    setFrist(gespeichert('SEPA_VORABANKUENDIGUNG_TAGE'));
  }, [data]);

  const speichern = useMutation({
    mutationFn: () => adminApi.updateSettings({
      COMPANY_SEPA_GLAEUBIGER_ID: gid.trim() || null,
      SEPA_VORABANKUENDIGUNG_TAGE: frist.trim() || null,
    }),
    onSuccess: () => {
      toast.success('SEPA-Einstellungen gespeichert');
      queryClient.invalidateQueries({ queryKey: ['admin-settings'] });
    },
    onError: (e) => toast.error(getErrorMessage(e, 'Speichern fehlgeschlagen')),
  });

  return (
    <div className="card">
      <div className="card-header">
        <h3 className="card-title">SEPA-Lastschrift</h3>
      </div>
      <div className="card-body space-y-3">
        <Input label="Gläubiger-Identifikationsnummer" placeholder="DE98ZZZ09999999999"
          value={gid} onChange={(e) => setGid(e.target.value)} />
        <Input label="Vorabankündigung: Tage vor Einzug (leer = 14)" type="number" min={1} max={30}
          value={frist} onChange={(e) => setFrist(e.target.value)} />
        <Button onClick={() => speichern.mutate()} loading={speichern.isPending}>Speichern</Button>
      </div>
    </div>
  );
}
