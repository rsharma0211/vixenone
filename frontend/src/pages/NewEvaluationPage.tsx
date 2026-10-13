import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { AlertCircle } from 'lucide-react';
import { apiClient, ApiValidationError } from '@/lib/api/client';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';

// Screen: S3 step 1 (Create evaluation). Vendors and files are managed on the Documents tab.

const CATEGORY_OPTIONS = ['Facilities / Housekeeping', 'Facilities / Security'];

export const NewEvaluationPage: React.FC = () => {
  const navigate = useNavigate();

  const [title, setTitle] = useState<string>('');
  const [category, setCategory] = useState<string>('');
  const [creating, setCreating] = useState<boolean>(false);
  const [pageError, setPageError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});

  const canCreate = !creating && Boolean(title.trim()) && Boolean(category.trim());

  const handleCreateEvaluation = async (event?: React.FormEvent) => {
    event?.preventDefault();
    if (!canCreate) return;

    try {
      setCreating(true);
      setPageError(null);
      setFieldErrors({});

      // Location is not sent: the api accepts it but neither stores nor returns it.
      const detail = await apiClient.createEvaluation({
        title: title.trim(),
        category,
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
            placeholder="e.g. Housekeeping Services — Main Office"
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
            value={category}
            onChange={(e) => {
              setCategory(e.target.value);
              setFieldErrors((prev) => ({ ...prev, category: '' }));
            }}
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

        <div className="pt-2 flex justify-end items-center gap-3 border-t border-border">
          <Button type="button" variant="outline" onClick={() => navigate('/evaluations')}>
            Cancel
          </Button>
          <Button type="submit" variant="primary" disabled={!canCreate} className="font-semibold">
            {creating ? 'Creating...' : 'Create evaluation'}
          </Button>
        </div>
      </form>
    </div>
  );
};

export default NewEvaluationPage;
