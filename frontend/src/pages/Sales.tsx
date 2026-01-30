import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { salesApi } from '../services/api';
import { PageHeader, FilterBar } from '../components/common/Layout';
import { StatCard } from '../components/domain/StatCard';
import { CustomerCard } from '../components/domain/CustomerCard';
import { OrderCard } from '../components/domain/OrderCard';
import {
  Tabs,
  PageLoader,
  EmptyState,
  Modal,
  Input,
  Select,
  useToast,
  SelectOption,
} from '../components/ui';
import {
  Plus,
  Users,
  ShoppingCart,
  TrendingUp,
  Calendar,
  Search,
  Clock,
} from 'lucide-react';
import type { Order, Customer, OrderWithCustomer } from '../types';

export default function Sales() {
  const toast = useToast();
  const queryClient = useQueryClient();

  const [activeTab, setActiveTab] = useState('orders');
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [selectedOrder, setSelectedOrder] = useState<OrderWithCustomer | null>(null);
  const [selectedCustomer, setSelectedCustomer] = useState<Customer | null>(null);

  const { data: ordersData, isLoading: ordersLoading } = useQuery({
    queryKey: ['orders', statusFilter],
    queryFn: () => salesApi.listOrders({ status: statusFilter || undefined }),
  });

  const { data: customersData, isLoading: customersLoading } = useQuery({
    queryKey: ['customers'],
    queryFn: () => salesApi.listCustomers(),
  });

  const markReadyMutation = useMutation({
    mutationFn: (id: string) => salesApi.updateOrderStatus(id, 'BEREIT'),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['orders'] });
      toast.success('Bestellung als bereit markiert');
    },
    onError: () => {
      toast.error('Fehler beim Aktualisieren');
    },
  });

  const markDeliveredMutation = useMutation({
    mutationFn: (id: string) => salesApi.updateOrderStatus(id, 'GELIEFERT'),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['orders'] });
      toast.success('Bestellung als geliefert markiert');
    },
    onError: () => {
      toast.error('Fehler beim Aktualisieren');
    },
  });

  const orders = ordersData?.items || [];
  const customers = customersData?.items || [];

  const filteredOrders = (orders as OrderWithCustomer[]).filter(
    (order: OrderWithCustomer) =>
      order.kunde?.name?.toLowerCase().includes(search.toLowerCase()) ||
      order.id.toLowerCase().includes(search.toLowerCase())
  );

  const filteredCustomers = customers.filter(
    (customer: Customer) =>
      customer.name?.toLowerCase().includes(search.toLowerCase()) ||
      customer.email?.toLowerCase().includes(search.toLowerCase())
  );

  const orderStatusOptions: SelectOption[] = [
    { value: '', label: 'Alle Status' },
    { value: 'OFFEN', label: 'Offen' },
    { value: 'BESTAETIGT', label: 'Bestätigt' },
    { value: 'IN_PRODUKTION', label: 'In Produktion' },
    { value: 'BEREIT', label: 'Bereit' },
    { value: 'GELIEFERT', label: 'Geliefert' },
  ];

  const tabs = [
    {
      id: 'orders',
      label: 'Bestellungen',
      icon: <ShoppingCart className="w-4 h-4" />,
      count: orders.length,
    },
    {
      id: 'customers',
      label: 'Kunden',
      icon: <Users className="w-4 h-4" />,
      count: customers.length,
    },
  ];

  // Stats
  const openOrders = orders.filter((o: Order) => o.status === 'OFFEN').length;
  const todayOrders = orders.filter((o: Order) => {
    const today = new Date().toISOString().split('T')[0];
    return o.liefer_datum === today;
  }).length;
  const totalRevenue = orders
    .filter((o: Order) => o.status === 'GELIEFERT')
    .reduce((sum: number, o: Order) => {
      const orderTotal = o.positionen?.reduce(
        (s, p) => s + p.menge * (p.preis_pro_einheit || 0),
        0
      ) || 0;
      return sum + orderTotal;
    }, 0);
  const activeCustomers = customers.filter((c: Customer) => c.aktiv).length;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Vertrieb"
        subtitle="Kunden und Bestellungen verwalten"
        actions={
          <div className="flex gap-2">
            <button
              className="btn btn-secondary"
              onClick={() => {
                salesApi.runDailySubscriptions()
                  .then(() => toast.success('Abo-Lauf gestartet'))
                  .catch(() => toast.error('Fehler beim Starten'));
              }}
            >
              <Clock className="w-4 h-4" />
              Abo-Lauf heute
            </button>
            <button className="btn btn-primary">
              <Plus className="w-4 h-4" />
              {activeTab === 'orders' ? 'Neue Bestellung' : 'Neuer Kunde'}
            </button>
          </div>
        }
      />

      {/* Stats */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          title="Offene Bestellungen"
          value={openOrders}
          icon={<ShoppingCart className="w-5 h-5" />}
          variant="warning"
        />
        <StatCard
          title="Lieferung heute"
          value={todayOrders}
          icon={<Calendar className="w-5 h-5" />}
          variant="info"
        />
        <StatCard
          title="Umsatz (geliefert)"
          value={`${totalRevenue.toFixed(2)} €`}
          icon={<TrendingUp className="w-5 h-5" />}
          variant="success"
        />
        <StatCard
          title="Aktive Kunden"
          value={activeCustomers}
          icon={<Users className="w-5 h-5" />}
          variant="primary"
        />
      </div>

      {/* Tabs */}
      <Tabs tabs={tabs} activeTab={activeTab} onChange={setActiveTab} />

      {/* Filters */}
      <FilterBar>
        <div className="flex-1 max-w-md">
          <Input
            placeholder={activeTab === 'orders' ? 'Bestellung oder Kunde suchen...' : 'Kunde suchen...'}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            startIcon={<Search className="w-4 h-4" />}
          />
        </div>
        {activeTab === 'orders' && (
          <Select
            options={orderStatusOptions}
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
          />
        )}
      </FilterBar>

      {/* Orders Tab */}
      {activeTab === 'orders' && (
        ordersLoading ? (
          <PageLoader />
        ) : filteredOrders.length === 0 ? (
          <EmptyState
            title="Keine Bestellungen gefunden"
            description={search || statusFilter ? 'Versuche andere Suchkriterien.' : 'Erstelle die erste Bestellung.'}
            action={
              !search && !statusFilter && (
                <button className="btn btn-primary">
                  <Plus className="w-4 h-4" />
                  Erste Bestellung
                </button>
              )
            }
          />
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {filteredOrders.map((order: Order) => (
              <OrderCard
                key={order.id}
                order={order}
                onClick={() => setSelectedOrder(order)}
                onMarkReady={() => markReadyMutation.mutate(order.id)}
                onMarkDelivered={() => markDeliveredMutation.mutate(order.id)}
              />
            ))}
          </div>
        )
      )}

      {/* Customers Tab */}
      {activeTab === 'customers' && (
        customersLoading ? (
          <PageLoader />
        ) : filteredCustomers.length === 0 ? (
          <EmptyState
            title="Keine Kunden gefunden"
            description={search ? 'Versuche eine andere Suche.' : 'Lege den ersten Kunden an.'}
            action={
              !search && (
                <button className="btn btn-primary">
                  <Plus className="w-4 h-4" />
                  Erster Kunde
                </button>
              )
            }
          />
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {filteredCustomers.map((customer: Customer) => (
              <CustomerCard
                key={customer.id}
                customer={customer}
                onClick={() => setSelectedCustomer(customer)}
                onEdit={() => setSelectedCustomer(customer)}
                onCreateOrder={() => {
                  // TODO: Open create order modal with pre-selected customer
                  toast.info('Bestellung erstellen...');
                }}
              />
            ))}
          </div>
        )
      )}

      {/* Order Detail Modal */}
      <Modal
        open={!!selectedOrder}
        onClose={() => setSelectedOrder(null)}
        title={`Bestellung #${selectedOrder?.id.slice(0, 8)}`}
        size="lg"
      >
        {selectedOrder && (
          <div className="space-y-6">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <p className="text-sm text-gray-500">Kunde</p>
                <p className="font-medium">{selectedOrder.kunde?.name || 'Unbekannt'}</p>
              </div>
              <div>
                <p className="text-sm text-gray-500">Lieferdatum</p>
                <p className="font-medium">
                  {new Date(selectedOrder.liefer_datum).toLocaleDateString('de-DE')}
                </p>
              </div>
              <div>
                <p className="text-sm text-gray-500">Status</p>
                <span className={`badge badge-${selectedOrder.status.toLowerCase()}`}>
                  {selectedOrder.status}
                </span>
              </div>
              <div>
                <p className="text-sm text-gray-500">Erstellt am</p>
                <p className="font-medium">
                  {new Date(selectedOrder.bestell_datum).toLocaleDateString('de-DE')}
                </p>
              </div>
            </div>

            <div className="border-t pt-4">
              <h4 className="font-medium mb-3">Positionen</h4>
              <table className="table">
                <thead>
                  <tr>
                    <th>Produkt</th>
                    <th>Menge</th>
                    <th>Preis/Einheit</th>
                    <th>Gesamt</th>
                  </tr>
                </thead>
                <tbody>
                  {selectedOrder.positionen?.map((item, idx) => (
                    <tr key={idx}>
                      <td>{item.seed_name || 'Produkt'}</td>
                      <td>{item.menge} {item.einheit}</td>
                      <td>{item.preis_pro_einheit?.toFixed(2)} €</td>
                      <td className="font-medium">
                        {(item.menge * (item.preis_pro_einheit || 0)).toFixed(2)} €
                      </td>
                    </tr>
                  ))}
                </tbody>
                <tfoot>
                  <tr className="border-t">
                    <td colSpan={3} className="text-right font-medium">Gesamt:</td>
                    <td className="font-bold">
                      {selectedOrder.positionen
                        ?.reduce((sum, p) => sum + p.menge * (p.preis_pro_einheit || 0), 0)
                        .toFixed(2)} €
                    </td>
                  </tr>
                </tfoot>
              </table>
            </div>

            {selectedOrder.notizen && (
              <div className="border-t pt-4">
                <h4 className="font-medium mb-2">Notizen</h4>
                <p className="text-gray-600">{selectedOrder.notizen}</p>
              </div>
            )}

            <div className="flex gap-3 pt-4 border-t">
              <button
                className="btn btn-secondary"
                onClick={() => setSelectedOrder(null)}
              >
                Schließen
              </button>
              {(selectedOrder.status === 'IN_PRODUKTION' || selectedOrder.status === 'BESTAETIGT') && (
                <button
                  className="btn btn-success"
                  onClick={() => {
                    markReadyMutation.mutate(selectedOrder.id);
                    setSelectedOrder(null);
                  }}
                >
                  Als bereit markieren
                </button>
              )}
              {selectedOrder.status === 'BEREIT' && (
                <button
                  className="btn btn-primary"
                  onClick={() => {
                    markDeliveredMutation.mutate(selectedOrder.id);
                    setSelectedOrder(null);
                  }}
                >
                  Als geliefert markieren
                </button>
              )}
            </div>
          </div>
        )}
      </Modal>

      {/* Customer Detail Modal */}
      <Modal
        open={!!selectedCustomer}
        onClose={() => setSelectedCustomer(null)}
        title={selectedCustomer?.name || 'Kundendetails'}
        size="lg"
      >
        {selectedCustomer && (
          <div className="space-y-6">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <p className="text-sm text-gray-500">Typ</p>
                <span className={`badge badge-${selectedCustomer.typ.toLowerCase()}`}>
                  {selectedCustomer.typ}
                </span>
              </div>
              <div>
                <p className="text-sm text-gray-500">Status</p>
                <span className={`badge ${selectedCustomer.aktiv ? 'badge-success' : 'badge-gray'}`}>
                  {selectedCustomer.aktiv ? 'Aktiv' : 'Inaktiv'}
                </span>
              </div>
              {selectedCustomer.email && (
                <div>
                  <p className="text-sm text-gray-500">E-Mail</p>
                  <a href={`mailto:${selectedCustomer.email}`} className="text-minga-600 hover:text-minga-700">
                    {selectedCustomer.email}
                  </a>
                </div>
              )}
              {selectedCustomer.telefon && (
                <div>
                  <p className="text-sm text-gray-500">Telefon</p>
                  <a href={`tel:${selectedCustomer.telefon}`} className="text-minga-600 hover:text-minga-700">
                    {selectedCustomer.telefon}
                  </a>
                </div>
              )}
              {selectedCustomer.adresse && (
                <div className="col-span-2">
                  <p className="text-sm text-gray-500">Adresse</p>
                  <p>{selectedCustomer.adresse}</p>
                </div>
              )}
              {selectedCustomer.liefertage && selectedCustomer.liefertage.length > 0 && (
                <div className="col-span-2">
                  <p className="text-sm text-gray-500">Liefertage</p>
                  <p>
                    {selectedCustomer.liefertage
                      .map((d) => ['Mo', 'Di', 'Mi', 'Do', 'Fr', 'Sa', 'So'][d])
                      .join(', ')}
                  </p>
                </div>
              )}
            </div>

            <div className="flex gap-3 pt-4 border-t">
              <button
                className="btn btn-secondary"
                onClick={() => setSelectedCustomer(null)}
              >
                Schließen
              </button>
              <button className="btn btn-primary">
                Bestellung erstellen
              </button>
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
}
