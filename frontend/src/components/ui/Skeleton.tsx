import { ReactNode } from 'react';

interface SkeletonProps {
  className?: string;
  style?: React.CSSProperties;
}

export function Skeleton({ className = '', style }: SkeletonProps) {
  return <div className={`skeleton ${className}`} style={style} />;
}

/** Mimics a single-line text block */
export function SkeletonText({ className = '', width = 'w-3/4' }: SkeletonProps & { width?: string }) {
  return <div className={`skeleton skeleton-text ${width} ${className}`} />;
}

/** Mimics a StatCard */
export function SkeletonStatCard() {
  return (
    <div className="card p-6 space-y-3">
      <div className="flex items-start justify-between">
        <div className="space-y-2 flex-1">
          <Skeleton className="h-3 w-24" />
          <Skeleton className="h-8 w-16" />
        </div>
        <Skeleton className="h-11 w-11 rounded-lg" />
      </div>
    </div>
  );
}

/** Mimics a list/table row */
export function SkeletonRow() {
  return (
    <div className="flex items-center gap-4 px-4 py-3 border-b border-gray-100 dark:border-gray-700">
      <Skeleton className="h-10 w-10 rounded-full" />
      <div className="flex-1 space-y-2">
        <Skeleton className="h-4 w-48" />
        <Skeleton className="h-3 w-32" />
      </div>
      <Skeleton className="h-6 w-20 rounded-full" />
    </div>
  );
}

/** Mimics a card in a grid */
export function SkeletonCard() {
  return (
    <div className="card p-4 space-y-3">
      <div className="flex items-center gap-3">
        <Skeleton className="h-10 w-10 rounded-lg" />
        <div className="space-y-1.5 flex-1">
          <Skeleton className="h-4 w-32" />
          <Skeleton className="h-3 w-20" />
        </div>
      </div>
      <Skeleton className="h-3 w-full" />
      <Skeleton className="h-3 w-2/3" />
    </div>
  );
}

/** Mimics a chart area */
export function SkeletonChart({ height = 'h-80' }: { height?: string }) {
  return (
    <div className="card p-6 space-y-4">
      <Skeleton className="h-5 w-48" />
      <div className={`${height} flex items-end gap-2 pt-4`}>
        {Array.from({ length: 8 }).map((_, i) => (
          <div key={i} className="flex-1 flex flex-col justify-end">
            <Skeleton
              className="w-full rounded-t-sm"
              // Varying heights for realistic bar chart skeleton
              style={{ height: `${30 + Math.random() * 60}%` } as React.CSSProperties}
            />
          </div>
        ))}
      </div>
    </div>
  );
}

/** Full-page skeleton for dashboard-style pages */
export function DashboardSkeleton() {
  return (
    <div className="space-y-6 animate-pulse">
      {/* Header */}
      <div className="space-y-2">
        <Skeleton className="h-7 w-40" />
        <Skeleton className="h-4 w-56" />
      </div>
      {/* Stat cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <SkeletonStatCard />
        <SkeletonStatCard />
        <SkeletonStatCard />
        <SkeletonStatCard />
      </div>
      {/* Content cards */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="card p-6 space-y-3">
          <Skeleton className="h-5 w-40" />
          <SkeletonRow />
          <SkeletonRow />
          <SkeletonRow />
        </div>
        <div className="card p-6 space-y-3">
          <Skeleton className="h-5 w-48" />
          <SkeletonRow />
          <SkeletonRow />
          <SkeletonRow />
        </div>
      </div>
    </div>
  );
}

/** Full-page skeleton for list/table pages */
export function ListPageSkeleton({ rows = 6 }: { rows?: number }) {
  return (
    <div className="space-y-6 animate-pulse">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="space-y-2">
          <Skeleton className="h-7 w-40" />
          <Skeleton className="h-4 w-56" />
        </div>
        <Skeleton className="h-10 w-36 rounded-lg" />
      </div>
      {/* Filter bar */}
      <div className="card p-4 flex gap-3">
        <Skeleton className="h-10 flex-1 max-w-md rounded-lg" />
        <Skeleton className="h-10 w-40 rounded-lg" />
      </div>
      {/* Table rows */}
      <div className="card overflow-hidden">
        <div className="px-4 py-3 bg-gray-50 dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700">
          <div className="flex gap-8">
            <Skeleton className="h-3 w-24" />
            <Skeleton className="h-3 w-20" />
            <Skeleton className="h-3 w-16" />
            <Skeleton className="h-3 w-20" />
          </div>
        </div>
        {Array.from({ length: rows }).map((_, i) => (
          <SkeletonRow key={i} />
        ))}
      </div>
    </div>
  );
}

/** Wrapper: shows skeleton while loading, children when done */
interface SkeletonGateProps {
  loading: boolean;
  skeleton: ReactNode;
  children: ReactNode;
}

export function SkeletonGate({ loading, skeleton, children }: SkeletonGateProps) {
  return <>{loading ? skeleton : children}</>;
}
