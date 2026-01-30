import { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { capacityApi } from '../services/api';
import { PageHeader } from '../components/common/Layout';
import { CapacityIndicator, Input, Select, SelectOption } from '../components/ui';
import { CapacityModal } from '../components/domain/CapacityModal';
import { Database, Server, Key, Bell, Pencil } from 'lucide-react';
import { Capacity } from '../types';

const forecastModelOptions: SelectOption[] = [
  { value: 'PROPHET', label: 'Prophet (empfohlen)' },
  { value: 'ARIMA', label: 'ARIMA' },
  { value: 'ENSEMBLE', label: 'Ensemble' },
];

export default function Settings() {
  const queryClient = useQueryClient();
  const [capacityModalOpen, setCapacityModalOpen] = useState(false);
  const [editingCapacity, setEditingCapacity] = useState<Capacity | null>(null);

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

  return (
    <div className="space-y-6">
      <PageHeader
        title="Einstellungen"
        subtitle="Systemkonfiguration verwalten"
      />

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* System Info */}
        <div className="card">
          <div className="card-header">
            <h3 className="card-title">Systeminfo</h3>
          </div>
          <div className="card-body space-y-4">
            <div className="flex items-center gap-3 p-3 bg-gray-50 rounded-lg">
              <Server className="w-5 h-5 text-gray-400" />
              <div>
                <p className="text-sm font-medium text-gray-900">Version</p>
                <p className="text-sm text-gray-500">Minga-Greens ERP v1.0.0</p>
              </div>
            </div>
            <div className="flex items-center gap-3 p-3 bg-gray-50 rounded-lg">
              <Database className="w-5 h-5 text-gray-400" />
              <div>
                <p className="text-sm font-medium text-gray-900">Datenbank</p>
                <p className="text-sm text-gray-500">PostgreSQL 15</p>
              </div>
            </div>
            <div className="flex items-center gap-3 p-3 bg-green-50 rounded-lg">
              <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse" />
              <div>
                <p className="text-sm font-medium text-gray-900">Status</p>
                <p className="text-sm text-green-600">Alle Dienste aktiv</p>
              </div>
            </div>
          </div>
        </div>

        {/* Kapazitäten */}
        <div className="card">
          <div className="card-header flex justify-between items-center">
            <h3 className="card-title">Kapazitäten</h3>
            <button
              className="text-sm text-minga-600 hover:text-minga-800"
              onClick={handleAddCapacity}
            >
              + Hinzufügen
            </button>
          </div>
          <div className="card-body space-y-4">
            {isLoadingCapacities ? (
              <p className="text-sm text-gray-500">Lade Kapazitäten...</p>
            ) : capacities?.length === 0 ? (
              <p className="text-sm text-gray-500">Keine Ressourcen definiert.</p>
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
                      className="text-xs text-blue-600 bg-white px-2 py-1 rounded shadow flex items-center gap-1"
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
            <label className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <Bell className="w-5 h-5 text-gray-400" />
                <span className="text-sm text-gray-700">Erntereife Chargen</span>
              </div>
              <input
                type="checkbox"
                defaultChecked
                className="w-4 h-4 rounded border-gray-300 text-minga-600 focus:ring-minga-500"
              />
            </label>
            <label className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <Bell className="w-5 h-5 text-gray-400" />
                <span className="text-sm text-gray-700">Kapazitätswarnungen</span>
              </div>
              <input
                type="checkbox"
                defaultChecked
                className="w-4 h-4 rounded border-gray-300 text-minga-600 focus:ring-minga-500"
              />
            </label>
            <label className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <Bell className="w-5 h-5 text-gray-400" />
                <span className="text-sm text-gray-700">Neue Bestellungen</span>
              </div>
              <input
                type="checkbox"
                defaultChecked
                className="w-4 h-4 rounded border-gray-300 text-minga-600 focus:ring-minga-500"
              />
            </label>
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
              defaultValue={14}
            />
            <Select
              label="Modell"
              options={forecastModelOptions}
              defaultValue="PROPHET"
            />
            <Input
              label="Sicherheitspuffer (%)"
              type="number"
              defaultValue={10}
            />
          </div>
        </div>
      </div>

      {/* API Keys */}
      <div className="card">
        <div className="card-header">
          <h3 className="card-title">API & Integration</h3>
        </div>
        <div className="card-body">
          <div className="flex items-center gap-4 p-4 bg-gray-50 rounded-lg">
            <Key className="w-6 h-6 text-gray-400" />
            <div className="flex-1">
              <p className="text-sm font-medium text-gray-900">API-Schlüssel</p>
              <p className="text-sm text-gray-500 font-mono">••••••••••••••••••••••••••••••••</p>
            </div>
            <button className="btn btn-secondary">Regenerieren</button>
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
