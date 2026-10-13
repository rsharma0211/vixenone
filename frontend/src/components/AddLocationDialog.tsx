import React, { useEffect, useState } from 'react';
import { AlertCircle } from 'lucide-react';
import { apiClient, ApiValidationError, LocationResponse } from '@/lib/api/client';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';

export interface AddLocationDialogProps {
  open: boolean;
  onCreated: (location: LocationResponse) => void;
  onCancel: () => void;
}

export const AddLocationDialog: React.FC<AddLocationDialogProps> = ({
  open,
  onCreated,
  onCancel,
}) => {
  const [name, setName] = useState<string>('');
  const [city, setCity] = useState<string>('');
  const [submitting, setSubmitting] = useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});

  useEffect(() => {
    if (open) {
      setName('');
      setCity('');
      setSubmitting(false);
      setErrorMessage(null);
      setFieldErrors({});
    }
  }, [open]);

  const canSubmit = !submitting && Boolean(name.trim()) && Boolean(city.trim());

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    event.stopPropagation();
    if (!canSubmit) return;

    try {
      setSubmitting(true);
      setErrorMessage(null);
      setFieldErrors({});

      const created = await apiClient.addLocation({
        name: name.trim(),
        city: city.trim(),
      });

      onCreated(created);
    } catch (err: unknown) {
      if (err instanceof ApiValidationError) {
        setFieldErrors(err.fieldErrors);
        setErrorMessage(err.message);
      } else if (err instanceof Error) {
        setErrorMessage(err.message);
      } else {
        setErrorMessage('Failed to add location');
      }
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (!next && !submitting) {
          onCancel();
        }
      }}
    >
      <DialogContent onInteractOutside={(e) => e.preventDefault()}>
        <DialogHeader>
          <DialogTitle>Add new location</DialogTitle>
          <DialogDescription>
            Add a company operating site with its name and city.
          </DialogDescription>
        </DialogHeader>

        {errorMessage && (
          <div
            role="alert"
            className="rounded-lg border border-status-noncompliant-text/30 bg-status-noncompliant-bg px-3 py-2 text-xs text-status-noncompliant-text flex items-center gap-2"
          >
            <AlertCircle className="w-4 h-4 shrink-0" />
            <span>{errorMessage}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-1.5">
            <label htmlFor="add-location-name" className="text-xs font-medium text-text block">
              Name
            </label>
            <Input
              id="add-location-name"
              autoFocus
              value={name}
              disabled={submitting}
              maxLength={80}
              placeholder="Location name"
              onChange={(e) => {
                setName(e.target.value);
                setErrorMessage(null);
                setFieldErrors((prev) => ({ ...prev, name: '' }));
              }}
              className={fieldErrors.name ? 'border-status-noncompliant-text' : ''}
            />
            {fieldErrors.name && (
              <p className="text-xs text-status-noncompliant-text">{fieldErrors.name}</p>
            )}
          </div>

          <div className="space-y-1.5">
            <label htmlFor="add-location-city" className="text-xs font-medium text-text block">
              City
            </label>
            <Input
              id="add-location-city"
              value={city}
              disabled={submitting}
              maxLength={80}
              placeholder="City"
              onChange={(e) => {
                setCity(e.target.value);
                setErrorMessage(null);
                setFieldErrors((prev) => ({ ...prev, city: '' }));
              }}
              className={fieldErrors.city ? 'border-status-noncompliant-text' : ''}
            />
            {fieldErrors.city && (
              <p className="text-xs text-status-noncompliant-text">{fieldErrors.city}</p>
            )}
          </div>

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={onCancel}
              disabled={submitting}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              variant="primary"
              disabled={!canSubmit}
              className="font-semibold"
            >
              {submitting ? 'Adding...' : 'Add location'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
};

export default AddLocationDialog;
