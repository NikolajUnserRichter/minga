import { ReactNode, useState, createContext, useContext } from 'react';

interface Tab {
  id: string;
  label: string;
  icon?: ReactNode;
  // Zahl (ab 1 sichtbar) oder Text wie „100+“ (Rechnungsliste an der
  // Listengrenze, Paket 4.1 Z)
  badge?: number | string;
}

interface TabsContextType {
  activeTab: string;
  setActiveTab: (id: string) => void;
}

const TabsContext = createContext<TabsContextType | null>(null);

interface TabsProps {
  tabs: Tab[];
  defaultTab?: string;
  activeTab?: string;
  onChange?: (tabId: string) => void;
  children?: ReactNode;
  className?: string;
}

export function Tabs({ tabs, defaultTab, activeTab: controlledTab, onChange, children, className = '' }: TabsProps) {
  const [internalTab, setInternalTab] = useState(defaultTab || tabs[0]?.id || '');
  const activeTab = controlledTab !== undefined ? controlledTab : internalTab;

  const handleTabChange = (tabId: string) => {
    if (controlledTab === undefined) {
      setInternalTab(tabId);
    }
    onChange?.(tabId);
  };

  return (
    <TabsContext.Provider value={{ activeTab, setActiveTab: handleTabChange }}>
      <div className={className}>
        <div className="tabs">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              className={`tab ${activeTab === tab.id ? 'tab-active' : ''}`}
              onClick={() => handleTabChange(tab.id)}
              role="tab"
              aria-selected={activeTab === tab.id}
            >
              {tab.icon && <span className="mr-2">{tab.icon}</span>}
              {tab.label}
              {(typeof tab.badge === 'string' ? tab.badge !== '' : tab.badge !== undefined && tab.badge > 0) && (
                <span className="ml-2 badge badge-sm badge-gray">{tab.badge}</span>
              )}
            </button>
          ))}
        </div>
        <div className="mt-4">{children}</div>
      </div>
    </TabsContext.Provider>
  );
}

interface TabPanelProps {
  id: string;
  children: ReactNode;
}

export function TabPanel({ id, children }: TabPanelProps) {
  const context = useContext(TabsContext);
  if (!context) {
    throw new Error('TabPanel must be used within a Tabs component');
  }

  if (context.activeTab !== id) return null;

  return (
    <div role="tabpanel" aria-labelledby={`tab-${id}`}>
      {children}
    </div>
  );
}
