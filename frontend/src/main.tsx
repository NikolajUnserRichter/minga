import React from 'react';
import ReactDOM from 'react-dom/client';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import App from './App';
import { AuthProvider } from './context/AuthContext';
import { ThemeProvider } from './context/ThemeContext';
import { ToastProvider } from './components/ui/Toast';
import './index.css';

// FastAPI / Pydantic serialize Decimal as a JSON string ("4.50"). The whole
// frontend was written assuming numbers and calls .toFixed everywhere, which
// crashes on strings. Patching String.prototype.toFixed to coerce numerically
// matches expectations without having to fix every component.
if (!(String.prototype as any).toFixed) {
  (String.prototype as any).toFixed = function (digits: number) {
    const n = Number(this);
    return Number.isFinite(n) ? n.toFixed(digits) : this.toString();
  };
}

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 1000 * 60, // 1 Minute
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <ThemeProvider>
        <AuthProvider>
          <ToastProvider>
            <App />
          </ToastProvider>
        </AuthProvider>
      </ThemeProvider>
    </QueryClientProvider>
  </React.StrictMode>
);
