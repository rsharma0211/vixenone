import React, { useCallback, useEffect, useRef, useState } from 'react';
import { useLocation, useNavigate, useOutletContext, useParams } from 'react-router-dom';
import { AlertCircle } from 'lucide-react';
import { apiClient, ApiHttpError, ApiValidationError } from '@/lib/api/client';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { ConfirmDialog } from '@/components/ConfirmDialog';
import { DocumentSlot, DocumentSlotError } from '@/components/DocumentSlot';
import { RerunExtractionDialog } from '@/components/RerunExtractionDialog';
import type { EvaluationLayoutContext } from '@/components/layout/EvaluationLayout';
import { isJobActive } from '@/lib/evaluationRouting';
import type {
  AnalysisJobResponse,
  DocumentResponse,
  EvaluationDetailResponse,
  VendorResponse,
} from '@/lib/types';

// Screen: S3 / S3-error (Documents tab: requirements document, vendors and proposals)

const MAX_FILE_SIZE = 10 * 1024 * 1024; // 10 MB
const MAX_VENDORS = 3;
const MIN_VENDORS = 2;
const REPLACE_NOTE = 'Re-run extraction to update requirements.';
const OUT_OF_DATE_WARNING = 'Results will be marked out of date.';

const ERROR_BANNER_CLASS =
  'rounded-lg border border-status-noncompliant-text/30 bg-status-noncompliant-bg px-4 py-3 text-sm text-status-noncompliant-text flex items-center gap-2';
const CARD_CLASS = 'rounded-lg border border-border bg-background p-6 space-y-4 shadow-sm';

function precheckFile(file: File): string | null {
  const ext = file.name.substring(file.name.lastIndexOf('.')).toLowerCase();
  const isPdfOrDocx =
    ext === '.pdf' ||
    ext === '.docx' ||
    file.type === 'application/pdf' ||
    file.type === 'application/vnd.openxmlformats-officedocument.wordprocessingml.document';
  if (!isPdfOrDocx) return 'Only PDF or DOCX files are supported.';
  if (file.size > MAX_FILE_SIZE) return 'File exceeds maximum size of 10 MB';
  return null;
}

