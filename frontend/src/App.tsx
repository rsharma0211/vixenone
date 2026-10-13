import { createBrowserRouter, RouterProvider, Navigate } from 'react-router-dom';
import { AuthProvider } from '@/lib/auth/AuthContext';
import { RequireAuth } from '@/components/auth/RequireAuth';
import { AppShell } from '@/components/layout/AppShell';
import { EvaluationLayout } from '@/components/layout/EvaluationLayout';
import { LandingPage } from '@/pages/LandingPage';
import { AuthPage } from '@/pages/AuthPage';
import { DevComponentsPage } from '@/pages/DevComponentsPage';
import { EvaluationsListPage } from '@/pages/EvaluationsListPage';
import { NewEvaluationPage } from '@/pages/NewEvaluationPage';
import { DocumentsPage } from '@/pages/DocumentsPage';
import { SettingsPage } from '@/pages/SettingsPage';
import { ProfilePage } from '@/pages/ProfilePage';
import { RequirementsReviewPage } from '@/pages/RequirementsReviewPage';
import { EvaluationTabPlaceholder } from '@/pages/EvaluationTabPlaceholder';

const router = createBrowserRouter([
  {
    path: '/',
    element: <LandingPage />,
  },
  {
    path: '/sign-in',
    element: <AuthPage />,
  },
  {
    path: '/sign-up',
    element: <AuthPage />,
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
        path: '/settings',
        element: <SettingsPage />,
      },
      {
        path: '/profile',
        element: <ProfilePage />,
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
            path: 'documents',
            element: <DocumentsPage />,
          },
          {
            // Legacy upload route: redirects to the Documents tab
            path: 'upload',
            element: <Navigate to="../documents" replace />,
          },
          {
            path: 'requirements',
            element: <RequirementsReviewPage />,
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
