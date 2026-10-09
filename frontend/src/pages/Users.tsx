import { useEffect, useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Plus, Search, Users as UsersIcon, UserCheck, UserX, ShieldAlert, Copy } from 'lucide-react';
import { usersApi } from '../services/api';
import type { MandantenBenutzer, BenutzerAendern, BenutzerAngelegt } from '../services/api';
import { MANDANTEN_ROLLEN, rollenInfo } from '../services/rollen';
import type { MandantenRolle } from '../services/rollen';
import { getErrorMessage } from '../services/errors';
import { PageHeader, FilterBar, useUser } from '../components/common/Layout';
import { UserCard, anzeigeName } from '../components/domain/UserCard';
import { StatCard } from '../components/domain/StatCard';
import { SkeletonStatCard, SkeletonCard } from '../components/ui/Skeleton';
import {
    Alert,
    Button,
    Input,
    Select,
    Modal,
    ConfirmDialog,
    EmptyState,
    useToast,
    SelectOption,
} from '../components/ui';

/** Schlüssel der früheren Attrappe. Die Daten darin sind erfunden und werden entfernt. */
const ALTER_ATTRAPPEN_SPEICHER = 'minga-mock-users';

const BENUTZER_KEY = ['mandanten-benutzer'];

const rollenFilterOptionen: SelectOption[] = [
    { value: 'alle', label: 'Alle Rollen' },
    ...MANDANTEN_ROLLEN.map((r) => ({ value: r.wert, label: r.label })),
    { value: 'ohne', label: 'Ohne Rolle' },
];

interface EinmalPasswort {
    anmeldename: string;
    passwort: string;
}

export default function Users() {
    // Gleiche Regel wie der Menüpunkt (Layout.tsx, Abschnitt „Admin", roles: ['ADMIN']).
    // Die Route in App.tsx ist nicht geschützt; ohne diese Prüfung käme jede Rolle
    // per URL auf die Seite. Durchgesetzt wird das Recht im Backend (403).
    const { user } = useUser();
    if (user.role !== 'ADMIN') {
        return (
            <EmptyState
                icon={<ShieldAlert className="w-16 h-16" />}
                title="Kein Zugriff"
                description="Die Benutzerverwaltung ist nur für Administratoren freigegeben."
            />
        );
    }
    return <Benutzerverwaltung />;
}

