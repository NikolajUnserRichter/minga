import { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Plus, Search, Calendar, CheckCircle, Truck } from 'lucide-react';
import { salesApi } from '../services/api';
import { Order, OrderStatus } from '../types';
import { PageHeader, FilterBar } from '../components/common/Layout';
import BulkActionBar from '../components/common/BulkActionBar';
import { useBulkSelection } from '../hooks/useBulkSelection';
import { OrderCard } from '../components/domain/OrderCard';
import { CreateOrderModal } from '../components/domain/CreateOrderModal';
import { OrderDocumentsModal } from '../components/domain/OrderDocumentsModal';
import { ExcelImport } from '../components/common/ExcelImport';
import { ListPageSkeleton } from '../components/ui/Skeleton';
import {
  Button,
  Input,
  Select,
  Tabs,
  TabPanel,
  EmptyState,
  useToast,
  SelectOption,
  formatDate,
  getRelativeDate,
} from '../components/ui';

const statusOptions: SelectOption[] = [
  { value: 'all', label: 'Alle Status' },
  { value: 'OFFEN', label: 'Offen' },
  { value: 'BESTAETIGT', label: 'Bestätigt' },
  { value: 'IN_PRODUKTION', label: 'In Produktion' },
  { value: 'BEREIT', label: 'Bereit' },
  { value: 'GELIEFERT', label: 'Geliefert' },
];

export default function Orders() {
  const toast = useToast();
  const queryClient = useQueryClient();

  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [search, setSearch] = useState('');
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [docsOrder, setDocsOrder] = useState<Order | null>(null);

  // Fetch orders
  const { data: ordersData, isLoading, isError, error, refetch, isFetching } = useQuery({
    queryKey: ['orders', { status: statusFilter }],
    queryFn: () =>
      salesApi.listOrders({
        status: statusFilter === 'all' ? undefined : (statusFilter as OrderStatus),
      }),
    retry: 2,                              // bis zu 2x re-tryen
    retryDelay: (n) => Math.min(2000 * n, 5000),
  });

  const orders = ordersData?.items || [];

  // Group orders by delivery date
  const today = new Date().toISOString().split('T')[0];
  const tomorrow = new Date(Date.now() + 86400000).toISOString().split('T')[0];

  const todayOrders = orders.filter((o) => o.liefer_datum === today);
  const tomorrowOrders = orders.filter((o) => o.liefer_datum === tomorrow);
  const upcomingOrders = orders.filter(
    (o) => o.liefer_datum > tomorrow
  );

  const filteredOrders = orders.filter(
    (order) =>
      order.kunde_name?.toLowerCase().includes(search.toLowerCase()) ||
      order.id.toLowerCase().includes(search.toLowerCase())
  );

  const handleMarkReady = async (order: Order) => {
    try {
      await salesApi.updateOrderStatus(order.id, 'BEREIT');
      queryClient.invalidateQueries({ queryKey: ['orders'] });
      toast.success('Bestellung als bereit markiert');
    } catch (error) {
      toast.error('Fehler beim Aktualisieren');
    }
  };

  const handleMarkDelivered = async (order: Order) => {
    try {
      await salesApi.updateOrderStatus(order.id, 'GELIEFERT');
      queryClient.invalidateQueries({ queryKey: ['orders'] });
      toast.success('Bestellung als geliefert markiert');
    } catch (error) {
      toast.error('Fehler beim Aktualisieren');
    }
  };

  // Bulk selection
  const bulk = useBulkSelection(orders);

  const handleBulkReady = async () => {
    try {
      await Promise.all(
        bulk.selectedItems
          .filter((o) => o.status === 'IN_PRODUKTION' || o.status === 'BESTAETIGT')
          .map((o) => salesApi.updateOrderStatus(o.id, 'BEREIT')),
      );
      queryClient.invalidateQueries({ queryKey: ['orders'] });
      bulk.clearSelection();
      toast.success('Bestellungen als bereit markiert');
    } catch (error) {
      toast.error('Fehler beim Aktualisieren');
    }
  };

  const handleBulkDelivered = async () => {
    try {
      await Promise.all(
        bulk.selectedItems
          .filter((o) => o.status === 'BEREIT')
          .map((o) => salesApi.updateOrderStatus(o.id, 'GELIEFERT')),
      );
      queryClient.invalidateQueries({ queryKey: ['orders'] });
      bulk.clearSelection();
      toast.success('Bestellungen als geliefert markiert');
    } catch (error) {
      toast.error('Fehler beim Aktualisieren');
    }
  };

  if (isLoading) {
    return <ListPageSkeleton />;
  }

  if (isError) {
    const errAny = error as any;
    const status = errAny?.response?.status;
    const detail = errAny?.response?.data?.detail || errAny?.message || 'Unbekannter Fehler';
    return (
      <div className="p-8 text-center">
        <div className="text-3xl mb-3">⚠️</div>
        <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-2">Bestellungen konnten nicht geladen werden</h2>
        <p className="text-sm text-gray-600 dark:text-gray-400 mb-1">
          {status ? `HTTP ${status}` : 'Netzwerkfehler'} — {String(detail)}
        </p>
        <button
          className="mt-4 px-4 py-2 bg-minga-600 hover:bg-minga-700 text-white rounded-lg text-sm"
          onClick={() => refetch()}
          disabled={isFetching}
        >
          {isFetching ? 'Lädt…' : 'Erneut versuchen'}
        </button>
      </div>
    );
  }

  const tabs = [
    { id: 'today', label: 'Heute', badge: todayOrders.length },
    { id: 'tomorrow', label: 'Morgen', badge: tomorrowOrders.length },
    { id: 'upcoming', label: 'Kommende', badge: upcomingOrders.length },
    { id: 'all', label: 'Alle', badge: orders.length },
  ];

  return (
    <div>
      <PageHeader
        title="Bestellungen"
        subtitle={`${orders.length} Bestellungen`}
        actions={
          <div className="flex items-center gap-2">
            <ExcelImport
              entity="order_history"
              label="Historie importieren"
              secondaryLabel="übersprungen"
              onImported={() => queryClient.invalidateQueries({ queryKey: ['orders'] })}
            />
            <Button icon={<Plus className="w-4 h-4" />} onClick={() => setIsCreateModalOpen(true)}>
              Neue Bestellung
            </Button>
          </div>
        }
      />

      <FilterBar>
        <div className="flex-1 max-w-md">
          <Input
            placeholder="Suchen nach Kunde oder Bestellnummer..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            startIcon={<Search className="w-4 h-4" />}
          />
        </div>
        <Select
          options={statusOptions}
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
        />
      </FilterBar>

      <Tabs tabs={tabs} defaultTab="today">
        <TabPanel id="today">
          <OrderList
            orders={todayOrders}
            title="Heutige Lieferungen"
            onMarkReady={handleMarkReady}
            onMarkDelivered={handleMarkDelivered}
            onOpenDocs={setDocsOrder}
            bulk={bulk}
          />
        </TabPanel>
        <TabPanel id="tomorrow">
          <OrderList
            orders={tomorrowOrders}
            title="Morgen"
            onMarkReady={handleMarkReady}
            onMarkDelivered={handleMarkDelivered}
            onOpenDocs={setDocsOrder}
            bulk={bulk}
          />
        </TabPanel>
        <TabPanel id="upcoming">
          <OrderList
            orders={upcomingOrders}
            title="Kommende Bestellungen"
            onMarkReady={handleMarkReady}
            onMarkDelivered={handleMarkDelivered}
            onOpenDocs={setDocsOrder}
            bulk={bulk}
          />
        </TabPanel>
        <TabPanel id="all">
          <OrderList
            orders={filteredOrders}
            title="Alle Bestellungen"
            onMarkReady={handleMarkReady}
            onMarkDelivered={handleMarkDelivered}
            onOpenDocs={setDocsOrder}
            bulk={bulk}
          />
        </TabPanel>
      </Tabs>

      {/* Bulk Action Bar */}
      <BulkActionBar count={bulk.count} onClear={bulk.clearSelection}>
        <button
          onClick={handleBulkReady}
          className="flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium bg-minga-600 hover:bg-minga-700 text-white rounded-lg transition-colors"
        >
          <CheckCircle className="w-4 h-4" />
          Bereit
        </button>
        <button
          onClick={handleBulkDelivered}
          className="flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors"
        >
          <Truck className="w-4 h-4" />
          Geliefert
        </button>
      </BulkActionBar>

      {/* Create Order Modal */}
      <CreateOrderModal
        open={isCreateModalOpen}
        onClose={() => setIsCreateModalOpen(false)}
      />
      <OrderDocumentsModal
        open={!!docsOrder}
        order={docsOrder}
        onClose={() => setDocsOrder(null)}
      />
    </div>
  );
}

