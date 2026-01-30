import { PageHeader } from '../components/common/Layout';
import { CapacityIndicator, Input, Select, SelectOption } from '../components/ui';
import { Database, Server, Key, Bell } from 'lucide-react';

const forecastModelOptions: SelectOption[] = [
  { value: 'PROPHET', label: 'Prophet (empfohlen)' },
  { value: 'ARIMA', label: 'ARIMA' },
  { value: 'ENSEMBLE', label: 'Ensemble' },
];

export default function Settings() {
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
          <div className="card-header">
            <h3 className="card-title">Kapazitäten</h3>
          </div>
          <div className="card-body space-y-4">
            <CapacityIndicator
              label="Regalplätze"
              current={42}
              max={50}
              showValues
            />
            <CapacityIndicator
              label="Trays verfügbar"
              current={150}
              max={200}
              showValues
            />
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
    </div>
  );
}
