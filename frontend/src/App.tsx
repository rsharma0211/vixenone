import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from '@/lib/auth/AuthContext';
import { RequireAuth } from '@/components/auth/RequireAuth';
import { AppShell } from '@/components/layout/AppShell';
import { EvaluationLayout } from '@/components/layout/EvaluationLayout';
import { LandingPage } from '@/pages/LandingPage';
import { S1 } from '@/pages/S1';
import { DevComponentsPage } from '@/pages/DevComponentsPage';
import { EvaluationsListPage } from '@/pages/EvaluationsListPage';
import { NewEvaluationPage } from '@/pages/NewEvaluationPage';
import { EvaluationTabPlaceholder } from '@/pages/EvaluationTabPlaceholder';

export function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          {/* Public Routes */}
          <Route path="/" element={<LandingPage />} />
          <Route path="/sign-in" element={<S1 />} />
          <Route path="/sign-up" element={<S1 />} />

          {/* Protected Application Routes */}
          <Route
            element={
              <RequireAuth>
                <AppShell />
              </RequireAuth>
            }
          >
            <Route path="/evaluations" element={<EvaluationsListPage />} />
            <Route path="/evaluations/new" element={<NewEvaluationPage />} />
            <Route path="/dev/components" element={<DevComponentsPage />} />

            <Route path="/evaluations/:id" element={<EvaluationLayout />}>
              <Route index element={<Navigate to="requirements" replace />} />
              <Route path="requirements" element={<EvaluationTabPlaceholder />} />
              <Route path="comparison" element={<EvaluationTabPlaceholder />} />
              <Route path="recommendation" element={<EvaluationTabPlaceholder />} />
            </Route>

            <Route path="*" element={<Navigate to="/evaluations" replace />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}

export default App;
