import { Eye } from 'lucide-react';
import { useReadOnlyMode } from '../../hooks/useReadOnlyMode';

/**
 * Banner für Read-Only-Demo-User. Wird oben in der App-Shell angezeigt.
 *
 * Reine UX-Maßnahme — die eigentliche Sperre läuft im FastAPI-Middleware
 * über die basic_auth_user_readonly-Identity (siehe backend/app/main.py).
 */
export function ReadOnlyBanner() {
  const { isReadOnly } = useReadOnlyMode();
  if (!isReadOnly) return null;
  return (
    <div className="bg-amber-100 dark:bg-amber-900/30 border-b border-amber-300 dark:border-amber-700 text-amber-900 dark:text-amber-100 px-4 py-2 flex items-center gap-2 text-sm">
      <Eye className="w-4 h-4" />
      <span>
        <strong>Demo-Modus (nur Lesen)</strong> — du kannst alle Daten ansehen,
        aber Änderungen werden nicht gespeichert. Für vollen Zugriff melde dich
        mit einem Vollnutzer-Account an.
      </span>
    </div>
  );
}
