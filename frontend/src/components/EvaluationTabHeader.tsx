import React from 'react';
import { cn } from '@/lib/utils';

export interface EvaluationTabHeaderProps {
  title: React.ReactNode;
  counts?: React.ReactNode;
  actions?: React.ReactNode;
  className?: string;
  children?: React.ReactNode;
}

export const EvaluationTabHeader: React.FC<EvaluationTabHeaderProps> = ({
  title,
  counts,
  actions,
  className,
  children,
}) => {
  const actionContent = actions ?? children;

  return (
    <div
      className={cn(
        'flex flex-wrap items-center justify-between gap-3 pt-1',
        className
      )}
    >
      {/* Left zone: tab title + counts on one line; the counts never wrap mid-phrase */}
      <div className="flex items-baseline gap-2.5 shrink-0 whitespace-nowrap">
        <h2 className="text-section-title text-text font-semibold">
          {title}
        </h2>
        {counts !== undefined && counts !== null && (
          <span className="text-sm text-muted whitespace-nowrap">
            {counts}
          </span>
        )}
      </div>

      {/* Right zone: all action buttons as one group, order unchanged, primary action last */}
      {actionContent && (
        <div className="flex items-center gap-2.5 shrink-0 max-w-full overflow-x-auto">
          {actionContent}
        </div>
      )}
    </div>
  );
};

export default EvaluationTabHeader;
