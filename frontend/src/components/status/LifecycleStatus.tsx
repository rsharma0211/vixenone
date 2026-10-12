import React from 'react';
import { RefreshCw } from 'lucide-react';
import { cn } from '@/lib/utils';
export type LifecycleStatusType =
  | 'Draft'
  | 'Requirements review'
  | 'Analysed'
  | 'Stale'
  | 'Ready'
  | 'Processing'
  | 'Error';

export interface LifecycleStatusProps {
  status: LifecycleStatusType;
  className?: string;
}

export const LifecycleStatus: React.FC<LifecycleStatusProps> = ({
  status,
  className,
}) => {
  if (status === 'Stale') {
    return (
      <span
        className={cn(
          "inline-flex items-center gap-1.5 text-sm font-normal text-text select-none whitespace-nowrap",
          className
        )}
      >
        <span className="w-2 h-2 rounded-full bg-status-partial-text inline-block shrink-0" />
        <RefreshCw className="w-3.5 h-3.5 text-status-partial-text shrink-0" />
        <span>Stale — re-run needed</span>
      </span>
    );
  }

  const dotColors: Record<LifecycleStatusType, string> = {
    'Draft': 'bg-muted',
    'Requirements review': 'bg-lifecycle-blue',
    'Analysed': 'bg-status-compliant-text',
    'Stale': 'bg-status-partial-text',
    'Ready': 'bg-status-compliant-text',
    'Processing': 'bg-lifecycle-blue',
    'Error': 'bg-status-noncompliant-text',
  };

  return (
    <span
      className={cn(
        "inline-flex items-center gap-2 text-sm font-normal text-text select-none whitespace-nowrap",
        className
      )}
    >
      <span
        className={cn(
          "w-2 h-2 rounded-full inline-block shrink-0",
          dotColors[status] || 'bg-muted'
        )}
      />
      <span>{status}</span>
    </span>
  );
};
