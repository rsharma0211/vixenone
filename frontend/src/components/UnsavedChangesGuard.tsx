import React, { useCallback, useEffect, useRef } from 'react';
import { useBlocker } from 'react-router-dom';
import { ConfirmDialog } from '@/components/ConfirmDialog';

export const UNSAVED_CHANGES_MESSAGE = 'You have unsaved changes. Leave without saving?';

/**
 * Blocks every in-app navigation (tabs, sidebar, breadcrumb, header menu, back/forward)
 * and the browser reload/close while `isDirty` is true. Requires a data router
 * (`createBrowserRouter` + `RouterProvider`), which App.tsx uses.
 *
 * Render `guardDialog` once in the page. Call `allowNavigation()` immediately before an
 * intentional navigation that discards the edits (e.g. a confirmed re-run).
 */
export function useUnsavedChangesGuard(isDirty: boolean): {
  guardDialog: React.ReactNode;
  allowNavigation: () => void;
} {
  const bypassRef = useRef(false);

  useEffect(() => {
    const handleBeforeUnload = (event: BeforeUnloadEvent) => {
      if (isDirty && !bypassRef.current) {
        event.preventDefault();
        event.returnValue = '';
      }
    };
    window.addEventListener('beforeunload', handleBeforeUnload);
    return () => window.removeEventListener('beforeunload', handleBeforeUnload);
  }, [isDirty]);

  const blocker = useBlocker(
    useCallback(
      ({
        currentLocation,
        nextLocation,
      }: {
        currentLocation: { pathname: string; search: string };
        nextLocation: { pathname: string; search: string };
      }) =>
        isDirty &&
        !bypassRef.current &&
        currentLocation.pathname + currentLocation.search !==
          nextLocation.pathname + nextLocation.search,
      [isDirty]
    )
  );

  const allowNavigation = useCallback(() => {
    bypassRef.current = true;
  }, []);

  const guardDialog = (
    <ConfirmDialog
      open={blocker.state === 'blocked'}
      title="Unsaved changes"
      description={UNSAVED_CHANGES_MESSAGE}
      confirmLabel="Leave"
      onConfirm={() => {
        if (blocker.state === 'blocked') blocker.proceed();
      }}
      onCancel={() => {
        if (blocker.state === 'blocked') blocker.reset();
      }}
    />
  );

  return { guardDialog, allowNavigation };
}
