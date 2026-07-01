/**
 * Dynamisches Editions-Logo. Rendert Icon + Wortmarke passend zum
 * Tenant-Branding (sprouddesk = grün/Sprossen, tradesk = blau/Handel,
 * novaerp = kupfer/Kompass). Export-Name bleibt `NovaLogo` für Kompatibilität.
 */
import { useBranding } from '../../context/BrandingContext';

interface LogoProps {
  size?: number;
  variant?: 'mark' | 'lockup';
  className?: string;
}

export function NovaLogo({ size = 32, variant = 'mark', className = '' }: LogoProps) {
  const b = useBranding();
  if (variant === 'lockup') {
    return (
      <span className={`inline-flex items-center gap-2 ${className}`}>
        <EditionMark icon={b.icon} colors={b.colors} size={size} />
        <span className="font-extrabold tracking-tight" style={{ fontSize: size * 0.55 }}>
          <span style={{ color: b.colors.a }}>{b.wordmark[0]}</span>
          <span style={{ color: b.colors.b }}>{b.wordmark[1]}</span>
        </span>
      </span>
    );
  }
  return <EditionMark icon={b.icon} colors={b.colors} size={size} className={className} />;
}

interface MarkProps {
  icon: string;
  colors: { a: string; b: string; mid: string; primary: string };
  size: number;
  className?: string;
}

export function EditionMark({ icon, colors, size, className }: MarkProps) {
  if (icon === 'trade') {
    // Handel/Distribution — Box mit Pfeil (Warenfluss)
    return (
      <svg viewBox="0 0 48 48" width={size} height={size} fill="none" xmlns="http://www.w3.org/2000/svg" className={className} aria-label="Tradesk">
        <path d="M24 6 L41 15 V33 L24 42 L7 33 V15 Z" stroke={colors.a} strokeWidth="3" strokeLinejoin="round" />
        <path d="M7 15 L24 24 L41 15" stroke={colors.mid} strokeWidth="2.5" strokeLinejoin="round" />
        <path d="M24 24 V42" stroke={colors.mid} strokeWidth="2.5" />
        <path d="M18 27 L24 30 L30 27" stroke={colors.b} strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    );
  }
  if (icon === 'nova') {
    // NovaERP — Kompass-Stern im Ring
    return (
      <svg viewBox="0 0 64 64" width={size} height={size} xmlns="http://www.w3.org/2000/svg" className={className} aria-label="NovaERP">
        <circle cx="32" cy="32" r="26" fill="none" stroke="currentColor" strokeWidth="2.5" opacity="0.85" />
        <path d="M 32 7 L 35.5 28.5 L 57 32 L 35.5 35.5 L 32 57 L 28.5 35.5 L 7 32 L 28.5 28.5 Z" fill={colors.b} />
      </svg>
    );
  }
  // Default: sprouddesk — Sprossen-Blätter
  return (
    <svg viewBox="0 0 48 48" width={size} height={size} fill="none" xmlns="http://www.w3.org/2000/svg" className={className} aria-label="Sprouddesk">
      <path d="M24 43 V25" stroke={colors.a} strokeWidth="3" strokeLinecap="round" />
      <path d="M23 27 C23 17 13.5 12.5 7 12.5 C7 22.5 15 28.5 23 26.5 Z" fill={colors.mid} />
      <path d="M25 25 C25 14.5 35 9.5 42 9.5 C42 19.5 32.5 26.5 25 24.5 Z" fill={colors.b} />
    </svg>
  );
}

export default NovaLogo;
