import { useState } from 'react';
import { Forecast } from '../../types';
import { Input, Textarea, Button, Alert, formatDate } from '../ui';
import { AlertTriangle, TrendingUp, TrendingDown } from 'lucide-react';

interface ForecastOverrideFormProps {
  forecast: Forecast;
  onSubmit: (data: ForecastOverrideData) => void;
  onCancel: () => void;
  loading?: boolean;
}

export interface ForecastOverrideData {
  override_menge: number;
  override_grund: string;
}

export function ForecastOverrideForm({
  forecast,
  onSubmit,
  onCancel,
  loading = false,
}: ForecastOverrideFormProps) {
  const originalValue = forecast.prognostizierte_menge;
  const currentOverride = forecast.override_menge;

  const [formData, setFormData] = useState<ForecastOverrideData>({
    override_menge: currentOverride || originalValue,
    override_grund: forecast.override_grund || '',
  });

  const [errors, setErrors] = useState<Partial<Record<keyof ForecastOverrideData, string>>>({});

  const deviation = ((formData.override_menge - originalValue) / originalValue) * 100;
  const isLargeDeviation = Math.abs(deviation) > 20;
  const requiresReason = Math.abs(deviation) > 20;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();

    const newErrors: Partial<Record<keyof ForecastOverrideData, string>> = {};

    if (formData.override_menge <= 0) {
      newErrors.override_menge = 'Menge muss größer als 0 sein';
    }
    if (requiresReason && !formData.override_grund.trim()) {
      newErrors.override_grund = 'Bei großer Abweichung ist eine Begründung erforderlich';
    }

    if (Object.keys(newErrors).length > 0) {
      setErrors(newErrors);
      return;
    }

    onSubmit(formData);
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      {/* Forecast Info */}
      <div className="p-4 bg-gray-50 rounded-lg">
        <div className="flex justify-between mb-2">
          <span className="text-sm text-gray-500">Produkt:</span>
          <span className="font-medium">{forecast.seed?.name || 'Unbekannt'}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-sm text-gray-500">Datum:</span>
          <span className="font-medium">{formatDate(forecast.datum)}</span>
        </div>
      </div>

      {/* Current Forecast */}
      <div className="p-4 border border-gray-200 rounded-lg">
        <p className="text-sm font-medium text-gray-700 mb-2">Aktuelle Prognose</p>
        <p className="text-2xl font-bold text-gray-900">
          {(originalValue / 1000).toFixed(2)} kg
        </p>
        {forecast.konfidenz_untergrenze && forecast.konfidenz_obergrenze && (
          <p className="text-sm text-gray-500 mt-1">
            Konfidenzintervall: {(forecast.konfidenz_untergrenze / 1000).toFixed(2)} -{' '}
            {(forecast.konfidenz_obergrenze / 1000).toFixed(2)} kg
          </p>
        )}
      </div>

      {/* Override Input */}
      <div>
        <Input
          label="Manuelle Anpassung"
          type="number"
          required
          min={0}
          step={0.1}
          value={(formData.override_menge / 1000).toFixed(2)}
          onChange={(e) =>
            setFormData({ ...formData, override_menge: Number(e.target.value) * 1000 })
          }
          error={errors.override_menge}
          suffix="kg"
        />
        {formData.override_menge !== originalValue && (
          <div
            className={`mt-2 flex items-center gap-2 text-sm ${
              deviation > 0 ? 'text-green-600' : 'text-red-600'
            }`}
          >
            {deviation > 0 ? (
              <TrendingUp className="w-4 h-4" />
            ) : (
              <TrendingDown className="w-4 h-4" />
            )}
            <span>
              {deviation > 0 ? '+' : ''}
              {deviation.toFixed(1)}% {deviation > 0 ? 'über' : 'unter'} Prognose
            </span>
          </div>
        )}
      </div>

      {/* Large deviation warning */}
      {isLargeDeviation && (
        <Alert variant="warning">
          <div className="flex items-center gap-2">
            <AlertTriangle className="w-4 h-4" />
            <span>Große Abweichung ({Math.abs(deviation).toFixed(0)}%) - Bitte Grund angeben</span>
          </div>
        </Alert>
      )}

      {/* Reason */}
      <Textarea
        label="Begründung"
        required={requiresReason}
        value={formData.override_grund}
        onChange={(e) => setFormData({ ...formData, override_grund: e.target.value })}
        error={errors.override_grund}
        placeholder="z.B. Sonderbestellung, Event, Markttrend..."
        rows={3}
      />

      {/* Current override info */}
      {currentOverride && currentOverride !== originalValue && (
        <div className="p-3 bg-blue-50 rounded-lg text-sm text-blue-800">
          <p className="font-medium">Bestehender Override:</p>
          <p>
            {(currentOverride / 1000).toFixed(2)} kg
            {forecast.override_grund && ` - "${forecast.override_grund}"`}
          </p>
        </div>
      )}

      {/* Actions */}
      <div className="flex gap-3 pt-4">
        <Button type="button" variant="secondary" onClick={onCancel} disabled={loading}>
          Abbrechen
        </Button>
        <Button type="submit" variant="primary" loading={loading} fullWidth>
          Override speichern
        </Button>
      </div>
    </form>
  );
}
