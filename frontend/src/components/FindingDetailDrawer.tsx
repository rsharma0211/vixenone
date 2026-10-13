import React from 'react';
import { Flag, AlertTriangle, FileText } from 'lucide-react';
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet';
import { FindingStatusBadge, FindingStatus } from '@/components/status/FindingStatusBadge';
import { RiskBadge } from '@/components/status/RiskBadge';
import type { FindingResponse } from '@/lib/types';

// Screen: S6 (Finding detail drawer)

export interface FindingDetailDrawerProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  finding: FindingResponse | null;
  vendorName: string;
  itemTitle: string;
}

export function normalizeFindingStatus(status?: string | null): FindingStatus {
  if (!status) return 'Not evidenced';
  const clean = status.trim().toLowerCase().replace(/_/g, ' ').replace(/-/g, ' ');
  if (clean.includes('compliant') && !clean.includes('non') && !clean.includes('part')) {
    return 'Compliant';
  }
  if (clean.includes('part')) {
    return 'Partially compliant';
  }
  if (clean.includes('non')) {
    return 'Non-compliant';
  }
  return 'Not evidenced';
}

export function formatFindingSource(finding: FindingResponse): string {
  const parts: string[] = [];
  const docName = finding.evidence?.document;
  if (docName && docName.trim()) {
    parts.push(docName.trim());
  }
  const page = finding.evidence_page ?? finding.evidence?.page;
  if (page !== null && page !== undefined) {
    parts.push(`p.${page}`);
  }
  const section = finding.evidence_section || finding.evidence?.section;
  if (section && section.trim()) {
    parts.push(section.trim());
  }
  return parts.join(' · ');
}

export const FindingDetailDrawer: React.FC<FindingDetailDrawerProps> = ({
  open,
  onOpenChange,
  finding,
  vendorName,
  itemTitle,
}) => {
  if (!finding) return null;

  const status = normalizeFindingStatus(finding.status);
  const sourceText = formatFindingSource(finding);
  const quote = finding.evidence_quote || finding.evidence?.quote;
  const isInference = finding.inferred || finding.fact_or_inference === 'Inference';

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent
        side="right"
        className="w-full sm:max-w-[520px] overflow-y-auto p-6 space-y-6 text-left"
      >
        <SheetHeader className="space-y-1.5 pb-3 border-b border-border">
          <div className="text-xs uppercase font-semibold tracking-wider text-muted truncate">
            {vendorName}
          </div>
          <SheetTitle className="text-base font-semibold text-text leading-snug">
            {itemTitle}
          </SheetTitle>
          <div className="flex items-center gap-2 pt-1.5 flex-wrap">
            <FindingStatusBadge status={status} />
            {finding.needs_review && (
              <span className="inline-flex items-center gap-1 rounded px-2 py-0.5 text-xs font-medium border border-status-review text-status-review bg-transparent whitespace-nowrap">
                <Flag className="w-3 h-3 stroke-[2]" />
                <span>Needs review</span>
              </span>
            )}
          </div>
        </SheetHeader>

        {/* Needs-Review Warning */}
        {finding.needs_review && (
          <div
            role="alert"
            className="rounded-lg border border-status-review/40 bg-status-review/5 p-3.5 text-xs text-status-review flex items-start gap-2.5"
          >
            <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
            <span className="leading-relaxed">
              We could not find this quote in the proposal text. Check the source before relying on it.
            </span>
          </div>
        )}

        {/* Evidence Block Quote */}
        {quote && (
          <div className="space-y-2">
            <div className="text-xs font-semibold text-muted uppercase tracking-wider">
              Evidence quote
            </div>
            <blockquote className="border-l-4 border-status-review bg-surface p-3.5 rounded-r text-xs leading-relaxed italic text-text">
              &ldquo;{quote}&rdquo;
            </blockquote>
            {sourceText && (
              <div className="flex items-center gap-1.5 text-xs text-muted pt-0.5">
                <FileText className="w-3.5 h-3.5 shrink-0" />
                <span>{sourceText}</span>
              </div>
            )}
          </div>
        )}

        {/* Source when quote is not provided */}
        {!quote && sourceText && (
          <div className="space-y-1.5">
            <div className="text-xs font-semibold text-muted uppercase tracking-wider">
              Source
            </div>
            <div className="flex items-center gap-1.5 text-xs text-muted">
              <FileText className="w-3.5 h-3.5 shrink-0" />
              <span>{sourceText}</span>
            </div>
          </div>
        )}

        {/* Confidence & Inference */}
        <div className="space-y-2 pt-1 border-t border-border">
          {finding.confidence && (
            <div className="flex items-center gap-2 text-xs">
              <span className="text-muted font-medium">Confidence:</span>
              <span className="font-semibold text-text">{finding.confidence}</span>
            </div>
          )}
          {isInference && (
            <div className="inline-flex items-center rounded px-2 py-0.5 text-xs font-medium border border-dashed border-status-notevidenced-text text-status-notevidenced-text bg-surface italic">
              Inferred — not directly stated
            </div>
          )}
        </div>

        {/* Related Risks */}
        {finding.risk_types && finding.risk_types.length > 0 && (
          <div className="space-y-2 pt-2 border-t border-border">
            <div className="text-xs font-semibold text-muted uppercase tracking-wider">
              Related risks
            </div>
            <div className="flex items-center gap-2 flex-wrap">
              {finding.risk_types.map((rt) => (
                <RiskBadge
                  key={rt}
                  type={rt as any}
                  severity={finding.severity as any}
                />
              ))}
              {finding.severity && (
                <span className="text-xs text-muted font-medium">
                  ({finding.severity} severity)
                </span>
              )}
            </div>
          </div>
        )}

        {/* Clarification Question */}
        {finding.clarification_question && (
          <div className="space-y-2 pt-2 border-t border-border">
            <div className="text-xs font-semibold text-muted uppercase tracking-wider">
              Clarification question
            </div>
            <div className="rounded-md border border-border bg-surface p-3.5 text-xs text-text leading-relaxed">
              {finding.clarification_question}
            </div>
          </div>
        )}
      </SheetContent>
    </Sheet>
  );
};
