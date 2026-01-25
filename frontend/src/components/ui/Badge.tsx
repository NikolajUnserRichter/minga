import { ReactNode } from 'react';
import { GrowBatchStatus, OrderStatus, SuggestionStatus, CustomerType } from '../../types';

type BadgeVariant = 'success' | 'warning' | 'danger' | 'info' | 'gray' | 'purple';
type BadgeSize = 'sm' | 'md' | 'lg';

interface BadgeProps {
  children: ReactNode;
  variant?: BadgeVariant;
  size?: BadgeSize;
  icon?: ReactNode;
  className?: string;
}

const variantClasses: Record<BadgeVariant, string> = {
  success: 'badge-success',
  warning: 'badge-warning',
  danger: 'badge-danger',
  info: 'badge-info',
  gray: 'badge-gray',
  purple: 'badge-purple',
};

const sizeClasses: Record<BadgeSize, string> = {
  sm: 'badge-sm',
  md: '',
  lg: 'badge-lg',
};

export function Badge({ children, variant = 'gray', size = 'md', icon, className = '' }: BadgeProps) {
  return (
    <span className={`badge ${variantClasses[variant]} ${sizeClasses[size]} ${className}`}>
      {icon}
      {children}
    </span>
  );
}

// Grow Batch Status Badge
const growBatchStatusConfig: Record<GrowBatchStatus, { label: string; class: string }> = {
  KEIMUNG: { label: 'Keimung', class: 'badge-keimung' },
  WACHSTUM: { label: 'Wachstum', class: 'badge-wachstum' },
  ERNTEREIF: { label: 'Erntereif', class: 'badge-erntereif' },
  GEERNTET: { label: 'Geerntet', class: 'badge-geerntet' },
  VERLUST: { label: 'Verlust', class: 'badge-verlust' },
};

interface GrowBatchStatusBadgeProps {
  status: GrowBatchStatus;
}

export function GrowBatchStatusBadge({ status }: GrowBatchStatusBadgeProps) {
  const config = growBatchStatusConfig[status];
  return <span className={`badge ${config.class}`}>{config.label}</span>;
}

// Order Status Badge
const orderStatusConfig: Record<OrderStatus, { label: string; variant: BadgeVariant }> = {
  OFFEN: { label: 'Offen', variant: 'gray' },
  BESTAETIGT: { label: 'Bestätigt', variant: 'info' },
  IN_PRODUKTION: { label: 'In Produktion', variant: 'warning' },
  BEREIT: { label: 'Bereit', variant: 'success' },
  GELIEFERT: { label: 'Geliefert', variant: 'gray' },
  STORNIERT: { label: 'Storniert', variant: 'danger' },
};

interface OrderStatusBadgeProps {
  status: OrderStatus;
}

export function OrderStatusBadge({ status }: OrderStatusBadgeProps) {
  const config = orderStatusConfig[status];
  return <Badge variant={config.variant}>{config.label}</Badge>;
}

// Suggestion Status Badge
const suggestionStatusConfig: Record<SuggestionStatus, { label: string; variant: BadgeVariant }> = {
  VORGESCHLAGEN: { label: 'Vorgeschlagen', variant: 'warning' },
  GENEHMIGT: { label: 'Genehmigt', variant: 'success' },
  ABGELEHNT: { label: 'Abgelehnt', variant: 'danger' },
  UMGESETZT: { label: 'Umgesetzt', variant: 'gray' },
};

interface SuggestionStatusBadgeProps {
  status: SuggestionStatus;
}

export function SuggestionStatusBadge({ status }: SuggestionStatusBadgeProps) {
  const config = suggestionStatusConfig[status];
  return <Badge variant={config.variant}>{config.label}</Badge>;
}

// Customer Type Badge
const customerTypeConfig: Record<CustomerType, { label: string; variant: BadgeVariant }> = {
  GASTRO: { label: 'Gastro', variant: 'purple' },
  HANDEL: { label: 'Handel', variant: 'info' },
  PRIVAT: { label: 'Privat', variant: 'gray' },
};

interface CustomerTypeBadgeProps {
  type: CustomerType;
}

export function CustomerTypeBadge({ type }: CustomerTypeBadgeProps) {
  const config = customerTypeConfig[type];
  return <Badge variant={config.variant}>{config.label}</Badge>;
}

// Warning Count Badge
interface WarningBadgeProps {
  count: number;
}

export function WarningBadge({ count }: WarningBadgeProps) {
  if (count === 0) return null;
  return (
    <Badge variant="warning">
      {count} {count === 1 ? 'Warnung' : 'Warnungen'}
    </Badge>
  );
}
