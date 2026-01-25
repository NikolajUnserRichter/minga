import { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Plus, Search, Calendar } from 'lucide-react';
import { salesApi } from '../services/api';
import { Order, OrderStatus } from '../types';
import { PageHeader, FilterBar } from '../components/common/Layout';
import { OrderCard, OrderRow } from '../components/domain/OrderCard';
import {
  Button,
  Input,
  Select,
  Tabs,
  TabPanel,
  PageLoader,
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

  // Fetch orders
  const { data: ordersData, isLoading } = useQuery({
    queryKey: ['orders', { status: statusFilter }],
    queryFn: () =>
      salesApi.getOrders({
        status: statusFilter === 'all' ? undefined : (statusFilter as OrderStatus),
      }),
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
      await salesApi.updateOrder(order.id, { status: 'BEREIT' });
      queryClient.invalidateQueries({ queryKey: ['orders'] });
      toast.success('Bestellung als bereit markiert');
    } catch (error) {
      toast.error('Fehler beim Aktualisieren');
    }
  };

  const handleMarkDelivered = async (order: Order) => {
    try {
      await salesApi.updateOrder(order.id, { status: 'GELIEFERT' });
      queryClient.invalidateQueries({ queryKey: ['orders'] });
      toast.success('Bestellung als geliefert markiert');
    } catch (error) {
      toast.error('Fehler beim Aktualisieren');
    }
  };

  if (isLoading) {
    return <PageLoader />;
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
          <Button icon={<Plus className="w-4 h-4" />} onClick={() => toast.info('Neue Bestellung noch nicht implementiert')}>
            Neue Bestellung
          </Button>
        }
      />

      <FilterBar>
        <div className="flex-1 max-w-md">
          <Input
            placeholder="Suchen nach Kunde oder Bestellnummer..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            prefix={<Search className="w-4 h-4" />}
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
          />
        </TabPanel>
        <TabPanel id="tomorrow">
          <OrderList
            orders={tomorrowOrders}
            title="Morgen"
            onMarkReady={handleMarkReady}
            onMarkDelivered={handleMarkDelivered}
          />
        </TabPanel>
        <TabPanel id="upcoming">
          <OrderList
            orders={upcomingOrders}
            title="Kommende Bestellungen"
            onMarkReady={handleMarkReady}
            onMarkDelivered={handleMarkDelivered}
          />
        </TabPanel>
        <TabPanel id="all">
          <OrderList
            orders={filteredOrders}
            title="Alle Bestellungen"
            onMarkReady={handleMarkReady}
            onMarkDelivered={handleMarkDelivered}
          />
        </TabPanel>
      </Tabs>
    </div>
  );
}

// Order List Component
interface OrderListProps {
  orders: Order[];
  title: string;
  onMarkReady: (order: Order) => void;
  onMarkDelivered: (order: Order) => void;
}

function OrderList({ orders, title, onMarkReady, onMarkDelivered }: OrderListProps) {
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
            <h3 className="font-medium text-gray-900">
              {formatDate(date)} - {getRelativeDate(date)}
            </h3>
            <span className="badge badge-gray">{dateOrders.length}</span>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {dateOrders.map((order) => (
              <OrderCard
                key={order.id}
                order={{
                  ...order,
                  kunde: { name: order.kunde_name } as any,
                }}
                onMarkReady={
                  order.status === 'IN_PRODUKTION' || order.status === 'BESTAETIGT'
                    ? () => onMarkReady(order)
                    : undefined
                }
                onMarkDelivered={
                  order.status === 'BEREIT' ? () => onMarkDelivered(order) : undefined
                }
              />
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
