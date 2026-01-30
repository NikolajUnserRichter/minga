import { Outlet, NavLink } from 'react-router-dom';
import {
  LayoutDashboard,
  Sprout,
  Layers,
  Scissors,
  Users,
  FileText,
  RefreshCw,
  TrendingUp,
  Target,
  BarChart3,
  Settings,
  UserCog,
  Menu,
  X,
  LogOut,
  ChevronDown,
  Warehouse,
  Receipt,
  Tag,
} from 'lucide-react';
import { useState, createContext, useContext, ReactNode } from 'react';
import { UserRole, User } from '../../types';

// Navigation configuration with role-based visibility
interface NavItem {
  name: string;
  href: string;
  icon: React.ComponentType<{ className?: string }>;
  roles: UserRole[];
}

interface NavSection {
  title: string;
  items: NavItem[];
}

const navigationSections: NavSection[] = [
  {
    title: '',
    items: [
      {
        name: 'Dashboard',
        href: '/dashboard',
        icon: LayoutDashboard,
        roles: ['ADMIN', 'SALES', 'PRODUCTION_PLANNER', 'PRODUCTION_STAFF', 'ACCOUNTING'],
      },
    ],
  },
  {
    title: 'Stammdaten',
    items: [
      {
        name: 'Saatgut',
        href: '/seeds',
        icon: Sprout,
        roles: ['ADMIN', 'SALES', 'PRODUCTION_PLANNER', 'PRODUCTION_STAFF', 'ACCOUNTING'],
      },
      {
        name: 'Produkte',
        href: '/products',
        icon: Tag,
        roles: ['ADMIN', 'SALES', 'PRODUCTION_PLANNER', 'ACCOUNTING'],
      },
      {
        name: 'Lager',
        href: '/inventory',
        icon: Warehouse,
        roles: ['ADMIN', 'SALES', 'PRODUCTION_PLANNER', 'PRODUCTION_STAFF', 'ACCOUNTING'],
      },
    ],
  },
  {
    title: 'Produktion',
    items: [
      {
        name: 'Wachstumschargen',
        href: '/production',
        icon: Layers,
        roles: ['ADMIN', 'PRODUCTION_PLANNER', 'PRODUCTION_STAFF'],
      },
      {
        name: 'Ernten',
        href: '/harvests',
        icon: Scissors,
        roles: ['ADMIN', 'PRODUCTION_PLANNER', 'PRODUCTION_STAFF'],
      },
    ],
  },
  {
    title: 'Vertrieb',
    items: [
      {
        name: 'Kunden',
        href: '/customers',
        icon: Users,
        roles: ['ADMIN', 'SALES', 'ACCOUNTING'],
      },
      {
        name: 'Bestellungen',
        href: '/orders',
        icon: FileText,
        roles: ['ADMIN', 'SALES', 'PRODUCTION_PLANNER', 'ACCOUNTING'],
      },
      {
        name: 'Abonnements',
        href: '/subscriptions',
        icon: RefreshCw,
        roles: ['ADMIN', 'SALES', 'PRODUCTION_PLANNER', 'ACCOUNTING'],
      },
      {
        name: 'Rechnungen',
        href: '/invoices',
        icon: Receipt,
        roles: ['ADMIN', 'SALES', 'ACCOUNTING'],
      },
    ],
  },
  {
    title: 'Forecasting',
    items: [
      {
        name: 'Prognosen',
        href: '/forecasting',
        icon: TrendingUp,
        roles: ['ADMIN', 'SALES', 'PRODUCTION_PLANNER', 'ACCOUNTING'],
      },
      {
        name: 'Produktionsvorschläge',
        href: '/suggestions',
        icon: Target,
        roles: ['ADMIN', 'PRODUCTION_PLANNER'],
      },
      {
        name: 'Accuracy Reports',
        href: '/accuracy',
        icon: BarChart3,
        roles: ['ADMIN', 'PRODUCTION_PLANNER', 'ACCOUNTING'],
      },
    ],
  },
  {
    title: 'Admin',
    items: [
      {
        name: 'Einstellungen',
        href: '/settings',
        icon: Settings,
        roles: ['ADMIN'],
      },
      {
        name: 'Benutzerverwaltung',
        href: '/users',
        icon: UserCog,
        roles: ['ADMIN'],
      },
    ],
  },
];

