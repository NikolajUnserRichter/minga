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
                    <img src="/logo.png" alt="Minga Greens" className="w-24 h-24 mx-auto mb-4 object-contain invert dark:invert-0" />
                    <div className="text-2xl font-semibold text-emerald-600 mb-2">Minga Greens ERP</div>
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
