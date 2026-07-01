/**
 * Sprouddesk-Logo (Branchen-Edition von NovaERP für Farmen & Manufakturen).
 * Inline-SVG: zwei grüne Sprossen-Blätter + Wortmarke "Sprouddesk".
 * Export-Name bleibt `NovaLogo` für Kompatibilität mit bestehenden Imports.
 */

interface LogoProps {
  size?: number;
  variant?: 'mark' | 'lockup'; // mark = nur Icon, lockup = Icon + "Sprouddesk"
  className?: string;
}

const GREEN_DARK = '#1F7A3D';
const GREEN_MID = '#3FA52A';
const GREEN_LIGHT = '#86CB3C';

export function NovaLogo({ size = 32, variant = 'mark', className = '' }: LogoProps) {
  if (variant === 'lockup') {
    return (
      <span className={`inline-flex items-center gap-2 ${className}`}>
        <SproutMark size={size} />
        <span className="font-extrabold tracking-tight" style={{ fontSize: size * 0.55 }}>
          <span style={{ color: GREEN_DARK }}>Sproud</span>
          <span style={{ color: GREEN_LIGHT }}>desk</span>
        </span>
      </span>
    );
  }
  return <SproutMark size={size} className={className} />;
}

function SproutMark({ size, className }: { size: number; className?: string }) {
  return (
    <svg
      viewBox="0 0 48 48"
      width={size}
      height={size}
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      aria-label="Sprouddesk"
    >
      {/* Stängel */}
      <path d="M24 43 V25" stroke={GREEN_DARK} strokeWidth="3" strokeLinecap="round" />
      {/* Linkes Blatt */}
      <path d="M23 27 C23 17 13.5 12.5 7 12.5 C7 22.5 15 28.5 23 26.5 Z" fill={GREEN_MID} />
      {/* Rechtes Blatt */}
      <path d="M25 25 C25 14.5 35 9.5 42 9.5 C42 19.5 32.5 26.5 25 24.5 Z" fill={GREEN_LIGHT} />
    </svg>
  );
}

export default NovaLogo;
