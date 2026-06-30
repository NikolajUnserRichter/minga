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
                    <div className="text-gray-900 dark:text-white mx-auto mb-4 inline-flex">
                      {/* Inline NovaERP-Logo */}
                      <svg viewBox="0 0 64 64" width="64" height="64" xmlns="http://www.w3.org/2000/svg">
                        <circle cx="32" cy="32" r="26" fill="none" stroke="currentColor" strokeWidth="2.5" opacity="0.85" />
                        <path d="M 32 7 L 35.5 28.5 L 57 32 L 35.5 35.5 L 32 57 L 28.5 35.5 L 7 32 L 28.5 28.5 Z" fill="#C57A3B" />
                      </svg>
                    </div>
                    <div className="text-2xl font-bold tracking-tight mb-2"><span className="text-gray-900 dark:text-white">Nova</span><span className="text-amber-600">ERP</span></div>
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
