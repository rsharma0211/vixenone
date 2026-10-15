import React, { useEffect, useState, useMemo, useCallback } from 'react';
import { useParams, Link, useOutletContext } from 'react-router-dom';
import {
  Printer,
  AlertTriangle,
  Copy,
  Check,
  ChevronDown,
  ChevronUp,
  RefreshCw,
} from 'lucide-react';
import { apiClient, ApiValidationError } from '@/lib/api/client';
import { VendorSummaryCards } from '@/components/VendorSummaryCards';
import { formatINR, formatPointsHalfUp, formatPrintDate } from '@/lib/format';
import { useUnsavedChangesGuard } from '@/components/UnsavedChangesGuard';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { FindingStatusBadge } from '@/components/status/FindingStatusBadge';
import { EVALUATION_CHANGED_EVENT } from '@/lib/events';
import { cn } from '@/lib/utils';
import type { EvaluationLayoutContext } from '@/components/layout/EvaluationLayout';
import type {
  EvaluationResultsResponse,
  FindingResponse,
  CostBreakdownResponse,
} from '@/lib/types';

// Screens: S7 (Recommendation), S7-insufficient, S7-P (Print report)

export const RecommendationPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const { evaluationDetail, refresh } = useOutletContext<EvaluationLayoutContext>();

  const [results, setResults] = useState<EvaluationResultsResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Weights state: local edits vs saved snapshot
  const [weights, setWeights] = useState<Record<string, number>>({});
  const [savedWeights, setSavedWeights] = useState<Record<string, number>>({});
  const [savingWeights, setSavingWeights] = useState<boolean>(false);
  const [weightsError, setWeightsError] = useState<string | null>(null);

  // Accordion open state for clarifications per vendor
  const [openClarifications, setOpenClarifications] = useState<Record<string, boolean>>({});
  const [copiedAll, setCopiedAll] = useState<boolean>(false);
  const [copiedItem, setCopiedItem] = useState<string | null>(null);

  const loadResults = useCallback(async (evalId: string) => {
    try {
      setLoading(true);
      setError(null);
      const data = await apiClient.getResults(evalId);
      setResults(data);

      const initial: Record<string, number> = {};
      data.scoring.forEach((row) => {
        initial[row.criterion_key] = row.weight;
      });
      setWeights(initial);
      setSavedWeights(initial);

      const initialOpen: Record<string, boolean> = {};
      data.vendors.forEach((v) => {
        const qs = data.clarifications[v.id] || [];
        initialOpen[v.id] = qs.length > 0;
      });
      setOpenClarifications(initialOpen);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load results');
    } finally {
      setLoading(false);
    }
  }, []);

  // Fetch results on mount and id change
  useEffect(() => {
    if (id) {
      loadResults(id);
    }

    const handleChanged = (e: Event) => {
      const custom = e as CustomEvent<{ evaluationId?: string | null }>;
      if (!custom.detail?.evaluationId || custom.detail.evaluationId === id) {
        if (id) loadResults(id);
      }
    };
    window.addEventListener(EVALUATION_CHANGED_EVENT, handleChanged);

    return () => {
      window.removeEventListener(EVALUATION_CHANGED_EVENT, handleChanged);
    };
  }, [id, loadResults]);

  // Determine if weights are modified
  const isDirty = useMemo(() => {
    const keys = Object.keys(weights);
    if (keys.length === 0) return false;
    return keys.some((k) => weights[k] !== savedWeights[k]);
  }, [weights, savedWeights]);

  // Guard in-app and browser navigation while weights are unsaved
  useUnsavedChangesGuard(isDirty);

  // Calculate running total of entered weights
  const totalWeight = useMemo(() => {
    return Object.values(weights).reduce((sum, w) => sum + (Number(w) || 0), 0);
  }, [weights]);

  // Handle single criterion weight input
  const handleWeightChange = (key: string, rawVal: string) => {
    setWeightsError(null);
    if (rawVal === '') {
      setWeights((prev) => ({ ...prev, [key]: 0 }));
      return;
    }
    const parsed = parseInt(rawVal, 10);
    if (!isNaN(parsed)) {
      const clamped = Math.max(0, Math.min(100, parsed));
      setWeights((prev) => ({ ...prev, [key]: clamped }));
    }
  };

  // Discard local weight edits
  const handleDiscardWeights = () => {
    setWeights(savedWeights);
    setWeightsError(null);
  };

  // Save weights via PUT /api/evaluations/{id}/weights
  const handleSaveWeights = async () => {
    if (!id || !isDirty || totalWeight !== 100 || savingWeights) return;

    setSavingWeights(true);
    setWeightsError(null);

    try {
      const updatedResults = await apiClient.updateWeights(id, weights);
      setResults(updatedResults);

      const newSaved: Record<string, number> = {};
      updatedResults.scoring.forEach((row) => {
        newSaved[row.criterion_key] = row.weight;
      });
      setSavedWeights(newSaved);
      setWeights(newSaved);

      // Refresh parent evaluation detail to ensure consistency
      await refresh();
    } catch (err) {
      if (err instanceof ApiValidationError) {
        setWeightsError(err.message || 'Validation failed');
      } else {
        setWeightsError(err instanceof Error ? err.message : 'Failed to update weights');
      }
    } finally {
      setSavingWeights(false);
    }
  };

  // Toggle clarification accordion per vendor
  const toggleClarification = (vendorId: string) => {
    setOpenClarifications((prev) => ({
      ...prev,
      [vendorId]: !prev[vendorId],
    }));
  };

  // Copy all clarifications across vendors to clipboard
  const handleCopyAllClarifications = async () => {
    if (!results) return;
    const lines: string[] = [];
    results.vendors.forEach((v) => {
      const qs = results.clarifications[v.id] || [];
      if (qs.length > 0) {
        lines.push(`${v.name}:`);
        qs.forEach((q, idx) => {
          lines.push(`  ${idx + 1}. ${q}`);
        });
        lines.push('');
      }
    });

    if (lines.length > 0) {
      await navigator.clipboard.writeText(lines.join('\n'));
      setCopiedAll(true);
      window.setTimeout(() => setCopiedAll(false), 2000);
    }
  };

  // Copy single question to clipboard
  const handleCopySingleClarification = async (q: string, key: string) => {
    await navigator.clipboard.writeText(q);
    setCopiedItem(key);
    window.setTimeout(() => setCopiedItem(null), 2000);
  };

  // Evaluation status checks
  const status = evaluationDetail?.status;
  const isNotAnalysed = status === 'draft' || status === 'requirements_review';
  const isStale = status === 'stale';

  // Format location label
  const locationLabel = evaluationDetail?.location
    ? `${evaluationDetail.location.name}, ${evaluationDetail.location.city}`
    : null;

  // Render loading state
  if (loading) {
    return (
      <div className="rounded-lg border border-border bg-background p-12 text-center text-muted text-sm space-y-3">
        <RefreshCw className="w-5 h-5 animate-spin mx-auto text-muted" />
        <p>Loading recommendation and scores...</p>
      </div>
    );
  }

  // Render error state
  if (error || !results) {
    return (
      <div className="rounded-lg border border-status-noncompliant-text/30 bg-status-noncompliant-bg p-6 text-sm text-status-noncompliant-text space-y-2">
        <h3 className="font-semibold">Unable to load recommendation</h3>
        <p>{error || 'No results available'}</p>
      </div>
    );
  }

  // Render empty state if not analysed
  if (isNotAnalysed) {
    return (
      <div className="rounded-lg border border-dashed border-border p-12 text-center space-y-3">
        <p className="text-muted text-sm">
          No analysis yet. Run analysis on the{' '}
          <Link
            to={`/evaluations/${id}/requirements`}
            className="text-navy font-medium underline hover:text-accent"
          >
            Requirements tab
          </Link>
          .
        </p>
      </div>
    );
  }

  // Recommendation details
  const recommendation = results.recommendation;
  const isRecommended = recommendation?.state === 'recommended';
  const recommendedVendor = isRecommended
    ? results.vendors.find((v) => v.id === recommendation?.vendor_id)
    : null;
  const displayTotal = recommendedVendor
    ? recommendedVendor.display_total ?? recommendedVendor.score ?? '—'
    : '—';
  const recommendationReasons = recommendation?.reasons || [];

  // Costs mapped by vendor ID
  const costsByVendor = new Map<string, CostBreakdownResponse>();
  results.costs.forEach((c) => costsByVendor.set(c.vendor_id, c));

  // High-severity findings and risks per vendor for key risks
  const highRisksByVendor = new Map<string, FindingResponse[]>();
  results.vendors.forEach((v) => {
    const vRisks = results.findings.filter(
      (f) =>
        String(f.vendor_id) === v.id &&
        (f.severity?.toLowerCase() === 'high' ||
          f.status === 'Non-compliant' ||
          f.needs_review)
    );
    highRisksByVendor.set(v.id, vRisks);
  });

  return (
    <div className="space-y-6 text-left">
      {/* Top action row: Print report button */}
      <div className="flex items-center justify-end -mt-3 mb-2 print:hidden">
        <TooltipProvider delayDuration={150}>
          <Tooltip open={isDirty ? undefined : false}>
            <TooltipTrigger asChild>
              <span>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  disabled={isDirty}
                  onClick={() => window.print()}
                  className="gap-2 text-xs"
                >
                  <Printer className="w-3.5 h-3.5" />
                  <span>Print report</span>
                </Button>
              </span>
            </TooltipTrigger>
            {isDirty && (
              <TooltipContent side="bottom" align="end">
                Save weights first
              </TooltipContent>
            )}
          </Tooltip>
        </TooltipProvider>
      </div>

      {/* Print-Only Report Header (S7-P) */}
      <div className="hidden print:block space-y-2 border-b border-border pb-4 print-avoid-break">
        <div className="text-[10px] font-semibold text-muted uppercase tracking-wider">
          VixenOne · Vendor evaluation report
        </div>
        <h1 className="text-xl font-bold text-navy tracking-tight">
          {evaluationDetail?.title || 'Vendor Evaluation'}
        </h1>
        <p className="text-xs text-muted break-words">
          Generated {formatPrintDate(new Date())}
          {results.company_name ? ` · Prepared for ${results.company_name}` : ''}
          {evaluationDetail?.category ? ` · ${evaluationDetail.category}` : ''}
          {locationLabel ? ` · ${locationLabel}` : ''}
        </p>
      </div>

      {/* Stale Banner */}
      {isStale && (
        <div
          role="alert"
          className="rounded-lg border border-status-partial-text/40 bg-status-partial-bg px-4 py-3 text-sm text-status-partial-text flex items-center gap-2.5 print:hidden"
        >
          <AlertTriangle className="w-4 h-4 shrink-0" />
          <span>
            Requirements were edited after analysis. Results are stale — re-run analysis to update.
          </span>
        </div>
      )}

      {/* Outcome Banner */}
      {isRecommended && recommendedVendor ? (
        <div className="rounded-lg border border-border border-l-4 border-l-navy bg-surface/70 p-5 space-y-3 print-avoid-break">
          <div>
            <h2 className="font-semibold text-base text-navy">
              Recommended: {recommendedVendor.name}
            </h2>
            <div className="text-xs font-medium text-muted mt-0.5">
              Total score: {displayTotal} / 100
            </div>
          </div>

          {recommendationReasons.length > 0 && (
            <ul className="list-disc list-inside text-xs text-text space-y-1">
              {recommendationReasons.map((reason, idx) => (
                <li key={idx} className="leading-relaxed">
                  {reason}
                </li>
              ))}
            </ul>
          )}

          <p className="text-xs text-muted">
            Based on the evidence and your current weights. Review the reasons before deciding.
          </p>
        </div>
      ) : (
        <div className="rounded-lg border border-status-partial-text/30 border-l-4 border-l-status-partial-text bg-status-partial-bg/40 p-5 space-y-3 print-avoid-break">
          <div className="flex items-start gap-2.5">
            <AlertTriangle className="w-5 h-5 text-status-partial-text shrink-0 mt-0.5" />
            <div className="space-y-1">
              <h2 className="font-semibold text-base text-navy">
                Insufficient information to recommend
              </h2>
              {recommendationReasons.length > 0 && (
                <ul className="list-disc list-inside text-xs text-text space-y-1 pt-1">
                  {recommendationReasons.map((reason, idx) => (
                    <li key={idx} className="leading-relaxed">
                      {reason}
                    </li>
                  ))}
                </ul>
              )}
              <div className="pt-2">
                <a
                  href="#clarifications"
                  className="inline-flex items-center gap-1 text-xs font-medium text-navy hover:underline focus:outline-none focus:ring-1 focus:ring-navy rounded"
                >
                  <span>Go to open clarifications</span>
                  <span aria-hidden="true">&darr;</span>
                </a>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Vendor Summary Cards (Section B) */}
      <section className="space-y-3 print:hidden">
        <h2 className="text-section-title font-semibold text-text">Vendor summary</h2>
        <VendorSummaryCards vendors={results.vendors} />
      </section>

      {/* Scoring Breakdown Table with Weights Panel */}
      <section className="rounded-lg border border-border bg-background p-5 space-y-4 print-avoid-break">
        <div className="flex items-center justify-between border-b border-border pb-3">
          <h2 className="text-section-title font-semibold text-text">Scoring breakdown</h2>
        </div>

        {/* Weights validation error */}
        {weightsError && (
          <div
            role="alert"
            className="rounded border border-status-noncompliant-text/30 bg-status-noncompliant-bg p-3 text-xs text-status-noncompliant-text"
          >
            {weightsError}
          </div>
        )}

        <div className="overflow-x-auto max-w-full">
          <table className="w-full text-left border-collapse text-xs">
            <thead>
              <tr className="border-b border-border bg-muted-surface">
                <th className="p-3 font-semibold text-text w-[220px] min-w-[160px]">
                  CRITERION
                </th>
                <th className="p-3 font-semibold text-text w-[120px] min-w-[100px]">
                  WEIGHT
                </th>
                {results.vendors.map((v) => (
                  <th key={v.id} className="p-3 font-semibold text-text min-w-[120px]">
                    {v.name}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {results.scoring.map((row) => {
                const currentWeight = weights[row.criterion_key] ?? row.weight;

                return (
                  <tr key={row.criterion_key} className="hover:bg-surface/40 transition-colors">
                    <td className="p-3 font-medium text-text align-middle">
                      {row.criterion}
                    </td>
                    <td className="p-3 align-middle">
                      {/* Interactive whole-number input on screen */}
                      <div className="flex items-center gap-1.5 print:hidden">
                        <Input
                          type="number"
                          min={0}
                          max={100}
                          step={1}
                          value={currentWeight}
                          aria-label={`${row.criterion} weight`}
                          onChange={(e) =>
                            handleWeightChange(row.criterion_key, e.target.value)
                          }
                          className="w-16 h-8 text-xs px-2"
                        />
                        <span className="text-muted text-xs">%</span>
                      </div>
                      {/* Plain number text in print */}
                      <span className="hidden print:inline text-xs font-semibold">
                        {row.weight}%
                      </span>
                    </td>
                    {results.vendors.map((v) => {
                      const cell = row.vendor_scores[v.id];
                      const scoreVal =
                        cell?.score !== null && cell?.score !== undefined
                          ? cell.score
                          : '—';
                      const pointsVal = formatPointsHalfUp(
                        cell?.points ?? cell?.raw_points
                      );

                      return (
                        <td key={v.id} className="p-3 align-middle">
                          <div className="font-semibold text-text">{scoreVal}</div>
                          <div className="text-[11px] text-muted">
                            = {pointsVal} pts
                          </div>
                        </td>
                      );
                    })}
                  </tr>
                );
              })}

              {/* Total row from API display values */}
              <tr className="bg-surface/80 font-bold border-t-2 border-border">
                <td className="p-3 text-navy">TOTAL</td>
                <td className="p-3 text-navy">
                  <span className="print:hidden">
                    {isDirty ? `${totalWeight}%` : '100%'}
                  </span>
                  <span className="hidden print:inline">100%</span>
                </td>
                {results.vendors.map((v) => {
                  const vTotal = results.vendor_totals[v.id];
                  const totalDisplay =
                    v.display_total ??
                    vTotal?.total ??
                    vTotal?.score ??
                    v.score ??
                    '—';

                  return (
                    <td key={v.id} className="p-3 text-navy text-sm">
                      {totalDisplay}
                    </td>
                  );
                })}
              </tr>
            </tbody>
          </table>
        </div>

        {/* Weights actions row below table (print:hidden) */}
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 pt-3 border-t border-border print:hidden">
          <div className="text-xs">
            <span
              className={cn(
                'font-medium',
                totalWeight === 100
                  ? 'text-muted'
                  : 'text-status-noncompliant-text font-semibold'
              )}
            >
              Total weight {totalWeight} / 100
            </span>
          </div>
          <div className="flex items-center gap-2 self-end sm:self-auto">
            {isDirty && (
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={handleDiscardWeights}
                disabled={savingWeights}
                className="text-xs text-muted hover:text-navy"
              >
                Discard changes
              </Button>
            )}
            <Button
              type="button"
              size="sm"
              disabled={!isDirty || totalWeight !== 100 || savingWeights}
              onClick={handleSaveWeights}
              className="text-xs bg-navy text-white hover:bg-navy/90"
            >
              {savingWeights ? (
                <>
                  <RefreshCw className="w-3.5 h-3.5 animate-spin mr-1.5" />
                  <span>Saving...</span>
                </>
              ) : (
                'Save weights'
              )}
            </Button>
          </div>
        </div>
      </section>

      {/* Cost Comparison Table (Print & Reference) */}
      <section className="rounded-lg border border-border bg-background p-5 space-y-3 print-avoid-break">
        <h2 className="text-section-title font-semibold text-text">Cost comparison</h2>
        <div className="overflow-x-auto max-w-full">
          <table className="w-full text-left border-collapse text-xs">
            <thead>
              <tr className="border-b border-border bg-muted-surface">
                <th className="p-3 font-semibold text-text w-[220px] min-w-[160px]">
                  ITEM
                </th>
                {results.vendors.map((v) => (
                  <th key={v.id} className="p-3 font-semibold text-text min-w-[160px]">
                    {v.name}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {/* Monthly base */}
              <tr>
                <td className="p-3 font-medium text-text">Monthly base</td>
                {results.vendors.map((v) => {
                  const cb = costsByVendor.get(v.id);
                  return (
                    <td key={v.id} className="p-3 text-text">
                      {formatINR(cb?.monthly_base)}
                    </td>
                  );
                })}
              </tr>
              {/* GST 18% */}
              <tr>
                <td className="p-3 font-medium text-text">GST 18%</td>
                {results.vendors.map((v) => {
                  const cb = costsByVendor.get(v.id);
                  return (
                    <td key={v.id} className="p-3 text-muted">
                      {cb?.gst_18 !== null && cb?.gst_18 !== undefined
                        ? formatINR(cb.gst_18)
                        : cb?.monthly_base === null
                        ? 'Not stated'
                        : '—'}
                    </td>
                  );
                })}
              </tr>
              {/* Monthly total */}
              <tr className="bg-surface/50 font-bold">
                <td className="p-3 text-navy">Monthly total</td>
                {results.vendors.map((v) => {
                  const cb = costsByVendor.get(v.id);
                  return (
                    <td key={v.id} className="p-3 text-navy font-bold">
                      {formatINR(cb?.monthly_total)}
                    </td>
                  );
                })}
              </tr>
              {/* Included */}
              <tr>
                <td className="p-3 align-top font-medium text-text">Included</td>
                {results.vendors.map((v) => {
                  const cb = costsByVendor.get(v.id);
                  const items = cb?.included || [];
                  return (
                    <td key={v.id} className="p-3 align-top text-muted">
                      {items.length > 0 ? items.join(', ') : '—'}
                    </td>
                  );
                })}
              </tr>
              {/* Excluded */}
              <tr>
                <td className="p-3 align-top font-medium text-text">Excluded</td>
                {results.vendors.map((v) => {
                  const cb = costsByVendor.get(v.id);
                  const items = cb?.excluded || [];
                  return (
                    <td key={v.id} className="p-3 align-top text-muted">
                      {items.length > 0 ? items.join(', ') : '—'}
                    </td>
                  );
                })}
              </tr>
              {/* Unknown */}
              <tr>
                <td className="p-3 align-top font-medium text-text">Unknown cost</td>
                {results.vendors.map((v) => {
                  const cb = costsByVendor.get(v.id);
                  const items = cb?.unknown || [];
                  return (
                    <td key={v.id} className="p-3 align-top text-muted">
                      {items.length > 0 ? items.join(', ') : '—'}
                    </td>
                  );
                })}
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      {/* Key Risks Section (Print & Screen) */}
      <section className="rounded-lg border border-border bg-background p-5 space-y-4 print-avoid-break">
        <h2 className="text-section-title font-semibold text-text">Key risks</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {results.vendors.map((v) => {
            const vRisks = highRisksByVendor.get(v.id) || [];

            return (
              <div
                key={v.id}
                className="rounded-lg border border-border bg-surface/50 p-4 space-y-3"
              >
                <div className="font-semibold text-xs text-navy border-b border-border pb-2">
                  {v.name}
                </div>
                {vRisks.length === 0 ? (
                  <p className="text-xs text-muted py-1">
                    No high-severity risks identified
                  </p>
                ) : (
                  <div className="space-y-2">
                    {vRisks.map((risk) => (
                      <div
                        key={risk.id}
                        className="rounded border border-border bg-background p-2.5 space-y-1.5 text-xs"
                      >
                        <div className="flex items-center gap-1.5 flex-wrap">
                          {risk.status && (
                            <FindingStatusBadge
                              status={
                                risk.status === 'Compliant'
                                  ? 'Compliant'
                                  : risk.status === 'Partially compliant'
                                  ? 'Partially compliant'
                                  : risk.status === 'Non-compliant'
                                  ? 'Non-compliant'
                                  : 'Not evidenced'
                              }
                              needsReview={risk.needs_review}
                              inferred={risk.inferred}
                            />
                          )}
                          {risk.severity && (
                            <span className="text-[11px] font-medium text-muted">
                              ({risk.severity} severity)
                            </span>
                          )}
                        </div>
                        {risk.evidence_quote && (
                          <p className="italic text-muted line-clamp-2">
                            &ldquo;{risk.evidence_quote}&rdquo;
                          </p>
                        )}
                        {risk.clarification_question && (
                          <p className="text-text font-medium line-clamp-2">
                            {risk.clarification_question}
                          </p>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </section>

      {/* Open Clarifications Section */}
      <section
        id="clarifications"
        className="rounded-lg border border-border bg-background p-5 space-y-4 print-avoid-break scroll-mt-6"
      >
        <div className="flex items-center justify-between border-b border-border pb-3">
          <h2 className="text-section-title font-semibold text-text">
            Clarification questions
          </h2>
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={handleCopyAllClarifications}
            className="text-xs gap-1.5 print:hidden"
          >
            {copiedAll ? (
              <>
                <Check className="w-3.5 h-3.5 text-status-compliant-text" />
                <span>Copied</span>
              </>
            ) : (
              <>
                <Copy className="w-3.5 h-3.5" />
                <span>Copy all</span>
              </>
            )}
          </Button>
        </div>

        <div className="space-y-3">
          {results.vendors.map((v) => {
            const qs = results.clarifications[v.id] || [];
            const isOpen = openClarifications[v.id] ?? true;

            return (
              <div
                key={v.id}
                className="rounded-lg border border-border bg-surface/30 overflow-hidden"
              >
                {/* Header toggle on screen; plain header in print */}
                <button
                  type="button"
                  onClick={() => toggleClarification(v.id)}
                  className="w-full p-3.5 flex items-center justify-between text-left hover:bg-surface/70 transition-colors focus:outline-none focus:ring-1 focus:ring-navy print:hover:bg-transparent"
                >
                  <span className="font-semibold text-xs text-navy">
                    {v.name} ({qs.length})
                  </span>
                  <span className="print:hidden text-muted">
                    {isOpen ? (
                      <ChevronUp className="w-4 h-4" />
                    ) : (
                      <ChevronDown className="w-4 h-4" />
                    )}
                  </span>
                </button>

                {/* Content body */}
                {(isOpen || true) && (
                  <div
                    className={cn(
                      'p-3.5 pt-0 space-y-2',
                      !isOpen && 'hidden print:block'
                    )}
                  >
                    {qs.length === 0 ? (
                      <p className="text-xs text-muted italic">None</p>
                    ) : (
                      <ol className="space-y-2">
                        {qs.map((q, idx) => {
                          const itemKey = `${v.id}-${idx}`;
                          const isCopied = copiedItem === itemKey;

                          return (
                            <li
                              key={idx}
                              className="rounded border border-border bg-background p-3 text-xs flex items-start justify-between gap-3"
                            >
                              <div className="space-y-1">
                                <span className="font-medium text-muted mr-1.5">
                                  {idx + 1}.
                                </span>
                                <span className="text-text leading-relaxed">{q}</span>
                              </div>
                              <Button
                                type="button"
                                variant="ghost"
                                size="sm"
                                onClick={() => handleCopySingleClarification(q, itemKey)}
                                className="h-7 w-7 p-0 shrink-0 text-muted hover:text-navy print:hidden"
                                aria-label="Copy clarification question"
                              >
                                {isCopied ? (
                                  <Check className="w-3.5 h-3.5 text-status-compliant-text" />
                                ) : (
                                  <Copy className="w-3.5 h-3.5" />
                                )}
                              </Button>
                            </li>
                          );
                        })}
                      </ol>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </section>

      {/* Limitations Note */}
      <section className="rounded-lg border border-border bg-surface/50 p-4 text-xs text-muted space-y-1.5 print-avoid-break">
        <h3 className="font-semibold text-text text-xs">Limitations</h3>
        <ul className="list-disc list-inside space-y-0.5">
          <li>Covers only the uploaded documents.</li>
          <li>Inferred findings are marked — verify before deciding.</li>
          <li>Scores depend on the weights above.</li>
        </ul>
      </section>
    </div>
  );
};

export default RecommendationPage;
