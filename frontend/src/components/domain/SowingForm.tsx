import { useState, useEffect } from 'react';
import { Seed } from '../../types';
import { Input, Select, DatePicker, Button, Alert, SelectOption } from '../ui';
import { Sprout, Calendar, Layers, MapPin, Scale } from 'lucide-react';

interface SowingFormProps {
  seeds: Seed[];
  onSubmit: (data: SowingFormData) => void;
  onCancel: () => void;
  loading?: boolean;
  defaultSeedId?: string;
}

export interface SowingFormData {
  seed_id: string;
  seed_batch_id?: string;
  tray_anzahl: number;
  aussaat_datum: string;
  regal_position: string;
}

// Mock seed batches - in real app, fetch from API
interface SeedBatch {
  id: string;
  charge_nummer: string;
  verbleibend_gramm: number;
  mhd?: string;
}

export function SowingForm({
  seeds,
  onSubmit,
  onCancel,
  loading = false,
  defaultSeedId,
}: SowingFormProps) {
  const today = new Date().toISOString().split('T')[0];
  const SEED_PER_TRAY = 12; // grams per tray

  const [formData, setFormData] = useState<SowingFormData>({
    seed_id: defaultSeedId || '',
    seed_batch_id: '',
    tray_anzahl: 1,
    aussaat_datum: today,
    regal_position: '',
  });

  const [errors, setErrors] = useState<Partial<Record<keyof SowingFormData, string>>>({});
  const [seedBatches, setSeedBatches] = useState<SeedBatch[]>([]);

  const selectedSeed = seeds.find((s) => s.id === formData.seed_id);
  const selectedBatch = seedBatches.find((b) => b.id === formData.seed_batch_id);

  // Calculate expected values
  const seedRequired = formData.tray_anzahl * SEED_PER_TRAY;
  const expectedYield = selectedSeed
    ? (formData.tray_anzahl * selectedSeed.ertrag_gramm_pro_tray * (1 - selectedSeed.verlustquote_prozent / 100)) / 1000
    : 0;

  const harvestWindow = selectedSeed
    ? {
        min: addDays(formData.aussaat_datum, selectedSeed.keimdauer_tage + selectedSeed.erntefenster_min_tage),
        optimal: addDays(formData.aussaat_datum, selectedSeed.keimdauer_tage + selectedSeed.erntefenster_optimal_tage),
        max: addDays(formData.aussaat_datum, selectedSeed.keimdauer_tage + selectedSeed.erntefenster_max_tage),
        keimungEnds: addDays(formData.aussaat_datum, selectedSeed.keimdauer_tage),
      }
    : null;

  const hasEnoughSeed = selectedBatch ? selectedBatch.verbleibend_gramm >= seedRequired : true;

  // Mock loading seed batches when seed changes
  useEffect(() => {
    if (formData.seed_id) {
      // In real app: fetch from API
      setSeedBatches([
        {
          id: 'batch-1',
          charge_nummer: 'SB-2024-0012',
          verbleibend_gramm: 5200,
          mhd: '2026-06-15',
        },
        {
          id: 'batch-2',
          charge_nummer: 'SB-2024-0008',
          verbleibend_gramm: 2100,
          mhd: '2026-04-01',
        },
      ]);
    } else {
      setSeedBatches([]);
    }
    setFormData((prev) => ({ ...prev, seed_batch_id: '' }));
  }, [formData.seed_id]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();

    const newErrors: Partial<Record<keyof SowingFormData, string>> = {};

    if (!formData.seed_id) {
      newErrors.seed_id = 'Saatgut ist erforderlich';
    }
    if (formData.tray_anzahl <= 0) {
      newErrors.tray_anzahl = 'Anzahl muss größer als 0 sein';
    }
    if (!formData.aussaat_datum) {
      newErrors.aussaat_datum = 'Aussaat-Datum ist erforderlich';
    }
    if (!hasEnoughSeed) {
      newErrors.seed_batch_id = 'Nicht genügend Saatgut in dieser Charge';
    }

    if (Object.keys(newErrors).length > 0) {
      setErrors(newErrors);
      return;
    }

    onSubmit(formData);
  };

  const seedOptions: SelectOption[] = seeds
    .filter((s) => s.aktiv)
    .map((s) => ({
      value: s.id,
      label: `${s.name}${s.sorte ? ` - ${s.sorte}` : ''}`,
    }));

  const batchOptions: SelectOption[] = seedBatches.map((b) => ({
    value: b.id,
    label: `#${b.charge_nummer} (${(b.verbleibend_gramm / 1000).toFixed(1)} kg, MHD: ${b.mhd || 'k.A.'})`,
    disabled: b.verbleibend_gramm < seedRequired,
  }));

  const regalOptions: SelectOption[] = [
    { value: 'A1', label: 'Regal A1' },
    { value: 'A2', label: 'Regal A2' },
    { value: 'A3', label: 'Regal A3' },
    { value: 'B1', label: 'Regal B1' },
    { value: 'B2', label: 'Regal B2' },
    { value: 'C1', label: 'Regal C1' },
    { value: 'C2', label: 'Regal C2' },
  ];

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      {/* Seed Selection */}
      <Select
        label="Saatgut"
        required
        options={seedOptions}
        value={formData.seed_id}
        onChange={(e) => setFormData({ ...formData, seed_id: e.target.value })}
        error={errors.seed_id}
        placeholder="Saatgut auswählen..."
      />

      {/* Seed Batch Selection */}
      {formData.seed_id && batchOptions.length > 0 && (
        <Select
          label="Saatgut-Charge"
          options={batchOptions}
          value={formData.seed_batch_id}
          onChange={(e) => setFormData({ ...formData, seed_batch_id: e.target.value })}
          error={errors.seed_batch_id}
          placeholder="Charge auswählen (optional)..."
        />
      )}

      {/* Tray Count */}
      <div>
        <Input
          label="Anzahl Trays"
          type="number"
          required
          min={1}
          value={formData.tray_anzahl}
          onChange={(e) => setFormData({ ...formData, tray_anzahl: Number(e.target.value) })}
          error={errors.tray_anzahl}
        />
        <p className="text-sm text-gray-500 mt-1">
          <span className="inline-flex items-center gap-1">
            <Scale className="w-3 h-3" />
            {seedRequired}g Saatgut benötigt
          </span>
        </p>
        {selectedBatch && !hasEnoughSeed && (
          <p className="text-sm text-red-600 mt-1">
            Nicht genügend Saatgut in dieser Charge ({selectedBatch.verbleibend_gramm}g verfügbar)
          </p>
        )}
      </div>

      {/* Date */}
      <DatePicker
        label="Aussaat-Datum"
        required
        value={formData.aussaat_datum}
        onChange={(e) => setFormData({ ...formData, aussaat_datum: e.target.value })}
        error={errors.aussaat_datum}
        min={today}
      />

      {/* Shelf Position */}
      <Select
        label="Regal-Position"
        options={regalOptions}
        value={formData.regal_position}
        onChange={(e) => setFormData({ ...formData, regal_position: e.target.value })}
        placeholder="Position auswählen (optional)..."
        hint="45 Plätze verfügbar in diesem Bereich"
      />

      {/* Preview */}
      {selectedSeed && harvestWindow && (
        <div className="p-4 bg-minga-50 rounded-lg border border-minga-200">
          <h4 className="font-medium text-minga-800 mb-3">Vorschau</h4>
          <div className="space-y-2 text-sm">
            <div className="flex justify-between">
              <span className="text-gray-600">Keimung endet:</span>
              <span className="font-medium">{formatDateDE(harvestWindow.keimungEnds)}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-600">Erntefenster:</span>
              <span className="font-medium">
                {formatDateDE(harvestWindow.min)} - {formatDateDE(harvestWindow.max)}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-600">Optimale Ernte:</span>
              <span className="font-medium text-minga-700">{formatDateDE(harvestWindow.optimal)}</span>
            </div>
            <div className="flex justify-between pt-2 border-t border-minga-200">
              <span className="text-gray-600">Erwarteter Ertrag:</span>
              <span className="font-medium">~{expectedYield.toFixed(2)} kg (±5%)</span>
            </div>
          </div>
        </div>
      )}

      {/* Actions */}
      <div className="flex gap-3 pt-4">
        <Button type="button" variant="secondary" onClick={onCancel} disabled={loading}>
          Abbrechen
        </Button>
        <Button type="submit" variant="primary" loading={loading} fullWidth>
          <Sprout className="w-4 h-4" />
          Aussaat starten
        </Button>
      </div>
    </form>
  );
}

// Helper functions
function addDays(dateStr: string, days: number): string {
  const date = new Date(dateStr);
  date.setDate(date.getDate() + days);
  return date.toISOString().split('T')[0];
}

function formatDateDE(dateStr: string): string {
  const date = new Date(dateStr);
  return date.toLocaleDateString('de-DE', { day: '2-digit', month: '2-digit', year: 'numeric' });
}
