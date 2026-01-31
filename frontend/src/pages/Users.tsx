import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Plus, Search } from 'lucide-react';
import { usersApi } from '../services/api';
import { User, UserRole } from '../types';
import { PageHeader, FilterBar } from '../components/common/Layout';
import { UserCard } from '../components/domain/UserCard';
import {
    Button,
    Input,
    Select,
    Modal,
    ConfirmDialog,
    PageLoader,
    EmptyState,
    useToast,
    SelectOption,
} from '../components/ui';

const roleOptions: SelectOption[] = [
    { value: 'all', label: 'Alle Rollen' },
    { value: 'ADMIN', label: 'Administrator' },
    { value: 'SALES', label: 'Vertrieb' },
    { value: 'PRODUCTION_PLANNER', label: 'Produktionsplanung' },
    { value: 'PRODUCTION_STAFF', label: 'Produktion' },
    { value: 'ACCOUNTING', label: 'Buchhaltung' },
];

export default function Users() {
    const toast = useToast();
    const queryClient = useQueryClient();

    const [search, setSearch] = useState('');
    const [roleFilter, setRoleFilter] = useState<string>('all');
    const [editingUser, setEditingUser] = useState<User | null>(null);
    const [isCreating, setIsCreating] = useState(false);
    const [deletingUser, setDeletingUser] = useState<User | null>(null);

    // Fetch users
    const { data: usersData, isLoading } = useQuery({
        queryKey: ['users', { role: roleFilter }],
        queryFn: () =>
            usersApi.list({
                role: roleFilter === 'all' ? undefined : (roleFilter as UserRole),
            }),
    });

    // Delete mutation
    const deleteMutation = useMutation({
        mutationFn: (id: string) => usersApi.delete(id),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['users'] });
            toast.success('Benutzer gelöscht');
            setDeletingUser(null);
        },
        onError: () => {
            toast.error('Fehler beim Löschen');
        },
    });

    const users = usersData?.items || [];
    const filteredUsers = users.filter(
        (user) =>
            user.name.toLowerCase().includes(search.toLowerCase()) ||
            user.email?.toLowerCase().includes(search.toLowerCase())
    );

    if (isLoading) {
        return <PageLoader />;
    }

    return (
        <div>
            <PageHeader
                title="Benutzerverwaltung"
                subtitle={`${users.length} Benutzer`}
                actions={
                    <Button icon={<Plus className="w-4 h-4" />} onClick={() => setIsCreating(true)}>
                        Neuer Benutzer
                    </Button>
                }
            />

            <FilterBar>
                <div className="flex-1 max-w-md">
                    <Input
                        placeholder="Suchen nach Name oder E-Mail..."
                        value={search}
                        onChange={(e) => setSearch(e.target.value)}
                        startIcon={<Search className="w-4 h-4" />}
                    />
                </div>
                <Select
                    options={roleOptions}
                    value={roleFilter}
                    onChange={(e) => setRoleFilter(e.target.value)}
                />
            </FilterBar>

            {filteredUsers.length === 0 ? (
                <EmptyState
                    title="Keine Benutzer gefunden"
                    description={search ? 'Versuche eine andere Suche.' : 'Erstelle deinen ersten Benutzer.'}
                    action={
                        !search && (
                            <Button icon={<Plus className="w-4 h-4" />} onClick={() => setIsCreating(true)}>
                                Ersten Benutzer anlegen
                            </Button>
                        )
                    }
                />
            ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                    {filteredUsers.map((user) => (
                        <UserCard
                            key={user.id}
                            user={user}
                            onEdit={() => setEditingUser(user)}
                            onDelete={() => setDeletingUser(user)}
                        />
                    ))}
                </div>
            )}

            {/* Create/Edit Modal */}
            <Modal
                open={isCreating || !!editingUser}
                onClose={() => {
                    setIsCreating(false);
                    setEditingUser(null);
                }}
                title={editingUser ? 'Benutzer bearbeiten' : 'Neuer Benutzer'}
                size="md"
            >
                <UserForm
                    user={editingUser}
                    onSubmit={() => {
                        queryClient.invalidateQueries({ queryKey: ['users'] });
                        setIsCreating(false);
                        setEditingUser(null);
                        toast.success(editingUser ? 'Benutzer aktualisiert' : 'Benutzer erstellt');
                    }}
                    onCancel={() => {
                        setIsCreating(false);
                        setEditingUser(null);
                    }}
                />
            </Modal>

            {/* Delete Confirmation */}
            <ConfirmDialog
                open={!!deletingUser}
                onClose={() => setDeletingUser(null)}
                onConfirm={() => deletingUser && deleteMutation.mutate(deletingUser.id)}
                title="Benutzer löschen?"
                message={`Möchtest du "${deletingUser?.name}" wirklich löschen? Diese Aktion kann nicht rückgängig gemacht werden.`}
                confirmLabel="Löschen"
                variant="danger"
                loading={deleteMutation.isPending}
            />
        </div>
    );
}

// User Form Component
interface UserFormProps {
    user: User | null;
    onSubmit: () => void;
    onCancel: () => void;
}

function UserForm({ user, onSubmit, onCancel }: UserFormProps) {
    const toast = useToast();
    const [loading, setLoading] = useState(false);
    const [formData, setFormData] = useState({
        name: user?.name || '',
        email: user?.email || '',
        role: user?.role || ('PRODUCTION_STAFF' as UserRole),
    });

    const userRoleOptions: SelectOption[] = [
        { value: 'ADMIN', label: 'Administrator' },
        { value: 'SALES', label: 'Vertrieb' },
        { value: 'PRODUCTION_PLANNER', label: 'Produktionsplanung' },
        { value: 'PRODUCTION_STAFF', label: 'Produktion' },
        { value: 'ACCOUNTING', label: 'Buchhaltung' },
    ];

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setLoading(true);

        try {
            if (user) {
                await usersApi.update(user.id, formData);
            } else {
                await usersApi.create(formData);
            }
            onSubmit();
        } catch (error) {
            toast.error('Fehler beim Speichern');
        } finally {
            setLoading(false);
        }
    };

    return (
        <form onSubmit={handleSubmit} className="space-y-6">
            <Input
                label="Name"
                required
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                placeholder="z.B. Max Mustermann"
            />

            <Input
                label="E-Mail"
                type="email"
                required
                value={formData.email}
                onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                placeholder="max@minga-greens.de"
            />

            <Select
                label="Rolle"
                required
                options={userRoleOptions}
                value={formData.role}
                onChange={(e) => setFormData({ ...formData, role: e.target.value as UserRole })}
            />

            <div className="flex gap-3 pt-4 border-t dark:border-gray-700">
                <Button type="button" variant="secondary" onClick={onCancel}>
                    Abbrechen
                </Button>
                <Button type="submit" loading={loading} fullWidth>
                    {user ? 'Speichern' : 'Erstellen'}
                </Button>
            </div>
        </form>
    );
}
