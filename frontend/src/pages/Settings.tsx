import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { capacityApi } from '../services/api';
import { PageHeader } from '../components/common/Layout';
import { CapacityIndicator, Input, Select, SelectOption, Button, useToast } from '../components/ui';
import { SkeletonStatCard } from '../components/ui/Skeleton';
import { CapacityModal } from '../components/domain/CapacityModal';
import { Database, Server, Key, Bell, Pencil, Building2, Save, Globe, Hash } from 'lucide-react';
import { Capacity } from '../types';

const forecastModelOptions: SelectOption[] = [
  { value: 'PROPHET', label: 'Prophet (empfohlen)' },
  { value: 'ARIMA', label: 'ARIMA' },
  { value: 'ENSEMBLE', label: 'Ensemble' },
];

export default function Settings() {
  const toast = useToast();

  const [capacityModalOpen, setCapacityModalOpen] = useState(false);
  const [editingCapacity, setEditingCapacity] = useState<Capacity | null>(null);

  const [company, setCompany] = useState(() => {
    const saved = localStorage.getItem('minga_settings_company');
    return saved ? JSON.parse(saved) : {
    name: 'Minga Greens GmbH',
    address: 'Breisacher Str. 12, 81667 München',
    taxId: 'DE328451962',
    email: 'info@minga-greens.de',
    phone: '+49 89 123 456 0',
    website: 'www.minga-greens.de',
  };
  });

  const [notifications, setNotifications] = useState(() => {
    const saved = localStorage.getItem('minga_settings_notifications');
    return saved ? JSON.parse(saved) : {
    harvestReady: true,
    capacityWarning: true,
    newOrders: true,
    lowStock: true,
    overdueInvoices: false,
  };
  });

  const [forecast, setForecast] = useState(() => {
    const saved = localStorage.getItem('minga_settings_forecast');
    return saved ? JSON.parse(saved) : {
    horizon: '14',
    model: 'PROPHET',
    buffer: '10',
  };
  });

  const { data: capacities, isLoading: isLoadingCapacities } = useQuery({
    queryKey: ['capacities'],
    queryFn: () => capacityApi.list()
  });

  const handleEditCapacity = (cap: Capacity) => {
    setEditingCapacity(cap);
    setCapacityModalOpen(true);
  };

  const handleAddCapacity = () => {
    setEditingCapacity(null);
    setCapacityModalOpen(true);
  };

  const handleSaveCompany = () => {
    localStorage.setItem('minga_settings_company', JSON.stringify(company));
    toast.success('Firmendaten gespeichert');
  };

  const handleSaveNotifications = () => {
    localStorage.setItem('minga_settings_notifications', JSON.stringify(notifications));
    toast.success('Benachrichtigungen aktualisiert');
  };

  const handleSaveForecast = () => {
    localStorage.setItem('minga_settings_forecast', JSON.stringify(forecast));
    toast.success('Forecast-Einstellungen gespeichert');
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="Einstellungen"
        subtitle="Systemkonfiguration verwalten"
      />

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Company Profile */}
        <div className="card lg:col-span-2">
          <div className="card-header">
            <h3 className="card-title flex items-center gap-2">
              <Building2 className="w-5 h-5 text-minga-600 dark:text-minga-400" />
              Firmendaten
            </h3>
          </div>
          <div className="card-body">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <Input
                label="Firmenname"
                value={company.name}
                onChange={(e) => setCompany({ ...company, name: e.target.value })}
              />
              <Input
                label="Adresse"
                value={company.address}
                onChange={(e) => setCompany({ ...company, address: e.target.value })}
              />
              <Input
                label="USt-IdNr."
                value={company.taxId}
                onChange={(e) => setCompany({ ...company, taxId: e.target.value })}
                startIcon={<Hash className="w-4 h-4" />}
              />
              <Input
                label="E-Mail"
                type="email"
                value={company.email}
                onChange={(e) => setCompany({ ...company, email: e.target.value })}
              />
              <Input
                label="Telefon"
                value={company.phone}
                onChange={(e) => setCompany({ ...company, phone: e.target.value })}
              />
              <Input
                label="Website"
                value={company.website}
                onChange={(e) => setCompany({ ...company, website: e.target.value })}
                startIcon={<Globe className="w-4 h-4" />}
              />
            </div>
            <div className="flex justify-end mt-4">
              <Button icon={<Save className="w-4 h-4" />} onClick={handleSaveCompany}>
                Speichern
              </Button>
            </div>
          </div>
        </div>

        {/* System Info */}
        <div className="card">
          <div className="card-header">
            <h3 className="card-title">Systeminfo</h3>
          </div>
          <div className="card-body space-y-4">
            <div className="flex items-center gap-3 p-3 bg-gray-50 dark:bg-gray-700/50 rounded-lg">
              <Server className="w-5 h-5 text-gray-400" />
              <div>
                <p className="text-sm font-medium text-gray-900 dark:text-white">Version</p>
                <p className="text-sm text-gray-500 dark:text-gray-400">Minga-Greens ERP v1.0.0</p>
              </div>
            </div>
            <div className="flex items-center gap-3 p-3 bg-gray-50 dark:bg-gray-700/50 rounded-lg">
              <Database className="w-5 h-5 text-gray-400" />
              <div>
                <p className="text-sm font-medium text-gray-900 dark:text-white">Datenbank</p>
                <p className="text-sm text-gray-500 dark:text-gray-400">PostgreSQL 15</p>
              </div>
            </div>
            <div className="flex items-center gap-3 p-3 bg-green-50 dark:bg-green-900/20 rounded-lg">
              <div className="w-2 h-2 bg-green-50 dark:bg-green-900/200 rounded-full animate-pulse" />
              <div>
                <p className="text-sm font-medium text-gray-900 dark:text-white">Status</p>
                <p className="text-sm text-green-600 dark:text-green-400">Alle Dienste aktiv</p>
              </div>
            </div>
          </div>
        </div>

        {/* Kapazitäten */}
        <div className="card">
          <div className="card-header flex justify-between items-center">
            <h3 className="card-title">Kapazitäten</h3>
            <button
              className="text-sm text-minga-600 dark:text-minga-400 hover:text-minga-800 dark:text-minga-400 dark:hover:text-minga-300"
              onClick={handleAddCapacity}
            >
              + Hinzufügen
            </button>
          </div>
          <div className="card-body space-y-4">
            {isLoadingCapacities ? (
              <div className="space-y-3">
                <SkeletonStatCard />
                <SkeletonStatCard />
              </div>
            ) : capacities?.length === 0 ? (
              <p className="text-sm text-gray-500 dark:text-gray-400">Keine Ressourcen definiert.</p>
            ) : (
              capacities?.map(cap => (
                <div key={cap.id} className="relative group">
                  <CapacityIndicator
                    label={cap.name || cap.ressource_typ}
                    current={cap.aktuell_belegt}
                    max={cap.max_kapazitaet}
                    showValues
                  />
                  <div className="absolute right-0 top-0 hidden group-hover:flex gap-2">
                    <button
                      className="text-xs text-blue-600 dark:text-blue-400 bg-white dark:bg-gray-800 px-2 py-1 rounded shadow flex items-center gap-1"
                      onClick={() => handleEditCapacity(cap)}
                    >
                      <Pencil className="w-3 h-3" /> Update
                    </button>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Benachrichtigungen */}
        <div className="card">
          <div className="card-header">
            <h3 className="card-title">Benachrichtigungen</h3>
          </div>
          <div className="card-body space-y-3">
            {([
              { key: 'harvestReady' as const, label: 'Erntereife Chargen' },
              { key: 'capacityWarning' as const, label: 'Kapazitätswarnungen' },
              { key: 'newOrders' as const, label: 'Neue Bestellungen' },
              { key: 'lowStock' as const, label: 'Niedriger Bestand' },
              { key: 'overdueInvoices' as const, label: 'Überfällige Rechnungen' },
            ]).map(({ key, label }) => (
              <label key={key} className="flex items-center justify-between cursor-pointer">
                <div className="flex items-center gap-3">
                  <Bell className="w-5 h-5 text-gray-400" />
                  <span className="text-sm text-gray-700 dark:text-gray-300">{label}</span>
                </div>
                <input
                  type="checkbox"
                  checked={notifications[key]}
                  onChange={(e) => setNotifications({ ...notifications, [key]: e.target.checked })}
                  className="w-4 h-4 rounded border-gray-300 dark:border-gray-600 text-minga-600 dark:text-minga-400 focus:ring-minga-500"
                />
              </label>
            ))}
            <div className="flex justify-end pt-2">
              <Button variant="secondary" size="sm" onClick={handleSaveNotifications}>Speichern</Button>
            </div>
          </div>
        </div>

        {/* Forecast Einstellungen */}
        <div className="card">
          <div className="card-header">
            <h3 className="card-title">Forecasting</h3>
          </div>
          <div className="card-body space-y-4">
            <Input
              label="Standardhorizont (Tage)"
              type="number"
              value={forecast.horizon}
              onChange={(e) => setForecast({ ...forecast, horizon: e.target.value })}
            />
            <Select
              label="Modell"
              options={forecastModelOptions}
              value={forecast.model}
              onChange={(e) => setForecast({ ...forecast, model: e.target.value })}
            />
            <Input
              label="Sicherheitspuffer (%)"
              type="number"
              value={forecast.buffer}
              onChange={(e) => setForecast({ ...forecast, buffer: e.target.value })}
            />
            <div className="flex justify-end pt-2">
              <Button variant="secondary" size="sm" onClick={handleSaveForecast}>Speichern</Button>
            </div>
          </div>
        </div>
      </div>

      {/* API Keys */}
      <div className="card">
        <div className="card-header">
          <h3 className="card-title">API & Integration</h3>
        </div>
        <div className="card-body">
          <div className="flex items-center gap-4 p-4 bg-gray-50 dark:bg-gray-700/50 rounded-lg">
            <Key className="w-6 h-6 text-gray-400" />
            <div className="flex-1">
              <p className="text-sm font-medium text-gray-900 dark:text-white">API-Schlüssel</p>
              <p className="text-sm text-gray-500 dark:text-gray-400 font-mono">••••••••••••••••••••••••••••••••</p>
            </div>
            <Button variant="secondary" onClick={() => toast.info('API-Schlüssel wird in Produktion generiert')}>Regenerieren</Button>
          </div>
        </div>
      </div>

      {/* Modals */}
      <CapacityModal
        open={capacityModalOpen}
        onClose={() => setCapacityModalOpen(false)}
        capacity={editingCapacity}
      />
    </div>
  );
}