function Benutzerverwaltung() {
    const toast = useToast();
    const queryClient = useQueryClient();

    const [suche, setSuche] = useState('');
    const [rollenFilter, setRollenFilter] = useState('alle');
    const [anlegen, setAnlegen] = useState(false);
    const [bearbeiten, setBearbeiten] = useState<MandantenBenutzer | null>(null);
    const [zuDeaktivieren, setZuDeaktivieren] = useState<MandantenBenutzer | null>(null);
    const [passwortFuer, setPasswortFuer] = useState<MandantenBenutzer | null>(null);
    const [einmalPasswort, setEinmalPasswort] = useState<EinmalPasswort | null>(null);

    // Die frühere Attrappe hat erfundene Nutzer im Browser abgelegt. Weg damit,
    // damit sie niemand mehr für echte Konten hält.
    useEffect(() => {
        try {
            localStorage.removeItem(ALTER_ATTRAPPEN_SPEICHER);
        } catch {
            /* Speicher gesperrt (privater Modus): nichts zu tun */
        }
    }, []);

    const benutzerQuery = useQuery({
        queryKey: BENUTZER_KEY,
        queryFn: () => usersApi.list(),
        // Ein Rechte- oder Keycloak-Fehler behebt sich nicht durch Wiederholen.
        retry: false,
    });

    const neuLaden = () => queryClient.invalidateQueries({ queryKey: BENUTZER_KEY });

    const statusMutation = useMutation({
        mutationFn: ({ b, aktiv }: { b: MandantenBenutzer; aktiv: boolean }) =>
            usersApi.update(b.id, { enabled: aktiv }),
        onSuccess: (b, { aktiv }) => {
            neuLaden();
            setZuDeaktivieren(null);
            toast.success(
                aktiv
                    ? `${anzeigeName(b)} ist wieder aktiv.`
                    : `${anzeigeName(b)} ist deaktiviert und kann sich nicht mehr anmelden.`,
            );
        },
        onError: (e) => toast.error(getErrorMessage(e, 'Status konnte nicht geändert werden')),
    });

    const passwortMutation = useMutation({
        mutationFn: (b: MandantenBenutzer) => usersApi.resetPassword(b.id),
        // Die Antwort enthält das Einmalpasswort: nicht im MutationCache halten.
        gcTime: 0,
        onSuccess: (r) => {
            setPasswortFuer(null);
            setEinmalPasswort({ anmeldename: r.user.email, passwort: r.temporary_password });
        },
        onError: (e) => toast.error(getErrorMessage(e, 'Passwort konnte nicht zurückgesetzt werden')),
    });

    if (benutzerQuery.isLoading) {
        return (
            <div className="space-y-6 animate-pulse">
                <div className="flex items-center justify-between">
                    <div className="space-y-2">
                        <div className="skeleton h-7 w-48" />
                        <div className="skeleton h-4 w-32" />
                    </div>
                    <div className="skeleton h-10 w-36 rounded-lg" />
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                    <SkeletonStatCard />
                    <SkeletonStatCard />
                    <SkeletonStatCard />
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                    <SkeletonCard />
                    <SkeletonCard />
                    <SkeletonCard />
                </div>
            </div>
        );
    }

    if (benutzerQuery.isError) {
        // Nie still als leere Liste zeigen: Wer „keine Benutzer" sieht, legt sonst
        // Konten doppelt an.
        return (
            <div className="space-y-6">
                <PageHeader title="Benutzerverwaltung" />
                <Alert variant="danger" title="Benutzer konnten nicht geladen werden">
                    {getErrorMessage(benutzerQuery.error, 'Unbekannter Fehler')}
                </Alert>
                <Button variant="secondary" onClick={() => benutzerQuery.refetch()} loading={benutzerQuery.isFetching}>
                    Erneut versuchen
                </Button>
            </div>
        );
    }

    const benutzer = benutzerQuery.data?.items ?? [];
    // Demo-Mandant (E-M6): Der Server lehnt jedes Schreiben ab, also nichts Schreibendes anbieten.
    const schreibgeschuetzt = benutzerQuery.data?.schreibgeschuetzt ?? false;
    const s = suche.trim().toLowerCase();
    const gefiltert = benutzer
        .filter((b) =>
            rollenFilter === 'alle'
                ? true
                : rollenFilter === 'ohne'
                  ? b.roles.length === 0
                  : b.roles.includes(rollenFilter as MandantenRolle),
        )
        .filter((b) => !s || anzeigeName(b).toLowerCase().includes(s) || b.email.toLowerCase().includes(s))
        .sort(
            (a, b) =>
                Number(b.enabled) - Number(a.enabled) || anzeigeName(a).localeCompare(anzeigeName(b), 'de'),
        );
    const aktive = benutzer.filter((b) => b.enabled).length;
    const aktivOhneRolle = benutzer.filter((b) => b.enabled && b.roles.length === 0).length;

    return (
        <div className="space-y-6">
            <PageHeader
                title="Benutzerverwaltung"
                subtitle={`${benutzer.length} Benutzer in diesem Betrieb`}
                actions={
                    schreibgeschuetzt ? undefined : (
                        <Button icon={<Plus className="w-4 h-4" />} onClick={() => setAnlegen(true)}>
                            Neuer Benutzer
                        </Button>
                    )
                }
            />

            {schreibgeschuetzt && (
                <Alert variant="info">
                    In der Demo können Benutzer nur angesehen werden. Anlegen, Bearbeiten, Deaktivieren und das
                    Zurücksetzen von Passwörtern sind hier abgeschaltet.
                </Alert>
            )}

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                <StatCard title="Gesamt" value={benutzer.length} icon={<UsersIcon className="w-5 h-5" />} variant="primary" />
                <StatCard title="Aktiv" value={aktive} icon={<UserCheck className="w-5 h-5" />} variant="success" />
                <StatCard
                    title="Deaktiviert"
                    value={benutzer.length - aktive}
                    icon={<UserX className="w-5 h-5" />}
                    variant="warning"
                />
            </div>

            {aktivOhneRolle > 0 && !schreibgeschuetzt && (
                <Alert variant="warning">
                    {aktivOhneRolle === 1
                        ? 'Ein aktiver Benutzer hat keine Rolle und kommt nach der Anmeldung nirgends hin.'
                        : `${aktivOhneRolle} aktive Benutzer haben keine Rolle und kommen nach der Anmeldung nirgends hin.`}{' '}
                    Bitte über „Bearbeiten" eine Rolle zuweisen.
                </Alert>
            )}

            <FilterBar>
                <div className="flex-1 max-w-md">
                    <Input
                        placeholder="Suchen nach Name oder E-Mail..."
                        value={suche}
                        onChange={(e) => setSuche(e.target.value)}
                        startIcon={<Search className="w-4 h-4" />}
                    />
                </div>
                <Select options={rollenFilterOptionen} value={rollenFilter} onChange={(e) => setRollenFilter(e.target.value)} />
            </FilterBar>

            {gefiltert.length === 0 ? (
                <EmptyState
                    title="Keine Benutzer gefunden"
                    description={benutzer.length > 0 ? 'Suche oder Rollenfilter ändern.' : 'Legen Sie den ersten Benutzer an.'}
                />
            ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                    {gefiltert.map((b) => (
                        <UserCard
                            key={b.id}
                            user={b}
                            gesperrt={statusMutation.isPending || passwortMutation.isPending}
                            schreibgeschuetzt={schreibgeschuetzt}
                            onEdit={() => setBearbeiten(b)}
                            onDeaktivieren={() => setZuDeaktivieren(b)}
                            onAktivieren={() => statusMutation.mutate({ b, aktiv: true })}
                            onPasswort={() => setPasswortFuer(b)}
                        />
                    ))}
                </div>
            )}

            <Modal
                open={anlegen || !!bearbeiten}
                onClose={() => {
                    setAnlegen(false);
                    setBearbeiten(null);
                }}
                title={bearbeiten ? 'Benutzer bearbeiten' : 'Neuer Benutzer'}
                size="lg"
                closeOnBackdrop={false}
                closeOnEscape={false}
            >
                <BenutzerFormular
                    key={bearbeiten?.id ?? 'neu'}
                    benutzer={bearbeiten}
                    onAngelegt={(neu) => {
                        neuLaden();
                        setAnlegen(false);
                        setEinmalPasswort({ anmeldename: neu.email, passwort: neu.temporary_password });
                    }}
                    onGeaendert={(b) => {
                        neuLaden();
                        setBearbeiten(null);
                        toast.success(`${anzeigeName(b)} gespeichert.`);
                    }}
                    onAbbrechen={() => {
                        setAnlegen(false);
                        setBearbeiten(null);
                    }}
                />
            </Modal>

            <ConfirmDialog
                open={!!zuDeaktivieren}
                onClose={() => setZuDeaktivieren(null)}
                onConfirm={() => zuDeaktivieren && statusMutation.mutate({ b: zuDeaktivieren, aktiv: false })}
                title="Benutzer deaktivieren?"
                message={
                    zuDeaktivieren
                        ? `${anzeigeName(zuDeaktivieren)} (${zuDeaktivieren.email}) kann sich danach nicht mehr anmelden. ` +
                          'Das Konto bleibt erhalten und lässt sich jederzeit wieder aktivieren.'
                        : ''
                }
                confirmLabel="Deaktivieren"
                variant="danger"
                loading={statusMutation.isPending}
            />

            <ConfirmDialog
                open={!!passwortFuer}
                onClose={() => setPasswortFuer(null)}
                onConfirm={() => passwortFuer && passwortMutation.mutate(passwortFuer)}
                title="Passwort zurücksetzen?"
                message={
                    passwortFuer
                        ? `Das bisherige Passwort von ${anzeigeName(passwortFuer)} gilt danach nicht mehr. ` +
                          'Sie bekommen ein Einmalpasswort angezeigt; beim nächsten Anmelden muss ein eigenes gesetzt werden.'
                        : ''
                }
                confirmLabel="Zurücksetzen"
                variant="warning"
                loading={passwortMutation.isPending}
            />

            <EinmalPasswortDialog
                daten={einmalPasswort}
                onClose={() => {
                    setEinmalPasswort(null);
                    // Sonst hielte passwortMutation.data das Passwort, solange die Seite offen ist.
                    passwortMutation.reset();
                }}
            />
        </div>
    );
}

