import { useEffect, useState } from 'react';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

interface HealthResponse {
  status: string;
  db?: string;
}

export function App() {
  const [apiStatus, setApiStatus] = useState<string>('checking...');
  const [dbStatus, setDbStatus] = useState<string>('checking...');

  useEffect(() => {
    let isMounted = true;

    fetch(`${API_BASE_URL}/health`)
      .then((res) => {
        if (!res.ok) {
          throw new Error('Health check response not OK');
        }
        return res.json() as Promise<HealthResponse>;
      })
      .then((data) => {
        if (isMounted) {
          setApiStatus(data.status === 'ok' ? 'ok' : 'unreachable');
          setDbStatus(data.db === 'ok' ? 'ok' : data.db || 'unreachable');
        }
      })
      .catch(() => {
        if (isMounted) {
          setApiStatus('unreachable');
          setDbStatus('unreachable');
        }
      });

    return () => {
      isMounted = false;
    };
  }, []);

  return (
    <div>
      <h1>VixenOne</h1>
      <p>API: {apiStatus} · DB: {dbStatus}</p>
    </div>
  );
}

export default App;
