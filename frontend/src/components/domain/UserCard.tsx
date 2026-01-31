import { User, UserRole } from '../../types';
import { Badge } from '../ui';
import { Mail, Edit2, Trash2, Shield } from 'lucide-react';

// Role display names and colors (using valid BadgeVariant types)
const roleConfig: Record<UserRole, { label: string; variant: 'success' | 'info' | 'warning' | 'purple' | 'gray' | 'danger' }> = {
    ADMIN: { label: 'Administrator', variant: 'purple' },
    SALES: { label: 'Vertrieb', variant: 'info' },
    PRODUCTION_PLANNER: { label: 'Produktionsplanung', variant: 'success' },
    PRODUCTION_STAFF: { label: 'Produktion', variant: 'warning' },
    ACCOUNTING: { label: 'Buchhaltung', variant: 'gray' },
};

interface UserCardProps {
    user: User;
    onEdit?: () => void;
    onDelete?: () => void;
}

export function UserCard({ user, onEdit, onDelete }: UserCardProps) {
    const config = roleConfig[user.role];

    // Generate initials from name
    const initials = user.name
        .split(' ')
        .map((n) => n[0])
        .join('')
        .toUpperCase();

    return (
        <div className="card card-hover">
            <div className="card-body">
                <div className="flex items-start gap-4">
                    {/* Avatar */}
                    <div className="w-12 h-12 rounded-full bg-minga-100 dark:bg-minga-900/50 flex items-center justify-center text-minga-700 dark:text-minga-400 font-semibold text-lg flex-shrink-0">
                        {user.avatar ? (
                            <img src={user.avatar} alt={user.name} className="w-full h-full rounded-full object-cover" />
                        ) : (
                            initials
                        )}
                    </div>

                    <div className="flex-1 min-w-0">
                        <h3 className="font-semibold text-gray-900 dark:text-white truncate">{user.name}</h3>
                        <div className="flex items-center gap-2 mt-1">
                            <Badge variant={config.variant}>
                                <Shield className="w-3 h-3 mr-1" />
                                {config.label}
                            </Badge>
                        </div>
                    </div>
                </div>

                <div className="mt-4 space-y-2">
                    <div className="flex items-center gap-2 text-sm text-gray-600 dark:text-gray-400">
                        <Mail className="w-4 h-4 text-gray-400" />
                        <a href={`mailto:${user.email}`} className="hover:text-minga-600 truncate">
                            {user.email}
                        </a>
                    </div>
                </div>

                {(onEdit || onDelete) && (
                    <div className="mt-4 pt-4 border-t border-gray-100 dark:border-gray-700 flex flex-wrap gap-2">
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
                                className="btn btn-ghost btn-sm text-red-600 hover:text-red-700 hover:bg-red-50 dark:hover:bg-red-900/20"
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