export const DocumentsPage: React.FC = () => {
  const { id: evaluationId } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const routerLocation = useLocation();
  const refreshLayout = useOutletContext<EvaluationLayoutContext | undefined>()?.refresh;

  // Read once per mount so the load effect depends only on the evaluation id.
  const navStateRef = useRef(routerLocation.state as { fromExtractStart?: boolean } | null);
  const isMountedRef = useRef<boolean>(true);
  const navigatedJobIdRef = useRef<string | null>(null);

  useEffect(() => {
    isMountedRef.current = true;
    return () => {
      isMountedRef.current = false;
    };
  }, []);

  const [detail, setDetail] = useState<EvaluationDetailResponse | null>(null);
  const [latestJob, setLatestJob] = useState<AnalysisJobResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [pageError, setPageError] = useState<string | null>(null);
  const [extractError, setExtractError] = useState<string | null>(null);
  const [startingExtraction, setStartingExtraction] = useState<boolean>(false);

  // Upload slots are keyed 'requirements' or by vendor id.
  const [uploadingSlots, setUploadingSlots] = useState<Record<string, boolean>>({});
  const [slotErrors, setSlotErrors] = useState<Record<string, DocumentSlotError>>({});
  const [replacedSlots, setReplacedSlots] = useState<Record<string, boolean>>({});

  // Vendor management
  const [vendorDrafts, setVendorDrafts] = useState<Record<string, string>>({});
  const [vendorErrors, setVendorErrors] = useState<Record<string, string>>({});
  const [busyVendors, setBusyVendors] = useState<Record<string, boolean>>({});
  const [addOpen, setAddOpen] = useState<boolean>(false);
  const [newVendorName, setNewVendorName] = useState<string>('');
  const [addError, setAddError] = useState<string | null>(null);
  const [addBusy, setAddBusy] = useState<boolean>(false);
  const skipRenameRef = useRef<string | null>(null);

  // Confirmation dialogs
  const [docToDelete, setDocToDelete] = useState<DocumentResponse | null>(null);
  const [vendorToRemove, setVendorToRemove] = useState<VendorResponse | null>(null);
  const [showAddWarning, setShowAddWarning] = useState<boolean>(false);
  const [rerunDialog, setRerunDialog] = useState<{ hasEdits: boolean } | null>(null);
  const [confirmBusy, setConfirmBusy] = useState<boolean>(false);

  const reloadDetail = useCallback(async () => {
    if (!evaluationId) return;
    const fresh = await apiClient.getEvaluation(evaluationId);
    setDetail(fresh);
    await refreshLayout?.();
  }, [evaluationId, refreshLayout]);

  // Initial load of detail + latest job
  useEffect(() => {
    if (!evaluationId) return;
    let active = true;
    setLoading(true);
    setPageError(null);

    Promise.all([apiClient.getEvaluation(evaluationId), apiClient.getLatestJob(evaluationId)])
      .then(async ([fresh, job]) => {
        if (!active || !isMountedRef.current) return;
        setDetail(fresh);
        const effectiveJob = job ?? fresh.latest_job ?? null;
        setLatestJob(effectiveJob);

        if (effectiveJob?.status === 'done') {
          // If explicitly redirected after starting extraction from Requirements review
          if (
            navStateRef.current?.fromExtractStart &&
            navigatedJobIdRef.current !== effectiveJob.id
          ) {
            navigatedJobIdRef.current = effectiveJob.id;
            await refreshLayout?.();
            if (active && isMountedRef.current) {
              navigate(`/evaluations/${evaluationId}/requirements`, { replace: true });
            }
          } else {
            // Already finished before this visit, or revisit: record so we never auto-navigate
            navigatedJobIdRef.current = effectiveJob.id;
          }
        }
      })
      .catch((err: unknown) => {
        if (!active) return;
        setPageError(err instanceof Error ? err.message : 'Failed to load evaluation');
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
    };
  }, [evaluationId, navigate, refreshLayout]);

  const jobActive = isJobActive(latestJob);

  // Poll jobs/latest every 2 s while a job is active; stop on done/failed and on unmount
  useEffect(() => {
    if (!evaluationId || !jobActive) return;

    const intervalId = window.setInterval(async () => {
      try {
        const [job, fresh] = await Promise.all([
          apiClient.getLatestJob(evaluationId),
          apiClient.getEvaluation(evaluationId),
        ]);
        if (!isMountedRef.current) return;

        if (!job || job.status === 'done' || job.status === 'failed') {
          window.clearInterval(intervalId);
          if (job?.status === 'done' && navigatedJobIdRef.current !== job.id) {
            navigatedJobIdRef.current = job.id;
            setLatestJob(job);
            setDetail(fresh);
            await refreshLayout?.();
            if (isMountedRef.current) {
              navigate(`/evaluations/${evaluationId}/requirements`);
            }
            return;
          }
        }

        if (isMountedRef.current) {
          setDetail(fresh);
          setLatestJob(job);
        }
      } catch {
        // Keep polling on transient errors
      }
    }, 2000);

    return () => {
      window.clearInterval(intervalId);
    };
  }, [evaluationId, jobActive, navigate, refreshLayout]);

  const vendors: VendorResponse[] = [...(detail?.vendors ?? [])].sort(
    (a, b) => a.position - b.position
  );
  const documents: DocumentResponse[] = detail?.documents ?? [];
  const requirementsCount = detail?.requirements_count ?? 0;
  const isAnalysed = detail?.status === 'analysed';
  const anyBusy =
    confirmBusy || addBusy || Object.values(busyVendors).some(Boolean);
  const controlsDisabled = jobActive || startingExtraction || anyBusy;

  const reqDoc = documents.find((d) => d.kind === 'requirements');
  const proposalFor = (vendorId: string) =>
    documents.find((d) => d.kind === 'proposal' && d.vendor_id === vendorId);

  // ---- Extract gating: one muted line saying exactly what is missing ----
  const vendorsMissingProposal = vendors.filter((v) => !proposalFor(v.id));
  const isAnySlotUploading = Object.values(uploadingSlots).some(Boolean);
  const hasSlotErrors = Object.keys(slotErrors).length > 0;

  const missing: string[] = [];
  if (!reqDoc) missing.push('Upload the requirements document.');
  if (vendors.length < MIN_VENDORS) missing.push('Add at least 2 vendors.');
  if (vendorsMissingProposal.length > 0) {
    missing.push(`Upload a proposal for ${vendorsMissingProposal.map((v) => v.name).join(', ')}.`);
  }
  if (missing.length === 0 && isAnySlotUploading) missing.push('Waiting for the upload to finish.');
  if (missing.length === 0 && hasSlotErrors) missing.push('Fix the file error shown above.');
  const missingLine = missing.length > 0 ? missing.join(' ') : null;
  const canExtract = missing.length === 0 && !controlsDisabled;

  // ---- Documents ----
  const handleUploadFile = async (file: File, kind: 'requirements' | 'proposal', vendorId?: string) => {
    if (!evaluationId || controlsDisabled) return;
    const slotKey = kind === 'requirements' ? 'requirements' : (vendorId as string);

    const precheckError = precheckFile(file);
    if (precheckError) {
      setSlotErrors((prev) => ({
        ...prev,
        [slotKey]: { label: 'Error', detail: precheckError, filename: file.name, sizeBytes: file.size },
      }));
      return;
    }

    setSlotErrors((prev) => {
      const copy = { ...prev };
      delete copy[slotKey];
      return copy;
    });
    setExtractError(null);

    const isReplacement =
      kind === 'requirements' ? Boolean(reqDoc) : Boolean(vendorId && proposalFor(vendorId));

    try {
      setUploadingSlots((prev) => ({ ...prev, [slotKey]: true }));
      await apiClient.uploadDocument(evaluationId, file, kind, vendorId);
      if (isReplacement) {
        setReplacedSlots((prev) => ({ ...prev, [slotKey]: true }));
      }
      await reloadDetail();
    } catch (err: unknown) {
      let label = 'Error';
      let detailText = err instanceof Error ? err.message : 'Upload failed';
      const lower = detailText.toLowerCase();
      if (err instanceof ApiValidationError && lower.includes('page')) {
        label = 'Too long — max 30 pages';
        detailText = 'Upload a shorter version or only the relevant sections.';
      } else if (err instanceof ApiValidationError && lower.includes('10 mb')) {
        label = 'Too large — max 10 MB';
      } else if (!(err instanceof ApiHttpError) && lower.includes('page')) {
        label = 'Too long — max 30 pages';
        detailText = 'Upload a shorter version or only the relevant sections.';
      }
      setSlotErrors((prev) => ({
        ...prev,
        [slotKey]: { label, detail: detailText, filename: file.name, sizeBytes: file.size },
      }));
    } finally {
      setUploadingSlots((prev) => ({ ...prev, [slotKey]: false }));
    }
  };

  const dismissSlotError = (slotKey: string) =>
    setSlotErrors((prev) => {
      const copy = { ...prev };
      delete copy[slotKey];
      return copy;
    });

  const handleConfirmDeleteDocument = async () => {
    if (!evaluationId || !docToDelete) return;
    const doc = docToDelete;
    try {
      setConfirmBusy(true);
      await apiClient.deleteDocument(evaluationId, doc.id);
      dismissSlotError(doc.kind === 'requirements' ? 'requirements' : doc.vendor_id ?? '');
      setDocToDelete(null);
      await reloadDetail();
    } catch (err: unknown) {
      setDocToDelete(null);
      setPageError(err instanceof Error ? err.message : 'Failed to delete document');
    } finally {
      setConfirmBusy(false);
    }
  };

  // ---- Vendors ----
  const commitRename = async (vendor: VendorResponse) => {
    if (skipRenameRef.current === vendor.id) {
      skipRenameRef.current = null;
      return;
    }
    const draft = vendorDrafts[vendor.id];
    if (!evaluationId || draft === undefined) return;
    const trimmed = draft.trim();
    if (trimmed === vendor.name) {
      setVendorDrafts((prev) => {
        const copy = { ...prev };
        delete copy[vendor.id];
        return copy;
      });
      return;
    }
    try {
      setBusyVendors((prev) => ({ ...prev, [vendor.id]: true }));
      await apiClient.renameVendor(evaluationId, vendor.id, { name: draft });
      setVendorDrafts((prev) => {
        const copy = { ...prev };
        delete copy[vendor.id];
        return copy;
      });
      setVendorErrors((prev) => ({ ...prev, [vendor.id]: '' }));
      await reloadDetail();
    } catch (err: unknown) {
      setVendorErrors((prev) => ({
        ...prev,
        [vendor.id]: err instanceof Error ? err.message : 'Failed to rename vendor',
      }));
    } finally {
      setBusyVendors((prev) => ({ ...prev, [vendor.id]: false }));
    }
  };

  const handleClickAddVendor = () => {
    setAddError(null);
    if (isAnalysed) {
      setShowAddWarning(true);
    } else {
      setAddOpen(true);
    }
  };

  const cancelAddVendor = () => {
    setAddOpen(false);
    setNewVendorName('');
    setAddError(null);
  };

  const submitAddVendor = async () => {
    if (!evaluationId || addBusy) return;
    try {
      setAddBusy(true);
      setAddError(null);
      await apiClient.addVendor(evaluationId, { name: newVendorName });
      setAddOpen(false);
      setNewVendorName('');
      setExtractError(null);
      await reloadDetail();
    } catch (err: unknown) {
      setAddError(err instanceof Error ? err.message : 'Failed to add vendor');
    } finally {
      setAddBusy(false);
    }
  };

  const handleConfirmRemoveVendor = async () => {
    if (!evaluationId || !vendorToRemove) return;
    const vendor = vendorToRemove;
    try {
      setConfirmBusy(true);
      await apiClient.deleteVendor(evaluationId, vendor.id);
      setVendorToRemove(null);
      dismissSlotError(vendor.id);
      setExtractError(null);
      await reloadDetail();
    } catch (err: unknown) {
      setVendorToRemove(null);
      setPageError(err instanceof Error ? err.message : 'Failed to remove vendor');
    } finally {
      setConfirmBusy(false);
    }
  };

  // ---- Extraction ----
  const startExtraction = async (confirmReplace: boolean) => {
    if (!evaluationId) return;
    try {
      setStartingExtraction(true);
      setExtractError(null);
      setPageError(null);

      const job = confirmReplace
        ? await apiClient.extractRequirements(evaluationId, { confirm_replace: true })
        : await apiClient.extractRequirements(evaluationId);
      setLatestJob(job);
      setReplacedSlots({});
      await reloadDetail();

      if (job.status === 'done' && navigatedJobIdRef.current !== job.id) {
        navigatedJobIdRef.current = job.id;
        await refreshLayout?.();
        if (isMountedRef.current) {
          navigate(`/evaluations/${evaluationId}/requirements`);
        }
      }
    } catch (err: unknown) {
      if (err instanceof ApiValidationError) {
        // Show the api message as-is
        setExtractError(err.message);
      } else if (err instanceof ApiHttpError && err.status === 409) {
        const lowerMsg = err.message.toLowerCase();
        if (lowerMsg.includes('replace') || lowerMsg.includes('edits')) {
          setRerunDialog({ hasEdits: true });
        } else {
          // A job is already active: resume progress and polling
          try {
            const [job, fresh] = await Promise.all([
              apiClient.getLatestJob(evaluationId),
              apiClient.getEvaluation(evaluationId),
            ]);
            setDetail(fresh);
            setLatestJob(job);
          } catch (resumeErr: unknown) {
            setExtractError(
              resumeErr instanceof Error ? resumeErr.message : 'Failed to resume active job'
            );
          }
        }
      } else if (err instanceof Error) {
        setExtractError(err.message);
      } else {
        setExtractError('Failed to start requirement extraction');
      }
    } finally {
      setStartingExtraction(false);
    }
  };

  const handleClickExtract = async () => {
    if (!evaluationId || !canExtract) return;
    if (requirementsCount === 0) {
      await startExtraction(false);
      return;
    }
    // Requirements already exist: this is a re-run, so always confirm first
    try {
      setStartingExtraction(true);
      setExtractError(null);
      const reqs = await apiClient.getRequirements(evaluationId);
      setRerunDialog({ hasEdits: reqs.some((r) => r.origin === 'user') });
    } catch (err: unknown) {
      setExtractError(
        err instanceof Error
          ? `Could not check the requirement list before re-running: ${err.message}`
          : 'Could not check the requirement list before re-running.'
      );
    } finally {
      setStartingExtraction(false);
    }
  };

  const handleConfirmRerun = async () => {
    setRerunDialog(null);
    await startExtraction(true);
  };

  // ---- Render ----
  if (loading) {
    return (
      <div className="rounded-lg border border-border bg-background p-12 text-center text-muted text-sm">
        Loading documents...
      </div>
    );
  }

  if (!detail) {
    return (
      <div role="alert" className={ERROR_BANNER_CLASS}>
        <AlertCircle className="w-4 h-4 shrink-0" />
        <span>{pageError ?? 'Evaluation not found'}</span>
      </div>
    );
  }

  const isJobFailed = latestJob?.status === 'failed' && !jobActive;
  const atMaxVendors = vendors.length >= MAX_VENDORS;
  const slotNote = (slotKey: string) =>
    replacedSlots[slotKey] && requirementsCount > 0 ? REPLACE_NOTE : null;

  return (
    <div className="space-y-6 text-left max-w-[880px]">
      {pageError && (
        <div role="alert" className={ERROR_BANNER_CLASS}>
          <AlertCircle className="w-4 h-4 shrink-0" />
          <span>{pageError}</span>
        </div>
      )}

      {jobActive && latestJob && (
        <div
          role="status"
          aria-live="polite"
          className="rounded-lg border border-border bg-surface px-4 py-3 flex items-center justify-between text-sm"
        >
          <div className="flex items-center gap-2.5">
            <span className="w-2 h-2 rounded-full bg-lifecycle-blue inline-block animate-pulse shrink-0" />
            <span className="font-medium text-text">{latestJob.step_label}</span>
          </div>
          <span className="text-xs text-muted">Extraction in progress</span>
        </div>
      )}

      {isJobFailed && (
        <div
          role="alert"
          className="rounded-lg border border-status-noncompliant-text/30 bg-status-noncompliant-bg px-4 py-3 text-sm text-status-noncompliant-text flex items-center justify-between gap-4"
        >
          <div className="flex items-center gap-2">
            <AlertCircle className="w-4 h-4 shrink-0" />
            <span>{latestJob?.error_message || 'Requirement extraction failed. Please try again.'}</span>
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={handleClickExtract}
            disabled={!canExtract}
            className="shrink-0"
          >
            Try again
          </Button>
        </div>
      )}

      {extractError && (
        <div role="alert" className={ERROR_BANNER_CLASS}>
          <AlertCircle className="w-4 h-4 shrink-0" />
          <span>{extractError}</span>
        </div>
      )}

      {/* Requirements document */}
      <div className={CARD_CLASS}>
        <div className="space-y-0.5">
          <h2 className="text-card-title text-text font-semibold">Requirements document</h2>
          <p className="text-xs text-muted">PDF or DOCX · max 10 MB · max 30 pages</p>
        </div>
        <DocumentSlot
          doc={reqDoc}
          error={slotErrors['requirements']}
          uploading={Boolean(uploadingSlots['requirements'])}
          disabled={controlsDisabled}
          note={slotNote('requirements')}
          removeLabel="Remove requirements document"
          onFileSelected={(file) => handleUploadFile(file, 'requirements')}
          onRemove={() => reqDoc && setDocToDelete(reqDoc)}
          onDismissError={() => dismissSlotError('requirements')}
        />
      </div>

      {/* Vendors */}
      <div className={CARD_CLASS}>
        <div className="space-y-0.5">
          <h2 className="text-card-title text-text font-semibold">Vendors</h2>
          <p className="text-xs text-muted">
            Add 2 or 3 vendors. PDF or DOCX · max 10 MB · max 30 pages each.
          </p>
        </div>

        {vendors.length === 0 && !addOpen && (
          <p className="text-sm text-muted">No vendors yet. Add at least 2 vendors to compare.</p>
        )}

        <div className="space-y-4">
          {vendors.map((vendor) => {
            const draft = vendorDrafts[vendor.id];
            const vendorError = vendorErrors[vendor.id];
            return (
              <div
                key={vendor.id}
                className="rounded-lg border border-border bg-surface/40 p-4 space-y-3"
              >
                <div className="flex items-start gap-3">
                  <div className="flex-1 space-y-1">
                    <label htmlFor={`vendor-name-${vendor.id}`} className="sr-only">
                      Vendor name
                    </label>
                    <Input
                      id={`vendor-name-${vendor.id}`}
                      value={draft ?? vendor.name}
                      disabled={controlsDisabled}
                      onChange={(e) => {
                        setVendorDrafts((prev) => ({ ...prev, [vendor.id]: e.target.value }));
                        setVendorErrors((prev) => ({ ...prev, [vendor.id]: '' }));
                      }}
                      onBlur={() => commitRename(vendor)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter') {
                          e.currentTarget.blur();
                        } else if (e.key === 'Escape') {
                          skipRenameRef.current = vendor.id;
                          setVendorDrafts((prev) => {
                            const copy = { ...prev };
                            delete copy[vendor.id];
                            return copy;
                          });
                          setVendorErrors((prev) => ({ ...prev, [vendor.id]: '' }));
                          e.currentTarget.blur();
                        }
                      }}
                      className={`h-9 font-medium ${
                        vendorError ? 'border-status-noncompliant-text' : ''
                      }`}
                    />
                    {vendorError && (
                      <p className="text-xs text-status-noncompliant-text">{vendorError}</p>
                    )}
                  </div>
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={controlsDisabled}
                    onClick={() => setVendorToRemove(vendor)}
                    aria-label={`Remove ${vendor.name}`}
                    className="shrink-0 h-9"
                  >
                    Remove
                  </Button>
                </div>

                <DocumentSlot
                  doc={proposalFor(vendor.id)}
                  error={slotErrors[vendor.id]}
                  uploading={Boolean(uploadingSlots[vendor.id])}
                  disabled={controlsDisabled}
                  note={slotNote(vendor.id)}
                  removeLabel={`Remove proposal for ${vendor.name}`}
                  onFileSelected={(file) => handleUploadFile(file, 'proposal', vendor.id)}
                  onRemove={() => {
                    const doc = proposalFor(vendor.id);
                    if (doc) setDocToDelete(doc);
                  }}
                  onDismissError={() => dismissSlotError(vendor.id)}
                />
              </div>
            );
          })}

          {addOpen && (
            <div className="rounded-lg border border-border bg-surface/40 p-4 space-y-2">
              <div className="flex items-start gap-3">
                <div className="flex-1 space-y-1">
                  <label htmlFor="new-vendor-name" className="sr-only">
                    New vendor name
                  </label>
                  <Input
                    id="new-vendor-name"
                    autoFocus
                    value={newVendorName}
                    placeholder="Vendor name"
                    disabled={addBusy}
                    onChange={(e) => {
                      setNewVendorName(e.target.value);
                      setAddError(null);
                    }}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') {
                        e.preventDefault();
                        submitAddVendor();
                      } else if (e.key === 'Escape') {
                        cancelAddVendor();
                      }
                    }}
                    className={`h-9 ${addError ? 'border-status-noncompliant-text' : ''}`}
                  />
                  {addError && <p className="text-xs text-status-noncompliant-text">{addError}</p>}
                </div>
                <Button
                  variant="primary"
                  size="sm"
                  onClick={submitAddVendor}
                  disabled={addBusy}
                  className="shrink-0 h-9"
                >
                  {addBusy ? 'Adding...' : 'Add'}
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={cancelAddVendor}
                  disabled={addBusy}
                  className="shrink-0 h-9"
                >
                  Cancel
                </Button>
              </div>
              <p className="text-xs text-muted">Upload the proposal once the vendor is added.</p>
            </div>
          )}
        </div>

        <div className="pt-1 flex items-center gap-3">
          <Button
            variant="outline"
            size="sm"
            onClick={handleClickAddVendor}
            disabled={atMaxVendors || controlsDisabled || addOpen}
            className="text-xs"
          >
            + Add vendor
          </Button>
          {atMaxVendors && <span className="text-xs text-muted">Maximum 3 vendors</span>}
        </div>
      </div>

      {/* Sticky actions */}
      <div className="sticky bottom-0 z-10 bg-background border-t border-border py-4 flex items-center justify-between gap-3">
        <div className="text-xs text-muted">{!jobActive && missingLine ? missingLine : null}</div>
        <Button
          variant="primary"
          disabled={!canExtract}
          onClick={handleClickExtract}
          className="font-semibold shrink-0"
        >
          {startingExtraction ? 'Starting...' : 'Extract requirements'}
        </Button>
      </div>

      <ConfirmDialog
        open={docToDelete !== null}
        title="Delete document"
        description={docToDelete ? `Removes ${docToDelete.filename}.` : ''}
        confirmLabel="Delete document"
        busy={confirmBusy}
        onConfirm={handleConfirmDeleteDocument}
        onCancel={() => setDocToDelete(null)}
      />

      <ConfirmDialog
        open={vendorToRemove !== null}
        title="Remove vendor"
        description={
          vendorToRemove ? (
            <>
              <span className="block">
                Removes {vendorToRemove.name}, their proposal and any results for them.
              </span>
              {isAnalysed && <span className="block mt-2">{OUT_OF_DATE_WARNING}</span>}
            </>
          ) : (
            ''
          )
        }
        confirmLabel="Remove vendor"
        busy={confirmBusy}
        onConfirm={handleConfirmRemoveVendor}
        onCancel={() => setVendorToRemove(null)}
      />

      <ConfirmDialog
        open={showAddWarning}
        title="Add vendor?"
        description={OUT_OF_DATE_WARNING}
        confirmLabel="Add vendor"
        destructive={false}
        onConfirm={() => {
          setShowAddWarning(false);
          setAddOpen(true);
        }}
        onCancel={() => setShowAddWarning(false)}
      />

      <RerunExtractionDialog
        open={rerunDialog !== null}
        hasEdits={rerunDialog?.hasEdits ?? false}
        busy={startingExtraction}
        onConfirm={handleConfirmRerun}
        onCancel={() => setRerunDialog(null)}
      />
    </div>
  );
};

export default DocumentsPage;
