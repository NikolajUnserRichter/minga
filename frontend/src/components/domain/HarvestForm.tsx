import { useState } from 'react';
import { GrowBatchWithSeed } from '../../types';
import { Input, Textarea, DatePicker, Button, Alert } from '../ui';
import { Scale, AlertTriangle, Star } from 'lucide-react';

interface HarvestFormProps {
  batch: GrowBatchWithSeed;
  onSubmit: (data: HarvestFormData) => void;
  onCancel: () => void;
  loading?: boolean;
}

export interface HarvestFormData {
  ernte_datum: string;
  einheit: 'G' | 'STK';
  menge_gramm: number;
  verlust_gramm: number;
  menge_stueck?: number;
  verlust_stueck?: number;
  stueck_pro_kiste?: number;
  qualitaet_note: number;
  notizen?: string;
}

const EINHEIT_STORAGE_KEY = 'harvest-einheit';
const STK_PRO_KISTE_STORAGE_KEY = 'harvest-stk-pro-kiste';

function loadDefaultEinheit(): 'G' | 'STK' {
  const stored = localStorage.getItem(EINHEIT_STORAGE_KEY);
  return stored === 'G' ? 'G' : 'STK';
}

function loadDefaultStkProKiste(): number {
  const stored = Number(localStorage.getItem(STK_PRO_KISTE_STORAGE_KEY));
  return stored > 0 ? stored : 15;
}