interface BenutzerFormularProps {
    /** null = neuen Benutzer anlegen */
    benutzer: MandantenBenutzer | null;
    onAngelegt: (neu: BenutzerAngelegt) => void;
    onGeaendert: (b: MandantenBenutzer) => void;
    onAbbrechen: () => void;
}

function BenutzerFormular({ benutzer, onAngelegt, onGeaendert, onAbbrechen }: BenutzerFormularProps) {
    const toast = useToast();
    const istSelbst = benutzer?.is_self ?? false;
    const [vorname, setVorname] = useState(benutzer?.first_name ?? '');
    const [nachname, setNachname] = useState(benutzer?.last_name ?? '');
    const [email, setEmail] = useState(benutzer?.email ?? '');
    // Mehrere Rollen: nichts vorwählen. Ohne Auswahl bleiben alle; wer eine wählt,
    // auch die höchste, behält nur diese (PATCH role setzt genau eine App-Rolle).
    const mehrereRollen = (benutzer?.roles.length ?? 0) > 1;
    // Neue Konten sind in aller Regel Mitarbeiter-Logins (Entscheidung B8).
    const [rolle, setRolle] = useState<MandantenRolle | null>(
        benutzer ? (mehrereRollen ? null : benutzer.role) : 'production_staff',
    );

    const anlegenMutation = useMutation({
        mutationFn: (r: MandantenRolle) =>
            usersApi.create({
                email: email.trim().toLowerCase(),
                first_name: vorname.trim(),
                last_name: nachname.trim(),
                role: r,
            }),
        // Die Antwort enthält das Einmalpasswort: nicht im MutationCache halten.
        gcTime: 0,
        onSuccess: onAngelegt,
        onError: (e) => toast.error(getErrorMessage(e, 'Benutzer konnte nicht angelegt werden')),
    });

    const aendernMutation = useMutation({
        mutationFn: ({ id, aenderung }: { id: string; aenderung: BenutzerAendern }) => usersApi.update(id, aenderung),
        onSuccess: onGeaendert,
        onError: (e) => toast.error(getErrorMessage(e, 'Änderung konnte nicht gespeichert werden')),
    });

    const laeuft = anlegenMutation.isPending || aendernMutation.isPending;

    const absenden = (e: React.FormEvent) => {
        e.preventDefault();
        if (!rolle && !mehrereRollen) {
            toast.error('Bitte eine Rolle wählen.');
            return;
        }
        if (!benutzer) {
            if (rolle) anlegenMutation.mutate(rolle);
            return;
        }
        // Nur Geändertes schicken: So bleibt beim Umbenennen die Rolle unangetastet,
        // und ein Benutzer mit mehreren Rollen behält sie, solange niemand eine wählt.
        const aenderung: BenutzerAendern = {};
        if (vorname.trim() !== benutzer.first_name) aenderung.first_name = vorname.trim();
        if (nachname.trim() !== benutzer.last_name) aenderung.last_name = nachname.trim();
        if (!istSelbst && rolle && (mehrereRollen || rolle !== benutzer.role)) aenderung.role = rolle;
        if (Object.keys(aenderung).length === 0) {
            toast.info('Keine Änderungen.');
            onAbbrechen();
            return;
        }
        aendernMutation.mutate({ id: benutzer.id, aenderung });
    };

    const weitereRollen = mehrereRollen && benutzer ? benutzer.roles : [];

    return (
        <form onSubmit={absenden} className="space-y-6">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <Input label="Vorname" required value={vorname} onChange={(e) => setVorname(e.target.value)} />
                <Input label="Nachname" required value={nachname} onChange={(e) => setNachname(e.target.value)} />
            </div>

            <Input
                label="E-Mail"
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                disabled={!!benutzer}
                hint={
                    benutzer
                        ? 'Die Anmeldeadresse lässt sich nicht ändern. Für eine neue Adresse einen neuen Benutzer anlegen und den bisherigen deaktivieren.'
                        : 'Mit dieser Adresse meldet sich die Person an. Bitte ohne Umlaute.'
                }
            />

            <fieldset className="space-y-2" disabled={istSelbst}>
                <legend className="label label-required">Rolle</legend>
                {istSelbst && (
                    <p className="text-xs text-gray-500 dark:text-gray-400">
                        Die eigene Rolle kann nur ein anderer Administrator ändern.
                    </p>
                )}
                {benutzer && benutzer.roles.length === 0 && (
                    <p className="text-xs text-amber-700 dark:text-amber-300">
                        Dieser Benutzer hat bisher keine Rolle. Bitte eine wählen.
                    </p>
                )}
                {weitereRollen.length > 0 && !istSelbst && (
                    <p className="text-xs text-amber-700 dark:text-amber-300">
                        Hat derzeit mehrere Rollen ({weitereRollen.map((r) => rollenInfo(r)?.label ?? r).join(', ')}).
                        Ohne Auswahl bleiben alle erhalten. Wird eine Rolle gewählt, bleibt nur diese.
                    </p>
                )}
                {MANDANTEN_ROLLEN.map((r) => (
                    <label
                        key={r.wert}
                        className={`flex items-start gap-3 rounded-lg border p-3 ${
                            rolle === r.wert
                                ? 'border-minga-500 bg-minga-50 dark:bg-minga-900/20'
                                : 'border-gray-200 dark:border-gray-700'
                        } ${istSelbst ? 'opacity-60 cursor-not-allowed' : 'cursor-pointer'}`}
                    >
                        <input
                            type="radio"
                            name="rolle"
                            className="mt-1"
                            value={r.wert}
                            checked={rolle === r.wert}
                            onChange={() => setRolle(r.wert)}
                            required={!mehrereRollen}
                        />
                        <span>
                            <span className="block text-sm font-medium text-gray-900 dark:text-white">{r.label}</span>
                            <span className="block text-xs text-gray-600 dark:text-gray-400">{r.beschreibung}</span>
                            {r.hinweis && (
                                <span className="block text-xs text-amber-700 dark:text-amber-300 mt-1">{r.hinweis}</span>
                            )}
                        </span>
                    </label>
                ))}
            </fieldset>

            {!benutzer && (
                <p className="text-sm text-gray-600 dark:text-gray-400">
                    Nach dem Anlegen wird einmalig ein Passwort angezeigt. Beim ersten Anmelden setzt die Person ein
                    eigenes.
                </p>
            )}

            <div className="flex gap-3 pt-4 border-t dark:border-gray-700">
                <Button type="button" variant="secondary" onClick={onAbbrechen} disabled={laeuft}>
                    Abbrechen
                </Button>
                <Button type="submit" loading={laeuft} fullWidth>
                    {benutzer ? 'Speichern' : 'Anlegen'}
                </Button>
            </div>
        </form>
    );
}

