import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Seed } from '../../types';
import { seedsApi, capacityApi } from '../../services/api';
import { Input, Select, DatePicker, Button, SelectOption } from '../ui';
import { Sprout, Scale } from 'lucide-react';

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
  // Soaking-Workflow: optional, sonst direkte Aussaat heute
  needs_soaking?: boolean;
  soaking_started_at?: string; // ISO datetime-local
  soaking_employee?: string;
}

export function SowingForm({
  seeds,
  onSubmit,
  onCancel,
  loading = false,
  defaultSeedId,
}: SowingFormProps) {
  const today = new Date().toISOString().split('T')[0];
  // Default Saatgut-Dichte falls kein GrowPlan/Seed-Wert hinterlegt ist.
  // TODO: zukünftig auf Seed bzw. GrowPlan hinterlegt
  const DEFAULT_SEED_PER_TRAY = 12;

  // Default-Einweich-Zeit: jetzt (für "datetime-local"-Input)
  const nowLocal = (() => {
    const d = new Date();
    d.setMinutes(d.getMinutes() - d.getTimezoneOffset());
    return d.toISOString().slice(0, 16);
  })();

  const [formData, setFormData] = useState<SowingFormData>({
    seed_id: defaultSeedId || '',
    seed_batch_id: '',
    tray_anzahl: 1,
    aussaat_datum: today,
    regal_position: '',
    needs_soaking: false,
    soaking_started_at: nowLocal,
    soaking_employee: '',
  });

  const [errors, setErrors] = useState<Partial<Record<keyof SowingFormData, string>>>({});

  const selectedSeed = seeds.find((s) => s.id === formData.seed_id);

  const { data: seedBatches = [] } = useQuery({
    queryKey: ['seed-batches', formData.seed_id],
    queryFn: () => seedsApi.listBatches(formData.seed_id),
    enabled: !!formData.seed_id,
  });

  const { data: capacities = [] } = useQuery({
    queryKey: ['capacity'],
    queryFn: () => capacityApi.list(),
  });

  const selectedBatch = seedBatches.find((b) => b.id === formData.seed_batch_id);

  // Saatgut-Dichte: vom Seed-Stammdatensatz (Sortenebene) — Fallback auf Default
  const seedPerTray = selectedSeed?.saatgut_pro_einheit_gramm ?? DEFAULT_SEED_PER_TRAY;
  const seedRequired = formData.tray_anzahl * seedPerTray;
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

  // Reset batch on seed change
  if (formData.seed_id && formData.seed_batch_id && !seedBatches.find((b) => b.id === formData.seed_batch_id)) {
    // batches changed, current selection invalid
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();

    const newErrors: Partial<Record<keyof SowingFormData, string>> = {};

    if (!formData.seed_id) {
      newErrors.seed_id = 'Saatgut ist erforderlich';
    }
    if (!formData.seed_batch_id) {
      newErrors.seed_batch_id = 'Bitte eine Saatgut-Charge wählen (ggf. erst im Lager erfassen)';
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

  const batchOptions: SelectOption[] = seedBatches.map((b) => {
    const lieferDate = b.lieferdatum ? new Date(b.lieferdatum).toLocaleDateString('de-DE') : 'k.A.';
    const bioFlag = b.bio_zertifiziert ? ' BIO' : '';
    return {
      value: b.id,
      label: `#${b.charge_nummer}${bioFlag} (${(b.verbleibend_gramm / 1000).toFixed(2)} kg · geliefert ${lieferDate}${b.mhd ? `, MHD ${new Date(b.mhd).toLocaleDateString('de-DE')}` : ''})`,
      disabled: b.verbleibend_gramm < seedRequired,
    };
  });

  // Regal-Positionen aus Capacity (Typ REGAL) — fallback wenn keine konfiguriert
  const regalCapacities = capacities.filter((c: any) => c.ressource_typ === 'REGAL');
  const regalOptions: SelectOption[] = regalCapacities.length
    ? regalCapacities.map((c: any) => ({
        value: c.name || c.id,
        label: `${c.name || c.id} — ${c.verfuegbar} von ${c.max_kapazitaet} frei`,
        disabled: c.verfuegbar <= 0,
      }))
    : [
        { value: '', label: 'Keine Regal-Kapazitäten gepflegt — unter Produktion → Kapazitäten anlegen' },
      ];

  const selectedRegal = regalCapacities.find((c: any) => (c.name || c.id) === formData.regal_position);
  const regalHint = selectedRegal
    ? `${selectedRegal.verfuegbar} von ${selectedRegal.max_kapazitaet} Plätzen frei`
    : (regalCapacities.length === 0 ? 'Keine Regal-Kapazitäten gepflegt — bitte unter Produktion → Kapazitäten anlegen' : 'Position wählen');

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
          label="Saatgut-Charge *"
          options={batchOptions}
          value={formData.seed_batch_id}
          onChange={(e) => setFormData({ ...formData, seed_batch_id: e.target.value })}
          error={errors.seed_batch_id}
          placeholder="Charge auswählen..."
        />
      )}
      {formData.seed_id && batchOptions.length === 0 && (
        <div className="text-sm text-amber-700 dark:text-amber-300 bg-amber-50 dark:bg-amber-900/20 p-3 rounded border border-amber-200 dark:border-amber-800">
          ⚠️ Für diese Sorte ist noch keine Saatgut-Charge im Lager.
          Bitte erst unter <b>Lager → Wareneingang Saatgut</b> eine Charge erfassen.
        </div>
      )}

      {/* Tray Count */}
      <div>
        <Input
          label="Anzahl Kisten"
          type="number"
          required
          min={1}
          value={formData.tray_anzahl}
          onChange={(e) => setFormData({ ...formData, tray_anzahl: Number(e.target.value) })}
          error={errors.tray_anzahl}
        />
        <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
          <span className="inline-flex items-center gap-1">
            <Scale className="w-3 h-3" />
            {seedRequired}g Saatgut benötigt ({seedPerTray} g/Kiste{!selectedSeed?.saatgut_pro_einheit_gramm && ' — Default, Sorte konfigurieren'})
          </span>
        </p>
        {selectedBatch && !hasEnoughSeed && (
          <p className="text-sm text-red-600 dark:text-red-400 mt-1">
            Nicht genügend Saatgut in dieser Charge ({selectedBatch.verbleibend_gramm}g verfügbar)
          </p>
        )}
      </div>

      {/* Soaking-Workflow */}
      <div className="border rounded-lg p-3 dark:border-gray-700 bg-gray-50/40 dark:bg-gray-800/40 space-y-2">
        <label className="flex items-center gap-2 text-sm font-medium text-gray-700 dark:text-gray-300">
          <input
            type="checkbox"
            checked={formData.needs_soaking || false}
            onChange={(e) => setFormData({ ...formData, needs_soaking: e.target.checked })}
            className="rounded"
          />
          💧 Saatgut wird vor der Aussaat eingeweicht (über Nacht)
        </label>
        {formData.needs_soaking && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-2 pl-6">
            <Input
              label="Einweichen gestartet am"
              type="datetime-local"
              value={formData.soaking_started_at || ''}
              onChange={(e) => setFormData({ ...formData, soaking_started_at: e.target.value })}
            />
            <Input
              label="Mitarbeiter:in"
              placeholder="z.B. Anna"
              value={formData.soaking_employee || ''}
              onChange={(e) => setFormData({ ...formData, soaking_employee: e.target.value })}
            />
            <p className="text-xs text-gray-500 dark:text-gray-400 md:col-span-2">
              Charge wird heute angelegt. Aussaat startet morgen — das
              SOAKING_STARTED-Event wird sofort in die Timeline geschrieben.
              Über die Timeline kannst du dann morgen „Aussaat gestartet" und
              „Aussaat abgeschlossen" eintragen.
            </p>
          </div>
        )}
      </div>

      {/* Date */}
      <DatePicker
        label={formData.needs_soaking ? "Geplantes Aussaat-Datum (üblicherweise morgen)" : "Aussaat-Datum"}
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
        hint={regalHint}
      />

      {/* Preview */}
      {selectedSeed && harvestWindow && (
        <div className="p-4 bg-minga-50 dark:bg-minga-900/30 rounded-lg border border-minga-200">
          <h4 className="font-medium text-minga-800 mb-3">Vorschau</h4>
          <div className="space-y-2 text-sm">
            <div className="flex justify-between">
              <span className="text-gray-600 dark:text-gray-400">Keimung endet:</span>
              <span className="font-medium">{formatDateDE(harvestWindow.keimungEnds)}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-600 dark:text-gray-400">Erntefenster:</span>
              <span className="font-medium">
                {formatDateDE(harvestWindow.min)} - {formatDateDE(harvestWindow.max)}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-600 dark:text-gray-400">Optimale Ernte:</span>
              <span className="font-medium text-minga-700">{formatDateDE(harvestWindow.optimal)}</span>
            </div>
            <div className="flex justify-between pt-2 border-t border-minga-200">
              <span className="text-gray-600 dark:text-gray-400">Erwarteter Ertrag:</span>
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