export function HarvestForm({ batch, onSubmit, onCancel, loading = false }: HarvestFormProps) {
  const today = new Date().toISOString().split('T')[0];

  const [einheit, setEinheit] = useState<'G' | 'STK'>(loadDefaultEinheit);
  const [stkProKiste, setStkProKiste] = useState<number>(loadDefaultStkProKiste);

  const [formData, setFormData] = useState({
    ernte_datum: today,
    menge: 0,
    verlust: 0,
    qualitaet_note: 4,
    notizen: '',
  });

  const [errors, setErrors] = useState<Partial<Record<string, string>>>({});

  // Erwartung: bei Stk aus Kistenformat, bei g aus dem hinterlegten Ertrag pro Tray
  const expectedYield = einheit === 'STK'
    ? batch.tray_anzahl * stkProKiste
    : batch.tray_anzahl * (batch.seed?.ertrag_gramm_pro_tray || 350);
  const tolerance = expectedYield * 0.05; // 5% tolerance
  const unitLabel = einheit === 'STK' ? 'Stk' : 'g';

  const isWithinExpectation =
    formData.menge >= expectedYield - tolerance &&
    formData.menge <= expectedYield + tolerance;

  const lossPercent =
    formData.menge > 0
      ? ((formData.verlust / (formData.menge + formData.verlust)) * 100).toFixed(1)
      : '0';

  const switchEinheit = (next: 'G' | 'STK') => {
    if (next === einheit) return;
    setEinheit(next);
    localStorage.setItem(EINHEIT_STORAGE_KEY, next);
    setFormData({ ...formData, menge: 0, verlust: 0 });
    setErrors({});
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();

    const newErrors: Partial<Record<string, string>> = {};

    if (!formData.ernte_datum) {
      newErrors.ernte_datum = 'Erntedatum ist erforderlich';
    }
    if (formData.menge <= 0) {
      newErrors.menge = 'Menge muss größer als 0 sein';
    }
    if (formData.verlust < 0) {
      newErrors.verlust = 'Verlust kann nicht negativ sein';
    }
    if (einheit === 'STK' && stkProKiste <= 0) {
      newErrors.stk_pro_kiste = 'Stk pro Kiste muss größer als 0 sein';
    }
    if (formData.qualitaet_note < 1 || formData.qualitaet_note > 5) {
      newErrors.qualitaet_note = 'Qualität muss zwischen 1 und 5 liegen';
    }

    if (Object.keys(newErrors).length > 0) {
      setErrors(newErrors);
      return;
    }

    if (einheit === 'STK') {
      localStorage.setItem(STK_PRO_KISTE_STORAGE_KEY, String(stkProKiste));
    }

    onSubmit({
      ernte_datum: formData.ernte_datum,
      einheit,
      // Bei Stück-Ernten gibt es kein Gewicht — Backend speichert menge_gramm=0
      menge_gramm: einheit === 'G' ? formData.menge : 0,
      verlust_gramm: einheit === 'G' ? formData.verlust : 0,
      menge_stueck: einheit === 'STK' ? formData.menge : undefined,
      verlust_stueck: einheit === 'STK' ? formData.verlust : undefined,
      stueck_pro_kiste: einheit === 'STK' ? stkProKiste : undefined,
      qualitaet_note: formData.qualitaet_note,
      notizen: formData.notizen,
    });
  };

  const qualityLabels = ['Mangelhaft', 'Ausreichend', 'Gut', 'Sehr gut', 'Ausgezeichnet'];

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      {/* Batch Info */}
      <div className="p-4 bg-gray-50 dark:bg-gray-700/50 rounded-lg">
        <p className="text-sm text-gray-500 dark:text-gray-400">Charge</p>
        <p className="font-semibold">{batch.seed?.name || 'Unbekannt'}</p>
        <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
          #{batch.id.slice(0, 8)} | {batch.tray_anzahl} Kisten | Regal {batch.regal_position || '-'}
        </p>
      </div>

      {/* Date */}
      <DatePicker
        label="Ernte-Datum"
        required
        value={formData.ernte_datum}
        onChange={(e) => setFormData({ ...formData, ernte_datum: e.target.value })}
        error={errors.ernte_datum}
        max={today}
      />

      {/* Unit toggle */}
      <div className="form-group">
        <label className="label">Erfassung in</label>
        <div className="flex gap-2">
          {([['STK', 'Stück (ganze Schalen)'], ['G', 'Gramm (geschnitten)']] as const).map(([value, label]) => (
            <button
              key={value}
              type="button"
              onClick={() => switchEinheit(value)}
              className={`flex-1 p-2 rounded-lg border-2 text-sm transition-colors ${einheit === value
                ? 'border-minga-500 bg-minga-50 dark:bg-minga-900/30 font-medium'
                : 'border-gray-200 dark:border-gray-700 hover:border-gray-300 dark:hover:border-gray-600'
                }`}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      {/* Kistenformat (nur bei Stück) */}
      {einheit === 'STK' && (
        <div className="form-group">
          <label className="label">Stk pro Anzuchtkiste</label>
          <div className="flex gap-2 items-center">
            {[15, 21].map((n) => (
              <button
                key={n}
                type="button"
                onClick={() => setStkProKiste(n)}
                className={`px-4 py-2 rounded-lg border-2 text-sm transition-colors ${stkProKiste === n
                  ? 'border-minga-500 bg-minga-50 dark:bg-minga-900/30 font-medium'
                  : 'border-gray-200 dark:border-gray-700 hover:border-gray-300 dark:hover:border-gray-600'
                  }`}
              >
                {n} Stk{n === 15 ? ' (Standard)' : ''}
              </button>
            ))}
            <div className="w-24">
              <Input
                type="number"
                value={stkProKiste || ''}
                onChange={(e) => setStkProKiste(Number(e.target.value))}
                error={errors.stk_pro_kiste}
                min={1}
                step={1}
              />
            </div>
          </div>
        </div>
      )}

      {/* Yield */}
      <div>
        <Input
          label="Ernte-Menge"
          type="number"
          required
          value={formData.menge || ''}
          onChange={(e) => setFormData({ ...formData, menge: Number(e.target.value) })}
          error={errors.menge}
          endIcon={unitLabel}
          hint={`Erwartet: ${expectedYield}${unitLabel} (±5%)`}
        />
        {formData.menge > 0 && (
          <div className={`mt-2 text-sm ${isWithinExpectation ? 'text-green-600 dark:text-green-400' : 'text-amber-600 dark:text-amber-400'}`}>
            {isWithinExpectation ? (
              <span className="flex items-center gap-1">
                <Scale className="w-4 h-4" />
                Im Rahmen der Erwartung
              </span>
            ) : (
              <span className="flex items-center gap-1">
                <AlertTriangle className="w-4 h-4" />
                Abweichung: {(((formData.menge - expectedYield) / expectedYield) * 100).toFixed(1)}%
              </span>
            )}
          </div>
        )}
      </div>

      {/* Loss */}
      <div>
        <Input
          label="Verlust-Menge (optional)"
          type="number"
          value={formData.verlust || ''}
          onChange={(e) => setFormData({ ...formData, verlust: Number(e.target.value) })}
          error={errors.verlust}
          endIcon={unitLabel}
        />
        {formData.verlust > 0 && (
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">({lossPercent}% Verlust)</p>
        )}
      </div>

      {/* Quality */}
      <div className="form-group">
        <label className="label">Qualität</label>
        <div className="flex gap-2">
          {[1, 2, 3, 4, 5].map((rating) => (
            <button
              key={rating}
              type="button"
              onClick={() => setFormData({ ...formData, qualitaet_note: rating })}
              className={`flex-1 p-3 rounded-lg border-2 transition-colors ${formData.qualitaet_note === rating
                ? 'border-minga-500 bg-minga-50 dark:bg-minga-900/30'
                : 'border-gray-200 dark:border-gray-700 hover:border-gray-300 dark:border-gray-600'
                }`}
            >
              <Star
                className={`w-5 h-5 mx-auto ${formData.qualitaet_note >= rating ? 'text-amber-400 fill-amber-400' : 'text-gray-300'
                  }`}
              />
              <span className="text-xs text-gray-600 dark:text-gray-400 mt-1 block">{rating}</span>
            </button>
          ))}
        </div>
        <p className="text-sm text-gray-500 dark:text-gray-400 mt-2">
          {qualityLabels[formData.qualitaet_note - 1]}
        </p>
      </div>

      {/* Notes */}
      <Textarea
        label="Notizen (optional)"
        value={formData.notizen || ''}
        onChange={(e) => setFormData({ ...formData, notizen: e.target.value })}
        placeholder="Beobachtungen zur Ernte..."
        rows={3}
      />

      {/* Large deviation warning */}
      {formData.menge > 0 && Math.abs(formData.menge - expectedYield) > tolerance * 2 && (
        <Alert variant="warning" title="Große Abweichung">
          Die eingegebene Menge weicht stark von der erwarteten Menge ab. Bitte überprüfen Sie die Eingabe.
        </Alert>
      )}

      {/* Actions */}
      <div className="flex gap-3 pt-4">
        <Button type="button" variant="secondary" onClick={onCancel} disabled={loading}>
          Abbrechen
        </Button>
        <Button type="submit" variant="success" loading={loading} fullWidth>
          Ernte speichern
        </Button>
      </div>
    </form>
  );
}
