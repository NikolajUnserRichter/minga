import React, { createContext, useContext, useEffect, useState } from 'react';
import keycloak from '../services/auth';

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

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
    const [authenticated, setAuthenticated] = useState(false);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        // Check if auth is enabled via env var, otherwise bypass for dev comfort
        // But since we installed Keycloak, let's try to initialize it.
        // Making initialization idempotent
        const initKeycloak = async () => {
            try {
                const auth = await keycloak.init({
                    onLoad: 'login-required', // or 'check-sso'
                    pkceMethod: 'S256',
                    // silentCheckSsoRedirectUri: window.location.origin + '/silent-check-sso.html'
                });

                if (auth) {
                    setAuthenticated(true);
                }
            } catch (error) {
                console.error("Keycloak Init Failed", error);
                // Fallback for dev if Keycloak isn't running?
                // setAuthenticated(true); // UNSAFE default
            } finally {
                setLoading(false);
            }
        };

        // Safety check to prevent double init in React 18 Strict Mode
        if (!keycloak.didInitialize) {
            initKeycloak();
        }
    }, []);

    if (loading) {
        return (
            <div className="flex items-center justify-center h-screen bg-gray-50">
                <div className="text-center">
                    <div className="text-2xl font-semibold text-emerald-600 mb-2">Minga Greens ERP</div>
                    <div className="text-gray-500">Authentifizierung läuft...</div>
                </div>
            </div>
        )
    }

    const user = authenticated ? {
        username: keycloak.tokenParsed?.preferred_username,
        email: keycloak.tokenParsed?.email,
        firstName: keycloak.tokenParsed?.given_name,
        lastName: keycloak.tokenParsed?.family_name,
        roles: keycloak.realmAccess?.roles
    } : undefined;

    return (
        <AuthContext.Provider value={{
            authenticated,
            token: keycloak.token,
            user,
            login: keycloak.login,
            logout: keycloak.logout
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
