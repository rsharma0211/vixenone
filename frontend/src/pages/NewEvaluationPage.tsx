import React, { useEffect, useState } from 'react';
import { useNavigate, Link, useLocation, useParams, useSearchParams } from 'react-router-dom';
import { AlertCircle } from 'lucide-react';
import {
  apiClient,
  ApiValidationError,
  LocationResponse,
} from '@/lib/api/client';
import type { EvaluationDetailResponse } from '@/lib/types';
import { AddLocationDialog } from '@/components/AddLocationDialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';

// Screen: S3 step 1 (Create evaluation). Vendors and files are managed on the Documents tab.

export const STANDARD_CATEGORY_OPTIONS = [
  'Facilities / Housekeeping',
  'Facilities / Security',
];
export const OTHERS_OPTION = 'Others';
export const CATEGORY_OPTIONS = [...STANDARD_CATEGORY_OPTIONS, OTHERS_OPTION];
const ADD_NEW_LOCATION_VALUE = '__add_new_location__';

export function resolveCategory(savedCat?: string | null): {
  selectedOption: string;
  customText: string;
} {
  if (!savedCat || !savedCat.trim()) {
    return { selectedOption: '', customText: '' };
  }
  const trimmed = savedCat.trim();
  const matched = STANDARD_CATEGORY_OPTIONS.find(
    (opt) => opt.trim().toLowerCase() === trimmed.toLowerCase()
  );
  if (matched) {
    return { selectedOption: matched, customText: '' };
  }
  return { selectedOption: OTHERS_OPTION, customText: trimmed };
}

export interface NewEvaluationPageProps {
  initialEvaluation?: EvaluationDetailResponse | null;
  draft?: EvaluationDetailResponse | null;
  initialTitle?: string;
  initialCategory?: string;
  initialLocationId?: string | null;
}

