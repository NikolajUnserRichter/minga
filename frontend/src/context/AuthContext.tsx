import React, { createContext, useContext, useEffect, useState } from 'react';
import keycloak from '../services/auth';

const AUTH_DISABLED = import.meta.env.VITE_AUTH_DISABLED === 'true';

interface AuthContextType {
    authenticated: boolean;
    token?: string;
    user?: {
        username?: string;
        email?: string;
        firstName?: string;
        lastName?: string;
        roles?: string[];
    };
    login: () => void;
    logout: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

const DEV_USER = {
    username: 'admin',
    email: 'admin@minga-greens.de',
    firstName: 'Admin',
    lastName: 'Minga',
    roles: ['admin', 'sales', 'production_planner', 'production_staff', 'accounting'],
};

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
    const [authenticated, setAuthenticated] = useState(AUTH_DISABLED);
    const [loading, setLoading] = useState(!AUTH_DISABLED);

    useEffect(() => {
        if (AUTH_DISABLED) return;

        const initKeycloak = async () => {
            try {
                const auth = await keycloak.init({
                    onLoad: 'login-required',
                    pkceMethod: 'S256',
                });

                if (auth) {
                    setAuthenticated(true);
                }
            } catch (_error) {
                // Keycloak init failed
            } finally {
                setLoading(false);
            }
        };

        if (!keycloak.didInitialize) {
            initKeycloak();
        }
    }, []);

    if (loading) {
        return (
            <div className="flex items-center justify-center h-screen bg-gray-50 dark:bg-gray-900">
                <div className="text-center">
                    <div className="mx-auto mb-4 inline-flex">
                      {/* Inline Sprouddesk-Logo (Sprossen-Blätter) */}
                      <svg viewBox="0 0 48 48" width="64" height="64" fill="none" xmlns="http://www.w3.org/2000/svg">
                        <path d="M24 43 V25" stroke="#1F7A3D" strokeWidth="3" strokeLinecap="round" />
                        <path d="M23 27 C23 17 13.5 12.5 7 12.5 C7 22.5 15 28.5 23 26.5 Z" fill="#3FA52A" />
                        <path d="M25 25 C25 14.5 35 9.5 42 9.5 C42 19.5 32.5 26.5 25 24.5 Z" fill="#86CB3C" />
                      </svg>
                    </div>
                    <div className="text-2xl font-extrabold tracking-tight mb-2"><span style={{ color: '#1F7A3D' }}>Sproud</span><span style={{ color: '#86CB3C' }}>desk</span></div>
                    <div className="text-gray-500 dark:text-gray-400">Authentifizierung läuft...</div>
                </div>
            </div>
        )
    }

    const user = AUTH_DISABLED
        ? DEV_USER
        : authenticated ? {
            username: keycloak.tokenParsed?.preferred_username,
            email: keycloak.tokenParsed?.email,
            firstName: keycloak.tokenParsed?.given_name,
            lastName: keycloak.tokenParsed?.family_name,
            roles: keycloak.realmAccess?.roles
        } : undefined;

    return (
        <AuthContext.Provider value={{
            authenticated,
            token: AUTH_DISABLED ? 'dev-bypass-token' : keycloak.token,
            user,
            login: AUTH_DISABLED ? () => {} : keycloak.login,
            logout: AUTH_DISABLED ? () => { window.location.href = '/'; } : keycloak.logout
        }}>
            {children}
        </AuthContext.Provider>
    );
};

export const useAuth = () => {
    const context = useContext(AuthContext);
    if (context === undefined) {
        throw new Error('useAuth must be used within an AuthProvider');
    }
    return context;
};
