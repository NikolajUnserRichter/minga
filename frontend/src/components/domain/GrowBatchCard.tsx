import { GrowBatch, GrowBatchStatus, GrowBatchWithSeed } from '../../types';
import { GrowBatchStatusBadge, formatDate, getRelativeDate } from '../ui';
import { Layers, MapPin, Calendar, Scale, AlertCircle, Scissors, Printer } from 'lucide-react';

interface GrowBatchCardProps {
  batch: GrowBatchWithSeed;
  onHarvest?: () => void;
  onStatusChange?: (status: GrowBatchStatus) => void;
  onClick?: () => void;
  onPrintLabel?: () => void;
  showActions?: boolean;
}

export function GrowBatchCard({
  batch,
  onHarvest,
  onClick,
  onPrintLabel,
  showActions = true,
}: GrowBatchCardProps) {
  const isHarvestReady = batch.status === 'ERNTEREIF';
  const currentDay = calculateCurrentDay(batch);
  const expectedYield = batch.tray_anzahl * 350; // Assuming 350g average per tray

  return (
    <div
      className={`card ${isHarvestReady ? 'border-green-300 bg-green-50/30' : ''} ${onClick ? 'cursor-pointer card-hover' : ''
        }`}
      onClick={onClick}
    >
      <div className="card-body">
        <div className="flex items-start justify-between">
          <div>
            <div className="flex items-center gap-2">
              <span className="text-sm font-mono text-gray-500">#{batch.id.slice(0, 8)}</span>
              {isHarvestReady && <AlertCircle className="w-4 h-4 text-green-600" />}
            </div>
            <h3 className="font-semibold text-gray-900 mt-1">{batch.seed?.name || 'Unbekannt'}</h3>
          </div>
          <GrowBatchStatusBadge status={batch.status} />
        </div>

        {/* Timeline */}
        <GrowBatchTimeline batch={batch} className="mt-4" />

        {/* Info Grid */}
        <div className="grid grid-cols-2 gap-3 mt-4">
          <div className="flex items-center gap-2 text-sm text-gray-600">
            <Layers className="w-4 h-4 text-gray-400" />
            <span>{batch.tray_anzahl} Trays</span>
          </div>
          <div className="flex items-center gap-2 text-sm text-gray-600">
            <Calendar className="w-4 h-4 text-gray-400" />
            <span>Tag {currentDay}</span>
          </div>
          {batch.regal_position && (
            <div className="flex items-center gap-2 text-sm text-gray-600">
              <MapPin className="w-4 h-4 text-gray-400" />
              <span>Regal {batch.regal_position}</span>
            </div>
          )}
          <div className="flex items-center gap-2 text-sm text-gray-600">
            <Scale className="w-4 h-4 text-gray-400" />
            <span>~{(expectedYield / 1000).toFixed(1)} kg</span>
          </div>
        </div>

        {/* Dates */}
        <div className="mt-4 pt-4 border-t border-gray-100 text-sm">
          <div className="flex justify-between">
            <span className="text-gray-500">Aussaat:</span>
            <span>{formatDate(batch.aussaat_datum)}</span>
          </div>
          <div className="flex justify-between mt-1">
            <span className="text-gray-500">Ernte (optimal):</span>
            <span className="text-minga-600 font-medium">
              {formatDate(batch.erwartete_ernte_optimal)}
            </span>
          </div>
        </div>

        {/* Actions */}
        {showActions && (
          <div className="mt-4 flex gap-2">
            {isHarvestReady && onHarvest && (
              <button
                className="btn btn-success flex-1"
                onClick={(e) => {
                  e.stopPropagation();
                  onHarvest();
                }}
              >
                <Scissors className="w-4 h-4" />
                Ernte erfassen
              </button>
            )}
            {onPrintLabel && (
              <button
                className="btn btn-secondary flex-1"
                onClick={(e) => {
                  e.stopPropagation();
                  onPrintLabel();
                }}
                title="Etikett drucken"
              >
                <Printer className="w-4 h-4" />
                Label
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

// Timeline component for grow batch progress
interface GrowBatchTimelineProps {
  batch: GrowBatchWithSeed;
  className?: string;
}

export function GrowBatchTimeline({ batch, className = '' }: GrowBatchTimelineProps) {
  const seed = batch.seed;
  if (!seed) return null;

  const totalDays = seed.keimdauer_tage + seed.wachstumsdauer_tage;
  const currentDay = calculateCurrentDay(batch);
  const keimungPercent = (seed.keimdauer_tage / totalDays) * 100;
  const progressPercent = Math.min((currentDay / totalDays) * 100, 100);

  const isKeimung = currentDay <= seed.keimdauer_tage;
  const isWachstum = currentDay > seed.keimdauer_tage && batch.status !== 'ERNTEREIF';
  const isErntereif = batch.status === 'ERNTEREIF';

  return (
    <div className={className}>
      <div className="batch-timeline relative">
        {/* Background segments */}
        <div
          className="batch-timeline-segment batch-timeline-keimung opacity-30"
          style={{ width: `${keimungPercent}%` }}
        />
        <div
          className="batch-timeline-segment batch-timeline-wachstum opacity-30"
          style={{ width: `${100 - keimungPercent}%` }}
        />

        {/* Progress overlay */}
        <div
          className="absolute inset-y-0 left-0 flex"
          style={{ width: `${progressPercent}%` }}
        >
          <div
            className={`h-full ${isKeimung ? 'batch-timeline-keimung' : 'batch-timeline-keimung'}`}
            style={{ width: `${Math.min(progressPercent, keimungPercent) / progressPercent * 100}%` }}
          />
          {progressPercent > keimungPercent && (
            <div
              className={`h-full ${isErntereif ? 'batch-timeline-erntereif' : 'batch-timeline-wachstum'}`}
              style={{ width: `${(progressPercent - keimungPercent) / progressPercent * 100}%` }}
            />
          )}
        </div>
      </div>

      <div className="flex justify-between mt-1 text-xs text-gray-500">
        <span>Tag {currentDay}/{totalDays}</span>
        <span>
          {isKeimung && 'Keimung'}
          {isWachstum && 'Wachstum'}
          {isErntereif && 'Erntereif'}
        </span>
      </div>
    </div>
  );
}

// Helper function to calculate current day
function calculateCurrentDay(batch: GrowBatch): number {
  const aussaat = new Date(batch.aussaat_datum);
  const today = new Date();
  const diffTime = today.getTime() - aussaat.getTime();
  const diffDays = Math.floor(diffTime / (1000 * 60 * 60 * 24));
  return Math.max(1, diffDays + 1);
}

// Compact row version for lists
interface GrowBatchRowProps {
  batch: GrowBatchWithSeed;
  onHarvest?: () => void;
  onClick?: () => void;
}

export function GrowBatchRow({ batch, onHarvest, onClick }: GrowBatchRowProps) {
  const currentDay = calculateCurrentDay(batch);
  const isHarvestReady = batch.status === 'ERNTEREIF';

  return (
    <div
      className={`flex items-center justify-between p-4 bg-white border rounded-lg ${isHarvestReady ? 'border-green-300 bg-green-50/30' : 'border-gray-200'
        } ${onClick ? 'cursor-pointer hover:bg-gray-50' : ''}`}
      onClick={onClick}
    >
      <div className="flex items-center gap-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="font-mono text-sm text-gray-500">#{batch.id.slice(0, 8)}</span>
            <span className="font-medium">{batch.seed?.name}</span>
          </div>
          <p className="text-sm text-gray-500">
            {batch.tray_anzahl} Trays | Tag {currentDay} | Regal {batch.regal_position || '-'}
          </p>
        </div>
      </div>

      <div className="flex items-center gap-4">
        <div className="text-right">
          <p className="text-sm text-gray-500">Ernte</p>
          <p className="text-sm font-medium">{getRelativeDate(batch.erwartete_ernte_optimal)}</p>
        </div>
        <GrowBatchStatusBadge status={batch.status} />
        {isHarvestReady && onHarvest && (
          <button
            className="btn btn-success btn-sm"
            onClick={(e) => {
              e.stopPropagation();
              onHarvest();
            }}
          >
            <Scissors className="w-4 h-4" />
            Ernten
          </button>
        )}
      </div>
    </div>
  );
}
