/**
 * NovaERP-Logo als Inline-SVG.
 * Damit funktioniert die App unabhängig vom Vorhandensein einer logo.png.
 * Falls /logo.png existiert (vom User selbst hochgeladen) bevorzugt die App
 * dort wo es passt diese Datei — sonst fällt sie auf dieses SVG zurück.
 */

interface LogoProps {
  size?: number;
  variant?: 'mark' | 'lockup'; // mark = nur Icon, lockup = Icon + "NovaERP"
  className?: string;
}

const COPPER = '#C57A3B';

export function NovaLogo({ size = 32, variant = 'mark', className = '' }: LogoProps) {
  if (variant === 'lockup') {
    return (
      <span className={`inline-flex items-center gap-2 ${className}`}>
        <NovaMark size={size} />
        <span className="font-bold tracking-tight" style={{ fontSize: size * 0.55 }}>
          <span className="text-gray-900 dark:text-white">Nova</span>
          <span className="text-gray-400 mx-0.5">|</span>
          <span style={{ color: COPPER }}>ERP</span>
        </span>
      </span>
    );
  }
  return <NovaMark size={size} className={className} />;
}

function NovaMark({ size, className }: { size: number; className?: string }) {
  return (
    <svg
      viewBox="0 0 64 64"
      width={size}
      height={size}
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      aria-label="NovaERP"
    >
      {/* Outer ring */}
      <circle cx="32" cy="32" r="28" fill="none" stroke="currentColor" strokeWidth="3" />
      {/* Four-point sparkle (Nova-Stern) */}
      <path
        d="M 32 12 L 35 29 L 52 32 L 35 35 L 32 52 L 29 35 L 12 32 L 29 29 Z"
        fill={COPPER}
      />
    </svg>
  );
}

export default NovaLogo;
