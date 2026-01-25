import { useState } from 'react';
import { GrowBatch } from '../../types';
import { Input, Textarea, DatePicker, Button, Alert, formatDate } from '../ui';
import { Scale, AlertTriangle, Star } from 'lucide-react';

interface HarvestFormProps {
  batch: GrowBatch;
  onSubmit: (data: HarvestFormData) => void;
  onCancel: () => void;
  loading?: boolean;
}

export interface HarvestFormData {
  ernte_datum: string;
  menge_gramm: number;
  verlust_gramm: number;
  qualitaet_note: number;
  notizen?: string;
}

export function HarvestForm({ batch, onSubmit, onCancel, loading = false }: HarvestFormProps) {
  const today = new Date().toISOString().split('T')[0];
  const expectedYield = batch.tray_anzahl * (batch.seed?.ertrag_gramm_pro_tray || 350);
  const tolerance = expectedYield * 0.05; // 5% tolerance

  const [formData, setFormData] = useState<HarvestFormData>({
    ernte_datum: today,
    menge_gramm: 0,
    verlust_gramm: 0,
    qualitaet_note: 4,
    notizen: '',
  });

  const [errors, setErrors] = useState<Partial<Record<keyof HarvestFormData, string>>>({});

  const isWithinExpectation =
    formData.menge_gramm >= expectedYield - tolerance &&
    formData.menge_gramm <= expectedYield + tolerance;

  const lossPercent =
    formData.menge_gramm > 0
      ? ((formData.verlust_gramm / (formData.menge_gramm + formData.verlust_gramm)) * 100).toFixed(1)
      : '0';

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();

    const newErrors: Partial<Record<keyof HarvestFormData, string>> = {};

    if (!formData.ernte_datum) {
      newErrors.ernte_datum = 'Erntedatum ist erforderlich';
    }
    if (formData.menge_gramm <= 0) {
      newErrors.menge_gramm = 'Menge muss größer als 0 sein';
    }
    if (formData.verlust_gramm < 0) {
      newErrors.verlust_gramm = 'Verlust kann nicht negativ sein';
    }
    if (formData.qualitaet_note < 1 || formData.qualitaet_note > 5) {
      newErrors.qualitaet_note = 'Qualität muss zwischen 1 und 5 liegen';
    }

    if (Object.keys(newErrors).length > 0) {
      setErrors(newErrors);
      return;
    }

    onSubmit(formData);
  };

  const qualityLabels = ['Mangelhaft', 'Ausreichend', 'Gut', 'Sehr gut', 'Ausgezeichnet'];

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      {/* Batch Info */}
      <div className="p-4 bg-gray-50 rounded-lg">
        <p className="text-sm text-gray-500">Charge</p>
        <p className="font-semibold">{batch.seed?.name || 'Unbekannt'}</p>
        <p className="text-sm text-gray-500 mt-1">
          #{batch.id.slice(0, 8)} | {batch.tray_anzahl} Trays | Regal {batch.regal_position || '-'}
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

      {/* Yield */}
      <div>
        <Input
          label="Ernte-Menge"
          type="number"
          required
          value={formData.menge_gramm || ''}
          onChange={(e) => setFormData({ ...formData, menge_gramm: Number(e.target.value) })}
          error={errors.menge_gramm}
          suffix="g"
          hint={`Erwartet: ${expectedYield}g (±5%)`}
        />
        {formData.menge_gramm > 0 && (
          <div className={`mt-2 text-sm ${isWithinExpectation ? 'text-green-600' : 'text-amber-600'}`}>
            {isWithinExpectation ? (
              <span className="flex items-center gap-1">
                <Scale className="w-4 h-4" />
                Im Rahmen der Erwartung
              </span>
            ) : (
              <span className="flex items-center gap-1">
                <AlertTriangle className="w-4 h-4" />
                Abweichung: {(((formData.menge_gramm - expectedYield) / expectedYield) * 100).toFixed(1)}%
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
          value={formData.verlust_gramm || ''}
          onChange={(e) => setFormData({ ...formData, verlust_gramm: Number(e.target.value) })}
          error={errors.verlust_gramm}
          suffix="g"
        />
        {formData.verlust_gramm > 0 && (
          <p className="text-sm text-gray-500 mt-1">({lossPercent}% Verlust)</p>
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
              className={`flex-1 p-3 rounded-lg border-2 transition-colors ${
                formData.qualitaet_note === rating
                  ? 'border-minga-500 bg-minga-50'
                  : 'border-gray-200 hover:border-gray-300'
              }`}
            >
              <Star
                className={`w-5 h-5 mx-auto ${
                  formData.qualitaet_note >= rating ? 'text-amber-400 fill-amber-400' : 'text-gray-300'
                }`}
              />
              <span className="text-xs text-gray-600 mt-1 block">{rating}</span>
            </button>
          ))}
        </div>
        <p className="text-sm text-gray-500 mt-2">
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
      {formData.menge_gramm > 0 && Math.abs(formData.menge_gramm - expectedYield) > tolerance * 2 && (
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
