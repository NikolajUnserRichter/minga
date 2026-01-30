import { ProductionSuggestionWithSeed } from '../../types';
import { SuggestionStatusBadge, formatDate } from '../ui';
import { Sprout, Calendar, Layers, AlertTriangle, Check, X, Scale } from 'lucide-react';

interface ProductionSuggestionCardProps {
  suggestion: ProductionSuggestionWithSeed;
  onApprove?: () => void;
  onReject?: () => void;
  onAdjust?: () => void;
  onClick?: () => void;
}

export function ProductionSuggestionCard({
  suggestion,
  onApprove,
  onReject,
  onAdjust,
  onClick,
}: ProductionSuggestionCardProps) {
  const isPending = suggestion.status === 'VORGESCHLAGEN';
  const hasWarnings = (suggestion.warnungen || []).length > 0;

  return (
    <div
      className={`card ${hasWarnings ? 'border-amber-300' : ''} ${onClick ? 'cursor-pointer card-hover' : ''
        }`}
      onClick={onClick}
    >
      <div className="card-body">
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-minga-50 rounded-lg">
              <Sprout className="w-5 h-5 text-minga-600" />
            </div>
            <div>
              <h3 className="font-semibold text-gray-900">{suggestion.seed?.name || 'Unbekannt'}</h3>
              <SuggestionStatusBadge status={suggestion.status} />
            </div>
          </div>
        </div>

        {/* Warnings */}
        {(suggestion.warnungen || []).length > 0 && (
          <div className="mt-4 space-y-2">
            {(suggestion.warnungen || []).map((warning, idx) => (
              <div key={idx} className="flex items-start gap-2 p-2 bg-amber-50 rounded-lg text-sm">
                <AlertTriangle className="w-4 h-4 text-amber-600 flex-shrink-0 mt-0.5" />
                <span className="text-amber-800">{formatWarning(warning.typ)}</span>
              </div>
            ))}
          </div>
        )}

        {/* Details */}
        <div className="mt-4 grid grid-cols-2 gap-3">
          <div className="flex items-center gap-2 text-sm text-gray-600">
            <Layers className="w-4 h-4 text-gray-400" />
            <span>{suggestion.empfohlene_trays} Trays</span>
          </div>
          <div className="flex items-center gap-2 text-sm text-gray-600">
            <Scale className="w-4 h-4 text-gray-400" />
            <span>~{((suggestion.empfohlene_trays * 350) / 1000).toFixed(1)} kg</span>
          </div>
          <div className="flex items-center gap-2 text-sm text-gray-600">
            <Calendar className="w-4 h-4 text-gray-400" />
            <span>Aussaat: {formatDate(suggestion.aussaat_datum)}</span>
          </div>
          <div className="flex items-center gap-2 text-sm text-gray-600">
            <Calendar className="w-4 h-4 text-gray-400" />
            <span>Ernte: {formatDate(suggestion.erwartete_ernte_datum)}</span>
          </div>
        </div>

        {/* Forecast reference */}
        {suggestion.forecast_id && (
          <p className="text-xs text-gray-500 mt-3">
            Basierend auf Forecast-Prognose
          </p>
        )}

        {/* Actions */}
        {isPending && (onApprove || onReject || onAdjust) && (
          <div className="mt-4 pt-4 border-t border-gray-100 flex gap-2">
            {onApprove && (
              <button
                className="btn btn-success btn-sm flex-1"
                onClick={(e) => {
                  e.stopPropagation();
                  onApprove();
                }}
              >
                <Check className="w-4 h-4" />
                Genehmigen
              </button>
            )}
            {onAdjust && (
              <button
                className="btn btn-secondary btn-sm"
                onClick={(e) => {
                  e.stopPropagation();
                  onAdjust();
                }}
              >
                Anpassen
              </button>
            )}
            {onReject && (
              <button
                className="btn btn-ghost btn-sm text-red-600 hover:bg-red-50"
                onClick={(e) => {
                  e.stopPropagation();
                  onReject();
                }}
              >
                <X className="w-4 h-4" />
                Ablehnen
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

// Helper to format warning messages
function formatWarning(warning: string): string {
  const warningMap: Record<string, string> = {
    UNTERDECKUNG: 'Mögliche Unterdeckung - Nachfrage übersteigt Kapazität',
    UEBERPRODUKTION: 'Mögliche Überproduktion - Mehr als prognostizierter Bedarf',
    KAPAZITAET: 'Kapazitätsengpass - Regalplätze werden knapp',
    SAATGUT_KNAPP: 'Saatgut wird knapp - Nachbestellung prüfen',
  };
  return warningMap[warning] || warning;
}

// Compact row version
interface ProductionSuggestionRowProps {
  suggestion: ProductionSuggestionWithSeed;
  onApprove?: () => void;
  onReject?: () => void;
}

export function ProductionSuggestionRow({
  suggestion,
  onApprove,
  onReject,
}: ProductionSuggestionRowProps) {
  const isPending = suggestion.status === 'VORGESCHLAGEN';
  const hasWarnings = (suggestion.warnungen || []).length > 0;

  return (
    <div
      className={`flex items-center justify-between p-4 bg-white border rounded-lg ${hasWarnings ? 'border-amber-300 bg-amber-50/30' : 'border-gray-200'
        }`}
    >
      <div className="flex items-center gap-4">
        {hasWarnings && <AlertTriangle className="w-5 h-5 text-amber-500" />}
        <div>
          <p className="font-medium">{suggestion.seed?.name}</p>
          <p className="text-sm text-gray-500">
            {suggestion.empfohlene_trays} Trays | Aussaat: {formatDate(suggestion.aussaat_datum)}
          </p>
        </div>
      </div>

      <div className="flex items-center gap-3">
        <span className="text-sm text-gray-500">
          Ernte: {formatDate(suggestion.erwartete_ernte_datum)}
        </span>
        <SuggestionStatusBadge status={suggestion.status} />

        {isPending && (
          <div className="flex gap-1">
            {onApprove && (
              <button
                className="btn btn-success btn-sm btn-icon"
                onClick={onApprove}
                aria-label="Genehmigen"
              >
                <Check className="w-4 h-4" />
              </button>
            )}
            {onReject && (
              <button
                className="btn btn-ghost btn-sm btn-icon text-red-600"
                onClick={onReject}
                aria-label="Ablehnen"
              >
                <X className="w-4 h-4" />
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
