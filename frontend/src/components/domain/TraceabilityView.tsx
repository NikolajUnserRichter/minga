import { TraceabilityChain } from '../../types';
import { formatDate } from '../ui';
import { Sprout, Scissors, Package, Truck, ShieldCheck, AlertCircle } from 'lucide-react';

interface TraceabilityViewProps {
    data: TraceabilityChain;
}

export function TraceabilityView({ data }: TraceabilityViewProps) {
    return (
        <div className="space-y-8 p-4">
            {/* Header Info */}
            <div className="bg-gray-50 p-4 rounded-lg flex justify-between items-start">
                <div>
                    <h3 className="text-lg font-bold text-gray-900">{data.product?.name || 'Unbekanntes Produkt'}</h3>
                    <p className="text-sm text-gray-500 font-mono">Charge: {data.finished_goods.batch}</p>
                </div>
                <div className="text-right">
                    <p className="text-sm text-gray-500">MHD</p>
                    <p className="font-medium text-gray-900">{formatDate(data.finished_goods.best_before)}</p>
                </div>
            </div>

            <div className="relative">
                <div className="absolute left-8 top-0 bottom-0 w-0.5 bg-gray-200" />

                {/* 1. SEED */}
                <div className="relative pl-16 pb-8">
                    <div className={`absolute left-0 w-16 h-16 rounded-full border-4 flex items-center justify-center bg-white z-10 ${data.seed_inventory ? 'border-minga-500 text-minga-600' : 'border-gray-200 text-gray-300'}`}>
                        <Sprout className="w-8 h-8" />
                    </div>
                    <div className="bg-white border rounded-lg p-4 ml-4">
                        <h4 className="font-semibold text-gray-900 mb-2">Saatgut & Herkunft</h4>
                        {data.seed_inventory ? (
                            <div className="grid grid-cols-2 gap-4 text-sm">
                                <div>
                                    <p className="text-gray-500">Sorte</p>
                                    <p>{data.seed_inventory.seed_name || 'Unbekannt'}</p>
                                </div>
                                <div>
                                    <p className="text-gray-500">Lieferant</p>
                                    <p>{data.seed_inventory.supplier || '-'}</p>
                                </div>
                                <div>
                                    <p className="text-gray-500">Orig. Charge</p>
                                    <p className="font-mono">{data.seed_inventory.supplier_batch || data.seed_inventory.batch}</p>
                                </div>
                                <div>
                                    <p className="text-gray-500">Bio-Status</p>
                                    {data.seed_inventory.is_organic ? (
                                        <span className="flex items-center gap-1 text-green-700 font-medium">
                                            <ShieldCheck className="w-4 h-4" /> Zertifiziert
                                        </span>
                                    ) : (
                                        <span className="text-gray-700">Konventionell</span>
                                    )}
                                </div>
                                <div>
                                    <p className="text-gray-500">Eingang</p>
                                    <p>{formatDate(data.seed_inventory.received)}</p>
                                </div>
                            </div>
                        ) : (
                            <div className="text-gray-400 italic flex items-center gap-2">
                                <AlertCircle className="w-4 h-4" />
                                Keine Saatgut-Daten verknüpft (Lücke in Historie)
                            </div>
                        )}
                    </div>
                </div>

                {/* 2. PRODUCTION */}
                <div className="relative pl-16 pb-8">
                    <div className={`absolute left-0 w-16 h-16 rounded-full border-4 flex items-center justify-center bg-white z-10 ${data.grow_batch ? 'border-blue-500 text-blue-600' : 'border-gray-200 text-gray-300'}`}>
                        <Package className="w-8 h-8" />
                    </div>
                    <div className="bg-white border rounded-lg p-4 ml-4">
                        <h4 className="font-semibold text-gray-900 mb-2">Anbau (Produktion)</h4>
                        {data.grow_batch ? (
                            <div className="grid grid-cols-2 gap-4 text-sm">
                                <div>
                                    <p className="text-gray-500">Aussaat</p>
                                    <p>{formatDate(data.grow_batch.sow_date)}</p>
                                </div>
                                <div>
                                    <p className="text-gray-500">Menge</p>
                                    <p>{data.grow_batch.trays} Trays</p>
                                </div>
                                <div>
                                    <p className="text-gray-500">Position</p>
                                    <p>{data.grow_batch.position || 'Standard'}</p>
                                </div>
                                <div>
                                    <p className="text-gray-500">Interne Charge</p>
                                    <p className="font-mono text-xs">{data.grow_batch.id.slice(0, 8)}...</p>
                                </div>
                            </div>
                        ) : (
                            <div className="text-gray-400 italic">Keine Produktionsdaten</div>
                        )}
                    </div>
                </div>

                {/* 3. HARVEST */}
                <div className="relative pl-16 pb-8">
                    <div className={`absolute left-0 w-16 h-16 rounded-full border-4 flex items-center justify-center bg-white z-10 ${data.harvest ? 'border-orange-400 text-orange-500' : 'border-gray-200 text-gray-300'}`}>
                        <Scissors className="w-8 h-8" />
                    </div>
                    <div className="bg-white border rounded-lg p-4 ml-4">
                        <h4 className="font-semibold text-gray-900 mb-2">Ernte & Verarbeitung</h4>
                        {data.harvest ? (
                            <div className="grid grid-cols-2 gap-4 text-sm">
                                <div>
                                    <p className="text-gray-500">Datum</p>
                                    <p>{formatDate(data.harvest.date)}</p>
                                </div>
                                <div>
                                    <p className="text-gray-500">Erntemenge</p>
                                    <p>{data.harvest.quantity_g} g</p>
                                </div>
                                <div>
                                    <p className="text-gray-500">Qualität</p>
                                    <div className="flex text-yellow-500">
                                        {[...Array(5)].map((_, i) => (
                                            <span key={i} className={i < (data.harvest?.quality || 0) ? 'fill-current' : 'text-gray-300'}>★</span>
                                        ))}
                                    </div>
                                </div>
                            </div>
                        ) : (
                            <div className="text-gray-400 italic">Keine Erntedaten</div>
                        )}
                    </div>
                </div>

                {/* 4. OUTBOUND */}
                <div className="relative pl-16">
                    <div className={`absolute left-0 w-16 h-16 rounded-full border-4 flex items-center justify-center bg-white z-10 ${data.deliveries.length > 0 ? 'border-purple-500 text-purple-600' : 'border-gray-200 text-gray-300'}`}>
                        <Truck className="w-8 h-8" />
                    </div>
                    <div className="bg-white border rounded-lg p-4 ml-4">
                        <h4 className="font-semibold text-gray-900 mb-2">Ausgang & Lieferung</h4>
                        {data.deliveries.length > 0 ? (
                            <div className="space-y-3">
                                {data.deliveries.map((del, idx) => (
                                    <div key={idx} className="flex justify-between items-center text-sm border-b pb-2 last:border-0 last:pb-0">
                                        <div>
                                            <p className="font-medium text-gray-900">{del.customer || 'Unbekannter Kunde'}</p>
                                            <p className="text-gray-500 text-xs">{formatDate(del.date)}</p>
                                        </div>
                                        <div className="text-right">
                                            <p className="font-medium">{del.quantity_g} g</p>
                                            {del.order_id && <p className="text-xs text-blue-500">#{del.order_id.slice(0, 6)}</p>}
                                        </div>
                                    </div>
                                ))}
                            </div>
                        ) : (
                            <div className="text-gray-500 flex items-center gap-2">
                                <span className="w-2 h-2 rounded-full bg-green-500"></span>
                                Noch im Lagerbestand
                            </div>
                        )}
                    </div>
                </div>
            </div>
        </div>
    );
}
