import React from 'react';
import { KpiTile } from '@/components/KpiTile';
import { KPI_HELP_TEXT } from '@/lib/kpiHelp';
import { formatINR } from '@/lib/format';
import { cn } from '@/lib/utils';
import type { VendorResultItem } from '@/lib/types';

export interface VendorSummaryCardsProps {
  vendors: VendorResultItem[];
  className?: string;
}

export const VendorSummaryCards: React.FC<VendorSummaryCardsProps> = ({
  vendors,
  className,
}) => {
  return (
    <div className={cn('grid grid-cols-1 xl:grid-cols-3 gap-4 min-w-0', className)}>
      {vendors.map((v) => {
        const total = v.mandatory_total;
        const met = v.mandatory_met;
        const failures = v.mandatory_failures;

        let mandatoryAccent: 'compliant' | 'noncompliant' | 'partial';
        let mandatorySubtext: string;

        if (failures === 0 && met === total) {
          mandatoryAccent = 'compliant';
          mandatorySubtext = 'All met';
        } else if (failures >= 1) {
          mandatoryAccent = 'noncompliant';
          mandatorySubtext = `${failures} failure${failures === 1 ? '' : 's'}`;
        } else {
          const toCheck = Math.max(0, total - met - failures);
          mandatoryAccent = 'partial';
          mandatorySubtext = `${toCheck} to check`;
        }

        const isCostNull =
          v.monthly_total_inr === null || v.monthly_total_inr === undefined;

        return (
          <div
            key={v.id}
            className="rounded-lg border border-border bg-background p-4 space-y-3.5 min-w-0"
          >
            <div className="border-b border-border pb-2 flex items-center justify-between min-w-0">
              <h3 className="font-semibold text-sm text-text truncate" title={v.name}>
                {v.name}
              </h3>
              {v.tag && (
                <span className="rounded bg-muted-surface text-muted text-[11px] font-medium px-2 py-0.5 shrink-0 ml-2">
                  {v.tag}
                </span>
              )}
            </div>
            <div className="flex flex-wrap gap-2 min-w-0">
              <KpiTile
                label="Vendor score"
                value={
                  v.score !== null && v.score !== undefined ? String(v.score) : '—'
                }
                helpText={KPI_HELP_TEXT.vendor_score}
                className="flex-1 min-w-[110px]"
              />
              <KpiTile
                label="Mandatory met"
                value={`${met} / ${total}`}
                subtext={mandatorySubtext}
                statusAccent={mandatoryAccent}
                helpText={KPI_HELP_TEXT.mandatory_met}
                className="flex-1 min-w-[110px]"
              />
              <KpiTile
                label="Monthly cost"
                value={isCostNull ? 'Not stated' : formatINR(v.monthly_total_inr)}
                statusAccent={isCostNull ? 'partial' : undefined}
                helpText={KPI_HELP_TEXT.monthly_cost}
                className="flex-1 min-w-[110px]"
              />
            </div>
          </div>
        );
      })}
    </div>
  );
};

export default VendorSummaryCards;
