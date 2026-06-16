import { useQuery } from '@tanstack/react-query';
import { authApi } from '../services/api';

/**
 * Liefert `true` wenn der eingeloggte User Read-Only-Demo ist.
 * Wird vom Banner + von Write-Buttons konsumiert um die UI zu sperren.
 *
 * Backend ist die Source of Truth (FastAPI-Middleware blockt zusätzlich
 * jede POST/PATCH/PUT/DELETE-Methode). Frontend-Gating ist nur UX —
 * verhindert Klicks die sowieso 403 zurückkommen würden.
 */
export function useReadOnlyMode(): { isReadOnly: boolean; username: string | null } {
  const { data } = useQuery({
    queryKey: ['auth', 'whoami'],
    queryFn: () => authApi.whoami(),
    staleTime: 5 * 60_000,
    refetchOnWindowFocus: false,
  });
  return {
    isReadOnly: data?.role === 'READONLY',
    username: data?.username ?? null,
  };
}
