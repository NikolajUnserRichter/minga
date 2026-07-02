import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { ShoppingBag, RefreshCw, Settings as SettingsIcon, DownloadCloud, UploadCloud } from 'lucide-react';
import { integrationsApi } from '../services/api';
import { PageHeader } from '../components/common/Layout';
import { ListPageSkeleton } from '../components/ui/Skeleton';
import {
  Button,
  Badge,
  Alert,
  EmptyState,
  Table,
  formatDate,
  useToast,
  type Column,
} from '../components/ui';

type ShopifyOrder = {
  order_number: string;
  created_at: string;
  customer?: string;
  total?: string;
  currency?: string;
  financial_status?: string;
};

type FinVariant = 'success' | 'warning' | 'danger' | 'info' | 'gray';

const financialStatusConfig: Record<string, { label: string; variant: FinVariant }> = {
  paid: { label: 'Bezahlt', variant: 'success' },
  pending: { label: 'Ausstehend', variant: 'warning' },
  authorized: { label: 'Autorisiert', variant: 'info' },
  partially_paid: { label: 'Teilzahlung', variant: 'info' },
  refunded: { label: 'Erstattet', variant: 'gray' },
  partially_refunded: { label: 'Teil-Erstattung', variant: 'gray' },
  voided: { label: 'Storniert', variant: 'danger' },
};

function FinancialStatusBadge({ status }: { status?: string }) {
  if (!status) return <span className="text-tertiary">—</span>;
  const cfg = financialStatusConfig[status] || { label: status, variant: 'gray' as FinVariant };
  return <Badge variant={cfg.variant}>{cfg.label}</Badge>;
}

/**
 * Shopify-Bestellungen — Nur-Lese-Vorschau.
 *
 * Die Bestellungen werden live über die Integration aus dem Shopify-Shop
 * geladen (`GET /integrations/shopify/orders`) und NICHT im ERP gespeichert.
 * Die Übernahme in echte ERP-Aufträge ist bewusst noch nicht enthalten
 * (einseitiger, schlanker Scope: Shop -> ERP, read-only).
 */
export default function ShopifyOrders() {
  const navigate = useNavigate();
  const toast = useToast();
  const queryClient = useQueryClient();

  const statusQuery = useQuery({
    queryKey: ['integration', 'shopify'],
    queryFn: () => integrationsApi.shopifyStatus(),
  });

  const configured = statusQuery.data?.configured === true;

  const importMutation = useMutation({
    mutationFn: () => integrationsApi.shopifyImportOrders(50),
    onSuccess: (r) => {
      toast.success(`${r.imported} importiert, ${r.skipped} übersprungen`);
      queryClient.invalidateQueries({ queryKey: ['orders'] });
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail || 'Import fehlgeschlagen'),
  });

  const pushMutation = useMutation({
    mutationFn: () => integrationsApi.shopifyPushProducts(),
    onSuccess: (r) => toast.success(`${r.pushed} Produkte in den Shop gepusht`),
    onError: (e: any) => toast.error(e?.response?.data?.detail || 'Push fehlgeschlagen'),
  });

  const ordersQuery = useQuery({
    queryKey: ['shopify-orders'],
    queryFn: () => integrationsApi.shopifyOrders(50),
    enabled: configured,
    retry: 1,
  });

  const orders = (ordersQuery.data || []) as ShopifyOrder[];

  const columns: Column<ShopifyOrder>[] = [
    {
      key: 'order_number',
      header: 'Bestellung',
      render: (o) => <span className="font-medium">{o.order_number}</span>,
    },
    {
      key: 'created_at',
      header: 'Datum',
      sortable: true,
      render: (o) => (o.created_at ? formatDate(o.created_at) : '—'),
    },
    { key: 'customer', header: 'Kunde', render: (o) => o.customer || '—' },
    {
      key: 'total',
      header: 'Betrag',
      align: 'right',
      render: (o) => (o.total ? `${o.total} ${o.currency || ''}`.trim() : '—'),
    },
    {
      key: 'financial_status',
      header: 'Zahlung',
      render: (o) => <FinancialStatusBadge status={o.financial_status} />,
    },
  ];

  const headerActions = (
    <div className="flex items-center gap-2">
      {configured && (
        <>
          <Button
            variant="secondary"
            onClick={() => ordersQuery.refetch()}
            disabled={ordersQuery.isFetching}
          >
            <RefreshCw className={`w-4 h-4 ${ordersQuery.isFetching ? 'animate-spin' : ''}`} />
            Aktualisieren
          </Button>
          <Button
            variant="secondary"
            icon={<UploadCloud className="w-4 h-4" />}
            loading={pushMutation.isPending}
            onClick={() => pushMutation.mutate()}
          >
            Produkte pushen
          </Button>
          <Button
            icon={<DownloadCloud className="w-4 h-4" />}
            loading={importMutation.isPending}
            onClick={() => importMutation.mutate()}
          >
            Bestellungen importieren
          </Button>
        </>
      )}
    </div>
  );

  return (
    <div>
      <PageHeader
        title="Shopify-Bestellungen"
        subtitle="Nur-Lese-Vorschau der letzten Bestellungen aus deinem Shopify-Shop"
        actions={headerActions}
      />

      {statusQuery.isLoading ? (
        <ListPageSkeleton />
      ) : !configured ? (
        <EmptyState
          icon={<ShoppingBag className="w-16 h-16" />}
          title="Kein Shopify-Shop verbunden"
          description="Verbinde deinen Shop in den Einstellungen (Shop-Domain + Access-Token), um hier die letzten Bestellungen als Vorschau zu sehen."
          action={
            <Button onClick={() => navigate('/settings')}>
              <SettingsIcon className="w-4 h-4" />
              Zu den Einstellungen
            </Button>
          }
        />
      ) : ordersQuery.isLoading ? (
        <ListPageSkeleton />
      ) : ordersQuery.isError ? (
        <EmptyState
          icon={<ShoppingBag className="w-16 h-16" />}
          title="Bestellungen konnten nicht geladen werden"
          description="Die Verbindung zu Shopify hat nicht geklappt. Prüfe Shop-Domain und Access-Token in den Einstellungen."
          action={<Button onClick={() => ordersQuery.refetch()}>Erneut versuchen</Button>}
        />
      ) : orders.length === 0 ? (
        <EmptyState
          icon={<ShoppingBag className="w-16 h-16" />}
          title="Keine Bestellungen gefunden"
          description="In deinem Shopify-Shop liegen aktuell keine Bestellungen vor."
        />
      ) : (
        <>
          <Alert variant="info" className="mb-4">
            Bestellungen werden live aus Shopify geladen. Mit <strong>„Bestellungen
            importieren"</strong> werden fehlende als ERP-Kunde + Auftrag (Entwurf) angelegt
            (bereits importierte werden übersprungen). <strong>„Produkte pushen"</strong>
            überträgt verkaufbare Artikel mit Bestand in den Shop.
          </Alert>
          <Table
            columns={columns}
            data={orders}
            keyExtractor={(o) => o.order_number}
            sortable
          />
        </>
      )}
    </div>
  );
}
