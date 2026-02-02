import { useState } from 'react';
import { GrowBatch, GrowBatchStatus, GrowBatchWithSeed } from '../../types';
import { formatDate } from '../ui';
import { Layers, Calendar, MapPin, Scissors, GripVertical } from 'lucide-react';

interface KanbanBoardProps {
    batches: GrowBatchWithSeed[];
    onStatusChange: (id: string, status: GrowBatchStatus) => void;
    onHarvest: (batch: GrowBatchWithSeed) => void;
}

interface KanbanColumnProps {
    title: string;
    status: GrowBatchStatus;
    batches: GrowBatchWithSeed[];
    onDrop: (batchId: string, newStatus: GrowBatchStatus) => void;
    onHarvest: (batch: GrowBatchWithSeed) => void;
    allowedFromStatuses: GrowBatchStatus[];
    color: string;
}

interface KanbanCardProps {
    batch: GrowBatchWithSeed;
    onHarvest?: () => void;
    isDragging?: boolean;
}

// Valid status transitions
const VALID_TRANSITIONS: Record<GrowBatchStatus, GrowBatchStatus[]> = {
    KEIMUNG: ['WACHSTUM'],
    WACHSTUM: ['ERNTEREIF'],
    ERNTEREIF: [], // Harvest only, no drag
    GEERNTET: [],
    VERLUST: [],
};

export function KanbanBoard({ batches, onStatusChange, onHarvest }: KanbanBoardProps) {
    const columns: { status: GrowBatchStatus; title: string; color: string; allowedFrom: GrowBatchStatus[] }[] = [
        { status: 'KEIMUNG', title: 'Keimung', color: 'bg-amber-500', allowedFrom: [] },
        { status: 'WACHSTUM', title: 'Wachstum', color: 'bg-lime-500', allowedFrom: ['KEIMUNG'] },
        { status: 'ERNTEREIF', title: 'Erntereif', color: 'bg-green-500', allowedFrom: ['WACHSTUM'] },
    ];

    const handleDrop = (batchId: string, newStatus: GrowBatchStatus) => {
        const batch = batches.find((b) => b.id === batchId);
        if (!batch) return;

        // Validate transition
        const validNextStatuses = VALID_TRANSITIONS[batch.status as GrowBatchStatus] || [];
        if (validNextStatuses.includes(newStatus)) {
            onStatusChange(batchId, newStatus);
        }
    };

    return (
        <div className="flex gap-4 overflow-x-auto pb-4">
            {columns.map((col) => (
                <KanbanColumn
                    key={col.status}
                    title={col.title}
                    status={col.status}
                    color={col.color}
                    batches={batches.filter((b) => b.status === col.status)}
                    onDrop={handleDrop}
                    onHarvest={onHarvest}
                    allowedFromStatuses={col.allowedFrom}
                />
            ))}
        </div>
    );
}

function KanbanColumn({
    title,
    status,
    batches,
    onDrop,
    onHarvest,
    allowedFromStatuses,
    color,
}: KanbanColumnProps) {
    const [isDragOver, setIsDragOver] = useState(false);
    const [isValidDrop, setIsValidDrop] = useState(true);

    const handleDragOver = (e: React.DragEvent) => {
        e.preventDefault();
        const draggedStatus = e.dataTransfer.types.find((t) => t.startsWith('status/'))?.replace('status/', '');
        const isValid = draggedStatus ? allowedFromStatuses.includes(draggedStatus as GrowBatchStatus) : false;
        setIsValidDrop(isValid);
        setIsDragOver(true);
    };

    const handleDragLeave = () => {
        setIsDragOver(false);
        setIsValidDrop(true);
    };

    const handleDrop = (e: React.DragEvent) => {
        e.preventDefault();
        setIsDragOver(false);
        const batchId = e.dataTransfer.getData('batchId');
        const draggedStatus = e.dataTransfer.getData('status');

        if (batchId && allowedFromStatuses.includes(draggedStatus as GrowBatchStatus)) {
            onDrop(batchId, status);
        }
    };

    return (
        <div
            className={`flex-1 min-w-[300px] max-w-[400px] rounded-lg transition-all ${isDragOver
                ? isValidDrop
                    ? 'ring-2 ring-minga-500 bg-minga-50'
                    : 'ring-2 ring-red-400 bg-red-50'
                : 'bg-gray-50'
                }`}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
        >
            {/* Column Header */}
            <div className="p-4 border-b border-gray-200">
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                        <div className={`w-3 h-3 rounded-full ${color}`} />
                        <h3 className="font-semibold text-gray-900">{title}</h3>
                    </div>
                    <span className="text-sm text-gray-500 bg-white px-2 py-0.5 rounded-full">
                        {batches.length}
                    </span>
                </div>
            </div>

            {/* Cards Container */}
            <div className="p-2 space-y-2 min-h-[400px]">
                {batches.length === 0 ? (
                    <div className="text-center text-gray-400 py-8 text-sm">
                        Keine Chargen
                    </div>
                ) : (
                    batches.map((batch) => (
                        <KanbanCard
                            key={batch.id}
                            batch={batch}
                            onHarvest={status === 'ERNTEREIF' ? () => onHarvest(batch) : undefined}
                        />
                    ))
                )}
            </div>
        </div>
    );
}

