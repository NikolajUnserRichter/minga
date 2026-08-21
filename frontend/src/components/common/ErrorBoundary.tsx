import { Component, ErrorInfo, ReactNode } from 'react';

interface Props {
  children: ReactNode;
}

interface State {
  error: Error | null;
}

/**
 * Fängt Render-Fehler ab, damit aus einem Fehler keine weiße Seite wird.
 *
 * Ohne Boundary hängt React bei einer Exception im Render den kompletten Baum
 * aus — der Nutzer sieht nur noch Weiß und kann nicht sagen, was passiert ist.
 * Hier bleibt stattdessen eine Meldung mit der Fehlerursache stehen, die sich
 * abtippen oder screenshotten lässt.
 */
export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('Render-Fehler:', error, info.componentStack);
  }

  render() {
    const { error } = this.state;
    if (!error) return this.props.children;

    return (
      <div className="min-h-screen flex items-center justify-center p-8 bg-gray-50 dark:bg-gray-900">
        <div className="max-w-lg w-full text-center">
          <div className="text-4xl mb-4">⚠️</div>
          <h1 className="text-lg font-semibold text-gray-900 dark:text-white mb-2">
            Diese Ansicht konnte nicht dargestellt werden
          </h1>
          <p className="text-sm text-gray-600 dark:text-gray-400 mb-4">
            Die Daten sind nicht verloren. Bitte die Seite neu laden — bleibt der Fehler,
            hilft der folgende Text beim Melden:
          </p>
          <pre className="text-xs text-left bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg p-3 overflow-auto max-h-40 text-gray-700 dark:text-gray-300">
            {error.message || String(error)}
          </pre>
          <div className="flex gap-2 justify-center mt-5">
            <button
              className="px-4 py-2 bg-minga-600 hover:bg-minga-700 text-white rounded-lg text-sm"
              onClick={() => window.location.reload()}
            >
              Seite neu laden
            </button>
            <button
              className="px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-sm text-gray-700 dark:text-gray-300"
              onClick={() => this.setState({ error: null })}
            >
              Nochmal versuchen
            </button>
          </div>
        </div>
      </div>
    );
  }
}
