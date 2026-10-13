import React, { useEffect, useState, useMemo, useCallback } from 'react';
import { Lock, Trash2, Plus, Pencil, AlertCircle, CheckCircle2 } from 'lucide-react';
import {
  apiClient,
  ApiHttpError,
  ApiValidationError,
  LocationResponse,
} from '@/lib/api/client';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import { ConfirmDialog } from '@/components/ConfirmDialog';
import { useUnsavedChangesGuard } from '@/components/UnsavedChangesGuard';
import type {
  EvaluationCriterionUpdateItem,
} from '@/lib/types';

const BUILTIN_DEFAULTS: EvaluationCriterionUpdateItem[] = [
  {
    kind: 'builtin',
    builtin_key: 'mandatory_compliance',
    name: 'Mandatory compliance',
    guidance:
      'Share of mandatory requirements the vendor meets with evidence. Any mandatory failure is also shown separately.',
    weight: 35,
    position: 0,
  },
  {
    kind: 'builtin',
    builtin_key: 'service_coverage',
    name: 'Service coverage',
    guidance:
      'How fully the proposal covers the required services, frequencies and staffing.',
    weight: 20,
    position: 1,
  },
  {
    kind: 'builtin',
    builtin_key: 'cost_comparability',
    name: 'Cost comparability',
    guidance:
      'How clearly and completely costs are stated: base, GST, inclusions, exclusions and unknowns.',
    weight: 20,
    position: 2,
  },
  {
    kind: 'builtin',
    builtin_key: 'sla_operational',
    name: 'SLA / operational',
    guidance:
      'Response times, supervision, reporting and penalties stated in the proposal.',
    weight: 15,
    position: 3,
  },
  {
    kind: 'builtin',
    builtin_key: 'unresolved_risks',
    name: 'Unresolved risks',
    guidance:
      'Fewer exclusions, ambiguities, contradictions and unknown costs score higher.',
    weight: 10,
    position: 4,
  },
];

interface FormCriterion {
  id?: string;
  kind: 'builtin' | 'custom';
  builtin_key?: string | null;
  name: string;
  guidance: string;
  weight: number | string;
  position: number;
}

