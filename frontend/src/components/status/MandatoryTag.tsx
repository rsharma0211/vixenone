import React from 'react';
import { cn } from '@/lib/utils';

export interface MandatoryTagProps {
  className?: string;
}

export const MandatoryTag: React.FC<MandatoryTagProps> = ({ className }) => {
  return (
    <span
      className={cn(
        "rounded bg-muted-surface text-muted text-xs font-medium px-1.5 py-0.5 inline-flex items-center select-none whitespace-nowrap",
        className
      )}
    >
      Mandatory
    </span>
  );
};
