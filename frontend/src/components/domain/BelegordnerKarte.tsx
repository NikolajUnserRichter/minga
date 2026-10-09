import { useEffect, useState } from 'react';
import { FolderOpen } from 'lucide-react';
import { Button, useToast } from '../ui';
import { getErrorMessage } from '../../services/errors';
import {
  belegordnerErlaubnis, belegordnerFreigeben, belegordnerMoeglich, belegordnerName,
  belegordnerWaehlen, belegordnerZuruecksetzen, ZUGRIFF_WIEDER_ERLAUBEN,
} from '../../services/belegordner';

/**
 * Einstellungen → Belegordner (Abschnitt O, Gernot 09.10.2026). Gilt nur für
 * diesen Browser auf diesem Gerät; nichts davon liegt auf dem Server.
 */
export function BelegordnerKarte() {
  const toast = useToast();
  const moeglich = belegordnerMoeglich();
  const [name, setName] = useState<string | null>(null);
  const [erlaubnis, setErlaubnis] = useState<string | null>(null);

  const neuLesen = async () => {
    setName(await belegordnerName());
    setErlaubnis(await belegordnerErlaubnis());
  };

  useEffect(() => {
    if (moeglich) void neuLesen();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [moeglich]);

  const waehlen = async () => {
    try {
      const gewaehlt = await belegordnerWaehlen();
      if (gewaehlt) toast.success(`Belegordner: ${gewaehlt}`);
    } catch (e) {
      // z. B. ein Systemordner, den der Browser nicht freigibt
      toast.error(getErrorMessage(e, 'Ordner konnte nicht gewählt werden'));
    }
    await neuLesen();
  };

  const freigeben = async () => {
    if (await belegordnerFreigeben()) toast.success('Zugriff auf den Belegordner erlaubt');
    else toast.warning('Kein Zugriff — Belege landen im Download-Ordner');
    await neuLesen();
  };

  const zuruecksetzen = async () => {
    await belegordnerZuruecksetzen();
    toast.info('Belegordner zurückgesetzt — Belege landen wieder im Download-Ordner');
    await neuLesen();
  };

  return (
    <div className="card">
      <div className="card-header">
        <h3 className="card-title flex items-center gap-2">
          <FolderOpen className="w-5 h-5" />
          Belegordner
        </h3>
      </div>
      <div className="card-body space-y-3">
        {!moeglich ? (
          <p className="text-sm text-gray-500 dark:text-gray-400">
            Dieser Browser kann Belege nicht direkt in einen Ordner speichern — das können Chrome
            und Edge am Computer. Belege landen im Download-Ordner.
          </p>
        ) : (
          <>
            <p className="text-sm text-gray-500 dark:text-gray-400">
              PDFs und Exporte landen direkt im gewählten Ordner, sortiert nach Belegart und Monat,
              z. B. <span className="font-mono">Belege/Rechnungen/2026-10/RE-2026-00006.pdf</span>.
              Gilt nur für diesen Browser auf diesem Gerät.
            </p>
            {name ? (
              <div className="text-sm space-y-1">
                <div>
                  Ordner: <span className="font-medium">{name}</span>
                </div>
                {erlaubnis === 'granted' && (
                  <div className="text-emerald-700 dark:text-emerald-300">Zugriff erlaubt</div>
                )}
                {erlaubnis === 'prompt' && (
                  <div className="text-amber-700 dark:text-amber-300">
                    Der Browser fragt beim nächsten Beleg einmal nach dem Zugriff (je Sitzung;
                    „Bei jedem Besuch zulassen" erspart die Frage).
                  </div>
                )}
                {erlaubnis === 'denied' && (
                  // Kein Knopf: Chrome fragt nach „Nicht zulassen" in dieser Sitzung nicht mehr
                  <div className="text-red-700 dark:text-red-300">
                    Zugriff verweigert — Belege landen im Download-Ordner. {ZUGRIFF_WIEDER_ERLAUBEN}
                  </div>
                )}
              </div>
            ) : (
              <p className="text-sm">Kein Ordner gewählt — Belege landen im Download-Ordner.</p>
            )}
            <div className="flex flex-wrap gap-2">
              <Button size="sm" onClick={waehlen}>
                {name ? 'Anderen Ordner wählen' : 'Belegordner wählen'}
              </Button>
              {name && erlaubnis === 'prompt' && (
                <Button size="sm" variant="secondary" onClick={freigeben}>
                  Zugriff erlauben
                </Button>
              )}
              {name && (
                <Button size="sm" variant="ghost" onClick={zuruecksetzen}>
                  Zurücksetzen
                </Button>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
