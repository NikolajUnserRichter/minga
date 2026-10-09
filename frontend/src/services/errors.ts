/**
 * Error message helper.
 *
 * FastAPI 422 returns `detail` as an array of validation errors:
 *   [{type, loc, msg, input, url}, ...]
 *
 * Other errors return `detail` as a string. Toast/UI components can't render
 * objects → use this helper everywhere we surface backend errors.
 */
export function getErrorMessage(error: unknown, fallback = 'Fehler'): string {
  const detail = (error as any)?.response?.data?.detail;

  if (typeof detail === 'string') return detail;

  if (Array.isArray(detail)) {
    return detail
      .map((d) => {
        const field = Array.isArray(d?.loc) ? d.loc.slice(1).join('.') : '';
        const msg = d?.msg || 'Ungültiger Wert';
        if (d?.type === 'empfaengerliste') return msg;
        return field ? `${field}: ${msg}` : msg;
      })
      .join(' · ');
  }

  if (typeof detail === 'object' && detail !== null && 'msg' in detail) {
    return (detail as any).msg || fallback;
  }

  if (error instanceof Error && error.message) return error.message;

  return fallback;
}

export function getFieldErrors(error: unknown): Record<string, string> {
  const detail = (error as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail;
  if (!Array.isArray(detail)) return {};
  return Object.fromEntries(
    detail
      .filter((item) => Array.isArray(item?.loc) && item.loc[0] === 'body' && item.loc.length > 1)
      .map((item) => [item.loc.slice(1).join('.'), item.msg || 'Ungültiger Wert']),
  );
}
