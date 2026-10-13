import React from 'react';
import { ConfirmDialog } from '@/components/ConfirmDialog';

export const RERUN_EXTRACTION_MESSAGE =
  'This re-reads all documents and replaces the requirement list. It takes about a minute.';
export const RERUN_EDITS_LOST_MESSAGE = 'Your edits will be lost.';

interface RerunExtractionDialogProps {
  open: boolean;
  /** True when any requirement row has origin "user" or the list has unsaved edits. */
  hasEdits: boolean;
  busy?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

/** Confirmation shown before every re-run of requirement extraction. */
export const RerunExtractionDialog: React.FC<RerunExtractionDialogProps> = ({
  open,
  hasEdits,
  busy,
  onConfirm,
  onCancel,
}) => (
  <ConfirmDialog
    open={open}
    title="Re-run extraction?"
    description={
      hasEdits
        ? `${RERUN_EXTRACTION_MESSAGE} ${RERUN_EDITS_LOST_MESSAGE}`
        : RERUN_EXTRACTION_MESSAGE
    }
    confirmLabel="Re-run extraction"
    destructive={hasEdits}
    busy={busy}
    onConfirm={onConfirm}
    onCancel={onCancel}
  />
);
