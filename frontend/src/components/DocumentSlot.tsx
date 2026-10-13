import React, { useRef } from 'react';
import { FileText, UploadCloud, X } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { LifecycleStatus, LifecycleStatusType } from '@/components/status/LifecycleStatus';
import type { DocumentResponse, DocumentStatus } from '@/lib/types';

// Screen: S3 / S3-error document slot (requirements document and each vendor proposal)

export interface DocumentSlotError {
  label: string;
  detail: string;
  filename: string;
  sizeBytes: number;
}

interface DocumentSlotProps {
  doc?: DocumentResponse;
  error?: DocumentSlotError;
  uploading: boolean;
  disabled: boolean;
  /** Muted note under the slot, e.g. "Re-run extraction to update requirements." */
  note?: string | null;
  removeLabel: string;
  onFileSelected: (file: File) => void;
  onRemove: () => void;
  onDismissError: () => void;
}

const ACCEPT =
  '.pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document';

function mapDocumentStatusToLifecycle(status: DocumentStatus): LifecycleStatusType {
  switch (status) {
    case 'uploaded':
      return 'Uploaded';
    case 'extracting':
      return 'Reading';
    case 'ready':
      return 'Ready';
    case 'error':
      return 'Error';
  }
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024 * 1024) {
    return `${(bytes / 1024).toFixed(1)} KB`;
  }
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export const DocumentSlot: React.FC<DocumentSlotProps> = ({
  doc,
  error,
  uploading,
  disabled,
  note,
  removeLabel,
  onFileSelected,
  onRemove,
  onDismissError,
}) => {
  const inputRef = useRef<HTMLInputElement>(null);
  const openPicker = () => inputRef.current?.click();

  const replaceButton = (
    <Button
      variant="outline"
      size="sm"
      disabled={disabled}
      onClick={openPicker}
      className="h-7 px-2.5 text-xs"
    >
      Replace file
    </Button>
  );

  let body: React.ReactNode;
  let detail: string | null = null;

  if (uploading) {
    body = (
      <div className="rounded-lg border border-border bg-surface p-3.5 flex items-center justify-between text-sm">
        <div className="flex items-center gap-3">
          <FileText className="w-5 h-5 text-muted shrink-0" />
          <span className="text-text font-medium">Uploading document...</span>
        </div>
        <LifecycleStatus status="Processing" />
      </div>
    );
  } else if (error) {
    detail = error.detail;
    body = (
      <div className="rounded-lg border border-status-noncompliant-text/40 bg-status-noncompliant-bg/20 p-3.5 flex items-center justify-between gap-3">
        <div className="flex items-center gap-3 min-w-0">
          <FileText className="w-5 h-5 text-status-noncompliant-text shrink-0" />
          <div className="flex items-center gap-2 min-w-0">
            <span className="text-sm font-medium text-text truncate max-w-xs">{error.filename}</span>
            <span className="text-xs text-muted shrink-0">{formatFileSize(error.sizeBytes)}</span>
          </div>
        </div>
        <div className="flex items-center gap-3 shrink-0">
          <span className="inline-flex items-center gap-2 text-sm font-normal text-status-noncompliant-text select-none whitespace-nowrap">
            <span className="w-2 h-2 rounded-full bg-status-noncompliant-text inline-block shrink-0" />
            <span>{error.label}</span>
          </span>
          {replaceButton}
          <button
            type="button"
            disabled={disabled}
            onClick={onDismissError}
            aria-label="Dismiss error"
            className="p-1 text-muted hover:text-text rounded disabled:opacity-40 disabled:pointer-events-none"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      </div>
    );
  } else if (doc) {
    const isError = doc.status === 'error';
    if (isError && doc.error_message) detail = doc.error_message;
    body = (
      <div
        className={
          isError
            ? 'rounded-lg border border-status-noncompliant-text/40 bg-status-noncompliant-bg/20 p-3.5 flex items-center justify-between gap-3'
            : 'rounded-lg border border-border bg-surface p-3.5 flex items-center justify-between gap-3'
        }
      >
        <div className="flex items-center gap-3 min-w-0">
          <FileText
            className={`w-5 h-5 shrink-0 ${isError ? 'text-status-noncompliant-text' : 'text-muted'}`}
          />
          <div className="flex items-center gap-2 min-w-0">
            <span className="text-sm font-medium text-text truncate max-w-xs">{doc.filename}</span>
            <span className="text-xs text-muted shrink-0">
              {doc.page_count ? `${doc.page_count} pages · ` : ''}
              {formatFileSize(doc.size_bytes)}
            </span>
          </div>
        </div>
        <div className="flex items-center gap-3 shrink-0">
          <LifecycleStatus status={mapDocumentStatusToLifecycle(doc.status)} />
          {replaceButton}
          <button
            type="button"
            disabled={disabled}
            onClick={onRemove}
            aria-label={removeLabel}
            className="p-1 text-muted hover:text-status-noncompliant-text rounded transition-colors disabled:opacity-40 disabled:pointer-events-none"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      </div>
    );
  } else {
    body = (
      <button
        type="button"
        disabled={disabled}
        onClick={openPicker}
        className="w-full rounded-lg border border-dashed border-border p-6 flex flex-col items-center justify-center gap-2 hover:bg-surface/50 hover:border-slate-400 transition-colors cursor-pointer text-muted focus:outline-none focus:ring-1 focus:ring-ring disabled:opacity-50 disabled:pointer-events-none"
      >
        <div className="flex items-center gap-2 text-sm font-medium text-text">
          <UploadCloud className="w-5 h-5 text-muted" />
          <span>Drop file or browse</span>
        </div>
      </button>
    );
  }

  return (
    <div className="space-y-2">
      <input
        ref={inputRef}
        type="file"
        disabled={disabled}
        accept={ACCEPT}
        className="hidden"
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) onFileSelected(file);
          e.target.value = '';
        }}
      />
      {body}
      {detail && <p className="text-xs text-status-noncompliant-text pl-1">{detail}</p>}
      {note && <p className="text-xs text-muted pl-1">{note}</p>}
    </div>
  );
};

export default DocumentSlot;
