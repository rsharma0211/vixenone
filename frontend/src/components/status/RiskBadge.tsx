import React from 'react';
import {
  Ban,
  HelpCircle,
  Receipt,
  ArrowLeftRight,
  MinusCircle,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { RiskType, Severity } from '@/lib/mockData';

export interface RiskBadgeProps {
  type: RiskType;
  severity?: Severity;
  iconOnly?: boolean;
  className?: string;
}

const riskIcons: Record<RiskType, React.ElementType> = {
  'Exclusion': Ban,
  'Ambiguity': HelpCircle,
  'Unknown cost': Receipt,
  'Contradiction': ArrowLeftRight,
  'Omission': MinusCircle,
};

export const RiskBadge: React.FC<RiskBadgeProps> = ({
  type,
  severity,
  iconOnly = false,
  className,
}) => {
  const IconComponent = riskIcons[type] || HelpCircle;

  if (iconOnly) {
    return (
      <span
        title={severity ? `${type} (${severity} severity)` : type}
        className={cn("inline-flex items-center text-muted select-none", className)}
      >
        <IconComponent className="w-3.5 h-3.5" />
      </span>
    );
  }

  const severityDotColors: Record<Severity, string> = {
    'High': 'bg-severity-high',
    'Medium': 'bg-severity-medium',
    'Low': 'bg-severity-low',
  };

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium border border-border bg-surface text-text select-none whitespace-nowrap",
        className
      )}
    >
      <IconComponent className="w-3.5 h-3.5 text-muted shrink-0" />
      <span>{type}</span>
      {severity && (
        <span className="inline-flex items-center gap-1 ml-0.5 text-muted">
          <span
            className={cn(
              "w-1.5 h-1.5 rounded-full inline-block",
              severityDotColors[severity]
            )}
          />
          <span>{severity}</span>
        </span>
      )}
    </span>
  );
};
