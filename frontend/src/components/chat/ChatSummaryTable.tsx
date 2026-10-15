import React from 'react';
import { cn } from '@/lib/utils';
import type { ChatSummary } from '@/lib/types';

interface ChatSummaryTableProps {
  summary: ChatSummary;
  onNavigate: (tab: 'comparison' | 'recommendation' | 'print') => void;
}

export const ChatSummaryTable: React.FC<ChatSummaryTableProps> = ({
  summary,
  onNavigate,
}) => {
  return (
    <div className="space-y-3 pt-2">
      <div className="overflow-x-auto max-w-full rounded-md border border-border bg-background">
        <table className="w-full min-w-[540px] text-left text-xs border-collapse">
          <thead>
            <tr className="border-b border-border bg-surface text-muted font-medium">
              <th className="py-2 px-3">Vendor</th>
              <th className="py-2 px-3 text-right">Score</th>
              <th className="py-2 px-3">Mandatory met</th>
              <th className="py-2 px-3 text-right">Monthly cost (incl. GST)</th>
              <th className="py-2 px-3 text-right">Needs review</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {summary.vendors.map((v) => {
              let colorClass = 'text-status-partial-text';
              let subtext = `${v.mandatory_to_check} to check`;

              if (v.mandatory_failures === 0 && v.mandatory_to_check === 0) {
                colorClass = 'text-status-compliant-text';
                subtext = 'All met';
              } else if (v.mandatory_failures >= 1) {
                colorClass = 'text-status-noncompliant-text';
                subtext = `${v.mandatory_failures} failure${v.mandatory_failures === 1 ? '' : 's'}`;
              }

              return (
                <tr key={v.name} className="hover:bg-surface/50">
                  <td className="py-2 px-3 font-medium text-text">{v.name}</td>
                  <td className="py-2 px-3 text-right text-text font-medium">
                    {v.total}
                  </td>
                  <td className="py-2 px-3">
                    <span className={cn('font-medium', colorClass)}>
                      {v.mandatory_met} ({subtext})
                    </span>
                  </td>
                  <td className="py-2 px-3 text-right text-text">
                    {v.monthly_total}
                  </td>
                  <td className="py-2 px-3 text-right text-muted">
                    {v.needs_review_count > 0
                      ? `${v.needs_review_count} item${v.needs_review_count === 1 ? '' : 's'}`
                      : '0'}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <div className="space-y-1.5 pt-1">
        <div className="font-semibold text-xs text-text">{summary.outcome}</div>
        {summary.reasons && summary.reasons.length > 0 && (
          <ul className="list-disc list-inside space-y-1 text-xs text-muted">
            {summary.reasons.map((r, i) => (
              <li key={i}>{r}</li>
            ))}
          </ul>
        )}
      </div>

      <div className="flex flex-wrap items-center gap-2 pt-2">
        <button
          type="button"
          onClick={() => onNavigate('comparison')}
          className="text-xs px-3 py-1.5 rounded-md border border-orange text-navy hover:bg-orange hover:text-navy active:bg-orange active:text-navy font-medium transition-colors focus:outline-none focus:ring-1 focus:ring-orange cursor-pointer"
        >
          Open comparison
        </button>
        <button
          type="button"
          onClick={() => onNavigate('recommendation')}
          className="text-xs px-3 py-1.5 rounded-md border border-orange text-navy hover:bg-orange hover:text-navy active:bg-orange active:text-navy font-medium transition-colors focus:outline-none focus:ring-1 focus:ring-orange cursor-pointer"
        >
          Open recommendation
        </button>
        <button
          type="button"
          onClick={() => onNavigate('print')}
          className="text-xs px-3 py-1.5 rounded-md border border-orange text-navy hover:bg-orange hover:text-navy active:bg-orange active:text-navy font-medium transition-colors focus:outline-none focus:ring-1 focus:ring-orange cursor-pointer"
        >
          Print report
        </button>
      </div>
    </div>
  );
};