// Order List Component
interface OrderListProps {
  orders: Order[];
  title: string;
  onMarkReady: (order: Order) => void;
  onMarkDelivered: (order: Order) => void;
  onOpenDocs: (order: Order) => void;
  bulk: ReturnType<typeof useBulkSelection<Order>>;
}

function OrderList({ orders, onMarkReady, onMarkDelivered, onOpenDocs, bulk }: OrderListProps) {
  if (orders.length === 0) {
    return (
      <EmptyState
        title="Keine Bestellungen"
        description="In diesem Zeitraum sind keine Bestellungen vorhanden."
      />
    );
  }

  // Group by delivery date
  const groupedByDate = orders.reduce((acc, order) => {
    const date = order.liefer_datum;
    if (!acc[date]) {
      acc[date] = [];
    }
    acc[date].push(order);
    return acc;
  }, {} as Record<string, Order[]>);

  return (
    <div className="space-y-6">
      {Object.entries(groupedByDate).map(([date, dateOrders]) => (
        <div key={date}>
          <div className="flex items-center gap-2 mb-3">
            <Calendar className="w-4 h-4 text-gray-400" />
            <h3 className="font-medium text-gray-900 dark:text-white">
              {formatDate(date)} - {getRelativeDate(date)}
            </h3>
            <span className="badge badge-gray">{dateOrders.length}</span>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {dateOrders.map((order) => (
              <div key={order.id} className="relative group">
                <div className="absolute top-3 left-3 z-10">
                  <input
                    type="checkbox"
                    checked={bulk.isSelected(order.id)}
                    onChange={() => bulk.toggle(order.id)}
                    className="w-4 h-4 rounded border-gray-300 dark:border-gray-600 text-minga-600 dark:text-minga-400 focus:ring-minga-500 cursor-pointer opacity-0 group-hover:opacity-100 transition-opacity data-[checked=true]:opacity-100"
                    data-checked={bulk.isSelected(order.id)}
                  />
                </div>
                <OrderCard
                key={order.id}
                order={{
                  ...order,
                  kunde: { name: order.kunde_name } as any,
                }}
                onClick={() => onOpenDocs(order)}
                onMarkReady={
                  order.status === 'IN_PRODUKTION' || order.status === 'BESTAETIGT'
                    ? () => onMarkReady(order)
                    : undefined
                }
                onMarkDelivered={
                  order.status === 'BEREIT' ? () => onMarkDelivered(order) : undefined
                }
              />
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
