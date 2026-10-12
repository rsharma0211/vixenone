import React, { useEffect, useState, useMemo, useCallback } from 'react';
import { useBlocker } from 'react-router-dom';
import { AlertCircle, CheckCircle2 } from 'lucide-react';
import { useAuth } from '@/lib/auth/AuthContext';
import { UserRole, ROLE_LABELS, USER_ROLES } from '@/lib/auth/roles';
import { apiClient, ApiValidationError } from '@/lib/api/client';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';

export const ProfilePage: React.FC = () => {
  const { user, setProfile } = useAuth();

  const [loading, setLoading] = useState<boolean>(true);
  const [saving, setSaving] = useState<boolean>(false);
  const [name, setName] = useState<string>('');
  const [role, setRole] = useState<UserRole>('facilities_manager');
  const [email, setEmail] = useState<string>('');

  const [initialName, setInitialName] = useState<string>('');
  const [initialRole, setInitialRole] = useState<UserRole>('facilities_manager');

  const [errorBanner, setErrorBanner] = useState<string | null>(null);
  const [successBanner, setSuccessBanner] = useState<string | null>(null);
  const [serverErrors, setServerErrors] = useState<Record<string, string>>({});

  const loadProfile = useCallback(async () => {
    try {
      setLoading(true);
      setErrorBanner(null);
      const data = await apiClient.getMe();
      setName(data.display_name || '');
      setRole((data.role as UserRole) || 'facilities_manager');
      setEmail(data.email || user?.email || '');
      setInitialName(data.display_name || '');
      setInitialRole((data.role as UserRole) || 'facilities_manager');
    } catch (err: unknown) {
      if (err instanceof Error) {
        setErrorBanner(err.message);
      } else {
        setErrorBanner('Failed to load profile');
      }
      // Fallback from auth state
      if (user) {
        const fallbackName = user.displayName || user.email?.split('@')[0] || '';
        setName(fallbackName);
        setEmail(user.email || '');
        setInitialName(fallbackName);
      }
    } finally {
      setLoading(false);
    }
  }, [user]);

  useEffect(() => {
    loadProfile();
  }, [loadProfile]);

  // Dirty check
  const isDirty = useMemo(() => {
    if (loading) return false;
    return name.trim() !== initialName.trim() || role !== initialRole;
  }, [loading, name, role, initialName, initialRole]);

  // Unsaved changes tab close / reload guard
  useEffect(() => {
    const handleBeforeUnload = (e: BeforeUnloadEvent) => {
      if (isDirty) {
        e.preventDefault();
        e.returnValue = '';
      }
    };
    window.addEventListener('beforeunload', handleBeforeUnload);
    return () => window.removeEventListener('beforeunload', handleBeforeUnload);
  }, [isDirty]);

  // In-app navigation blocker
  const blocker = useBlocker(
    useCallback(
      ({ currentLocation, nextLocation }: { currentLocation: { pathname: string }; nextLocation: { pathname: string } }) =>
        isDirty && currentLocation.pathname !== nextLocation.pathname,
      [isDirty]
    )
  );

  // Client validation
  const clientErrors = useMemo(() => {
    const errors: Record<string, string> = {};
    if (!name.trim()) {
      errors.name = 'Full name is required';
    }
    return errors;
  }, [name]);

  const allFieldsValid = Object.keys(clientErrors).length === 0;
  const canSave = isDirty && allFieldsValid && !saving;

  const handleSave = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!canSave) return;

    try {
      setSaving(true);
      setErrorBanner(null);
      setSuccessBanner(null);
      setServerErrors({});

      const updated = await apiClient.updateMe({
        display_name: name.trim(),
        role: role,
      });

      // Update shared current profile state for Header and whole app
      setProfile(updated);

      setName(updated.display_name);
      setRole(updated.role as UserRole);
      setInitialName(updated.display_name);
      setInitialRole(updated.role as UserRole);
      setSuccessBanner('Profile updated successfully.');
    } catch (err: unknown) {
      if (err instanceof ApiValidationError) {
        setServerErrors(err.fieldErrors);
        setErrorBanner(err.message);
      } else if (err instanceof Error) {
        setErrorBanner(err.message);
      } else {
        setErrorBanner('Failed to update profile');
      }
    } finally {
      setSaving(false);
    }
  };

  const nameError = serverErrors.display_name || serverErrors.name || clientErrors.name;
  const roleError = serverErrors.role;

  if (loading) {
    return (
      <div className="space-y-6 text-left max-w-2xl">
        <div className="h-8 w-48 bg-surface animate-pulse rounded" />
        <div className="rounded-lg border border-border bg-background p-6 space-y-4">
          <div className="h-10 bg-surface animate-pulse rounded" />
          <div className="h-10 bg-surface animate-pulse rounded" />
          <div className="h-10 bg-surface animate-pulse rounded" />
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6 text-left max-w-2xl">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-page-title text-text font-semibold tracking-tight">
            Profile
          </h1>
          <p className="text-body text-muted">
            Manage your personal information and role.
          </p>
        </div>
        <Button
          variant="primary"
          onClick={() => handleSave()}
          disabled={!canSave}
        >
          {saving ? 'Saving...' : 'Save changes'}
        </Button>
      </div>

      {/* Notifications */}
      {errorBanner && (
        <div className="rounded-lg border border-status-noncompliant-text/30 bg-status-noncompliant-bg px-4 py-3 text-sm text-status-noncompliant-text flex items-center gap-2">
          <AlertCircle className="w-4 h-4 shrink-0" />
          <span>{errorBanner}</span>
        </div>
      )}

      {successBanner && (
        <div className="rounded-lg border border-status-compliant-text/30 bg-status-compliant-bg px-4 py-3 text-sm text-status-compliant-text flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4 shrink-0" />
          <span>{successBanner}</span>
        </div>
      )}

      {/* Single Card Form */}
      <div className="rounded-lg border border-border bg-background shadow-sm p-6 space-y-5">
        <form onSubmit={handleSave} className="space-y-5">
          {/* Full Name */}
          <div className="space-y-1.5">
            <label
              htmlFor="profile-name"
              className="text-xs font-medium text-text block"
            >
              Full name
            </label>
            <Input
              id="profile-name"
              type="text"
              value={name}
              onChange={(e) => {
                setName(e.target.value);
                setSuccessBanner(null);
                if (serverErrors.display_name || serverErrors.name) {
                  const updated = { ...serverErrors };
                  delete updated.display_name;
                  delete updated.name;
                  setServerErrors(updated);
                }
              }}
              placeholder="Your full name"
              className={nameError ? 'border-status-noncompliant-text focus-visible:ring-status-noncompliant-text' : ''}
            />
            {nameError && (
              <p className="text-xs text-status-noncompliant-text">{nameError}</p>
            )}
          </div>

          {/* Role */}
          <div className="space-y-1.5">
            <label
              htmlFor="profile-role"
              className="text-xs font-medium text-text block"
            >
              Role
            </label>
            <Select
              value={role}
              onValueChange={(val) => {
                setRole(val as UserRole);
                setSuccessBanner(null);
                if (serverErrors.role) {
                  const updated = { ...serverErrors };
                  delete updated.role;
                  setServerErrors(updated);
                }
              }}
            >
              <SelectTrigger id="profile-role" className={roleError ? 'border-status-noncompliant-text focus-visible:ring-status-noncompliant-text' : ''}>
                <SelectValue placeholder="Select role">{ROLE_LABELS[role]}</SelectValue>
              </SelectTrigger>
              <SelectContent>
                {USER_ROLES.map((roleKey) => (
                  <SelectItem key={roleKey} value={roleKey}>
                    {ROLE_LABELS[roleKey]}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {roleError && (
              <p className="text-xs text-status-noncompliant-text">{roleError}</p>
            )}
          </div>

          {/* Email (Read-Only) */}
          <div className="space-y-1.5">
            <label
              htmlFor="profile-email"
              className="text-xs font-medium text-text block"
            >
              Email address
            </label>
            <Input
              id="profile-email"
              type="email"
              value={email}
              disabled
              readOnly
              className="bg-surface text-muted cursor-not-allowed"
            />
            <p className="text-xs text-muted">
              Email address is linked to your account and cannot be modified.
            </p>
          </div>
        </form>
      </div>

      {/* In-App Navigation Unsaved Changes Dialog */}
      {blocker && blocker.state === 'blocked' && (
        <Dialog open={true} onOpenChange={() => blocker.reset?.()}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Unsaved changes</DialogTitle>
              <DialogDescription>
                You have unsaved changes to your profile. If you leave this page now, your changes will be lost.
              </DialogDescription>
            </DialogHeader>
            <DialogFooter>
              <Button variant="outline" onClick={() => blocker.reset?.()}>
                Stay on page
              </Button>
              <Button variant="destructive" onClick={() => blocker.proceed?.()}>
                Discard changes and leave
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      )}
    </div>
  );
};

export default ProfilePage;