export const NewEvaluationPage: React.FC<NewEvaluationPageProps> = ({
  initialEvaluation,
  draft,
  initialTitle,
  initialCategory,
  initialLocationId,
}) => {
  const navigate = useNavigate();
  const location = useLocation();
  const { id: routeEvalId } = useParams<{ id?: string }>();
  const [searchParams] = useSearchParams();

  const [evaluationId, setEvaluationId] = useState<string | null>(null);
  const [title, setTitle] = useState<string>('');
  const [selectedCategory, setSelectedCategory] = useState<string>('');
  const [customCategory, setCustomCategory] = useState<string>('');
  const [customCategoryError, setCustomCategoryError] = useState<string>('');
  const [locations, setLocations] = useState<LocationResponse[]>([]);
  const [selectedLocationId, setSelectedLocationId] = useState<string>('');
  const [previousLocationId, setPreviousLocationId] = useState<string>('');
  const [addLocationOpen, setAddLocationOpen] = useState<boolean>(false);

  const [creating, setCreating] = useState<boolean>(false);
  const [pageError, setPageError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});

  useEffect(() => {
    let active = true;
    apiClient
      .getCompany()
      .then((company) => {
        if (!active) return;
        const sorted = [...(company.locations ?? [])].sort(
          (a, b) => a.position - b.position
        );
        setLocations(sorted);
      })
      .catch(() => {
        // Location remains optional if loading company locations fails
      });
    return () => {
      active = false;
    };
  }, []);

  // Reopen draft or populate initial values
  useEffect(() => {
    if (initialEvaluation || draft) {
      const d = (initialEvaluation || draft)!;
      if (d.id) setEvaluationId(d.id);
      if (d.title) setTitle(d.title);
      if (d.category) {
        const { selectedOption, customText } = resolveCategory(d.category);
        setSelectedCategory(selectedOption);
        setCustomCategory(customText);
      }
      if (d.location?.id) setSelectedLocationId(d.location.id);
      return;
    }

    if (initialCategory) {
      const { selectedOption, customText } = resolveCategory(initialCategory);
      setSelectedCategory(selectedOption);
      setCustomCategory(customText);
      if (initialTitle) setTitle(initialTitle);
      if (initialLocationId) setSelectedLocationId(initialLocationId);
      return;
    }

    if (location.state) {
      const stateObj = location.state as {
        draft?: EvaluationDetailResponse & { location_id?: string | null };
        evaluation?: EvaluationDetailResponse & { location_id?: string | null };
        title?: string;
        category?: string;
        location_id?: string | null;
      };
      const d = stateObj.draft || stateObj.evaluation;
      if (d) {
        if (d.id) setEvaluationId(d.id);
        if (d.title) setTitle(d.title);
        if (d.category) {
          const { selectedOption, customText } = resolveCategory(d.category);
          setSelectedCategory(selectedOption);
          setCustomCategory(customText);
        }
        if (d.location?.id) setSelectedLocationId(d.location.id);
        else if (d.location_id) setSelectedLocationId(d.location_id);
        return;
      }
      if (stateObj.category) {
        const { selectedOption, customText } = resolveCategory(stateObj.category);
        setSelectedCategory(selectedOption);
        setCustomCategory(customText);
        if (stateObj.title) setTitle(stateObj.title);
        if (stateObj.location_id) setSelectedLocationId(stateObj.location_id);
        return;
      }
    }

    const targetId = routeEvalId || searchParams.get('id') || searchParams.get('draft_id');
    if (targetId) {
      let active = true;
      apiClient
        .getEvaluation(targetId)
        .then((detail) => {
          if (!active) return;
          setEvaluationId(detail.id);
          setTitle(detail.title);
          const { selectedOption, customText } = resolveCategory(detail.category);
          setSelectedCategory(selectedOption);
          setCustomCategory(customText);
          if (detail.location?.id) setSelectedLocationId(detail.location.id);
        })
        .catch(() => {
          // ignore error if draft not found
        });
      return () => {
        active = false;
      };
    }
  }, [
    initialEvaluation,
    draft,
    initialTitle,
    initialCategory,
    initialLocationId,
    location.state,
    routeEvalId,
    searchParams,
  ]);

  const validateCustomCategory = (val: string): string => {
    const trimmed = val.trim();
    if (!trimmed) {
      return 'Category is required';
    }
    if (trimmed.length > 60) {
      return 'Category cannot exceed 60 characters';
    }
    return '';
  };

  const handleCategoryChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const val = e.target.value;
    setSelectedCategory(val);
    setFieldErrors((prev) => ({ ...prev, category: '' }));
    if (val === OTHERS_OPTION) {
      setCustomCategoryError(validateCustomCategory(customCategory));
    } else {
      setCustomCategoryError('');
    }
  };

  const handleCustomCategoryChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = e.target.value;
    setCustomCategory(val);
    setFieldErrors((prev) => ({ ...prev, category: '' }));
    setCustomCategoryError(validateCustomCategory(val));
  };

  const handleCustomCategoryBlur = () => {
    setCustomCategoryError(validateCustomCategory(customCategory));
  };

  const isCustomCategoryValid =
    selectedCategory === OTHERS_OPTION
      ? customCategory.trim().length >= 1 && customCategory.trim().length <= 60
      : true;

  const canCreate =
    !creating &&
    Boolean(title.trim()) &&
    Boolean(selectedCategory) &&
    isCustomCategoryValid;

  const handleCreateEvaluation = async (event?: React.FormEvent) => {
    event?.preventDefault();
    if (!canCreate) {
      if (selectedCategory === OTHERS_OPTION) {
        setCustomCategoryError(validateCustomCategory(customCategory));
      }
      return;
    }

    const effectiveCategory =
      selectedCategory === OTHERS_OPTION
        ? customCategory.trim()
        : selectedCategory;

    try {
      setCreating(true);
      setPageError(null);
      setFieldErrors({});

      const detail = evaluationId
        ? await apiClient.updateEvaluation(evaluationId, {
            title: title.trim(),
            category: effectiveCategory,
            location_id: selectedLocationId ? selectedLocationId : null,
          })
        : await apiClient.createEvaluation({
            title: title.trim(),
            category: effectiveCategory,
            location_id: selectedLocationId ? selectedLocationId : null,
          });

      navigate(`/evaluations/${detail.id}/documents`, { replace: true });
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

  return (
    <div className="space-y-6 text-left max-w-[880px]">
      <div className="space-y-1">
        <nav className="flex items-center text-xs text-muted mb-2">
          <Link to="/evaluations" className="hover:text-text transition-colors">
            Evaluations
          </Link>
          <span className="mx-1.5">/</span>
          <span>New evaluation</span>
        </nav>
        <h1 className="text-page-title text-text font-semibold tracking-tight">New evaluation</h1>
        <p className="text-body text-muted">
          Name the evaluation first. You add vendors and upload documents on the next screen.
        </p>
      </div>

      {pageError && (
        <div
          role="alert"
          className="rounded-lg border border-status-noncompliant-text/30 bg-status-noncompliant-bg px-4 py-3 text-sm text-status-noncompliant-text flex items-center gap-2"
        >
          <AlertCircle className="w-4 h-4 shrink-0" />
          <span>{pageError}</span>
        </div>
      )}

      <form
        onSubmit={handleCreateEvaluation}
        className="rounded-lg border border-border bg-background p-6 space-y-4 shadow-sm"
      >
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
            placeholder="e.g. Housekeeping Services — FY 2026–27"
            className={fieldErrors.title ? 'border-status-noncompliant-text' : ''}
          />
          {fieldErrors.title && (
            <p className="text-xs text-status-noncompliant-text">{fieldErrors.title}</p>
          )}
        </div>

        <div className="space-y-1.5 sm:max-w-sm">
          <label htmlFor="eval-category" className="text-xs font-medium text-text block">
            Category
          </label>
          <select
            id="eval-category"
            value={selectedCategory}
            onChange={handleCategoryChange}
            className={`flex h-9 w-full rounded-lg border bg-background px-3 py-1 text-sm text-text focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring focus-visible:border-ring ${
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

        {selectedCategory === OTHERS_OPTION && (
          <div className="space-y-1.5 sm:max-w-sm">
            <label htmlFor="eval-custom-category" className="text-xs font-medium text-text block">
              Your category
            </label>
            <Input
              id="eval-custom-category"
              value={customCategory}
              onChange={handleCustomCategoryChange}
              onBlur={handleCustomCategoryBlur}
              placeholder="e.g. Pest control"
              className={customCategoryError ? 'border-status-noncompliant-text' : ''}
            />
            {customCategoryError && (
              <p className="text-xs text-status-noncompliant-text">{customCategoryError}</p>
            )}
          </div>
        )}

        <div className="space-y-1.5 sm:max-w-sm">
          <label htmlFor="eval-location" className="text-xs font-medium text-text block">
            Location
          </label>
          <select
            id="eval-location"
            value={selectedLocationId}
            onChange={(e) => {
              const val = e.target.value;
              if (val === ADD_NEW_LOCATION_VALUE) {
                setPreviousLocationId(selectedLocationId);
                setAddLocationOpen(true);
                return;
              }
              setSelectedLocationId(val);
              setFieldErrors((prev) => ({ ...prev, location_id: '' }));
            }}
            className={`flex h-9 w-full rounded-lg border bg-background px-3 py-1 text-sm text-text focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring focus-visible:border-ring ${
              fieldErrors.location_id ? 'border-status-noncompliant-text' : 'border-border'
            }`}
          >
            <option value="">No specific location</option>
            {locations.map((loc) => (
              <option key={loc.id} value={loc.id}>
                {loc.name}, {loc.city}
              </option>
            ))}
            <option value={ADD_NEW_LOCATION_VALUE}>+ Add new location</option>
          </select>
          {fieldErrors.location_id && (
            <p className="text-xs text-status-noncompliant-text">{fieldErrors.location_id}</p>
          )}
        </div>

        <div className="pt-2 flex justify-end items-center gap-3 border-t border-border">
          <Button type="button" variant="outline" onClick={() => navigate('/evaluations')}>
            Cancel
          </Button>
          <Button type="submit" variant="primary" disabled={!canCreate} className="font-semibold">
            {creating ? 'Creating...' : 'Create evaluation'}
          </Button>
        </div>
      </form>

      <AddLocationDialog
        open={addLocationOpen}
        onCreated={(created) => {
          setLocations((prev) => [...prev, created]);
          setSelectedLocationId(created.id);
          setFieldErrors((prev) => ({ ...prev, location_id: '' }));
          setAddLocationOpen(false);
        }}
        onCancel={() => {
          setSelectedLocationId(previousLocationId);
          setAddLocationOpen(false);
        }}
      />
    </div>
  );
};

export default NewEvaluationPage;
