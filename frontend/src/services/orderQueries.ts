import type { QueryClient } from '@tanstack/react-query';

/**
 * Alle Ansichten, die den Bestellstatus zeigen. Nach jedem Statuswechsel neu
 * laden — sonst zeigt ein offener Tagesplan (Hallen-Tablet) den alten Stand,
 * weil main.tsx refetchOnWindowFocus abschaltet.
 * 'packagingPlan' (Production.tsx) und 'packaging-plan' (Tagesplan.tsx) sind
 * zwei Schlüssel für denselben Endpunkt.
 */
const BESTELL_ANSICHTEN = [['orders'], ['day-plan'], ['packaging-plan'], ['packagingPlan']];

export async function invalidateOrderViews(queryClient: QueryClient): Promise<void> {
  await Promise.all(
    BESTELL_ANSICHTEN.map((queryKey) => queryClient.invalidateQueries({ queryKey })),
  );
}
