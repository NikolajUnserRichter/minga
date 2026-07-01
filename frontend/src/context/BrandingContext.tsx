import React, { createContext, useContext, useEffect, useState } from 'react';

export interface Branding {
  edition: string;
  name: string;
  wordmark: [string, string];
  colors: { a: string; b: string; mid: string; primary: string };
  icon: 'sprout' | 'trade' | 'nova';
  hidden_modules: string[];
  tagline: string;
}

// Default = Sprouddesk (Farming) — verhindert Null-Flash bevor der Fetch da ist.
const DEFAULT_BRANDING: Branding = {
  edition: 'sprouddesk',
  name: 'Sprouddesk',
  wordmark: ['Sproud', 'desk'],
  colors: { a: '#1F7A3D', b: '#86CB3C', mid: '#3FA52A', primary: '#2E9A4B' },
  icon: 'sprout',
  hidden_modules: [],
  tagline: 'Grow smart. Run your farm.',
};

const BrandingContext = createContext<Branding>(DEFAULT_BRANDING);

const API_URL = import.meta.env.VITE_API_URL ?? (import.meta.env.DEV ? 'http://localhost:8000' : '');

export const BrandingProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [branding, setBranding] = useState<Branding>(DEFAULT_BRANDING);

  useEffect(() => {
    let cancelled = false;
    // Öffentlicher Endpoint, kein Auth nötig — lädt Tenant-Branding via Subdomain.
    fetch(`${API_URL}/api/v1/branding`)
      .then((r) => (r.ok ? r.json() : null))
      .then((b: Branding | null) => {
        if (!cancelled && b && b.name) {
          setBranding(b);
          document.title = b.name;
        }
      })
      .catch(() => { /* Default behalten */ });
    return () => { cancelled = true; };
  }, []);

  return <BrandingContext.Provider value={branding}>{children}</BrandingContext.Provider>;
};

export const useBranding = () => useContext(BrandingContext);
