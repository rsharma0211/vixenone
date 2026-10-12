import { createBrowserRouter, RouterProvider, Navigate } from 'react-router-dom';
import { AuthProvider } from '@/lib/auth/AuthContext';
import { RequireAuth } from '@/components/auth/RequireAuth';
import { AppShell } from '@/components/layout/AppShell';
import { EvaluationLayout } from '@/components/layout/EvaluationLayout';
import { LandingPage } from '@/pages/LandingPage';
import { S1 } from '@/pages/S1';
import { DevComponentsPage } from '@/pages/DevComponentsPage';
import { EvaluationsListPage } from '@/pages/EvaluationsListPage';
import { NewEvaluationPage } from '@/pages/NewEvaluationPage';
import { SettingsPage } from '@/pages/SettingsPage';
import { EvaluationTabPlaceholder } from '@/pages/EvaluationTabPlaceholder';

const router = createBrowserRouter([
  {
    path: '/',
    element: <LandingPage />,
  },
  {
    path: '/sign-in',
    element: <S1 />,
  },
  {
    path: '/sign-up',
    element: <S1 />,
  },
  {
    element: (
      <RequireAuth>
        <AppShell />
      </RequireAuth>
    ),
    children: [
      {
        path: '/evaluations',
        element: <EvaluationsListPage />,
      },
      {
        path: '/evaluations/new',
        element: <NewEvaluationPage />,
      },
      {
        path: '/evaluations/:id/upload',
        element: <NewEvaluationPage />,
      },
      {
        path: '/settings',
        element: <SettingsPage />,
      },
      {
        path: '/dev/components',
        element: <DevComponentsPage />,
      },
      {
        path: '/evaluations/:id',
        element: <EvaluationLayout />,
        children: [
          {
            index: true,
            element: <Navigate to="requirements" replace />,
          },
          {
            path: 'requirements',
            element: <EvaluationTabPlaceholder />,
          },
          {
            path: 'comparison',
            element: <EvaluationTabPlaceholder />,
          },
          {
            path: 'recommendation',
            element: <EvaluationTabPlaceholder />,
          },
        ],
      },
      {
        path: '*',
        element: <Navigate to="/evaluations" replace />,
      },
    ],
  },
]);

export function App() {
  return (
    <AuthProvider>
      <RouterProvider router={router} />
    </AuthProvider>
  );
}

export default App;
