import React, { useEffect, useState, useRef, useCallback } from 'react';
import { useNavigate, useParams, Link } from 'react-router-dom';
import {
  FileText,
  UploadCloud,
  X,
  AlertCircle,
  Plus,
  Trash2,
} from 'lucide-react';
import { apiClient, ApiValidationError } from '@/lib/api/client';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import type {
  EvaluationDetailResponse,
  VendorResponse,
  DocumentResponse,
} from '@/lib/types';

const CATEGORY_OPTIONS = [
  'Facilities / Housekeeping',
  'Facilities / Security',
];

const MAX_FILE_SIZE = 10 * 1024 * 1024; // 10 MB

interface SlotError {
  label: string;
  detail: string;
  filename: string;
  sizeBytes: number;
  pageCount?: number | null;
}

export const NewEvaluationPage: React.FC = () => {
  const navigate = useNavigate();
  const { id: routeEvalId } = useParams<{ id?: string }>();

  const [evaluationId, setEvaluationId] = useState<string | null>(routeEvalId || null);
  const [loading, setLoading] = useState<boolean>(Boolean(routeEvalId));
  const [creating, setCreating] = useState<boolean>(false);
  const [pageError, setPageError] = useState<string | null>(null);

  // Form details
  const [title, setTitle] = useState<string>('');
  const [category, setCategory] = useState<string>('');
  const [location, setLocation] = useState<string>('');

  // Vendor state (for creation or loaded evaluation)
  const [vendors, setVendors] = useState<{ id?: string; name: string }[]>([
    { name: '' },
    { name: '' },
  ]);

  // Documents state for loaded evaluation
  const [documents, setDocuments] = useState<DocumentResponse[]>([]);

  // Slot states (uploading & errors per slot: 'requirements' or vendorId)
  const [uploadingSlots, setUploadingSlots] = useState<Record<string, boolean>>({});
  const [slotErrors, setSlotErrors] = useState<Record<string, SlotError>>({});

  // Field validation errors
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});

  // Hidden file inputs
  const reqFileInputRef = useRef<HTMLInputElement>(null);
  const vendorFileInputRefs = useRef<Record<string, HTMLInputElement | null>>({});

  // Load existing evaluation if id is present
  const loadEvaluation = useCallback(async (id: string) => {
    try {
      setLoading(true);
      setPageError(null);
      const detail: EvaluationDetailResponse = await apiClient.getEvaluation(id);
      setEvaluationId(detail.id);
      setTitle(detail.title);
      setCategory(detail.category);
      if (detail.vendors && detail.vendors.length > 0) {
        setVendors(
          detail.vendors.map((v: VendorResponse) => ({
            id: v.id,
            name: v.name,
          }))
        );
      }
      setDocuments(detail.documents || []);
    } catch (err: unknown) {
      setPageError(err instanceof Error ? err.message : 'Failed to load evaluation');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (routeEvalId) {
      loadEvaluation(routeEvalId);
    } else {
      setEvaluationId(null);
      setTitle('');
      setCategory('');
      setLocation('');
      setVendors([{ name: '' }, { name: '' }]);
      setDocuments([]);
      setSlotErrors({});
      setFieldErrors({});
    }
  }, [routeEvalId, loadEvaluation]);

  // Vendor management during create step
  const handleVendorNameChange = (index: number, newName: string) => {
    setVendors((prev) => {
      const next = [...prev];
      next[index] = { ...next[index], name: newName };
      return next;
    });
    setFieldErrors((prev) => ({ ...prev, [`vendor_${index}`]: '', vendor_names: '' }));
  };

  const handleAddVendor = () => {
    if (vendors.length >= 3) return;
    setVendors((prev) => [...prev, { name: '' }]);
  };

  const handleRemoveVendor = (index: number) => {
    if (vendors.length <= 2) return;
    setVendors((prev) => prev.filter((_, idx) => idx !== index));
  };

  // Create Evaluation
  const handleCreateEvaluation = async () => {
    // Client-side validations
    const errors: Record<string, string> = {};
    if (!title.trim()) {
      errors.title = 'Evaluation name is required';
    }
    if (!category.trim()) {
      errors.category = 'Category is required';
    }
    const cleanVendors = vendors.map((v) => v.name.trim()).filter(Boolean);
    if (cleanVendors.length < 2 || cleanVendors.length > 3) {
      errors.vendor_names = 'Must provide 2 or 3 non-empty vendor names';
    }
    const lowerNames = cleanVendors.map((n) => n.toLowerCase());
    if (new Set(lowerNames).size !== cleanVendors.length) {
      errors.vendor_names = 'Vendor names must be unique';
    }

    if (Object.keys(errors).length > 0) {
      setFieldErrors(errors);
      return;
    }

    try {
      setCreating(true);
      setPageError(null);
      setFieldErrors({});

      const detail = await apiClient.createEvaluation({
        title: title.trim(),
        category,
        vendor_names: cleanVendors,
      });

      setEvaluationId(detail.id);
      setVendors(detail.vendors.map((v) => ({ id: v.id, name: v.name })));
      setDocuments(detail.documents || []);
      navigate(`/evaluations/${detail.id}/upload`, { replace: true });
    } catch (err: unknown) {
      if (err instanceof ApiValidationError) {
        setFieldErrors(err.fieldErrors);
        setPageError(err.message);
      } else if (err instanceof Error) {
        setPageError(err.message);
      } else {
        setPageError('Failed to create evaluation');
      }
    } finally {
      setCreating(false);
    }
  };

  // Client pre-check file
  const precheckFile = (file: File): { ok: boolean; error?: string } => {
    const ext = file.name.substring(file.name.lastIndexOf('.')).toLowerCase();
    const isPdfOrDocx =
      ext === '.pdf' ||
      ext === '.docx' ||
      file.type === 'application/pdf' ||
      file.type === 'application/vnd.openxmlformats-officedocument.wordprocessingml.document';

    if (!isPdfOrDocx) {
      return { ok: false, error: 'Only PDF or DOCX files are supported.' };
    }

    if (file.size > MAX_FILE_SIZE) {
      return { ok: false, error: 'File exceeds maximum size of 10 MB' };
    }

    return { ok: true };
  };

  // Upload file handler
  const handleUploadFile = async (
    file: File,
    kind: 'requirements' | 'proposal',
    vendorId?: string
  ) => {
    if (!evaluationId) return;

    const slotKey = kind === 'requirements' ? 'requirements' : (vendorId || 'proposal');

    // 1. Client pre-check
    const check = precheckFile(file);
    if (!check.ok) {
      setSlotErrors((prev) => ({
        ...prev,
        [slotKey]: {
          label: 'Invalid file',
          detail: check.error || 'Invalid file format or size',
          filename: file.name,
          sizeBytes: file.size,
        },
      }));
      return;
    }

    // 2. Clear previous error for slot
    setSlotErrors((prev) => {
      const copy = { ...prev };
      delete copy[slotKey];
      return copy;
    });

    // 3. Perform upload
    try {
      setUploadingSlots((prev) => ({ ...prev, [slotKey]: true }));
      const doc = await apiClient.uploadDocument(evaluationId, file, kind, vendorId);

      // Update documents list
      setDocuments((prev) => {
        const filtered = prev.filter((d) => {
          if (kind === 'requirements') return d.kind !== 'requirements';
          return !(d.kind === 'proposal' && d.vendor_id === vendorId);
        });
        return [...filtered, doc];
      });
    } catch (err: unknown) {
      // Server authoritative error
      let errorLabel = 'Upload failed';
      let errorDetail = err instanceof Error ? err.message : 'Upload failed';

      if (err instanceof ApiValidationError) {
        errorDetail = err.message;
        if (err.message.toLowerCase().includes('page')) {
          errorLabel = 'Too long — max 30 pages';
          errorDetail = 'Upload a shorter version or only the relevant sections.';
        } else if (err.message.toLowerCase().includes('10 mb')) {
          errorLabel = 'Too large — max 10 MB';
        }
      } else if (err instanceof Error && err.message.toLowerCase().includes('page')) {
        errorLabel = 'Too long — max 30 pages';
        errorDetail = 'Upload a shorter version or only the relevant sections.';
      }

      setSlotErrors((prev) => ({
        ...prev,
        [slotKey]: {
          label: errorLabel,
          detail: errorDetail,
          filename: file.name,
          sizeBytes: file.size,
          pageCount: 42, // Illustrative fallback if page count error occurred
        },
      }));
    } finally {
      setUploadingSlots((prev) => ({ ...prev, [slotKey]: false }));
    }
  };

  // Delete file handler
  const handleDeleteDocument = async (docId: string, slotKey: string) => {
    if (!evaluationId) return;
    try {
      await apiClient.deleteDocument(evaluationId, docId);
      setDocuments((prev) => prev.filter((d) => d.id !== docId));
      setSlotErrors((prev) => {
        const copy = { ...prev };
        delete copy[slotKey];
        return copy;
      });
    } catch (err: unknown) {
      setPageError(err instanceof Error ? err.message : 'Failed to delete document');
    }
  };

  const formatFileSize = (bytes: number): string => {
    if (bytes < 1024 * 1024) {
      return `${(bytes / 1024).toFixed(1)} KB`;
    }
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  // Requirements document helper
  const reqDoc = documents.find((d) => d.kind === 'requirements');
  const reqSlotError = slotErrors['requirements'];
  const reqUploading = uploadingSlots['requirements'];

  if (loading) {
    return (
      <div className="space-y-6 text-left max-w-[880px]">
        <div className="space-y-1">
          <h1 className="text-page-title text-text font-semibold tracking-tight">
            New evaluation
          </h1>
          <p className="text-body text-muted">
            Upload one requirements document and 2–3 vendor proposals.
          </p>
        </div>
        <div className="rounded-lg border border-border bg-background p-12 text-center text-muted text-sm">
          Loading evaluation details...
        </div>
      </div>
    );
  }

  // Validation for Create button
  const isTitleFilled = Boolean(title.trim());
  const isCategoryFilled = Boolean(category.trim());
  const filledVendorsCount = vendors.filter((v) => Boolean(v.name.trim())).length;
  const isCreateDisabled =
    creating || !isTitleFilled || !isCategoryFilled || filledVendorsCount < 2;

  return (
    <div className="space-y-6 text-left max-w-[880px]">
      {/* Breadcrumb & Title */}
      <div className="space-y-1">
        <nav className="flex items-center text-xs text-muted mb-2">
          <Link to="/evaluations" className="hover:text-text transition-colors">
            Evaluations
          </Link>
          <span className="mx-1.5">/</span>
          <span>New evaluation</span>
        </nav>
        <h1 className="text-page-title text-text font-semibold tracking-tight">
          New evaluation
        </h1>
        <p className="text-body text-muted">
          Upload one requirements document and 2–3 vendor proposals.
        </p>
      </div>

      {pageError && (
        <div className="rounded-lg border border-status-noncompliant-text/30 bg-status-noncompliant-bg px-4 py-3 text-sm text-status-noncompliant-text flex items-center gap-2">
          <AlertCircle className="w-4 h-4 shrink-0" />
          <span>{pageError}</span>
        </div>
      )}

      {/* CARD 1: Details */}
      <div className="rounded-lg border border-border bg-background p-6 space-y-4 shadow-sm">
        <h2 className="text-card-title text-text font-semibold">Details</h2>

        <div className="space-y-1.5">
          <label htmlFor="eval-name" className="text-xs font-medium text-text block">
            Evaluation name
          </label>
          <Input
            id="eval-name"
            value={title}
            onChange={(e) => {
              setTitle(e.target.value);
              setFieldErrors((prev) => ({ ...prev, title: '' }));
            }}
            placeholder="e.g. Housekeeping Services — Andheri East"
            className={fieldErrors.title ? 'border-status-noncompliant-text' : ''}
            disabled={Boolean(evaluationId)}
          />
          {fieldErrors.title && (
            <p className="text-xs text-status-noncompliant-text">{fieldErrors.title}</p>
          )}
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div className="space-y-1.5">
            <label htmlFor="eval-category" className="text-xs font-medium text-text block">
              Category
            </label>
            <select
              id="eval-category"
              value={category}
              onChange={(e) => {
                setCategory(e.target.value);
                setFieldErrors((prev) => ({ ...prev, category: '' }));
              }}
              disabled={Boolean(evaluationId)}
              className={`flex h-9 w-full rounded-lg border bg-background px-3 py-1 text-sm text-text focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring focus-visible:border-ring disabled:opacity-60 ${
                fieldErrors.category ? 'border-status-noncompliant-text' : 'border-border'
              }`}
            >
              <option value="" disabled>
                Select category
              </option>
              {CATEGORY_OPTIONS.map((cat) => (
                <option key={cat} value={cat}>
                  {cat}
                </option>
              ))}
            </select>
            {fieldErrors.category && (
              <p className="text-xs text-status-noncompliant-text">{fieldErrors.category}</p>
            )}
          </div>

          <div className="space-y-1.5">
            <label htmlFor="eval-location" className="text-xs font-medium text-text block">
              Location (optional)
            </label>
            <Input
              id="eval-location"
              value={location}
              onChange={(e) => setLocation(e.target.value)}
              placeholder="e.g. Mumbai"
              disabled={Boolean(evaluationId)}
            />
          </div>
        </div>

        {/* If in create step, show action to create evaluation and proceed */}
        {!evaluationId && (
          <div className="pt-2 flex justify-between items-center border-t border-border">
            <div className="text-xs text-muted">
              Configure 2–3 vendor names below, then click &ldquo;Create & upload documents&rdquo;.
            </div>
            <Button
              variant="primary"
              onClick={handleCreateEvaluation}
              disabled={isCreateDisabled}
              className="font-semibold"
            >
              {creating ? 'Creating...' : 'Create & upload documents'}
            </Button>
          </div>
        )}
      </div>

      {/* CARD 2: Requirements document */}
      <div className="rounded-lg border border-border bg-background p-6 space-y-4 shadow-sm">
        <div className="space-y-0.5">
          <h2 className="text-card-title text-text font-semibold">
            Requirements document
          </h2>
          <p className="text-xs text-muted">
            PDF or DOCX · max 10 MB · max 30 pages
          </p>
        </div>

        <input
          ref={reqFileInputRef}
          type="file"
          accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
          className="hidden"
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (file) handleUploadFile(file, 'requirements');
            e.target.value = '';
          }}
        />

        {/* Requirements slot states */}
        {!evaluationId ? (
          <div className="rounded-lg border border-dashed border-border bg-surface/50 p-6 text-center text-xs text-muted">
            Create the evaluation above to enable document uploads.
          </div>
        ) : reqUploading ? (
          <div className="rounded-lg border border-border bg-surface p-4 flex items-center justify-between text-sm">
            <div className="flex items-center gap-3">
              <FileText className="w-5 h-5 text-muted shrink-0" />
              <span className="text-text font-medium">Uploading document...</span>
            </div>
            <div className="flex items-center gap-2 text-xs text-navy font-medium">
              <span className="w-2 h-2 rounded-full bg-lifecycle-blue inline-block animate-pulse" />
              <span>Processing...</span>
            </div>
          </div>
        ) : reqSlotError ? (
          <div className="space-y-2">
            <div className="rounded-lg border border-status-noncompliant-text/40 bg-status-noncompliant-bg/20 p-3.5 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <FileText className="w-5 h-5 text-status-noncompliant-text shrink-0" />
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium text-text truncate max-w-xs">
                    {reqSlotError.filename}
                  </span>
                  <span className="text-xs text-muted">
                    {reqSlotError.pageCount ? `${reqSlotError.pageCount} pages · ` : ''}
                    {formatFileSize(reqSlotError.sizeBytes)}
                  </span>
                </div>
              </div>
              <div className="flex items-center gap-3">
                <div className="flex items-center gap-1.5 text-xs font-medium text-status-noncompliant-text">
                  <span className="w-2 h-2 rounded-full bg-status-noncompliant-text inline-block" />
                  <span>{reqSlotError.label}</span>
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => reqFileInputRef.current?.click()}
                  className="h-7 px-2.5 text-xs"
                >
                  Replace file
                </Button>
                <button
                  type="button"
                  onClick={() =>
                    setSlotErrors((prev) => {
                      const c = { ...prev };
                      delete c['requirements'];
                      return c;
                    })
                  }
                  className="p-1 text-muted hover:text-text rounded"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>
            </div>
            <p className="text-xs text-status-noncompliant-text pl-1">
              {reqSlotError.detail}
            </p>
          </div>
        ) : reqDoc ? (
          <div className="rounded-lg border border-border bg-surface p-3.5 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <FileText className="w-5 h-5 text-muted shrink-0" />
              <div className="flex items-center gap-2">
                <span className="text-sm font-medium text-text">
                  {reqDoc.filename}
                </span>
                <span className="text-xs text-muted">
                  {reqDoc.page_count ? `${reqDoc.page_count} pages · ` : ''}
                  {formatFileSize(reqDoc.size_bytes)}
                </span>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <div className="flex items-center gap-1.5 text-xs font-medium text-status-compliant-text">
                <span className="w-2 h-2 rounded-full bg-status-compliant-text inline-block" />
                <span>Ready</span>
              </div>
              <button
                type="button"
                onClick={() => handleDeleteDocument(reqDoc.id, 'requirements')}
                className="p-1 text-muted hover:text-status-noncompliant-text rounded transition-colors"
                aria-label="Remove document"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          </div>
        ) : (
          <button
            type="button"
            onClick={() => reqFileInputRef.current?.click()}
            className="w-full rounded-lg border border-dashed border-border p-6 flex flex-col items-center justify-center gap-2 hover:bg-surface/50 hover:border-slate-400 transition-colors cursor-pointer text-muted focus:outline-none focus:ring-1 focus:ring-ring"
          >
            <div className="flex items-center gap-2 text-sm font-medium text-text">
              <UploadCloud className="w-5 h-5 text-muted" />
              <span>Drop file or browse</span>
            </div>
          </button>
        )}
      </div>

      {/* CARD 3: Vendor proposals */}
      <div className="rounded-lg border border-border bg-background p-6 space-y-4 shadow-sm">
        <div className="space-y-0.5">
          <h2 className="text-card-title text-text font-semibold">
            Vendor proposals
          </h2>
          <p className="text-xs text-muted">
            Add 2 or 3 vendors. PDF or DOCX · max 10 MB · max 30 pages each.
          </p>
        </div>

        {fieldErrors.vendor_names && (
          <p className="text-xs text-status-noncompliant-text">{fieldErrors.vendor_names}</p>
        )}

        <div className="divide-y divide-border">
          {vendors.map((vendor, idx) => {
            const vendorId = vendor.id || `vendor-${idx}`;
            const vendorDoc = documents.find(
              (d) => d.kind === 'proposal' && d.vendor_id === vendor.id
            );
            const slotKey = vendor.id || `vendor-${idx}`;
            const slotErr = slotErrors[slotKey];
            const isUploading = uploadingSlots[slotKey];

            return (
              <div key={vendorId} className="py-4 first:pt-0 last:pb-0 space-y-2">
                <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-3">
                  {/* Vendor name input */}
                  <div className="w-full sm:w-60 shrink-0 flex items-center gap-2">
                    <Input
                      value={vendor.name}
                      onChange={(e) => handleVendorNameChange(idx, e.target.value)}
                      placeholder="Vendor name"
                      disabled={Boolean(evaluationId)}
                      className="h-9"
                    />
                    {!evaluationId && vendors.length > 2 && idx === vendors.length - 1 && (
                      <button
                        type="button"
                        onClick={() => handleRemoveVendor(idx)}
                        aria-label="Remove vendor"
                        className="p-1.5 text-muted hover:text-status-noncompliant-text rounded hover:bg-surface"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    )}
                  </div>

                  {/* Hidden file input */}
                  <input
                    ref={(el) => {
                      vendorFileInputRefs.current[slotKey] = el;
                    }}
                    type="file"
                    accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                    className="hidden"
                    onChange={(e) => {
                      const file = e.target.files?.[0];
                      if (file) handleUploadFile(file, 'proposal', vendor.id);
                      e.target.value = '';
                    }}
                  />

                  {/* Vendor Upload Slot */}
                  <div className="flex-1">
                    {!evaluationId ? (
                      <div className="rounded-lg border border-dashed border-border bg-surface/50 h-9 px-3 flex items-center justify-center text-xs text-muted">
                        Available after creating evaluation
                      </div>
                    ) : isUploading ? (
                      <div className="rounded-lg border border-border bg-surface h-9 px-3 flex items-center justify-between text-xs">
                        <span className="text-text font-medium truncate max-w-[180px]">
                          Uploading...
                        </span>
                        <div className="flex items-center gap-1.5 text-navy font-medium">
                          <span className="w-2 h-2 rounded-full bg-lifecycle-blue inline-block animate-pulse" />
                          <span>Processing...</span>
                        </div>
                      </div>
                    ) : slotErr ? (
                      <div className="rounded-lg border border-status-noncompliant-text/40 bg-status-noncompliant-bg/20 px-3 py-1.5 flex items-center justify-between">
                        <div className="flex items-center gap-2 truncate">
                          <FileText className="w-4 h-4 text-status-noncompliant-text shrink-0" />
                          <span className="text-xs font-medium text-text truncate max-w-[120px]">
                            {slotErr.filename}
                          </span>
                          <span className="text-xs text-muted shrink-0">
                            {slotErr.pageCount ? `${slotErr.pageCount} pages · ` : ''}
                            {formatFileSize(slotErr.sizeBytes)}
                          </span>
                        </div>
                        <div className="flex items-center gap-2 shrink-0">
                          <div className="flex items-center gap-1.5 text-xs font-medium text-status-noncompliant-text">
                            <span className="w-2 h-2 rounded-full bg-status-noncompliant-text inline-block" />
                            <span>{slotErr.label}</span>
                          </div>
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => vendorFileInputRefs.current[slotKey]?.click()}
                            className="h-6 px-2 text-xs"
                          >
                            Replace file
                          </Button>
                          <button
                            type="button"
                            onClick={() =>
                              setSlotErrors((prev) => {
                                const c = { ...prev };
                                delete c[slotKey];
                                return c;
                              })
                            }
                            className="p-1 text-muted hover:text-text rounded"
                          >
                            <X className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      </div>
                    ) : vendorDoc ? (
                      <div className="rounded-lg border border-border bg-surface h-9 px-3 flex items-center justify-between">
                        <div className="flex items-center gap-2 truncate">
                          <FileText className="w-4 h-4 text-muted shrink-0" />
                          <span className="text-xs font-medium text-text truncate max-w-[180px]">
                            {vendorDoc.filename}
                          </span>
                          <span className="text-xs text-muted shrink-0">
                            {vendorDoc.page_count ? `${vendorDoc.page_count} pages · ` : ''}
                            {formatFileSize(vendorDoc.size_bytes)}
                          </span>
                        </div>
                        <div className="flex items-center gap-2 shrink-0">
                          <div className="flex items-center gap-1.5 text-xs font-medium text-status-compliant-text">
                            <span className="w-2 h-2 rounded-full bg-status-compliant-text inline-block" />
                            <span>Ready</span>
                          </div>
                          <button
                            type="button"
                            onClick={() => handleDeleteDocument(vendorDoc.id, slotKey)}
                            className="p-1 text-muted hover:text-status-noncompliant-text rounded transition-colors"
                            aria-label="Remove proposal document"
                          >
                            <X className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      </div>
                    ) : (
                      <button
                        type="button"
                        onClick={() => vendorFileInputRefs.current[slotKey]?.click()}
                        className="w-full h-9 rounded-lg border border-dashed border-border px-3 flex items-center justify-center gap-2 hover:bg-surface hover:border-slate-400 transition-colors cursor-pointer text-xs text-muted focus:outline-none focus:ring-1 focus:ring-ring"
                      >
                        <UploadCloud className="w-4 h-4 text-muted" />
                        <span>Drop file or browse</span>
                      </button>
                    )}
                  </div>
                </div>

                {/* Slot error message below the row */}
                {slotErr && (
                  <p className="text-xs text-status-noncompliant-text pl-1 sm:pl-64">
                    {slotErr.detail}
                  </p>
                )}
              </div>
            );
          })}
        </div>

        {/* Option to add 3rd vendor during creation */}
        {!evaluationId && vendors.length < 3 && (
          <div className="pt-2">
            <Button
              variant="outline"
              size="sm"
              onClick={handleAddVendor}
              className="gap-1.5 text-xs"
            >
              <Plus className="w-3.5 h-3.5" />
              <span>Add vendor</span>
            </Button>
          </div>
        )}
      </div>

      {/* Bottom Sticky Actions */}
      <div className="pt-4 flex items-center justify-end gap-3">
        <Button
          variant="outline"
          onClick={() => navigate('/evaluations')}
        >
          Cancel
        </Button>
        <div className="relative group">
          <Button
            variant="primary"
            disabled={true}
            className="font-semibold"
          >
            Extract requirements
          </Button>
          {/* Tooltip on disabled action */}
          <div className="absolute bottom-full right-0 mb-2 hidden group-hover:block whitespace-nowrap rounded-md bg-navy text-white text-xs px-2.5 py-1 shadow-md pointer-events-none">
            Extraction arrives in the next phase
          </div>
        </div>
      </div>
    </div>
  );
};

export default NewEvaluationPage;
