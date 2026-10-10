/**
 * Bestellverlauf (Paket 4.1, Abschnitt V): GET /sales/orders/{id}/audit-log.
 * Eigene Datei statt api.ts, wie belegstatusApi.ts.
 */
import api from './api';
import type { VerlaufEintrag } from './bestellverlauf';

export const bestellverlaufApi = {
  liste: (orderId: string) =>
    api.get<VerlaufEintrag[]>(`/sales/orders/${orderId}/audit-log`).then((r) => r.data),
};
