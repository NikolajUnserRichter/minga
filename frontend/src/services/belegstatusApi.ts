/**
 * Belegstatus (Paket 4, Abschnitt C): GET /belegstatus. Eigene Datei statt
 * api.ts — dort ändern D und O die Abschnitte invoicesApi und documentsApi.
 */
import api from './api';
import type { BelegstatusFilter, BelegstatusListe } from './belegstatus';

export const belegstatusApi = {
  /** Leere Filter gehen nicht mit; nur_unvollstaendig nur, wenn gesetzt. */
  liste: (filter: BelegstatusFilter) =>
    api.get<BelegstatusListe>('/belegstatus', {
      params: Object.fromEntries(
        Object.entries(filter).filter(([, wert]) => wert !== undefined && wert !== '' && wert !== false),
      ),
    }).then((r) => r.data),
};
