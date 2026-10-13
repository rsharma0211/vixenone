import React, { useEffect, useState, useMemo, useCallback, useRef } from 'react';
import { useParams, useNavigate, useOutletContext } from 'react-router-dom';
import {
  Plus,
  Pencil,
  Trash2,
  FileText,
  AlertTriangle,
  AlertCircle,
  CheckCircle2,
  Check,
  RefreshCw,
} from 'lucide-react';
import { apiClient, ApiHttpError, ApiValidationError } from '@/lib/api/client';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Switch } from '@/components/ui/switch';
import { ConfirmDialog } from '@/components/ConfirmDialog';
import { RerunExtractionDialog } from '@/components/RerunExtractionDialog';
import { useUnsavedChangesGuard } from '@/components/UnsavedChangesGuard';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import type { EvaluationLayoutContext } from '@/components/layout/EvaluationLayout';
import type {
  RequirementItem,
  RequirementOrigin,
} from '@/lib/types';

// Screen: S4 (Requirements review)

interface EditableRequirementRow {
  localId: string;
  id?: string | null;
  code: string;
  text: string;
  category: string;
  mandatory: boolean;
  acceptance: string;
  source_document_id?: string | null;
  source_page: string;
  source_section: string;
  origin: RequirementOrigin;
  isNew?: boolean;
}

export function formatRequirementSource(
  page?: number | string | null,
  section?: string | null
): string {
  const parsedPage =
    page === null || page === undefined || page === ''
      ? null
      : typeof page === 'number'
      ? page
      : parseInt(String(page), 10);
  const hasPage = parsedPage !== null && !isNaN(parsedPage);
  const hasSection = Boolean(section && section.trim());

  if (hasPage && hasSection) {
    return `p.${parsedPage} · ${section}`;
  }
  if (hasPage) {
    return `p.${parsedPage}`;
  }
  if (hasSection) {
    return section as string;
  }
  return '—';
}

export function generateNextRequirementCode(existingCodes: string[]): string {
  const existingUpper = new Set(existingCodes.map((c) => c.trim().toUpperCase()));

  for (let i = existingCodes.length - 1; i >= 0; i--) {
    const raw = existingCodes[i].trim();
    const match = raw.match(/^(.*?)(\d+)$/);
    if (match) {
      const prefix = match[1];
      const numStr = match[2];
      const width = numStr.length;

      // Find highest number sharing the same prefix (case-insensitive)
      let maxNum = parseInt(numStr, 10);
      for (const code of existingCodes) {
        const m = code.trim().match(/^(.*?)(\d+)$/);
        if (m && m[1].toUpperCase() === prefix.toUpperCase()) {
          const val = parseInt(m[2], 10);
          if (!isNaN(val) && val > maxNum) {
            maxNum = val;
          }
        }
      }

      let candidateNum = maxNum + 1;
      let candidate = `${prefix}${String(candidateNum).padStart(width, '0')}`;
      while (existingUpper.has(candidate.toUpperCase())) {
        candidateNum += 1;
        candidate = `${prefix}${String(candidateNum).padStart(width, '0')}`;
      }
      return candidate;
    }
  }

  let fallbackNum = existingCodes.length + 1;
  let fallback = `REQ-${String(fallbackNum).padStart(2, '0')}`;
  while (existingUpper.has(fallback.toUpperCase())) {
    fallbackNum += 1;
    fallback = `REQ-${String(fallbackNum).padStart(2, '0')}`;
  }
  return fallback;
}

function parseOptionalPage(val: string | number | null | undefined): number | null {
  if (val === null || val === undefined || String(val).trim() === '') {
    return null;
  }
  const n = typeof val === 'number' ? val : parseInt(String(val).trim(), 10);
  return isNaN(n) ? null : n;
}

function isRowUnchanged(
  row: EditableRequirementRow,
  initial: RequirementItem | undefined
): boolean {
  if (!initial) return false;
  return (
    row.code.trim() === initial.code.trim() &&
    row.text.trim() === initial.text.trim() &&
    row.category.trim() === initial.category.trim() &&
    Boolean(row.mandatory) === Boolean(initial.mandatory) &&
    row.acceptance.trim() === initial.acceptance.trim() &&
    parseOptionalPage(row.source_page) === (initial.source_page ?? null) &&
    (row.source_section.trim() || null) === (initial.source_section?.trim() || null)
  );
}

