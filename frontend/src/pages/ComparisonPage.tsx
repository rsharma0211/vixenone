import React, { useEffect, useState, useMemo, useCallback } from 'react';
import { useParams, Link, useOutletContext } from 'react-router-dom';
import { RefreshCw, AlertTriangle, Flag, ArrowRight } from 'lucide-react';
import { apiClient } from '@/lib/api/client';
import { KpiTile } from '@/components/KpiTile';
import { KPI_HELP_TEXT } from '@/lib/kpiHelp';
import { FindingStatusBadge } from '@/components/status/FindingStatusBadge';
import { RiskBadge } from '@/components/status/RiskBadge';
import {
  FindingDetailDrawer,
  normalizeFindingStatus,
} from '@/components/FindingDetailDrawer';
import { formatINR } from '@/lib/format';
import type {
  EvaluationResultsResponse,
  FindingResponse,
  RequirementItem,
  AnalysisJobResponse,
  VendorResultItem,
  CostBreakdownResponse,
} from '@/lib/types';
import type { EvaluationLayoutContext } from '@/components/layout/EvaluationLayout';

// Screen: S5 (Vendor comparison)

export const ComparisonPage: React.FC = () => {
  const { id: evaluationId } = useParams<{ id: string }>();
  const outletContext = useOutletContext<EvaluationLayoutContext | undefined>();
  const evaluation = outletContext?.evaluationDetail ?? null;

  const [results, setResults] = useState<EvaluationResultsResponse | null>(null);
  const [requirements, setRequirements] = useState<RequirementItem[]>([]);
  const [latestJob, setLatestJob] = useState<AnalysisJobResponse | null>(
    evaluation?.latest_job ?? null
  );
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Drawer state
  const [drawerOpen, setDrawerOpen] = useState<boolean>(false);
  const [selectedFinding, setSelectedFinding] = useState<FindingResponse | null>(null);
  const [drawerVendorName, setDrawerVendorName] = useState<string>('');
  const [drawerItemTitle, setDrawerItemTitle] = useState<string>('');

  const loadData = useCallback(async (evId: string) => {
    try {
      setLoading(true);
      setError(null);
      const [res, reqs, job] = await Promise.all([
        apiClient.getResults(evId),
        apiClient.getRequirements(evId).catch(() => []),
        apiClient.getLatestJob(evId).catch(() => null),
      ]);
      setResults(res);
      setRequirements(reqs);
      setLatestJob(job);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to load analysis results');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (evaluationId) {
      loadData(evaluationId);
    }
  }, [evaluationId, loadData]);

  // Keep latest job in sync
  useEffect(() => {
    if (evaluation?.latest_job !== undefined) {
      setLatestJob(evaluation.latest_job);
    }
  }, [evaluation?.latest_job]);

  const jobActive = Boolean(
    latestJob &&
      (latestJob.status === 'queued' ||
        latestJob.status === 'analysing' ||
        latestJob.status === 'extracting')
  );

  // Poll while analysis is active
  useEffect(() => {
    if (!evaluationId || !jobActive) return;
    let cancelled = false;

    const intervalId = window.setInterval(async () => {
      try {
        const [job, freshResults] = await Promise.all([
          apiClient.getLatestJob(evaluationId),
          apiClient.getResults(evaluationId).catch(() => null),
        ]);
        if (cancelled) return;
        setLatestJob(job);
        if (freshResults) {
          setResults(freshResults);
        }

        if (!job || job.status === 'done' || job.status === 'failed') {
          window.clearInterval(intervalId);
          await outletContext?.refresh();
          if (!cancelled && evaluationId) {
            await loadData(evaluationId);
          }
        }
      } catch {
        // Keep polling
      }
    }, 2000);

    return () => {
      cancelled = true;
      window.clearInterval(intervalId);
    };
  }, [evaluationId, jobActive, loadData, outletContext]);

  const openDrawer = useCallback(
    (finding: FindingResponse, vendorName: string, itemTitle: string) => {
      setSelectedFinding(finding);
      setDrawerVendorName(vendorName);
      setDrawerItemTitle(itemTitle);
      setDrawerOpen(true);
    },
    []
  );

  // Groupings & Lookups
  const vendors: VendorResultItem[] = useMemo(
    () => results?.vendors || [],
    [results?.vendors]
  );

  const costsByVendor = useMemo(() => {
    const map = new Map<string, CostBreakdownResponse>();
    (results?.costs || []).forEach((c) => {
      map.set(String(c.vendor_id), c);
    });
    return map;
  }, [results?.costs]);

  const reqFindingsMap = useMemo(() => {
    const map = new Map<string, FindingResponse>();
    (results?.findings || []).forEach((f) => {
      if (f.requirement_id) {
        map.set(`${f.vendor_id}:${f.requirement_id}`, f);
      }
    });
    return map;
  }, [results?.findings]);

  const critFindingsMap = useMemo(() => {
    const map = new Map<string, FindingResponse>();
    (results?.findings || []).forEach((f) => {
      if (f.criterion_key) {
        map.set(`${f.vendor_id}:${f.criterion_key}`, f);
      }
    });
    return map;
  }, [results?.findings]);

  const standaloneRisks = useMemo(() => {
    return (results?.findings || []).filter(
      (f) => !f.requirement_id && !f.criterion_key
    );
  }, [results?.findings]);

  const mandatoryRequirements = useMemo(
    () => requirements.filter((r) => r.mandatory),
    [requirements]
  );

  const otherRequirements = useMemo(
    () => requirements.filter((r) => !r.mandatory),
    [requirements]
  );

  // Judged criteria from snapshot (snapshot order, excluding pure formula criteria)
  const judgedCriteria = useMemo(() => {
    const snapshot = results?.criteria_snapshot || [];
    return snapshot.filter(
      (c: any) =>
        c.key !== 'mandatory_compliance' &&
        c.key !== 'cost_comparability' &&
        c.key !== 'unresolved_risks'
    );
  }, [results?.criteria_snapshot]);

  if (loading) {
    return (
      <div className="rounded-lg border border-border bg-background p-12 text-center text-muted text-sm">
        Loading comparison results...
      </div>
    );
  }

  if (error) {
    return (
      <div
        role="alert"
        className="rounded-lg border border-status-noncompliant-text/40 bg-status-noncompliant-bg px-4 py-3 text-sm text-status-noncompliant-text flex items-center gap-2.5 text-left"
      >
        <AlertTriangle className="w-4 h-4 shrink-0" />
        <span>{error}</span>
      </div>
    );
  }

  // Not analysed: empty state with link to Requirements tab
  const isAnalysedOrStale =
    results?.status === 'analysed' || results?.status === 'stale';
  if (!isAnalysedOrStale || vendors.length === 0) {
    return (
      <div className="rounded-lg border border-border bg-background py-16 px-6 text-center space-y-4 max-w-lg mx-auto">
        <div className="w-12 h-12 rounded-lg bg-surface border border-border flex items-center justify-center mx-auto text-muted">
          <AlertTriangle className="w-6 h-6 text-muted" />
        </div>
        <div className="space-y-1">
          <h3 className="text-base font-semibold text-text">No analysis yet</h3>
          <p className="text-sm text-muted">
            Run analysis on the{' '}
            <Link
              to={`/evaluations/${evaluationId}/requirements`}
              className="text-navy font-semibold underline hover:text-accent transition-colors"
            >
              Requirements tab
            </Link>
            .
          </p>
        </div>
        <div>
          <Link
            to={`/evaluations/${evaluationId}/requirements`}
            className="inline-flex items-center gap-2 rounded-md bg-navy px-4 py-2 text-sm font-semibold text-white hover:bg-navy/90 transition-colors"
          >
            <span>Go to Requirements</span>
            <ArrowRight className="w-4 h-4" />
          </Link>
        </div>
      </div>
    );
  }

  const isStale = results?.status === 'stale' || evaluation?.status === 'stale';

  return (
    <div className="space-y-8 text-left max-w-full overflow-hidden pb-12">
      {/* Active analyse job indicator */}
      {jobActive && (
        <div className="flex items-center gap-2.5 rounded-lg border border-accent/40 bg-accent-tint px-4 py-3 text-xs font-medium text-navy">
          <RefreshCw className="w-3.5 h-3.5 animate-spin text-accent shrink-0" />
          <span>Analysis in progress</span>
          {latestJob?.step_label && (
            <span className="text-muted">· {latestJob.step_label}</span>
          )}
        </div>
      )}

      {/* Stale Banner */}
      {isStale && (
        <div
          role="alert"
          className="rounded-lg border border-status-partial-text/40 bg-status-partial-bg px-4 py-3 text-sm text-status-partial-text flex items-center gap-2.5"
        >
          <AlertTriangle className="w-4 h-4 shrink-0" />
          <span>
            Requirements were edited after analysis. Results are stale — re-run analysis to update.
          </span>
        </div>
      )}

      {/* Vendor Summary: 3 KPI Tiles per vendor */}
      <section className="space-y-3">
        <h2 className="text-section-title font-semibold text-text">Vendor summary</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {vendors.map((v) => (
            <div
              key={v.id}
              className="rounded-lg border border-border bg-background p-4 space-y-3.5"
            >
              <div className="border-b border-border pb-2 flex items-center justify-between">
                <h3 className="font-semibold text-sm text-text truncate" title={v.name}>
                  {v.name}
                </h3>
                {v.tag && (
                  <span className="rounded bg-muted-surface text-muted text-[11px] font-medium px-2 py-0.5">
                    {v.tag}
                  </span>
                )}
              </div>
              <div className="grid grid-cols-3 gap-2">
                <KpiTile
                  label="Vendor score"
                  value={
                    v.score !== null && v.score !== undefined ? String(v.score) : '—'
                  }
                  helpText={KPI_HELP_TEXT.vendor_score}
                />
                <KpiTile
                  label="Mandatory met"
                  value={`${v.mandatory_met} / ${v.mandatory_total}`}
                  helpText={KPI_HELP_TEXT.mandatory_met}
                />
                <KpiTile
                  label="Monthly cost"
                  value={formatINR(v.monthly_total_inr)}
                  helpText={KPI_HELP_TEXT.monthly_cost}
                />
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* Compliance Matrix */}
      <section className="space-y-3">
        <h2 className="text-section-title font-semibold text-text">Compliance matrix</h2>
        <div className="rounded-lg border border-border bg-background overflow-x-auto max-w-full">
          <table className="w-full text-left border-collapse text-xs">
            <thead>
              <tr className="border-b border-border bg-muted-surface">
                <th className="p-3 font-semibold text-text w-[340px] min-w-[280px]">
                  Requirement / Criterion
                </th>
                {vendors.map((v) => (
                  <th
                    key={v.id}
                    className="p-3 font-semibold text-text min-w-[200px]"
                  >
                    {v.name}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {/* Group 1: Mandatory requirements */}
              {mandatoryRequirements.length > 0 && (
                <>
                  <tr className="bg-surface/80">
                    <td
                      colSpan={vendors.length + 1}
                      className="px-3 py-2 font-semibold text-[11px] uppercase tracking-wider text-muted"
                    >
                      Mandatory requirements ({mandatoryRequirements.length})
                    </td>
                  </tr>
                  {mandatoryRequirements.map((req) => (
                    <tr key={req.id || req.code} className="hover:bg-surface/40 transition-colors">
                      <td className="p-3 align-top">
                        <div className="font-semibold text-text">{req.code}</div>
                        <div
                          tabIndex={0}
                          title={req.text}
                          className="text-muted truncate max-w-xs md:max-w-md focus:outline-none focus:ring-1 focus:ring-accent rounded cursor-default"
                        >
                          {req.text}
                        </div>
                      </td>
                      {vendors.map((v) => {
                        const finding = reqFindingsMap.get(`${v.id}:${req.id}`);
                        if (!finding) {
                          return (
                            <td key={v.id} className="p-3 align-middle text-muted">
                              —
                            </td>
                          );
                        }
                        return (
                          <td key={v.id} className="p-2 align-middle">
                            <button
                              type="button"
                              onClick={() =>
                                openDrawer(finding, v.name, `${req.code} · ${req.text}`)
                              }
                              className="w-full text-left p-1.5 rounded hover:bg-muted-surface transition-colors focus:outline-none focus:ring-1 focus:ring-accent"
                            >
                              <div className="flex items-center gap-1.5 flex-wrap">
                                <FindingStatusBadge
                                  status={normalizeFindingStatus(finding.status)}
                                />
                                {finding.needs_review && (
                                  <span className="inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[11px] font-medium border border-status-review text-status-review bg-transparent whitespace-nowrap">
                                    <Flag className="w-2.5 h-2.5 stroke-[2]" />
                                    <span>Needs review</span>
                                  </span>
                                )}
                              </div>
                            </button>
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </>
              )}

              {/* Group 2: Other requirements */}
              {otherRequirements.length > 0 && (
                <>
                  <tr className="bg-surface/80">
                    <td
                      colSpan={vendors.length + 1}
                      className="px-3 py-2 font-semibold text-[11px] uppercase tracking-wider text-muted"
                    >
                      Other requirements ({otherRequirements.length})
                    </td>
                  </tr>
                  {otherRequirements.map((req) => (
                    <tr key={req.id || req.code} className="hover:bg-surface/40 transition-colors">
                      <td className="p-3 align-top">
                        <div className="font-semibold text-text">{req.code}</div>
                        <div
                          tabIndex={0}
                          title={req.text}
                          className="text-muted truncate max-w-xs md:max-w-md focus:outline-none focus:ring-1 focus:ring-accent rounded cursor-default"
                        >
                          {req.text}
                        </div>
                      </td>
                      {vendors.map((v) => {
                        const finding = reqFindingsMap.get(`${v.id}:${req.id}`);
                        if (!finding) {
                          return (
                            <td key={v.id} className="p-3 align-middle text-muted">
                              —
                            </td>
                          );
                        }
                        return (
                          <td key={v.id} className="p-2 align-middle">
                            <button
                              type="button"
                              onClick={() =>
                                openDrawer(finding, v.name, `${req.code} · ${req.text}`)
                              }
                              className="w-full text-left p-1.5 rounded hover:bg-muted-surface transition-colors focus:outline-none focus:ring-1 focus:ring-accent"
                            >
                              <div className="flex items-center gap-1.5 flex-wrap">
                                <FindingStatusBadge
                                  status={normalizeFindingStatus(finding.status)}
                                />
                                {finding.needs_review && (
                                  <span className="inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[11px] font-medium border border-status-review text-status-review bg-transparent whitespace-nowrap">
                                    <Flag className="w-2.5 h-2.5 stroke-[2]" />
                                    <span>Needs review</span>
                                  </span>
                                )}
                              </div>
                            </button>
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </>
              )}

              {/* Group 3: Criteria */}
              {judgedCriteria.length > 0 && (
                <>
                  <tr className="bg-surface/80">
                    <td
                      colSpan={vendors.length + 1}
                      className="px-3 py-2 font-semibold text-[11px] uppercase tracking-wider text-muted"
                    >
                      Criteria ({judgedCriteria.length})
                    </td>
                  </tr>
                  {judgedCriteria.map((c: any) => (
                    <tr key={c.key} className="hover:bg-surface/40 transition-colors">
                      <td className="p-3 align-top">
                        <div className="font-semibold text-text">{c.name}</div>
                        {c.guidance && (
                          <div
                            tabIndex={0}
                            title={c.guidance}
                            className="text-muted truncate max-w-xs md:max-w-md focus:outline-none focus:ring-1 focus:ring-accent rounded cursor-default"
                          >
                            {c.guidance}
                          </div>
                        )}
                      </td>
                      {vendors.map((v) => {
                        const finding = critFindingsMap.get(`${v.id}:${c.key}`);
                        if (!finding) {
                          return (
                            <td key={v.id} className="p-3 align-middle text-muted">
                              —
                            </td>
                          );
                        }
                        return (
                          <td key={v.id} className="p-2 align-middle">
                            <button
                              type="button"
                              onClick={() => openDrawer(finding, v.name, c.name)}
                              className="w-full text-left p-1.5 rounded hover:bg-muted-surface transition-colors focus:outline-none focus:ring-1 focus:ring-accent"
                            >
                              <div className="flex items-center gap-1.5 flex-wrap">
                                <FindingStatusBadge
                                  status={normalizeFindingStatus(finding.status)}
                                />
                                {finding.needs_review && (
                                  <span className="inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[11px] font-medium border border-status-review text-status-review bg-transparent whitespace-nowrap">
                                    <Flag className="w-2.5 h-2.5 stroke-[2]" />
                                    <span>Needs review</span>
                                  </span>
                                )}
                              </div>
                            </button>
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </>
              )}
            </tbody>
          </table>
        </div>
      </section>

      {/* Risks: findings not tied to a requirement or criterion */}
      <section className="space-y-3">
        <h2 className="text-section-title font-semibold text-text">Risks</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {vendors.map((v) => {
            const vRisks = standaloneRisks.filter((r) => String(r.vendor_id) === v.id);
            return (
              <div
                key={v.id}
                className="rounded-lg border border-border bg-background p-4 space-y-3"
              >
                <div className="font-semibold text-sm text-text border-b border-border pb-2">
                  {v.name}
                </div>
                {vRisks.length === 0 ? (
                  <div className="text-xs text-muted py-2">
                    No standalone risks identified
                  </div>
                ) : (
                  <div className="space-y-2">
                    {vRisks.map((risk) => (
                      <button
                        key={risk.id}
                        type="button"
                        onClick={() => openDrawer(risk, v.name, 'Standalone risk')}
                        className="w-full text-left p-3 rounded border border-border bg-surface hover:bg-muted-surface transition-colors space-y-2 focus:outline-none focus:ring-1 focus:ring-accent block"
                      >
                        <div className="flex items-center gap-1.5 flex-wrap">
                          {risk.risk_types?.map((rt) => (
                            <RiskBadge
                              key={rt}
                              type={rt as any}
                              severity={risk.severity as any}
                            />
                          ))}
                          {risk.severity && (
                            <span className="text-[11px] text-muted font-medium">
                              ({risk.severity} severity)
                            </span>
                          )}
                        </div>
                        {risk.evidence_quote && (
                          <p className="text-xs italic text-muted line-clamp-2">
                            &ldquo;{risk.evidence_quote}&rdquo;
                          </p>
                        )}
                        {risk.clarification_question && (
                          <p className="text-xs text-text line-clamp-2">
                            {risk.clarification_question}
                          </p>
                        )}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </section>

      {/* Cost Comparison Table */}
      <section className="space-y-3">
        <h2 className="text-section-title font-semibold text-text">Cost comparison</h2>
        <div className="rounded-lg border border-border bg-background overflow-x-auto max-w-full">
          <table className="w-full text-left border-collapse text-xs">
            <thead>
              <tr className="border-b border-border bg-muted-surface">
                <th className="p-3 font-semibold text-text w-[220px] min-w-[180px]">
                  Cost item
                </th>
                {vendors.map((v) => (
                  <th key={v.id} className="p-3 font-semibold text-text min-w-[200px]">
                    {v.name}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {/* Monthly base */}
              <tr>
                <td className="p-3 font-medium text-text">Monthly base</td>
                {vendors.map((v) => {
                  const cb = costsByVendor.get(v.id);
                  return (
                    <td key={v.id} className="p-3 font-medium text-text">
                      {formatINR(cb?.monthly_base)}
                    </td>
                  );
                })}
              </tr>
              {/* GST 18% */}
              <tr>
                <td className="p-3 font-medium text-text">GST 18%</td>
                {vendors.map((v) => {
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
              <tr className="bg-surface/50 font-semibold">
                <td className="p-3 text-text">Monthly total</td>
                {vendors.map((v) => {
                  const cb = costsByVendor.get(v.id);
                  return (
                    <td key={v.id} className="p-3 text-text font-bold">
                      {formatINR(cb?.monthly_total)}
                    </td>
                  );
                })}
              </tr>
              {/* Included */}
              <tr>
                <td className="p-3 align-top font-medium text-text">Included</td>
                {vendors.map((v) => {
                  const cb = costsByVendor.get(v.id);
                  const items = cb?.included || [];
                  return (
                    <td key={v.id} className="p-3 align-top">
                      {items.length === 0 ? (
                        <span className="text-muted">—</span>
                      ) : (
                        <ul className="space-y-1">
                          {items.map((it, idx) => (
                            <li key={idx} className="leading-snug">
                              {it}
                            </li>
                          ))}
                        </ul>
                      )}
                    </td>
                  );
                })}
              </tr>
              {/* Excluded */}
              <tr>
                <td className="p-3 align-top font-medium text-text">Excluded</td>
                {vendors.map((v) => {
                  const cb = costsByVendor.get(v.id);
                  const items = cb?.excluded || [];
                  return (
                    <td key={v.id} className="p-3 align-top">
                      {items.length === 0 ? (
                        <span className="text-muted">—</span>
                      ) : (
                        <ul className="space-y-1">
                          {items.map((it, idx) => (
                            <li key={idx} className="leading-snug">
                              {it}
                            </li>
                          ))}
                        </ul>
                      )}
                    </td>
                  );
                })}
              </tr>
              {/* Optional */}
              <tr>
                <td className="p-3 align-top font-medium text-text">Optional</td>
                {vendors.map((v) => {
                  const cb = costsByVendor.get(v.id);
                  const items = cb?.optional || [];
                  return (
                    <td key={v.id} className="p-3 align-top">
                      {items.length === 0 ? (
                        <span className="text-muted">—</span>
                      ) : (
                        <ul className="space-y-1">
                          {items.map((it, idx) => (
                            <li key={idx} className="leading-snug">
                              {it}
                            </li>
                          ))}
                        </ul>
                      )}
                    </td>
                  );
                })}
              </tr>
              {/* Unknown */}
              <tr>
                <td className="p-3 align-top font-medium text-text">Unknown cost</td>
                {vendors.map((v) => {
                  const cb = costsByVendor.get(v.id);
                  const items = cb?.unknown || [];
                  return (
                    <td key={v.id} className="p-3 align-top">
                      {items.length === 0 ? (
                        <span className="text-muted">—</span>
                      ) : (
                        <ul className="space-y-1">
                          {items.map((it, idx) => (
                            <li key={idx} className="leading-snug flex items-start gap-1.5">
                              <span className="inline-block shrink-0 px-1.5 py-0.5 rounded text-[10px] font-medium border border-border bg-surface text-muted">
                                Unknown
                              </span>
                              <span>{it}</span>
                            </li>
                          ))}
                        </ul>
                      )}
                    </td>
                  );
                })}
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      {/* Clarifications */}
      <section className="space-y-3">
        <h2 className="text-section-title font-semibold text-text">Clarifications</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {vendors.map((v) => {
            const questions = results?.clarifications?.[v.id] || [];
            return (
              <div
                key={v.id}
                className="rounded-lg border border-border bg-background p-4 space-y-3"
              >
                <div className="font-semibold text-sm text-text border-b border-border pb-2">
                  {v.name}
                </div>
                {questions.length === 0 ? (
                  <div className="text-xs text-muted py-2">
                    No clarification questions
                  </div>
                ) : (
                  <ul className="space-y-2">
                    {questions.map((q, idx) => (
                      <li
                        key={idx}
                        className="rounded-md border border-border bg-surface p-3 text-xs text-text leading-relaxed"
                      >
                        <span className="text-muted mr-1.5 font-medium">{idx + 1}.</span>
                        <span>{q}</span>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            );
          })}
        </div>
      </section>

      {/* Finding Detail Drawer */}
      <FindingDetailDrawer
        open={drawerOpen}
        onOpenChange={setDrawerOpen}
        finding={selectedFinding}
        vendorName={drawerVendorName}
        itemTitle={drawerItemTitle}
      />
    </div>
  );
};

export default ComparisonPage;