export const SettingsPage: React.FC = () => {
  // --- Company & Locations state ---
  const [companyLoading, setCompanyLoading] = useState<boolean>(true);
  const [companyName, setCompanyName] = useState<string>('');
  const [savedCompanyName, setSavedCompanyName] = useState<string>('');
  const [savingCompany, setSavingCompany] = useState<boolean>(false);
  const [companyError, setCompanyError] = useState<string | null>(null);
  const [companySuccess, setCompanySuccess] = useState<string | null>(null);

  const [locations, setLocations] = useState<LocationResponse[]>([]);
  const [locationBannerError, setLocationBannerError] = useState<string | null>(null);

  // Inline add location row
  const [addingLocation, setAddingLocation] = useState<boolean>(false);
  const [newLocationName, setNewLocationName] = useState<string>('');
  const [newLocationCity, setNewLocationCity] = useState<string>('');
  const [addingLocationBusy, setAddingLocationBusy] = useState<boolean>(false);
  const [addLocationError, setAddLocationError] = useState<string | null>(null);

  // Inline edit (rename) location row
  const [editingLocationId, setEditingLocationId] = useState<string | null>(null);
  const [editLocationName, setEditLocationName] = useState<string>('');
  const [editLocationCity, setEditLocationCity] = useState<string>('');
  const [savingLocationEdit, setSavingLocationEdit] = useState<boolean>(false);
  const [editLocationError, setEditLocationError] = useState<string | null>(null);

  // Delete location confirmation
  const [locationToDelete, setLocationToDelete] = useState<LocationResponse | null>(null);
  const [deletingLocation, setDeletingLocation] = useState<boolean>(false);

  // --- Criteria state ---
  const [criteria, setCriteria] = useState<FormCriterion[]>([]);
  const [initialJson, setInitialJson] = useState<string>('');
  const [loading, setLoading] = useState<boolean>(true);
  const [saving, setSaving] = useState<boolean>(false);
  const [errorBanner, setErrorBanner] = useState<string | null>(null);
  const [successBanner, setSuccessBanner] = useState<string | null>(null);

  // Criteria modals
  const [deleteIndex, setDeleteIndex] = useState<number | null>(null);
  const [showResetDialog, setShowResetDialog] = useState<boolean>(false);

  // Criteria server validation errors
  const [serverErrors, setServerErrors] = useState<Record<string, string>>({});

  const loadCompany = useCallback(async () => {
    try {
      setCompanyLoading(true);
      setCompanyError(null);
      const data = await apiClient.getCompany();
      const loadedName = data.name ?? '';
      setCompanyName(loadedName);
      setSavedCompanyName(loadedName);
      const sortedLocations = [...(data.locations ?? [])].sort(
        (a, b) => a.position - b.position
      );
      setLocations(sortedLocations);
    } catch (err: unknown) {
      setCompanyError(
        err instanceof Error ? err.message : 'Failed to load company settings'
      );
    } finally {
      setCompanyLoading(false);
    }
  }, []);

  const loadCriteria = useCallback(async () => {
    try {
      setLoading(true);
      setErrorBanner(null);
      const data = await apiClient.getCriteria();
      const mapped: FormCriterion[] = data.map((c, idx) => ({
        id: c.id,
        kind: c.kind,
        builtin_key: c.builtin_key || null,
        name: c.name,
        guidance: c.guidance,
        weight: c.weight,
        position: c.position !== undefined ? c.position : idx,
      }));
      setCriteria(mapped);
      setInitialJson(JSON.stringify(mapped));
    } catch (err: unknown) {
      setErrorBanner(
        err instanceof Error ? err.message : 'Failed to load evaluation criteria'
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadCompany();
    loadCriteria();
  }, [loadCompany, loadCriteria]);

  // Track if company name or criteria have unsaved changes
  const isCompanyDirty = useMemo(() => {
    if (companyLoading) return false;
    return companyName !== savedCompanyName;
  }, [companyLoading, companyName, savedCompanyName]);

  const isCriteriaDirty = useMemo(() => {
    if (loading || !initialJson) return false;
    return JSON.stringify(criteria) !== initialJson;
  }, [criteria, initialJson, loading]);

  const isDirty = isCompanyDirty || isCriteriaDirty;

  // Unsaved changes: reload/close warning and in-app navigation blocking
  const { guardDialog } = useUnsavedChangesGuard(isDirty);

  // --- Company & Location handlers ---
  const handleSaveCompany = async (event?: React.FormEvent) => {
    event?.preventDefault();
    if (!isCompanyDirty || savingCompany) return;

    try {
      setSavingCompany(true);
      setCompanyError(null);
      setCompanySuccess(null);

      const trimmed = companyName.trim();
      const res = await apiClient.updateCompany({
        name: trimmed ? trimmed : null,
      });
      const updatedName = res.name ?? '';
      setCompanyName(updatedName);
      setSavedCompanyName(updatedName);
      setCompanySuccess('Company name saved.');
    } catch (err: unknown) {
      if (err instanceof Error) {
        setCompanyError(err.message);
      } else {
        setCompanyError('Failed to save company name');
      }
    } finally {
      setSavingCompany(false);
    }
  };

  const handleStartAddLocation = () => {
    setLocationBannerError(null);
    setAddingLocation(true);
    setNewLocationName('');
    setNewLocationCity('');
    setAddLocationError(null);
  };

  const handleCancelAddLocation = () => {
    setAddingLocation(false);
    setNewLocationName('');
    setNewLocationCity('');
    setAddLocationError(null);
  };

  const handleSubmitAddLocation = async () => {
    const trimmedName = newLocationName.trim();
    const trimmedCity = newLocationCity.trim();
    if (!trimmedName || !trimmedCity || addingLocationBusy) return;

    try {
      setAddingLocationBusy(true);
      setAddLocationError(null);
      setLocationBannerError(null);

      const created = await apiClient.addLocation({
        name: trimmedName,
        city: trimmedCity,
      });

      setLocations((prev) => [...prev, created]);
      setAddingLocation(false);
      setNewLocationName('');
      setNewLocationCity('');
    } catch (err: unknown) {
      if (err instanceof Error) {
        setAddLocationError(err.message);
      } else {
        setAddLocationError('Failed to add location');
      }
    } finally {
      setAddingLocationBusy(false);
    }
  };

  const handleStartEditLocation = (loc: LocationResponse) => {
    setLocationBannerError(null);
    setEditingLocationId(loc.id);
    setEditLocationName(loc.name);
    setEditLocationCity(loc.city);
    setEditLocationError(null);
  };

  const handleCancelEditLocation = () => {
    setEditingLocationId(null);
    setEditLocationName('');
    setEditLocationCity('');
    setEditLocationError(null);
  };

  const handleSubmitEditLocation = async (locationId: string) => {
    const trimmedName = editLocationName.trim();
    const trimmedCity = editLocationCity.trim();
    if (!trimmedName || !trimmedCity || savingLocationEdit) return;

    try {
      setSavingLocationEdit(true);
      setEditLocationError(null);
      setLocationBannerError(null);

      const updated = await apiClient.updateLocation(locationId, {
        name: trimmedName,
        city: trimmedCity,
      });

      setLocations((prev) =>
        prev.map((item) => (item.id === locationId ? updated : item))
      );
      setEditingLocationId(null);
      setEditLocationName('');
      setEditLocationCity('');
    } catch (err: unknown) {
      if (err instanceof Error) {
        setEditLocationError(err.message);
      } else {
        setEditLocationError('Failed to update location');
      }
    } finally {
      setSavingLocationEdit(false);
    }
  };

  const handleConfirmDeleteLocation = async () => {
    if (!locationToDelete || deletingLocation) return;
    const target = locationToDelete;

    try {
      setDeletingLocation(true);
      setLocationBannerError(null);
      await apiClient.deleteLocation(target.id);
      setLocations((prev) => prev.filter((item) => item.id !== target.id));
      setLocationToDelete(null);
    } catch (err: unknown) {
      setLocationToDelete(null);
      if (err instanceof ApiHttpError || err instanceof Error) {
        setLocationBannerError(err.message);
      } else {
        setLocationBannerError('Failed to delete location');
      }
    } finally {
      setDeletingLocation(false);
    }
  };

  // --- Criteria calculations & handlers ---
  const totalWeight = useMemo(() => {
    return criteria.reduce((sum, item) => {
      const val = typeof item.weight === 'number' ? item.weight : parseInt(String(item.weight), 10);
      return sum + (isNaN(val) ? 0 : val);
    }, 0);
  }, [criteria]);

  const customCount = useMemo(() => {
    return criteria.filter((c) => c.kind === 'custom').length;
  }, [criteria]);

  const validationErrors = useMemo(() => {
    const errors: Record<string, string> = {};
    const namesSeen = new Map<string, number>();

    criteria.forEach((item, idx) => {
      const trimmedName = item.name.trim().toLowerCase();
      if (!trimmedName) {
        errors[`${idx}.name`] = 'Criterion name is required';
      } else if (trimmedName.length > 80) {
        errors[`${idx}.name`] = 'Name cannot exceed 80 characters';
      } else if (namesSeen.has(trimmedName)) {
        errors[`${idx}.name`] = 'Criterion names must be unique';
        const prevIdx = namesSeen.get(trimmedName)!;
        errors[`${prevIdx}.name`] = 'Criterion names must be unique';
      } else {
        namesSeen.set(trimmedName, idx);
      }

      if (item.kind === 'custom') {
        const trimmedGuidance = item.guidance.trim();
        if (!trimmedGuidance) {
          errors[`${idx}.guidance`] = 'Guidance is required';
        } else if (trimmedGuidance.length < 20 || trimmedGuidance.length > 1000) {
          errors[`${idx}.guidance`] = 'Guidance must be between 20 and 1000 characters';
        }
      }

      const w = typeof item.weight === 'number' ? item.weight : parseInt(String(item.weight), 10);
      if (isNaN(w) || w < 0 || w > 100) {
        errors[`${idx}.weight`] = 'Weight must be between 0 and 100';
      }
    });

    return errors;
  }, [criteria]);

  const allFieldsValid = Object.keys(validationErrors).length === 0;
  const canSave = totalWeight === 100 && allFieldsValid && isCriteriaDirty && !saving;

  const handleWeightChange = (index: number, valStr: string) => {
    setSuccessBanner(null);
    setServerErrors({});
    const val = valStr === '' ? '' : parseInt(valStr, 10);
    setCriteria((prev) => {
      const updated = [...prev];
      updated[index] = { ...updated[index], weight: isNaN(val as number) ? '' : (val as number) };
      return updated;
    });
  };

  const handleNameChange = (index: number, name: string) => {
    setSuccessBanner(null);
    setServerErrors({});
    setCriteria((prev) => {
      const updated = [...prev];
      updated[index] = { ...updated[index], name };
      return updated;
    });
  };

  const handleGuidanceChange = (index: number, guidance: string) => {
    setSuccessBanner(null);
    setServerErrors({});
    setCriteria((prev) => {
      const updated = [...prev];
      updated[index] = { ...updated[index], guidance };
      return updated;
    });
  };

  const handleAddCustom = () => {
    if (customCount >= 10) return;
    setSuccessBanner(null);
    setServerErrors({});
    setCriteria((prev) => [
      ...prev,
      {
        kind: 'custom',
        builtin_key: null,
        name: '',
        guidance: '',
        weight: 0,
        position: prev.length,
      },
    ]);
  };

  const handleConfirmDelete = () => {
    if (deleteIndex === null) return;
    setSuccessBanner(null);
    setServerErrors({});
    setCriteria((prev) => prev.filter((_, idx) => idx !== deleteIndex));
    setDeleteIndex(null);
  };

  const handleSave = async () => {
    if (!canSave) return;
    try {
      setSaving(true);
      setErrorBanner(null);
      setSuccessBanner(null);
      setServerErrors({});

      const payload: EvaluationCriterionUpdateItem[] = criteria.map((c, index) => ({
        id: c.id,
        kind: c.kind,
        builtin_key: c.builtin_key || null,
        name: c.name.trim(),
        guidance: c.guidance.trim(),
        weight: Number(c.weight),
        position: index,
      }));

      const res = await apiClient.updateCriteria(payload);
      const mapped: FormCriterion[] = res.map((c, idx) => ({
        id: c.id,
        kind: c.kind,
        builtin_key: c.builtin_key || null,
        name: c.name,
        guidance: c.guidance,
        weight: c.weight,
        position: c.position !== undefined ? c.position : idx,
      }));
      setCriteria(mapped);
      setInitialJson(JSON.stringify(mapped));
      setSuccessBanner('Evaluation criteria saved successfully.');
    } catch (err: unknown) {
      if (err instanceof ApiValidationError) {
        setServerErrors(err.fieldErrors);
        setErrorBanner(err.message);
      } else if (err instanceof Error) {
        setErrorBanner(err.message);
      } else {
        setErrorBanner('Failed to save criteria');
      }
    } finally {
      setSaving(false);
    }
  };

  const handleResetToDefaults = async () => {
    try {
      setSaving(true);
      setErrorBanner(null);
      setSuccessBanner(null);
      setServerErrors({});
      setShowResetDialog(false);

      const res = await apiClient.updateCriteria(BUILTIN_DEFAULTS);
      const mapped: FormCriterion[] = res.map((c, idx) => ({
        id: c.id,
        kind: c.kind,
        builtin_key: c.builtin_key || null,
        name: c.name,
        guidance: c.guidance,
        weight: c.weight,
        position: c.position !== undefined ? c.position : idx,
      }));
      setCriteria(mapped);
      setInitialJson(JSON.stringify(mapped));
      setSuccessBanner('Evaluation criteria reset to defaults.');
    } catch (err: unknown) {
      if (err instanceof Error) {
        setErrorBanner(err.message);
      } else {
        setErrorBanner('Failed to reset criteria');
      }
    } finally {
      setSaving(false);
    }
  };

  return (
    <TooltipProvider delayDuration={150}>
      <div className="space-y-10 text-left max-w-5xl">
        {/* ================= COMPANY SECTION ================= */}
        <section aria-labelledby="company-section-heading" className="space-y-4">
          <div>
            <h1
              id="company-section-heading"
              className="text-page-title text-text font-semibold tracking-tight"
            >
              Company
            </h1>
            <p className="text-body text-muted">
              Manage your company name and operating locations.
            </p>
          </div>

          {companyLoading ? (
            <div className="rounded-lg border border-border bg-background p-8 text-center text-muted text-sm">
              Loading company settings...
            </div>
          ) : (
            <div className="rounded-lg border border-border bg-background shadow-sm overflow-hidden">
              {/* 1. Company name at the top */}
              <form
                onSubmit={handleSaveCompany}
                className="p-4 sm:p-5 border-b border-border space-y-2"
              >
                <label
                  htmlFor="company-name-input"
                  className="text-xs font-medium text-text block"
                >
                  Company name
                </label>
                <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-3 max-w-xl">
                  <Input
                    id="company-name-input"
                    type="text"
                    value={companyName}
                    maxLength={120}
                    placeholder="Company name"
                    disabled={savingCompany}
                    onChange={(e) => {
                      setCompanyName(e.target.value);
                      setCompanyError(null);
                      setCompanySuccess(null);
                    }}
                    className={
                      companyError
                        ? 'border-status-noncompliant-text focus-visible:ring-status-noncompliant-text'
                        : ''
                    }
                  />
                  <Button
                    type="submit"
                    variant="primary"
                    disabled={!isCompanyDirty || savingCompany}
                    className="shrink-0 font-semibold"
                  >
                    {savingCompany ? 'Saving...' : 'Save'}
                  </Button>
                </div>
                {companyError && (
                  <p role="alert" className="text-xs text-status-noncompliant-text">
                    {companyError}
                  </p>
                )}
                {companySuccess && (
                  <p className="text-xs text-status-compliant-text">{companySuccess}</p>
                )}
              </form>

              {/* 2. Locations directly below, inside the same section */}
              <div>
                {locationBannerError && (
                  <div
                    role="alert"
                    className="border-b border-status-noncompliant-text/30 bg-status-noncompliant-bg px-4 py-2.5 text-xs text-status-noncompliant-text flex items-center gap-2"
                  >
                    <AlertCircle className="w-4 h-4 shrink-0" />
                    <span>{locationBannerError}</span>
                  </div>
                )}

                <table className="w-full border-collapse text-left">
                  <thead>
                    <tr className="border-b border-border bg-surface text-table-header text-muted">
                      <th className="py-3 px-4 w-[34%] font-medium">Name</th>
                      <th className="py-3 px-4 w-[28%] font-medium">City</th>
                      <th className="py-3 px-4 w-[20%] font-medium">Used by</th>
                      <th className="py-3 px-4 w-[18%] font-medium text-center">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {locations.length === 0 && !addingLocation ? (
                      <tr>
                        <td colSpan={4} className="py-8 px-4 text-center text-sm text-muted">
                          No locations yet. Add the sites where your company operates.
                        </td>
                      </tr>
                    ) : (
                      locations.map((loc) => {
                        const isEditing = editingLocationId === loc.id;
                        const usedByLabel = `${loc.evaluation_count} ${
                          loc.evaluation_count === 1 ? 'evaluation' : 'evaluations'
                        }`;
                        const inUseTooltip = `Used by ${loc.evaluation_count} evaluations — change their location first.`;

                        if (isEditing) {
                          const canSaveLoc =
                            Boolean(editLocationName.trim()) &&
                            Boolean(editLocationCity.trim()) &&
                            !savingLocationEdit;

                          return (
                            <tr key={loc.id} className="bg-surface/40 align-top">
                              <td className="py-3 px-4">
                                <div className="space-y-1">
                                  <Input
                                    autoFocus
                                    value={editLocationName}
                                    maxLength={80}
                                    placeholder="Name"
                                    aria-label="Location name"
                                    disabled={savingLocationEdit}
                                    onChange={(e) => {
                                      setEditLocationName(e.target.value);
                                      setEditLocationError(null);
                                    }}
                                    onKeyDown={(e) => {
                                      if (e.key === 'Enter') {
                                        e.preventDefault();
                                        handleSubmitEditLocation(loc.id);
                                      } else if (e.key === 'Escape') {
                                        handleCancelEditLocation();
                                      }
                                    }}
                                    className={
                                      editLocationError
                                        ? 'border-status-noncompliant-text focus-visible:ring-status-noncompliant-text'
                                        : ''
                                    }
                                  />
                                  {editLocationError && (
                                    <p
                                      role="alert"
                                      className="text-xs text-status-noncompliant-text"
                                    >
                                      {editLocationError}
                                    </p>
                                  )}
                                </div>
                              </td>
                              <td className="py-3 px-4">
                                <Input
                                  value={editLocationCity}
                                  maxLength={80}
                                  placeholder="City"
                                  aria-label="City"
                                  disabled={savingLocationEdit}
                                  onChange={(e) => {
                                    setEditLocationCity(e.target.value);
                                    setEditLocationError(null);
                                  }}
                                  onKeyDown={(e) => {
                                    if (e.key === 'Enter') {
                                      e.preventDefault();
                                      handleSubmitEditLocation(loc.id);
                                    } else if (e.key === 'Escape') {
                                      handleCancelEditLocation();
                                    }
                                  }}
                                />
                              </td>
                              <td className="py-3 px-4 text-sm text-muted align-middle">
                                {usedByLabel}
                              </td>
                              <td className="py-3 px-4 text-center align-middle">
                                <div className="flex items-center justify-center gap-2">
                                  <Button
                                    type="button"
                                    variant="primary"
                                    size="sm"
                                    disabled={!canSaveLoc}
                                    onClick={() => handleSubmitEditLocation(loc.id)}
                                  >
                                    {savingLocationEdit ? 'Saving...' : 'Save'}
                                  </Button>
                                  <Button
                                    type="button"
                                    variant="outline"
                                    size="sm"
                                    disabled={savingLocationEdit}
                                    onClick={handleCancelEditLocation}
                                  >
                                    Cancel
                                  </Button>
                                </div>
                              </td>
                            </tr>
                          );
                        }

                        return (
                          <tr
                            key={loc.id}
                            className="hover:bg-surface/50 transition-colors align-middle"
                          >
                            <td className="py-3.5 px-4 text-sm font-medium text-text">
                              {loc.name}
                            </td>
                            <td className="py-3.5 px-4 text-sm text-muted">{loc.city}</td>
                            <td className="py-3.5 px-4 text-sm text-muted">{usedByLabel}</td>
                            <td className="py-3.5 px-4 text-center">
                              <div className="flex items-center justify-center gap-2">
                                <button
                                  type="button"
                                  onClick={() => handleStartEditLocation(loc)}
                                  aria-label={`Rename ${loc.name}`}
                                  className="p-1.5 text-muted hover:text-text rounded-md hover:bg-surface transition-colors inline-flex items-center gap-1 text-xs font-medium"
                                >
                                  <Pencil className="w-3.5 h-3.5" />
                                  <span>Rename</span>
                                </button>

                                {loc.evaluation_count > 0 ? (
                                  <Tooltip>
                                    <TooltipTrigger asChild>
                                      <span
                                        tabIndex={0}
                                        title={inUseTooltip}
                                        className="inline-flex"
                                      >
                                        <button
                                          type="button"
                                          disabled
                                          aria-label={`Delete ${loc.name}`}
                                          className="p-1.5 text-muted/40 rounded-md cursor-not-allowed"
                                        >
                                          <Trash2 className="w-4 h-4" />
                                        </button>
                                      </span>
                                    </TooltipTrigger>
                                    <TooltipContent>{inUseTooltip}</TooltipContent>
                                  </Tooltip>
                                ) : (
                                  <button
                                    type="button"
                                    onClick={() => setLocationToDelete(loc)}
                                    aria-label={`Delete ${loc.name}`}
                                    className="p-1.5 text-muted hover:text-status-noncompliant-text rounded-md hover:bg-surface transition-colors"
                                  >
                                    <Trash2 className="w-4 h-4" />
                                  </button>
                                )}
                              </div>
                            </td>
                          </tr>
                        );
                      })
                    )}

                    {/* Inline Add Location Row */}
                    {addingLocation && (
                      <tr className="bg-surface/40 align-top">
                        <td className="py-3 px-4">
                          <div className="space-y-1">
                            <Input
                              autoFocus
                              value={newLocationName}
                              maxLength={80}
                              placeholder="Name"
                              aria-label="New location name"
                              disabled={addingLocationBusy}
                              onChange={(e) => {
                                setNewLocationName(e.target.value);
                                setAddLocationError(null);
                              }}
                              onKeyDown={(e) => {
                                if (e.key === 'Enter') {
                                  e.preventDefault();
                                  handleSubmitAddLocation();
                                } else if (e.key === 'Escape') {
                                  handleCancelAddLocation();
                                }
                              }}
                              className={
                                addLocationError
                                  ? 'border-status-noncompliant-text focus-visible:ring-status-noncompliant-text'
                                  : ''
                              }
                            />
                            {addLocationError && (
                              <p
                                role="alert"
                                className="text-xs text-status-noncompliant-text"
                              >
                                {addLocationError}
                              </p>
                            )}
                          </div>
                        </td>
                        <td className="py-3 px-4">
                          <Input
                            value={newLocationCity}
                            maxLength={80}
                            placeholder="City"
                            aria-label="New location city"
                            disabled={addingLocationBusy}
                            onChange={(e) => {
                              setNewLocationCity(e.target.value);
                              setAddLocationError(null);
                            }}
                            onKeyDown={(e) => {
                              if (e.key === 'Enter') {
                                e.preventDefault();
                                handleSubmitAddLocation();
                              } else if (e.key === 'Escape') {
                                handleCancelAddLocation();
                              }
                            }}
                          />
                        </td>
                        <td className="py-3 px-4 text-sm text-muted align-middle">
                          0 evaluations
                        </td>
                        <td className="py-3 px-4 text-center align-middle">
                          <div className="flex items-center justify-center gap-2">
                            <Button
                              type="button"
                              variant="primary"
                              size="sm"
                              disabled={
                                !newLocationName.trim() ||
                                !newLocationCity.trim() ||
                                addingLocationBusy
                              }
                              onClick={handleSubmitAddLocation}
                            >
                              {addingLocationBusy ? 'Adding...' : 'Add'}
                            </Button>
                            <Button
                              type="button"
                              variant="outline"
                              size="sm"
                              disabled={addingLocationBusy}
                              onClick={handleCancelAddLocation}
                            >
                              Cancel
                            </Button>
                          </div>
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>

                {/* Locations Footer */}
                <div className="border-t border-border bg-surface px-4 py-3 flex items-center justify-between">
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={handleStartAddLocation}
                    disabled={addingLocation}
                    className="gap-1.5"
                  >
                    <Plus className="w-3.5 h-3.5" />
                    <span>Add location</span>
                  </Button>
                </div>
              </div>
            </div>
          )}
        </section>

        {/* ================= EVALUATION CRITERIA SECTION ================= */}
        <section aria-labelledby="criteria-section-heading" className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h2
                id="criteria-section-heading"
                className="text-page-title text-text font-semibold tracking-tight"
              >
                Evaluation criteria
              </h2>
              <p className="text-body text-muted">
                Configure default weights and criteria for vendor evaluations.
              </p>
            </div>
            {!loading && (
              <div className="flex items-center gap-3">
                <Button
                  variant="outline"
                  onClick={() => setShowResetDialog(true)}
                  disabled={saving}
                >
                  Reset to defaults
                </Button>
                <Button
                  variant="primary"
                  onClick={handleSave}
                  disabled={!canSave}
                >
                  {saving ? 'Saving...' : 'Save criteria'}
                </Button>
              </div>
            )}
          </div>

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

          {loading ? (
            <div className="rounded-lg border border-border bg-background p-12 text-center text-muted text-sm">
              Loading criteria...
            </div>
          ) : (
            <div className="rounded-lg border border-border bg-background shadow-sm overflow-hidden">
              <table className="w-full border-collapse text-left">
                <thead>
                  <tr className="border-b border-border bg-surface text-table-header text-muted">
                    <th className="py-3 px-4 w-[28%] font-medium">Criterion</th>
                    <th className="py-3 px-4 w-[48%] font-medium">Guidance</th>
                    <th className="py-3 px-4 w-[14%] font-medium text-right">Weight (%)</th>
                    <th className="py-3 px-4 w-[10%] font-medium text-center">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {criteria.map((item, index) => {
                    const isBuiltin = item.kind === 'builtin';
                    const nameError =
                      validationErrors[`${index}.name`] ||
                      serverErrors[`${index}.name`] ||
                      serverErrors.name;
                    const guidanceError =
                      validationErrors[`${index}.guidance`] ||
                      serverErrors[`${index}.guidance`] ||
                      serverErrors.guidance;
                    const weightError =
                      validationErrors[`${index}.weight`] ||
                      serverErrors[`${index}.weight`] ||
                      serverErrors.weight;

                    return (
                      <tr
                        key={item.id || item.builtin_key || `crit-${index}`}
                        className="hover:bg-surface/50 transition-colors align-top"
                      >
                        <td className="py-3.5 px-4">
                          {isBuiltin ? (
                            <div className="flex items-center gap-2 font-medium text-text text-sm">
                              <Lock className="w-3.5 h-3.5 text-muted shrink-0" />
                              <span>{item.name}</span>
                            </div>
                          ) : (
                            <div className="space-y-1">
                              <Input
                                value={item.name}
                                onChange={(e) => handleNameChange(index, e.target.value)}
                                placeholder="Criterion name"
                                maxLength={80}
                                className={
                                  nameError
                                    ? 'border-status-noncompliant-text focus-visible:ring-status-noncompliant-text'
                                    : ''
                                }
                              />
                              {nameError && (
                                <p className="text-xs text-status-noncompliant-text">
                                  {nameError}
                                </p>
                              )}
                            </div>
                          )}
                        </td>

                        <td className="py-3.5 px-4 text-sm text-text leading-relaxed">
                          {isBuiltin ? (
                            <span className="text-muted">{item.guidance}</span>
                          ) : (
                            <div className="space-y-1">
                              <Textarea
                                value={item.guidance}
                                onChange={(e) => handleGuidanceChange(index, e.target.value)}
                                placeholder="Describe guidance for evaluation (20–1000 characters)"
                                rows={2}
                                maxLength={1000}
                                className={
                                  guidanceError
                                    ? 'border-status-noncompliant-text focus-visible:ring-status-noncompliant-text'
                                    : ''
                                }
                              />
                              <div className="flex justify-between items-center text-xs">
                                {guidanceError ? (
                                  <span className="text-status-noncompliant-text">
                                    {guidanceError}
                                  </span>
                                ) : (
                                  <span />
                                )}
                                <span
                                  className={
                                    item.guidance.trim().length < 20
                                      ? 'text-status-partial-text'
                                      : 'text-muted'
                                  }
                                >
                                  {item.guidance.trim().length}/1000
                                </span>
                              </div>
                            </div>
                          )}
                        </td>

                        <td className="py-3.5 px-4 text-right">
                          <div className="flex flex-col items-end gap-1">
                            <Input
                              type="number"
                              min={0}
                              max={100}
                              value={item.weight}
                              onChange={(e) => handleWeightChange(index, e.target.value)}
                              className={`w-20 text-right ${
                                weightError
                                  ? 'border-status-noncompliant-text focus-visible:ring-status-noncompliant-text'
                                  : ''
                              }`}
                            />
                            {weightError && (
                              <p className="text-xs text-status-noncompliant-text text-right">
                                {weightError}
                              </p>
                            )}
                          </div>
                        </td>

                        <td className="py-3.5 px-4 text-center">
                          {!isBuiltin ? (
                            <button
                              type="button"
                              onClick={() => setDeleteIndex(index)}
                              aria-label="Delete criterion"
                              className="p-1.5 text-muted hover:text-status-noncompliant-text rounded-md hover:bg-surface transition-colors"
                            >
                              <Trash2 className="w-4 h-4" />
                            </button>
                          ) : (
                            <span className="text-xs text-muted select-none">—</span>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>

              <div className="border-t border-border bg-surface px-4 py-3 flex items-center justify-between">
                <div>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={handleAddCustom}
                    disabled={customCount >= 10}
                    className="gap-1.5"
                  >
                    <Plus className="w-3.5 h-3.5" />
                    <span>Add custom criterion</span>
                    {customCount >= 10 && (
                      <span className="text-xs text-muted ml-1">(max 10)</span>
                    )}
                  </Button>
                </div>

                <div className="flex items-center gap-3">
                  <span className="text-sm font-medium text-text">Total weight:</span>
                  <span
                    className={`text-sm font-semibold px-2 py-0.5 rounded ${
                      totalWeight === 100
                        ? 'bg-status-compliant-bg text-status-compliant-text'
                        : 'bg-status-noncompliant-bg text-status-noncompliant-text'
                    }`}
                  >
                    {totalWeight}%
                  </span>
                  {totalWeight !== 100 && (
                    <span className="text-xs text-status-noncompliant-text">
                      (Must equal 100% to save)
                    </span>
                  )}
                </div>
              </div>
            </div>
          )}
        </section>

        {/* Delete Location Confirmation Dialog */}
        <ConfirmDialog
          open={locationToDelete !== null}
          title="Delete location"
          description={locationToDelete ? `Removes ${locationToDelete.name}.` : ''}
          confirmLabel={deletingLocation ? 'Deleting...' : 'Delete location'}
          busy={deletingLocation}
          onConfirm={handleConfirmDeleteLocation}
          onCancel={() => setLocationToDelete(null)}
        />

        {/* Delete Criterion Confirmation Dialog */}
        <ConfirmDialog
          open={deleteIndex !== null}
          title="Delete criterion"
          description={
            <>
              Are you sure you want to delete &ldquo;
              {deleteIndex !== null && criteria[deleteIndex] ? criteria[deleteIndex].name : ''}
              &rdquo;? This change will take effect once you save your criteria.
            </>
          }
          confirmLabel="Delete criterion"
          onConfirm={handleConfirmDelete}
          onCancel={() => setDeleteIndex(null)}
        />

        {/* Reset Criteria Confirmation Dialog */}
        <ConfirmDialog
          open={showResetDialog}
          title="Reset to default criteria?"
          description="Built-in criteria weights will return to their default values (Mandatory compliance: 35%, Service coverage: 20%, Cost comparability: 20%, SLA / operational: 15%, Unresolved risks: 10%), and any custom criteria you created will be permanently removed."
          confirmLabel={saving ? 'Resetting...' : 'Reset to defaults'}
          busy={saving}
          onConfirm={handleResetToDefaults}
          onCancel={() => setShowResetDialog(false)}
        />

        {/* In-App Navigation Unsaved Changes Dialog */}
        {guardDialog}
      </div>
    </TooltipProvider>
  );
};

export default SettingsPage;
