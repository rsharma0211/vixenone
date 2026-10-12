import React from 'react';
import { FindingStatusBadge } from '@/components/status/FindingStatusBadge';
import { LifecycleStatus } from '@/components/status/LifecycleStatus';
import { RiskBadge } from '@/components/status/RiskBadge';
import { MandatoryTag } from '@/components/status/MandatoryTag';
import { Button } from '@/components/ui/button';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { useDrawer } from '@/components/layout/AppShell';

export const DevComponentsPage: React.FC = () => {
  const { openDrawer } = useDrawer();

  const handleOpenDrawer = () => {
    openDrawer(
      'REQ-03 · BrightNest Facility Services',
      <div className="space-y-6 text-left">
        <div className="flex items-center gap-2">
          <MandatoryTag />
          <FindingStatusBadge status="Non-compliant" />
        </div>

        <div className="space-y-1.5 border-t border-border pt-4">
          <div className="text-xs font-semibold text-muted uppercase tracking-wider">
            Requirement
          </div>
          <p className="text-sm font-medium text-text">
            Supply of washroom consumables included in monthly fee.
          </p>
          <p className="text-xs text-muted">
            Acceptance: priced within base fee.
          </p>
        </div>

        <div className="space-y-1.5 border-t border-border pt-4">
          <div className="text-xs font-semibold text-muted uppercase tracking-wider">
            Finding
          </div>
          <p className="text-sm text-text">
            The proposal explicitly excludes washroom consumables and bills them at actuals, so the monthly fee does not cover them.
          </p>
          <div className="pt-1">
            <span className="rounded bg-muted-surface text-muted text-xs font-medium px-2 py-0.5">
              Fact — directly quoted
            </span>
          </div>
        </div>

        <div className="space-y-2 border-t border-border pt-4">
          <div className="text-xs font-semibold text-muted uppercase tracking-wider">
            Evidence
          </div>
          <div className="rounded-md border-l-4 border-status-noncompliant-text bg-surface p-3 text-xs leading-relaxed text-text">
            &ldquo;Washroom consumables (tissue, hand wash, air freshener) are{' '}
            <span className="bg-status-partial-bg text-status-partial-text px-1 rounded font-medium">
              not included
            </span>{' '}
            and will be billed at actuals.&rdquo;
          </div>
          <div className="text-xs text-muted">
            BrightNest_Proposal.pdf · Page 4 · §3.2 Exclusions
          </div>
        </div>

        <div className="space-y-2 border-t border-border pt-4">
          <div className="text-xs font-semibold text-muted uppercase tracking-wider">
            Related Risks
          </div>
          <div className="flex flex-wrap gap-2">
            <RiskBadge type="Exclusion" severity="High" />
            <RiskBadge type="Unknown cost" severity="High" />
          </div>
        </div>

        <div className="space-y-2 border-t border-border pt-4">
          <div className="text-xs font-semibold text-muted uppercase tracking-wider">
            Clarification Question
          </div>
          <div className="rounded-md border border-border bg-surface p-3 text-xs text-text">
            Please provide a fixed monthly rate for washroom consumables, or confirm a cap on billing at actuals.
          </div>
        </div>
      </div>
    );
  };

  return (
    <div className="space-y-10 text-left">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-border pb-6">
        <div>
          <h1 className="text-page-title text-text font-semibold tracking-tight">
            Design System Components (S0)
          </h1>
          <p className="text-body text-muted">
            Central design tokens, status components, and drawer preview.
          </p>
        </div>
        <div>
          <Button variant="primary" onClick={handleOpenDrawer}>
            Open Drawer (L4)
          </Button>
        </div>
      </div>

      {/* 1. FindingStatusBadge Specimen */}
      <Card>
        <CardHeader>
          <CardTitle>Finding Status Badges</CardTitle>
          <p className="text-body text-muted">
            Filled pills with color + text, needs review outline, and inferred dashed style.
          </p>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex flex-wrap items-center gap-3">
            <FindingStatusBadge status="Compliant" />
            <FindingStatusBadge status="Partially compliant" />
            <FindingStatusBadge status="Non-compliant" />
            <FindingStatusBadge status="Not evidenced" />
            <FindingStatusBadge status="Not evidenced" needsReview />
            <FindingStatusBadge status="Not evidenced" inferred />
          </div>
        </CardContent>
      </Card>

      {/* 2. LifecycleStatus Specimen */}
      <Card>
        <CardHeader>
          <CardTitle>Evaluation & File Lifecycle Status</CardTitle>
          <p className="text-body text-muted">
            8px dot + plain text, no pill. Stale includes refresh icon.
          </p>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            <LifecycleStatus status="Draft" />
            <LifecycleStatus status="Requirements review" />
            <LifecycleStatus status="Analysed" />
            <LifecycleStatus status="Stale" />
            <LifecycleStatus status="Ready" />
            <LifecycleStatus status="Processing" />
            <LifecycleStatus status="Error" />
          </div>
        </CardContent>
      </Card>

      {/* 3. RiskBadge & Severity Specimen */}
      <Card>
        <CardHeader>
          <CardTitle>Risk Taxonomy & Severity Badges</CardTitle>
          <p className="text-body text-muted">
            Line icon + label with optional severity, plus 14px muted icon-only variant.
          </p>
        </CardHeader>
        <CardContent className="space-y-6">
          <div className="space-y-2">
            <div className="text-xs font-semibold text-muted uppercase tracking-wider">
              Full Risk Badges
            </div>
            <div className="flex flex-wrap items-center gap-3">
              <RiskBadge type="Exclusion" />
              <RiskBadge type="Omission" />
              <RiskBadge type="Ambiguity" />
              <RiskBadge type="Contradiction" />
              <RiskBadge type="Unknown cost" />
            </div>
          </div>

          <div className="space-y-2">
            <div className="text-xs font-semibold text-muted uppercase tracking-wider">
              With Severity Levels
            </div>
            <div className="flex flex-wrap items-center gap-3">
              <RiskBadge type="Exclusion" severity="High" />
              <RiskBadge type="Ambiguity" severity="Medium" />
              <RiskBadge type="Omission" severity="Low" />
            </div>
          </div>

          <div className="space-y-2">
            <div className="text-xs font-semibold text-muted uppercase tracking-wider">
              Icon-Only Variants (Matrix Cells)
            </div>
            <div className="flex items-center gap-4 p-3 bg-surface rounded-lg border border-border w-fit">
              <RiskBadge type="Exclusion" iconOnly />
              <RiskBadge type="Omission" iconOnly />
              <RiskBadge type="Ambiguity" iconOnly />
              <RiskBadge type="Contradiction" iconOnly />
              <RiskBadge type="Unknown cost" iconOnly />
            </div>
          </div>
        </CardContent>
      </Card>

      {/* 4. Mandatory Tag */}
      <Card>
        <CardHeader>
          <CardTitle>Mandatory Tag</CardTitle>
          <p className="text-body text-muted">
            Small muted grey tag used in tables and matrices.
          </p>
        </CardHeader>
        <CardContent>
          <div className="flex items-center gap-3">
            <MandatoryTag />
            <span className="text-xs text-muted">
              Appears next to requirement identifiers e.g. REQ-01
            </span>
          </div>
        </CardContent>
      </Card>

      {/* 5. Typography Scale Specimen */}
      <Card>
        <CardHeader>
          <CardTitle>Typography Scale & Tabular Numbers</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <div className="text-xs text-muted">Page Title (24/600):</div>
            <div className="text-page-title text-text">Housekeeping Services — Andheri East Office</div>
          </div>
          <div>
            <div className="text-xs text-muted">Section Title (18/600):</div>
            <div className="text-section-title text-text">Cost comparison</div>
          </div>
          <div>
            <div className="text-xs text-muted">Card Title (16/600):</div>
            <div className="text-card-title text-text">Scoring breakdown</div>
          </div>
          <div>
            <div className="text-xs text-muted">Body (14/400):</div>
            <div className="text-body text-text">
              All vendors must submit certified equipment calibration logs and verify minimum staffing levels on site.
            </div>
          </div>
          <div>
            <div className="text-xs text-muted">Meta (12/500):</div>
            <div className="text-meta text-muted">Updated 12 Oct 2026 · Mumbai</div>
          </div>
          <div>
            <div className="text-xs text-muted">Tabular Figures (14px):</div>
            <div className="text-body font-normal tabular-nums text-text">
              ₹3,85,000 · ₹4,60,000 · ₹4,10,000
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

export default DevComponentsPage;
