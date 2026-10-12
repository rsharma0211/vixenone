import React from 'react';
import { Flag } from 'lucide-react';
import { cn } from '@/lib/utils';
import { FindingStatus } from '@/lib/mockData';

export interface FindingStatusBadgeProps {
  status: FindingStatus;
  needsReview?: boolean;
  inferred?: boolean;
  className?: string;
}

export const FindingStatusBadge: React.FC<FindingStatusBadgeProps> = ({
  status,
  needsReview,
  inferred,
  className,
}) => {
  if (needsReview) {
    return (
      <span
        className={cn(
          "inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium border border-status-review text-status-review bg-transparent select-none whitespace-nowrap",
          className
        )}
      >
        <Flag className="w-3 h-3 stroke-[2]" />
        <span>Needs review</span>
      </span>
    );
  }

  if (inferred) {
    return (
      <span
        className={cn(
          "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium border border-dashed border-status-notevidenced-text text-status-notevidenced-text bg-transparent italic select-none whitespace-nowrap",
          className
        )}
      >
        Inferred
      </span>
    );
  }

  const statusStyles: Record<FindingStatus, string> = {
    'Compliant': 'text-status-compliant-text bg-status-compliant-bg',
    'Partially compliant': 'text-status-partial-text bg-status-partial-bg',
    'Non-compliant': 'text-status-noncompliant-text bg-status-noncompliant-bg',
    'Not evidenced': 'text-status-notevidenced-text bg-status-notevidenced-bg',
  };

  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium select-none whitespace-nowrap",
        statusStyles[status] || statusStyles['Not evidenced'],
        className
      )}
    >
      {status}
    </span>
  );
};
