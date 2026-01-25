import { Seed } from '../../types';
import { Badge } from '../ui';
import { Sprout, Clock, Scale, Percent, Edit2, Trash2 } from 'lucide-react';

interface SeedCardProps {
  seed: Seed;
  onEdit?: () => void;
  onDelete?: () => void;
  onClick?: () => void;
  showActions?: boolean;
}

export function SeedCard({ seed, onEdit, onDelete, onClick, showActions = true }: SeedCardProps) {
  const totalGrowthDays = seed.keimdauer_tage + seed.wachstumsdauer_tage;

  return (
    <div
      className={`card card-hover ${onClick ? 'cursor-pointer' : ''}`}
      onClick={onClick}
    >
      <div className="card-body">
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-minga-50 rounded-lg">
              <Sprout className="w-6 h-6 text-minga-600" />
            </div>
            <div>
              <h3 className="font-semibold text-gray-900">{seed.name}</h3>
              {seed.sorte && <p className="text-sm text-gray-500">{seed.sorte}</p>}
            </div>
          </div>
          <Badge variant={seed.aktiv ? 'success' : 'gray'}>
            {seed.aktiv ? 'Aktiv' : 'Inaktiv'}
          </Badge>
        </div>

        <div className="grid grid-cols-2 gap-4 mt-4">
          <div className="flex items-center gap-2 text-sm text-gray-600">
            <Clock className="w-4 h-4 text-gray-400" />
            <span>Keimung: {seed.keimdauer_tage} Tage</span>
          </div>
          <div className="flex items-center gap-2 text-sm text-gray-600">
            <Clock className="w-4 h-4 text-gray-400" />
            <span>Wachstum: {seed.wachstumsdauer_tage} Tage</span>
          </div>
          <div className="flex items-center gap-2 text-sm text-gray-600">
            <Scale className="w-4 h-4 text-gray-400" />
            <span>Ertrag: {seed.ertrag_gramm_pro_tray}g/Tray</span>
          </div>
          <div className="flex items-center gap-2 text-sm text-gray-600">
            <Percent className="w-4 h-4 text-gray-400" />
            <span>Verlust: {seed.verlustquote_prozent}%</span>
          </div>
        </div>

        <div className="mt-4 p-3 bg-gray-50 rounded-lg">
          <p className="text-sm">
            <span className="text-gray-500">Erntefenster:</span>{' '}
            <span className="font-medium">
              Tag {seed.erntefenster_min_tage} - {seed.erntefenster_max_tage}
            </span>
            <span className="text-minga-600 ml-2">(optimal: Tag {seed.erntefenster_optimal_tage})</span>
          </p>
          <p className="text-sm mt-1">
            <span className="text-gray-500">Gesamte Wachstumsdauer:</span>{' '}
            <span className="font-medium">{totalGrowthDays} Tage</span>
          </p>
        </div>

        {showActions && (onEdit || onDelete) && (
          <div className="flex items-center gap-2 mt-4 pt-4 border-t border-gray-100">
            {onEdit && (
              <button
                className="btn btn-ghost btn-sm"
                onClick={(e) => {
                  e.stopPropagation();
                  onEdit();
                }}
              >
                <Edit2 className="w-4 h-4" />
                Bearbeiten
              </button>
            )}
            {onDelete && (
              <button
                className="btn btn-ghost btn-sm text-red-600 hover:bg-red-50"
                onClick={(e) => {
                  e.stopPropagation();
                  onDelete();
                }}
              >
                <Trash2 className="w-4 h-4" />
                Löschen
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

// Compact version for lists/tables
interface SeedRowProps {
  seed: Seed;
  onEdit?: () => void;
  onDelete?: () => void;
}

export function SeedRow({ seed, onEdit, onDelete }: SeedRowProps) {
  return (
    <div className="flex items-center justify-between p-4 bg-white border border-gray-200 rounded-lg hover:bg-gray-50">
      <div className="flex items-center gap-3">
        <Sprout className="w-5 h-5 text-minga-600" />
        <div>
          <p className="font-medium text-gray-900">{seed.name}</p>
          {seed.sorte && <p className="text-sm text-gray-500">{seed.sorte}</p>}
        </div>
      </div>

      <div className="flex items-center gap-6 text-sm text-gray-600">
        <span>Keimung: {seed.keimdauer_tage}T</span>
        <span>Wachstum: {seed.wachstumsdauer_tage}T</span>
        <span>{seed.ertrag_gramm_pro_tray}g/Tray</span>
        <Badge variant={seed.aktiv ? 'success' : 'gray'} size="sm">
          {seed.aktiv ? 'Aktiv' : 'Inaktiv'}
        </Badge>

        {(onEdit || onDelete) && (
          <div className="flex items-center gap-1">
            {onEdit && (
              <button className="p-1 hover:bg-gray-100 rounded" onClick={onEdit}>
                <Edit2 className="w-4 h-4 text-gray-500" />
              </button>
            )}
            {onDelete && (
              <button className="p-1 hover:bg-red-50 rounded" onClick={onDelete}>
                <Trash2 className="w-4 h-4 text-red-500" />
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