function EinmalPasswortDialog({ daten, onClose }: { daten: EinmalPasswort | null; onClose: () => void }) {
    const toast = useToast();
    const kopieren = async () => {
        if (!daten) return;
        try {
            await navigator.clipboard.writeText(daten.passwort);
            toast.success('Passwort kopiert.');
        } catch {
            toast.warning('Kopieren nicht möglich. Bitte das Passwort markieren und von Hand kopieren.');
        }
    };

    return (
        <Modal
            open={!!daten}
            onClose={onClose}
            title="Einmalpasswort"
            size="sm"
            // Ein versehentliches Esc oder ein Klick daneben verwürfe das Passwort
            // unwiderruflich. Schließen nur über den Knopf oder das X.
            closeOnBackdrop={false}
            closeOnEscape={false}
            footer={<Button onClick={onClose}>Passwort ist notiert</Button>}
        >
            {daten && (
                <div className="space-y-4">
                    <p className="text-sm text-gray-600 dark:text-gray-400">
                        Anmeldename: <span className="font-medium text-gray-900 dark:text-white">{daten.anmeldename}</span>
                    </p>
                    <div className="flex items-center gap-2">
                        <code
                            data-testid="einmalpasswort"
                            className="flex-1 select-all rounded bg-gray-100 dark:bg-gray-900 px-3 py-2 font-mono text-base"
                        >
                            {daten.passwort}
                        </code>
                        <Button type="button" variant="secondary" icon={<Copy className="w-4 h-4" />} onClick={kopieren}>
                            Kopieren
                        </Button>
                    </div>
                    <Alert variant="warning">
                        Das Passwort wird nur jetzt angezeigt und nirgends gespeichert. Bitte persönlich übergeben, nicht
                        per Chat oder E-Mail. Beim ersten Anmelden muss ein eigenes Passwort gesetzt werden.
                    </Alert>
                </div>
            )}
        </Modal>
    );
}