function KanbanCard({ batch, onHarvest }: KanbanCardProps) {
    const [isDragging, setIsDragging] = useState(false);
    const canDrag = VALID_TRANSITIONS[batch.status as GrowBatchStatus]?.length > 0;

    const currentDay = calculateCurrentDay(batch);

    const handleDragStart = (e: React.DragEvent) => {
        setIsDragging(true);
        e.dataTransfer.setData('batchId', batch.id);
        e.dataTransfer.setData('status', batch.status);
        // Set a custom type to check during dragover
        e.dataTransfer.setData(`status/${batch.status}`, 'true');
        e.dataTransfer.effectAllowed = 'move';
    };

    const handleDragEnd = () => {
        setIsDragging(false);
    };

    return (
        <div
            draggable={canDrag}
            onDragStart={handleDragStart}
            onDragEnd={handleDragEnd}
            className={`bg-white rounded-lg border border-gray-200 p-3 transition-all ${isDragging ? 'opacity-50 shadow-lg ring-2 ring-minga-500' : 'hover:shadow-md'
                } ${canDrag ? 'cursor-grab active:cursor-grabbing' : ''}`}
        >
            {/* Header */}
            <div className="flex items-start justify-between gap-2">
                <div className="flex-1 min-w-0">
                    <span className="text-xs font-mono text-gray-400">#{batch.id.slice(0, 8)}</span>
                    <h4 className="font-medium text-gray-900 truncate">{batch.seed?.name || 'Unbekannt'}</h4>
                </div>
                {canDrag && (
                    <GripVertical className="w-4 h-4 text-gray-300 flex-shrink-0" />
                )}
            </div>

            {/* Info Row */}
            <div className="flex items-center gap-3 mt-2 text-xs text-gray-500">
                <div className="flex items-center gap-1">
                    <Layers className="w-3 h-3" />
                    <span>{batch.tray_anzahl} Trays</span>
                </div>
                <div className="flex items-center gap-1">
                    <Calendar className="w-3 h-3" />
                    <span>Tag {currentDay}</span>
                </div>
                {batch.regal_position && (
                    <div className="flex items-center gap-1">
                        <MapPin className="w-3 h-3" />
                        <span>{batch.regal_position}</span>
                    </div>
                )}
            </div>

            {/* Dates */}
            <div className="mt-2 pt-2 border-t border-gray-100 text-xs">
                <div className="flex justify-between text-gray-500">
                    <span>Ernte:</span>
                    <span className="font-medium text-gray-700">
                        {formatDate(batch.erwartete_ernte_optimal)}
                    </span>
                </div>
            </div>

            {/* Harvest Button */}
            {onHarvest && (
                <button
                    onClick={(e) => {
                        e.stopPropagation();
                        onHarvest();
                    }}
                    className="mt-2 w-full btn btn-success btn-sm"
                >
                    <Scissors className="w-3 h-3" />
                    Ernten
                </button>
            )}
        </div>
    );
}

// Helper function
function calculateCurrentDay(batch: GrowBatch): number {
    const aussaat = new Date(batch.aussaat_datum);
    const today = new Date();
    const diffTime = today.getTime() - aussaat.getTime();
    const diffDays = Math.floor(diffTime / (1000 * 60 * 60 * 24));
    return Math.max(1, diffDays + 1);
}