// Role display names
const roleDisplayNames: Record<UserRole, string> = {
  ADMIN: 'Administrator',
  SALES: 'Vertrieb',
  PRODUCTION_PLANNER: 'Produktionsplanung',
  PRODUCTION_STAFF: 'Produktion',
  ACCOUNTING: 'Buchhaltung',
};

// User Context for role-based UI
interface UserContextType {
  user: User;
  setUser: (user: User) => void;
}

const UserContext = createContext<UserContextType | null>(null);

export function useUser() {
  const context = useContext(UserContext);
  if (!context) {
    throw new Error('useUser must be used within a UserProvider');
  }
  return context;
}

// Mock user - in real app, this would come from auth
const mockUser: User = {
  id: '1',
  name: 'Max Mustermann',
  email: 'max@minga-greens.de',
  role: 'PRODUCTION_PLANNER',
};

export default function Layout() {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [user, setUser] = useState<User>(mockUser);
  const [userMenuOpen, setUserMenuOpen] = useState(false);


  // Filter navigation based on user role
  const filteredNavigation = navigationSections
    .map((section) => ({
      ...section,
      items: section.items.filter((item) => item.roles.includes(user.role)),
    }))
    .filter((section) => section.items.length > 0);

  const getGreeting = () => {
    const hour = new Date().getHours();
    if (hour < 12) return 'Guten Morgen';
    if (hour < 18) return 'Guten Tag';
    return 'Guten Abend';
  };

  return (
    <UserContext.Provider value={{ user, setUser }}>
      <div className="min-h-screen bg-gray-50">
        {/* Mobile Sidebar Overlay */}
        {sidebarOpen && (
          <div
            className="fixed inset-0 z-40 bg-black/50 lg:hidden animate-fade-in"
            onClick={() => setSidebarOpen(false)}
          />
        )}

        {/* Sidebar */}
        <aside
          className={`fixed inset-y-0 left-0 z-50 w-64 bg-white border-r border-gray-200 transform transition-transform duration-200 lg:translate-x-0 flex flex-col ${sidebarOpen ? 'translate-x-0' : '-translate-x-full'
            }`}
        >
          {/* Logo */}
          <div className="flex items-center justify-between h-16 px-6 border-b border-gray-200 flex-shrink-0">
            <NavLink to="/dashboard" className="flex items-center gap-3">
              <div className="w-8 h-8 bg-minga-500 rounded-lg flex items-center justify-center">
                <Sprout className="w-5 h-5 text-white" />
              </div>
              <span className="text-lg font-bold text-gray-900">Minga-Greens</span>
            </NavLink>
            <button
              className="lg:hidden p-2 text-gray-500 hover:text-gray-700 rounded-lg hover:bg-gray-100"
              onClick={() => setSidebarOpen(false)}
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          {/* Navigation */}
          <nav className="flex-1 overflow-y-auto py-4 scrollbar-thin">
            {filteredNavigation.map((section, idx) => (
              <div key={idx} className="nav-section">
                {section.title && (
                  <p className="nav-section-title">{section.title}</p>
                )}
                <div className="space-y-1">
                  {section.items.map((item) => (
                    <NavLink
                      key={item.name}
                      to={item.href}
                      className={({ isActive }) =>
                        `nav-item ${isActive ? 'nav-item-active' : ''}`
                      }
                      onClick={() => setSidebarOpen(false)}
                    >
                      <item.icon className="nav-item-icon" />
                      {item.name}
                    </NavLink>
                  ))}
                </div>
              </div>
            ))}
          </nav>

          {/* User Info */}
          <div className="border-t border-gray-200 p-4 flex-shrink-0">
            <div className="relative">
              <button
                onClick={() => setUserMenuOpen(!userMenuOpen)}
                className="w-full flex items-center gap-3 p-2 rounded-lg hover:bg-gray-100 transition-colors"
              >
                <div className="avatar avatar-md bg-minga-100 text-minga-700">
                  {user.name
                    .split(' ')
                    .map((n) => n[0])
                    .join('')}
                </div>
                <div className="flex-1 text-left">
                  <p className="text-sm font-medium text-gray-900">{user.name}</p>
                  <p className="text-xs text-gray-500">{roleDisplayNames[user.role]}</p>
                </div>
                <ChevronDown
                  className={`w-4 h-4 text-gray-400 transition-transform ${userMenuOpen ? 'rotate-180' : ''
                    }`}
                />
              </button>

              {/* User Dropdown Menu */}
              {userMenuOpen && (
                <div className="absolute bottom-full left-0 right-0 mb-2 bg-white rounded-lg shadow-lg border border-gray-200 py-1 animate-slide-up">
                  <div className="px-3 py-2 border-b border-gray-100">
                    <p className="text-xs text-gray-500">Rolle wechseln (Demo)</p>
                  </div>
                  {(
                    ['ADMIN', 'SALES', 'PRODUCTION_PLANNER', 'PRODUCTION_STAFF', 'ACCOUNTING'] as UserRole[]
                  ).map((role) => (
                    <button
                      key={role}
                      onClick={() => {
                        setUser({ ...user, role });
                        setUserMenuOpen(false);
                      }}
                      className={`w-full text-left px-3 py-2 text-sm hover:bg-gray-50 ${user.role === role ? 'text-minga-600 font-medium' : 'text-gray-700'
                        }`}
                    >
                      {roleDisplayNames[role]}
                      {user.role === role && ' ✓'}
                    </button>
                  ))}
                  <div className="border-t border-gray-100 mt-1 pt-1">
                    <button className="w-full text-left px-3 py-2 text-sm text-red-600 hover:bg-red-50 flex items-center gap-2">
                      <LogOut className="w-4 h-4" />
                      Abmelden
                    </button>
                  </div>
                </div>
              )}
            </div>
          </div>
        </aside>

        {/* Main Content */}
        <div className="lg:pl-64">
          {/* Top Bar */}
          <header className="sticky top-0 z-30 h-16 bg-white border-b border-gray-200 flex items-center px-6">
            <button
              className="lg:hidden p-2 -ml-2 text-gray-500 hover:text-gray-700 rounded-lg hover:bg-gray-100"
              onClick={() => setSidebarOpen(true)}
            >
              <Menu className="w-6 h-6" />
            </button>

            {/* Greeting (Desktop) */}
            <div className="hidden lg:block">
              <p className="text-gray-900">
                {getGreeting()}, <span className="font-medium">{user.name.split(' ')[0]}</span>!
              </p>
            </div>

            <div className="flex-1" />

            {/* Date */}
            <div className="flex items-center gap-4">
              <div className="text-sm text-gray-500">
                {new Date().toLocaleDateString('de-DE', {
                  weekday: 'long',
                  day: 'numeric',
                  month: 'long',
                  year: 'numeric',
                })}
              </div>
            </div>
          </header>

          {/* Page Content */}
          <main className="p-6">
            <Outlet />
          </main>
        </div>
      </div>
    </UserContext.Provider>
  );
}

// PageHeader component for consistent page headers
interface PageHeaderProps {
  title: string;
  subtitle?: string;
  actions?: ReactNode;
}

export function PageHeader({ title, subtitle, actions }: PageHeaderProps) {
  return (
    <div className="page-header">
      <div>
        <h1 className="page-title">{title}</h1>
        {subtitle && <p className="page-subtitle">{subtitle}</p>}
      </div>
      {actions && <div className="flex items-center gap-3">{actions}</div>}
    </div>
  );
}

// FilterBar component for list pages
interface FilterBarProps {
  children: ReactNode;
}

export function FilterBar({ children }: FilterBarProps) {
  return <div className="filter-bar">{children}</div>;
}