function mapItemToEditableRow(item: RequirementItem, idx: number): EditableRequirementRow {
  return {
    localId: item.id || `req-row-${idx}`,
    id: item.id ?? null,
    code: item.code,
    text: item.text,
    category: item.category,
    mandatory: Boolean(item.mandatory),
    acceptance: item.acceptance,
    source_document_id: item.source_document_id ?? null,
    source_page:
      item.source_page !== null && item.source_page !== undefined
        ? String(item.source_page)
        : '',
    source_section: item.source_section || '',
    origin: item.origin,
    isNew: false,
  };
}

export const RequirementsReviewPage: React.FC = () => {
  const { id: evaluationId } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const outletContext = useOutletContext<EvaluationLayoutContext | undefined>();
  const evaluation = outletContext?.evaluationDetail ?? null;

  const [initialItems, setInitialItems] = useState<RequirementItem[]>([]);
  const [rows, setRows] = useState<EditableRequirementRow[]>([]);
  const [editingRowIds, setEditingRowIds] = useState<Set<string>>(new Set());
  const [rowBackups, setRowBackups] = useState<Record<string, EditableRequirementRow>>({});

  const [loading, setLoading] = useState<boolean>(true);
  const [hasLoaded, setHasLoaded] = useState<boolean>(false);
  const [saving, setSaving] = useState<boolean>(false);
  const [rerunning, setRerunning] = useState<boolean>(false);
  const [errorBanner, setErrorBanner] = useState<string | null>(null);
  const [successBanner, setSuccessBanner] = useState<string | null>(null);
  const [serverErrors, setServerErrors] = useState<Record<string, string>>({});
  const [showRerunDialog, setShowRerunDialog] = useState<boolean>(false);
  const [rowToDelete, setRowToDelete] = useState<{ localId: string; code: string } | null>(null);

  const nextLocalIdCounter = useRef<number>(1);

  useEffect(() => {
    let active = true;
    if (!evaluationId) return;

    setLoading(true);
    setErrorBanner(null);

    apiClient
      .getRequirements(evaluationId)
      .then((reqs) => {
        if (!active) return;
        setInitialItems(reqs);
        setRows(reqs.map((item, idx) => mapItemToEditableRow(item, idx)));
        setEditingRowIds(new Set());
        setRowBackups({});
        setServerErrors({});
        setHasLoaded(true);
      })
      .catch((err: unknown) => {
        if (!active) return;
        setErrorBanner(
          err instanceof Error ? err.message : 'Failed to load requirements'
        );
      })
      .finally(() => {
        if (active) {
          setLoading(false);
        }
      });

    return () => {
      active = false;
    };
  }, [evaluationId]);

  // Map initial items by localId
  const initialByLocalId = useMemo(() => {
    const map = new Map<string, RequirementItem>();
    initialItems.forEach((item, idx) => {
      const key = item.id || `req-row-${idx}`;
      map.set(key, item);
    });
    return map;
  }, [initialItems]);

  // Live mandatory count for the page's own count line (includes unsaved edits)
  const mandatoryCount = useMemo(
    () => rows.filter((r) => r.mandatory).length,
    [rows]
  );

  // Check if local rows differ from initialItems
  const isDirty = useMemo(() => {
    if (loading && !hasLoaded) return false;
    if (rows.length !== initialItems.length) return true;
    for (let i = 0; i < rows.length; i++) {
      const row = rows[i];
      const expectedKey = initialItems[i].id || `req-row-${i}`;
      if (row.localId !== expectedKey) return true;
      const initial = initialByLocalId.get(row.localId);
      if (!isRowUnchanged(row, initial)) return true;
    }
    return false;
  }, [rows, initialItems, initialByLocalId, loading, hasLoaded]);

  // Unsaved edits: warn on reload/close and block every in-app navigation
  const { guardDialog, allowNavigation } = useUnsavedChangesGuard(isDirty);

  // Client validation: code and text required; codes unique within list
  const validationErrors = useMemo(() => {
    const errors: Record<string, string> = {};
    const seenCodes = new Map<string, number>();

    rows.forEach((row, idx) => {
      const trimmedCode = row.code.trim();
      const trimmedText = row.text.trim();

      if (!trimmedCode) {
        errors[`${idx}.code`] = 'Code is required';
      } else {
        const lowerCode = trimmedCode.toLowerCase();
        if (seenCodes.has(lowerCode)) {
          errors[`${idx}.code`] = 'Requirement codes must be unique';
          const prevIdx = seenCodes.get(lowerCode)!;
          errors[`${prevIdx}.code`] = 'Requirement codes must be unique';
        } else {
          seenCodes.set(lowerCode, idx);
        }
      }

      if (!trimmedText) {
        errors[`${idx}.text`] = 'Requirement text is required';
      }
    });

    return errors;
  }, [rows]);

  const isValid = Object.keys(validationErrors).length === 0;
  const canSave = isDirty && isValid && !saving;

  // Determine effective origin for a row
  const getEffectiveOrigin = useCallback(
    (row: EditableRequirementRow): RequirementOrigin => {
      const initial = initialByLocalId.get(row.localId);
      if (isRowUnchanged(row, initial) && initial) {
        return initial.origin;
      }
      return 'user';
    },
    [initialByLocalId]
  );

  // Whether any row has origin === 'user' (saved or locally edited/added)
  const hasAnyUserOriginRow = useMemo(() => {
    const savedHasUser = initialItems.some((item) => item.origin === 'user');
    const currentHasUser = rows.some((row) => getEffectiveOrigin(row) === 'user');
    return savedHasUser || currentHasUser;
  }, [initialItems, rows, getEffectiveOrigin]);

  // A re-run replaces the whole list: warn when that discards user work
  const rerunWillLoseEdits = isDirty || hasAnyUserOriginRow;

  // Row edit handlers
  const handleStartRowEdit = (row: EditableRequirementRow) => {
    setSuccessBanner(null);
    setRowBackups((prev) => ({
      ...prev,
      [row.localId]: { ...row },
    }));
    setEditingRowIds((prev) => {
      const next = new Set(prev);
      next.add(row.localId);
      return next;
    });
  };

  const handleFinishRowEdit = (localId: string) => {
    setEditingRowIds((prev) => {
      const next = new Set(prev);
      next.delete(localId);
      return next;
    });
    setRowBackups((prev) => {
      const copy = { ...prev };
      delete copy[localId];
      return copy;
    });
    setRows((prev) =>
      prev.map((r) => (r.localId === localId ? { ...r, isNew: false } : r))
    );
  };

  const handleCancelRowEdit = (localId: string) => {
    const backup = rowBackups[localId];
    if (backup) {
      setRows((prev) =>
        prev.map((r) => (r.localId === localId ? { ...backup } : r))
      );
    } else {
      // Newly added row being cancelled before commitment
      setRows((prev) => prev.filter((r) => r.localId !== localId));
    }
    setEditingRowIds((prev) => {
      const next = new Set(prev);
      next.delete(localId);
      return next;
    });
    setRowBackups((prev) => {
      const copy = { ...prev };
      delete copy[localId];
      return copy;
    });
  };

  const handleRowFieldChange = <K extends keyof EditableRequirementRow>(
    localId: string,
    field: K,
    value: EditableRequirementRow[K]
  ) => {
    setSuccessBanner(null);
    setServerErrors({});
    setRows((prev) =>
      prev.map((r) => (r.localId === localId ? { ...r, [field]: value } : r))
    );
  };

  const handleAddRow = () => {
    setSuccessBanner(null);
    setServerErrors({});
    const nextCode = generateNextRequirementCode(rows.map((r) => r.code));
    const newLocalId = `new-req-${nextLocalIdCounter.current++}`;
    const newRow: EditableRequirementRow = {
      localId: newLocalId,
      id: null,
      code: nextCode,
      text: '',
      category: '',
      mandatory: false,
      acceptance: '',
      source_document_id: null,
      source_page: '',
      source_section: '',
      origin: 'user',
      isNew: true,
    };
    setRows((prev) => [...prev, newRow]);
    setEditingRowIds((prev) => {
      const next = new Set(prev);
      next.add(newLocalId);
      return next;
    });
  };

  const handleDeleteRow = (localId: string) => {
    setSuccessBanner(null);
    setServerErrors({});
    setRows((prev) => prev.filter((r) => r.localId !== localId));
    setEditingRowIds((prev) => {
      const next = new Set(prev);
      next.delete(localId);
      return next;
    });
    setRowBackups((prev) => {
      const copy = { ...prev };
      delete copy[localId];
      return copy;
    });
  };

  // Save full list via PUT /api/evaluations/{id}/requirements
  const handleSave = async () => {
    if (!evaluationId || !isDirty || saving) return;

    if (!isValid) {
      setErrorBanner('Please fix validation errors before saving.');
      return;
    }

    try {
      setSaving(true);
      setErrorBanner(null);
      setSuccessBanner(null);
      setServerErrors({});

      const payload: RequirementItem[] = rows.map((row, idx) => {
        const initial = initialByLocalId.get(row.localId);
        const unchanged = isRowUnchanged(row, initial);
        return {
          id: row.id ?? null,
          code: row.code.trim(),
          text: row.text.trim(),
          category: row.category.trim(),
          mandatory: Boolean(row.mandatory),
          acceptance: row.acceptance.trim(),
          source_document_id: row.source_document_id ?? null,
          source_page: parseOptionalPage(row.source_page),
          source_section: row.source_section.trim() || null,
          position: idx,
          origin: unchanged && initial ? initial.origin : 'user',
        };
      });

      await apiClient.replaceRequirements(evaluationId, payload);

      // Refetch requirements on success, clear dirty state, and refresh layout header counts + detail
      const refetchedReqs = await apiClient.getRequirements(evaluationId);
      setInitialItems(refetchedReqs);
      setRows(refetchedReqs.map((item, idx) => mapItemToEditableRow(item, idx)));
      setEditingRowIds(new Set());
      setRowBackups({});
      setServerErrors({});
      await outletContext?.refresh();
      setSuccessBanner('Requirements saved successfully.');
    } catch (err: unknown) {
      if (err instanceof ApiValidationError) {
        setServerErrors(err.fieldErrors);
        setErrorBanner(err.message);
      } else if (err instanceof Error) {
        setErrorBanner(err.message);
      } else {
        setErrorBanner('Failed to save requirements');
      }
    } finally {
      setSaving(false);
    }
  };

  // Re-run extraction: always confirmed first, then sent with confirm_replace true
  const executeRerunExtraction = async () => {
    if (!evaluationId) return;
    try {
      setRerunning(true);
      setErrorBanner(null);
      setSuccessBanner(null);

      await apiClient.extractRequirements(evaluationId, { confirm_replace: true });

      await outletContext?.refresh();

      // The confirmed re-run intentionally discards any unsaved edits
      allowNavigation();
      navigate(`/evaluations/${evaluationId}/documents`, {
        state: { fromExtractStart: true },
      });
    } catch (err: unknown) {
      if (err instanceof ApiHttpError && err.status === 409) {
        // A job is already active: the Documents tab shows its progress
        allowNavigation();
        navigate(`/evaluations/${evaluationId}/documents`, {
          state: { fromExtractStart: true },
        });
      } else if (err instanceof Error) {
        // Includes 422 messages naming what is missing, shown as-is
        setErrorBanner(err.message);
      } else {
        setErrorBanner('Failed to start extraction');
      }
    } finally {
      setRerunning(false);
    }
  };

  const handleClickRerunExtraction = () => {
    setShowRerunDialog(true);
  };

  const handleConfirmRerunExtraction = async () => {
    setShowRerunDialog(false);
    await executeRerunExtraction();
  };

  if (loading && !hasLoaded && rows.length === 0) {
    return (
      <div className="rounded-lg border border-border bg-background p-12 text-center text-muted text-sm">
        Loading requirements...
      </div>
    );
  }

  const isStale = evaluation?.status === 'stale';
  const isAnalysedOrStale =
    evaluation?.status === 'analysed' || evaluation?.status === 'stale';
  const vendors = evaluation?.vendors || [];

  return (
    <TooltipProvider delayDuration={150}>
      <div className="space-y-5 text-left">
        {/* Horizontal Stepper Card (per S4 layout) */}
        <div className="rounded-lg border border-border bg-background px-5 py-3.5 flex items-center justify-between gap-2 overflow-x-auto">
          {[
            { label: 'Extract', done: rows.length > 0 || evaluation?.status !== 'draft' },
            ...vendors.map((v) => ({
              label: `Analyse ${v.name.split(' ')[0]}`,
              done: isAnalysedOrStale,
            })),
            { label: 'Score', done: isAnalysedOrStale },
            { label: 'Recommend', done: isAnalysedOrStale },
          ].map((step, idx, arr) => (
            <React.Fragment key={step.label}>
              <div className="flex items-center gap-2 shrink-0 text-sm">
                {step.done ? (
                  <span className="w-5 h-5 rounded-full bg-status-compliant-text text-background inline-flex items-center justify-center shrink-0">
                    <Check className="w-3 h-3 stroke-[3]" />
                  </span>
                ) : (
                  <span className="w-2.5 h-2.5 rounded-full bg-border inline-block shrink-0" />
                )}
                <span className={step.done ? 'font-medium text-text' : 'text-muted'}>
                  {step.label}
                </span>
              </div>
              {idx < arr.length - 1 && (
                <div className="h-px bg-border flex-1 min-w-[16px]" />
              )}
            </React.Fragment>
          ))}
        </div>

        {/* Stale Banner when evaluation status is stale */}
        {isStale && (
          <div
            role="alert"
            className="rounded-lg border border-status-partial-text/40 bg-status-partial-bg px-4 py-3 text-sm text-status-partial-text flex items-center gap-2.5"
          >
            <AlertTriangle className="w-4 h-4 shrink-0" />
            <span>
              Requirements were edited after analysis. Results are stale — re-run analysis to update.
            </span>
          </div>
        )}

        {/* Error & Success Notifications */}
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

        {/* Section Header Row */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pt-1">
          <div className="flex items-baseline gap-2.5">
            <h2 className="text-section-title text-text font-semibold">
              Requirements
            </h2>
            <span className="text-sm text-muted">
              {rows.length} requirement{rows.length === 1 ? '' : 's'} · {mandatoryCount} mandatory
            </span>
          </div>

          <div className="flex flex-wrap items-center gap-2.5">
            <Button
              variant="outline"
              size="sm"
              onClick={handleAddRow}
              disabled={saving || rerunning}
              className="gap-1.5"
            >
              <Plus className="w-4 h-4" />
              <span>Add requirement</span>
            </Button>

            <Button
              variant="outline"
              size="sm"
              onClick={handleClickRerunExtraction}
              disabled={saving || rerunning}
              className="gap-1.5"
            >
              <RefreshCw className="w-3.5 h-3.5" />
              <span>{rerunning ? 'Starting...' : 'Re-run extraction'}</span>
            </Button>

            <Button
              variant="outline"
              size="sm"
              onClick={handleSave}
              disabled={!canSave}
              className="font-semibold"
            >
              {saving ? 'Saving...' : 'Save changes'}
            </Button>

            {/* Disabled Run Analysis Primary Action with Tooltip */}
            <Tooltip>
              <TooltipTrigger asChild>
                <div className="relative group inline-block">
                  <Button
                    variant="primary"
                    size="sm"
                    disabled={true}
                    className="gap-1.5 font-semibold"
                  >
                    <span>Run analysis</span>
                  </Button>
                  <div className="absolute bottom-full right-0 mb-2 hidden group-hover:block whitespace-nowrap rounded-md bg-navy text-white text-xs px-2.5 py-1 shadow-md pointer-events-none z-50">
                    Analysis arrives in the next phase
                  </div>
                </div>
              </TooltipTrigger>
              <TooltipContent>Analysis arrives in the next phase</TooltipContent>
            </Tooltip>
          </div>
        </div>

        {/* Empty State or Requirements Table */}
        {rows.length === 0 ? (
          <div className="rounded-lg border border-border bg-background py-16 px-6 text-center space-y-4">
            <div className="w-11 h-11 rounded-lg bg-surface border border-border flex items-center justify-center mx-auto text-muted">
              <FileText className="w-5 h-5" />
            </div>
            <div className="space-y-1 max-w-md mx-auto">
              <h3 className="text-base font-semibold text-text">
                No requirements found
              </h3>
              <p className="text-sm text-muted">
                Add a requirement manually or re-run extraction from your uploaded requirements document.
              </p>
            </div>
            <div className="flex items-center justify-center gap-3 pt-1">
              <Button variant="outline" size="sm" onClick={handleAddRow} className="gap-1.5">
                <Plus className="w-4 h-4" />
                <span>Add requirement</span>
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={handleClickRerunExtraction}
                disabled={rerunning}
                className="gap-1.5"
              >
                <RefreshCw className="w-3.5 h-3.5" />
                <span>Re-run extraction</span>
              </Button>
            </div>
          </div>
        ) : (
          <div className="space-y-2">
            <div className="rounded-lg border border-border bg-background shadow-sm overflow-hidden">
              <table className="w-full border-collapse text-left">
                <thead>
                  <tr className="border-b border-border bg-surface text-table-header text-muted uppercase">
                    <th className="py-3 px-4 w-[9%] font-medium">ID</th>
                    <th className="py-3 px-4 w-[31%] font-medium">REQUIREMENT</th>
                    <th className="py-3 px-4 w-[12%] font-medium">CATEGORY</th>
                    <th className="py-3 px-4 w-[10%] font-medium">MANDATORY</th>
                    <th className="py-3 px-4 w-[20%] font-medium">
                      ACCEPTANCE CONDITION
                    </th>
                    <th className="py-3 px-4 w-[11%] font-medium">SOURCE</th>
                    <th className="py-3 px-4 w-[7%] font-medium text-right">
                      ACTIONS
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {rows.map((row, idx) => {
                    const codeError =
                      validationErrors[`${idx}.code`] ||
                      serverErrors[`${idx}.code`] ||
                      serverErrors.code;
                    const textError =
                      validationErrors[`${idx}.text`] ||
                      serverErrors[`${idx}.text`] ||
                      serverErrors.text;
                    const categoryError = serverErrors[`${idx}.category`];
                    const acceptanceError = serverErrors[`${idx}.acceptance`];
                    const isEditing =
                      editingRowIds.has(row.localId) ||
                      Boolean(codeError) ||
                      Boolean(textError);

                    const formattedSource = formatRequirementSource(
                      row.source_page,
                      row.source_section
                    );

                    return (
                      <tr
                        key={row.localId}
                        className="hover:bg-surface/40 transition-colors align-top"
                      >
                        {/* ID / Code Column */}
                        <td className="py-3.5 px-4 text-xs font-medium text-muted whitespace-nowrap">
                          {isEditing ? (
                            <div className="space-y-1">
                              <Input
                                value={row.code}
                                onChange={(e) =>
                                  handleRowFieldChange(row.localId, 'code', e.target.value)
                                }
                                placeholder="Code"
                                aria-label="Requirement code"
                                className={`h-8 text-xs font-medium ${
                                  codeError ? 'border-status-noncompliant-text' : ''
                                }`}
                              />
                              {codeError && (
                                <p className="text-xs text-status-noncompliant-text whitespace-normal">
                                  {codeError}
                                </p>
                              )}
                            </div>
                          ) : (
                            <span className="text-muted font-medium">{row.code}</span>
                          )}
                        </td>

                        {/* Requirement Text Column */}
                        <td className="py-3.5 px-4 text-sm text-text">
                          {isEditing ? (
                            <div className="space-y-1">
                              <Input
                                value={row.text}
                                onChange={(e) =>
                                  handleRowFieldChange(row.localId, 'text', e.target.value)
                                }
                                placeholder="Requirement description"
                                aria-label="Requirement text"
                                className={`h-8 text-sm ${
                                  textError ? 'border-status-noncompliant-text' : ''
                                }`}
                              />
                              {textError && (
                                <p className="text-xs text-status-noncompliant-text">
                                  {textError}
                                </p>
                              )}
                            </div>
                          ) : (
                            <span className="font-semibold text-text leading-snug">
                              {row.text}
                            </span>
                          )}
                        </td>

                        {/* Category Column */}
                        <td className="py-3.5 px-4 text-xs text-muted">
                          {isEditing ? (
                            <div className="space-y-1">
                              <Input
                                value={row.category}
                                onChange={(e) =>
                                  handleRowFieldChange(row.localId, 'category', e.target.value)
                                }
                                placeholder="Category"
                                aria-label="Category"
                                className="h-8 text-xs"
                              />
                              {categoryError && (
                                <p className="text-xs text-status-noncompliant-text">
                                  {categoryError}
                                </p>
                              )}
                            </div>
                          ) : (
                            <span>{row.category || '—'}</span>
                          )}
                        </td>

                        {/* Mandatory Column */}
                        <td className="py-3.5 px-4">
                          <Switch
                            checked={row.mandatory}
                            onCheckedChange={(checked) =>
                              handleRowFieldChange(row.localId, 'mandatory', checked)
                            }
                            aria-label={`Mandatory switch for ${row.code}`}
                          />
                        </td>

                        {/* Acceptance Condition Column */}
                        <td className="py-3.5 px-4 text-xs text-text">
                          {isEditing ? (
                            <div className="space-y-1">
                              <Input
                                value={row.acceptance}
                                onChange={(e) =>
                                  handleRowFieldChange(
                                    row.localId,
                                    'acceptance',
                                    e.target.value
                                  )
                                }
                                placeholder="Acceptance condition"
                                aria-label="Acceptance condition"
                                className="h-8 text-xs"
                              />
                              {acceptanceError && (
                                <p className="text-xs text-status-noncompliant-text">
                                  {acceptanceError}
                                </p>
                              )}
                            </div>
                          ) : (
                            <span>{row.acceptance || '—'}</span>
                          )}
                        </td>

                        {/* Source Column */}
                        <td className="py-3.5 px-4 text-xs text-muted break-words">
                          {isEditing ? (
                            <div className="flex items-center gap-1.5">
                              <Input
                                type="number"
                                min={1}
                                value={row.source_page}
                                onChange={(e) =>
                                  handleRowFieldChange(
                                    row.localId,
                                    'source_page',
                                    e.target.value
                                  )
                                }
                                placeholder="Page"
                                aria-label="Source page"
                                className="h-8 w-16 text-xs px-2"
                              />
                              <Input
                                value={row.source_section}
                                onChange={(e) =>
                                  handleRowFieldChange(
                                    row.localId,
                                    'source_section',
                                    e.target.value
                                  )
                                }
                                placeholder="Section"
                                aria-label="Source section"
                                className="h-8 w-20 text-xs px-2"
                              />
                            </div>
                          ) : formattedSource === '—' ? (
                            <span>—</span>
                          ) : (
                            <span className="inline-flex items-center gap-1.5 text-muted">
                              <FileText className="w-3.5 h-3.5 shrink-0" />
                              <span>{formattedSource}</span>
                            </span>
                          )}
                        </td>

                        {/* Actions Column */}
                        <td className="py-3.5 px-4 text-right whitespace-nowrap">
                          {isEditing ? (
                            <div className="inline-flex items-center gap-2">
                              <Button
                                variant="primary"
                                size="sm"
                                onClick={() => handleFinishRowEdit(row.localId)}
                                disabled={Boolean(codeError) || Boolean(textError)}
                                className="h-7 px-2.5 text-xs font-semibold"
                              >
                                Done
                              </Button>
                              <button
                                type="button"
                                onClick={() => handleCancelRowEdit(row.localId)}
                                className="text-xs text-muted hover:text-text px-1"
                              >
                                Cancel
                              </button>
                            </div>
                          ) : (
                            <div className="inline-flex items-center gap-1">
                              <button
                                type="button"
                                onClick={() => handleStartRowEdit(row)}
                                aria-label={`Edit ${row.code}`}
                                className="p-1.5 text-muted hover:text-text rounded hover:bg-surface transition-colors"
                              >
                                <Pencil className="w-3.5 h-3.5" />
                              </button>
                              <button
                                type="button"
                                onClick={() =>
                                  setRowToDelete({ localId: row.localId, code: row.code })
                                }
                                aria-label={`Delete ${row.code}`}
                                className="p-1.5 text-muted hover:text-status-noncompliant-text rounded hover:bg-surface transition-colors"
                              >
                                <Trash2 className="w-3.5 h-3.5" />
                              </button>
                            </div>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            <div className="text-xs text-muted px-1">
              Showing {rows.length} of {rows.length} requirement{rows.length === 1 ? '' : 's'}
            </div>
          </div>
        )}

        {/* Re-run extraction: always confirm */}
        <RerunExtractionDialog
          open={showRerunDialog}
          hasEdits={rerunWillLoseEdits}
          busy={rerunning}
          onConfirm={handleConfirmRerunExtraction}
          onCancel={() => setShowRerunDialog(false)}
        />

        {/* Delete requirement row: confirm first */}
        <ConfirmDialog
          open={rowToDelete !== null}
          title={rowToDelete ? `Delete ${rowToDelete.code || 'requirement'}` : 'Delete requirement'}
          description="Removed from the list when you save."
          confirmLabel="Delete requirement"
          onConfirm={() => {
            if (rowToDelete) handleDeleteRow(rowToDelete.localId);
            setRowToDelete(null);
          }}
          onCancel={() => setRowToDelete(null)}
        />

        {/* Unsaved changes: in-app navigation blocker dialog */}
        {guardDialog}
      </div>
    </TooltipProvider>
  );
};

export default RequirementsReviewPage;
