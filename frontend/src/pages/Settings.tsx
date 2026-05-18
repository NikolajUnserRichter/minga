import { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { capacityApi, adminApi } from '../services/api';
import { PageHeader } from '../components/common/Layout';
import { CapacityIndicator, Input, Select, SelectOption, Button, useToast } from '../components/ui';
import { SkeletonStatCard } from '../components/ui/Skeleton';
import { CapacityModal } from '../components/domain/CapacityModal';
import { Database, Server, Key, Bell, Pencil, Building2, Save, Globe, Hash, Mail, Send } from 'lucide-react';
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
        {/* SMTP Settings */}
        <SmtpSettingsCard />

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

// ==================== SMTP-Settings (E-Mail-Versand konfigurieren) ====================

export function SmtpSettingsCard() {
  const toast = useToast();
  const queryClient = useQueryClient();

  const { data, isLoading } = useQuery({
    queryKey: ['admin-settings'],
    queryFn: () => adminApi.listSettings(),
  });

  const [edit, setEdit] = useState<Record<string, string>>({});
  const [testEmail, setTestEmail] = useState('');

  useEffect(() => {
    if (!data) return;
    const next: Record<string, string> = {};
    data.forEach((s) => {
      next[s.key] = s.value || '';
    });
    setEdit(next);
  }, [data]);

  const saveMutation = useMutation({
    mutationFn: (updates: Record<string, string | null>) => adminApi.updateSettings(updates),
    onSuccess: () => {
      toast.success('SMTP-Einstellungen gespeichert');
      queryClient.invalidateQueries({ queryKey: ['admin-settings'] });
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail || 'Speichern fehlgeschlagen'),
  });

  const testMailMutation = useMutation({
    mutationFn: (to: string) => adminApi.sendTestEmail(to),
    onSuccess: (r) => toast.success(`Test-Mail an ${r.sent_to} verschickt`),
    onError: (e: any) => toast.error(e?.response?.data?.detail || 'Test-Mail fehlgeschlagen'),
  });

  if (isLoading || !data) {
    return <div className="card"><div className="card-body text-sm text-gray-500">Lädt SMTP-Settings…</div></div>;
  }

  const findSetting = (key: string) => data.find((s) => s.key === key);
  const fieldFor = (key: string, type: 'text' | 'password' = 'text', placeholder = '') => {
    const s = findSetting(key);
    if (!s) return null;
    return (
      <Input
        label={s.label}
        type={type}
        placeholder={placeholder}
        value={edit[key] ?? ''}
        onChange={(e) => setEdit((p) => ({ ...p, [key]: e.target.value }))}
      />
    );
  };

  const sourceBadge = (key: string) => {
    const s = findSetting(key);
    if (!s) return null;
    if (s.source === 'db') return <span className="text-xs text-emerald-600 dark:text-emerald-400">aus DB</span>;
    if (s.source === 'env') return <span className="text-xs text-amber-600 dark:text-amber-400">aus env-Var</span>;
    return <span className="text-xs text-red-600 dark:text-red-400">nicht gesetzt</span>;
  };

  return (
    <div className="card lg:col-span-2">
      <div className="card-header">
        <h3 className="card-title flex items-center gap-2">
          <Mail className="w-5 h-5 text-minga-600 dark:text-minga-400" />
          E-Mail-Versand (SMTP)
        </h3>
        <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
          Wird für „AB versenden" und „Rechnung per Mail" verwendet. DB-Werte
          überschreiben Server-env-Vars.
        </p>
      </div>
      <div className="card-body space-y-4">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            {fieldFor('SMTP_HOST', 'text', 'smtp.ionos.de')}
            <div className="mt-1">{sourceBadge('SMTP_HOST')}</div>
          </div>
          <div>
            {fieldFor('SMTP_PORT', 'text', '587 (TLS) oder 465 (SSL)')}
            <div className="mt-1">{sourceBadge('SMTP_PORT')}</div>
          </div>
          <div>
            {fieldFor('SMTP_USER', 'text', 'hello@minga-greens.de')}
            <div className="mt-1">{sourceBadge('SMTP_USER')}</div>
          </div>
          <div>
            {fieldFor('SMTP_PASSWORD', 'password', findSetting('SMTP_PASSWORD')?.has_value ? '*** (zum Ändern überschreiben)' : '')}
            <div className="mt-1">{sourceBadge('SMTP_PASSWORD')}</div>
          </div>
          <div>
            <label className="flex items-center gap-2 text-sm text-gray-700 dark:text-gray-300">
              <input
                type="checkbox"
                checked={['true', '1', 'yes', 'ja'].includes((edit['SMTP_USE_TLS'] || '').toLowerCase())}
                onChange={(e) => setEdit((p) => ({ ...p, SMTP_USE_TLS: e.target.checked ? 'true' : 'false' }))}
                className="rounded"
              />
              STARTTLS verwenden (Port 587)
            </label>
            {sourceBadge('SMTP_USE_TLS')}
          </div>
          <div>
            <label className="flex items-center gap-2 text-sm text-gray-700 dark:text-gray-300">
              <input
                type="checkbox"
                checked={['true', '1', 'yes', 'ja'].includes((edit['SMTP_USE_SSL'] || '').toLowerCase())}
                onChange={(e) => setEdit((p) => ({ ...p, SMTP_USE_SSL: e.target.checked ? 'true' : 'false' }))}
                className="rounded"
              />
              Direct SSL verwenden (Port 465)
            </label>
            {sourceBadge('SMTP_USE_SSL')}
          </div>
          <div>
            {fieldFor('EMAILS_FROM_EMAIL', 'text', 'hello@minga-greens.de')}
            <div className="mt-1">{sourceBadge('EMAILS_FROM_EMAIL')}</div>
          </div>
          <div>
            {fieldFor('EMAILS_FROM_NAME', 'text', 'Minga Greens')}
            <div className="mt-1">{sourceBadge('EMAILS_FROM_NAME')}</div>
          </div>
        </div>

        <div className="flex justify-end pt-2 border-t border-gray-100 dark:border-gray-700">
          <Button
            icon={<Save className="w-4 h-4" />}
            loading={saveMutation.isPending}
            onClick={() => {
              const updates: Record<string, string | null> = {};
              data.forEach((s) => {
                const current = edit[s.key] ?? '';
                // Bei Secrets: maskiertes "***" beibehalten = no-op (Backend ignoriert)
                if (s.is_secret && current === '***') return;
                updates[s.key] = current === '' ? null : current;
              });
              saveMutation.mutate(updates);
            }}
          >
            Speichern
          </Button>
        </div>

        <div className="border-t border-gray-100 dark:border-gray-700 pt-4">
          <p className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
            Test-Mail
          </p>
          <div className="flex gap-2 items-end">
            <div className="flex-1">
              <Input
                label="Empfänger"
                type="email"
                placeholder="dein-name@example.com"
                value={testEmail}
                onChange={(e) => setTestEmail(e.target.value)}
              />
            </div>
            <Button
              icon={<Send className="w-4 h-4" />}
              loading={testMailMutation.isPending}
              disabled={!testEmail}
              onClick={() => testMailMutation.mutate(testEmail)}
            >
              Test-Mail senden
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
