import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import Layout from './components/common/Layout';
import Dashboard from './pages/Dashboard';
import Production from './pages/Production';
import Sales from './pages/Sales';
import Forecasting from './pages/Forecasting';
import Settings from './pages/Settings';
import Seeds from './pages/Seeds';
import Customers from './pages/Customers';
import Orders from './pages/Orders';
import ProductionSuggestions from './pages/ProductionSuggestions';
import Products from './pages/Products';
import Invoices from './pages/Invoices';
import Inventory from './pages/Inventory';
import Analytics from './pages/Analytics';
import Harvests from './pages/Harvests';

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<Navigate to="/dashboard" replace />} />
          <Route path="dashboard" element={<Dashboard />} />
          <Route path="analytics" element={<Analytics />} />

          {/* Stammdaten */}
          <Route path="seeds" element={<Seeds />} />
          <Route path="products" element={<Products />} />
          <Route path="inventory" element={<Inventory />} />

          {/* Produktion */}
          <Route path="production" element={<Production />} />
          <Route path="harvests" element={<Harvests />} />

          {/* Vertrieb */}
          <Route path="customers" element={<Customers />} />
          <Route path="orders" element={<Orders />} />
          <Route path="subscriptions" element={<NotImplemented title="Abonnements" />} />
          <Route path="invoices" element={<Invoices />} />
          <Route path="sales" element={<Sales />} />

          {/* Forecasting */}
          <Route path="forecasting" element={<Forecasting />} />
          <Route path="suggestions" element={<ProductionSuggestions />} />
          <Route path="accuracy" element={<NotImplemented title="Accuracy Reports" />} />

          {/* Admin */}
          <Route path="settings" element={<Settings />} />
          <Route path="users" element={<NotImplemented title="Benutzerverwaltung" />} />

          {/* Catch all */}
          <Route path="*" element={<NotFound />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

// Placeholder for not yet implemented pages
function NotImplemented({ title }: { title: string }) {
  return (
    <div className="flex flex-col items-center justify-center min-h-[400px] text-center">
      <div className="w-16 h-16 bg-gray-100 rounded-full flex items-center justify-center mb-4">
        <span className="text-3xl">🚧</span>
      </div>
      <h1 className="text-2xl font-bold text-gray-900">{title}</h1>
      <p className="text-gray-500 mt-2">Diese Seite wird noch implementiert.</p>
    </div>
  );
}

// 404 Not Found page
function NotFound() {
  return (
    <div className="flex flex-col items-center justify-center min-h-[400px] text-center">
      <div className="w-16 h-16 bg-red-100 rounded-full flex items-center justify-center mb-4">
        <span className="text-3xl">🔍</span>
      </div>
      <h1 className="text-2xl font-bold text-gray-900">Seite nicht gefunden</h1>
      <p className="text-gray-500 mt-2">Die angeforderte Seite existiert nicht.</p>
      <a href="/dashboard" className="btn btn-primary mt-4">
        Zum Dashboard
      </a>
    </div>
  );
}

export default App;
