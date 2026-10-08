import { Badge } from '../ui';
import { Mail, Edit2, Shield, KeyRound, UserX, UserCheck, CalendarPlus } from 'lucide-react';
import type { MandantenBenutzer } from '../../services/api';
import { rollenInfo } from '../../services/rollen';

/** Vor- und Nachname; fehlen beide, die E-Mail. */
export function anzeigeName(b: MandantenBenutzer): string {
    return [b.first_name, b.last_name].filter(Boolean).join(' ') || b.email;
}

interface UserCardProps {
    user: MandantenBenutzer;
    onEdit: () => void;
    onDeaktivieren: () => void;
    onAktivieren: () => void;
    onPasswort: () => void;
    /** Während eine Änderung läuft, keine zweite auslösen. */
    gesperrt?: boolean;
    /** Demo-Mandant (E-M6): keine Aktionen anbieten, der Server lehnt jedes Schreiben ab. */
    schreibgeschuetzt?: boolean;
}

export function UserCard({
    user,
    onEdit,
    onDeaktivieren,
    onAktivieren,
    onPasswort,
    gesperrt = false,
    schreibgeschuetzt = false,
}: UserCardProps) {
    const name = anzeigeName(user);
    const initialen =
        [user.first_name, user.last_name]
            .filter(Boolean)
            .map((n) => n[0])
            .join('')
            .toUpperCase() || user.email.slice(0, 1).toUpperCase();

    return (
        <div className={`card card-hover ${user.enabled ? '' : 'opacity-60'}`}>
            <div className="card-body">
                <div className="flex items-start gap-4">
                    <div className="w-12 h-12 rounded-full bg-minga-100 dark:bg-minga-900/50 flex items-center justify-center text-minga-700 dark:text-minga-400 font-semibold text-lg flex-shrink-0">
                        {initialen}
                    </div>

                    <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                            <h3 className="font-semibold text-gray-900 dark:text-white truncate">{name}</h3>
                            {user.is_self && <span className="text-xs text-gray-500 dark:text-gray-400">(Sie)</span>}
                        </div>
                        <div className="flex flex-wrap items-center gap-2 mt-1">
                            {user.roles.length === 0 && <Badge variant="danger">Keine Rolle</Badge>}
                            {user.roles.map((r) => {
                                const info = rollenInfo(r);
                                return (
                                    <Badge key={r} variant={info?.badge ?? 'gray'}>
                                        <Shield className="w-3 h-3 mr-1" />
                                        {info?.label ?? r}
                                    </Badge>
                                );
                            })}
                            {!user.enabled && <Badge variant="gray">Deaktiviert</Badge>}
                        </div>
                    </div>
                </div>

                <div className="mt-4 space-y-2">
                    <div className="flex items-center gap-2 text-sm text-gray-600 dark:text-gray-400">
                        <Mail className="w-4 h-4 text-gray-400" />
                        <span className="truncate">{user.email}</span>
                    </div>
                    {user.created_at && (
                        <div className="flex items-center gap-2 text-sm text-gray-500 dark:text-gray-400">
                            <CalendarPlus className="w-4 h-4 text-gray-400" />
                            <span>
                                Angelegt am{' '}
                                {new Date(user.created_at).toLocaleDateString('de-DE', {
                                    day: '2-digit',
                                    month: '2-digit',
                                    year: 'numeric',
                                })}
                            </span>
                        </div>
                    )}
                </div>

                {!schreibgeschuetzt && (
                    <div className="mt-4 pt-4 border-t border-gray-100 dark:border-gray-700 flex flex-wrap gap-2">
                        <button className="btn btn-ghost btn-sm" onClick={onEdit} disabled={gesperrt}>
                            <Edit2 className="w-4 h-4" />
                            Bearbeiten
                        </button>
                        <button className="btn btn-ghost btn-sm" onClick={onPasswort} disabled={gesperrt || !user.enabled}>
                            <KeyRound className="w-4 h-4" />
                            Passwort zurücksetzen
                        </button>
                        {user.enabled ? (
                            // Das eigene Konto nicht anbieten: wer sich selbst sperrt, kommt nicht mehr hinein.
                            // Der Server lehnt es ohnehin mit 409 ab.
                            !user.is_self && (
                                <button
                                    className="btn btn-ghost btn-sm text-red-600 dark:text-red-400 hover:text-red-700 hover:bg-red-50 dark:hover:bg-red-900/20"
                                    onClick={onDeaktivieren}
                                    disabled={gesperrt}
                                >
                                    <UserX className="w-4 h-4" />
                                    Deaktivieren
                                </button>
                            )
                        ) : (
                            <button className="btn btn-ghost btn-sm" onClick={onAktivieren} disabled={gesperrt}>
                                <UserCheck className="w-4 h-4" />
                                Aktivieren
                            </button>
                        )}
                    </div>
                )}
            </div>
        </div>
    );
}
