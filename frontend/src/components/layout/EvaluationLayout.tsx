import React, { useEffect, useState, useCallback, useMemo } from 'react';
import { NavLink, Outlet, useParams, Link } from 'react-router-dom';
import { apiClient } from '@/lib/api/client';
import { cn } from '@/lib/utils';
import type { EvaluationDetailResponse } from '@/lib/types';

export interface EvaluationLayoutContext {
  evaluationDetail: EvaluationDetailResponse | null;
  savedRequirementCount: number;
  savedMandatoryCount: number;
  refresh: () => Promise<void>;
}

export const EvaluationLayout: React.FC = () => {
  const { id } = useParams<{ id: string }>();

  const [evaluationDetail, setDetail] = useState<EvaluationDetailResponse | null>(null);
  const [savedRequirementCount, setSavedRequirementCount] = useState<number>(0);
  const [savedMandatoryCount, setSavedMandatoryCount] = useState<number>(0);

  useEffect(() => {
    let active = true;
    if (id) {
      Promise.all([
        apiClient.getEvaluation(id),
        apiClient.getRequirements(id).catch(() => []),
      ])
        .then(([detail, reqs]) => {
          if (!active) return;
          setDetail(detail);
          setSavedRequirementCount(reqs.length);
          setSavedMandatoryCount(reqs.filter((r) => r.mandatory).length);
        })
        .catch(() => {});
    }
    return () => {
      active = false;
    };
  }, [id]);

  const refresh = useCallback(async () => {
    if (!id) return;
    try {
      const [detail, reqs] = await Promise.all([
        apiClient.getEvaluation(id),
        apiClient.getRequirements(id).catch(() => []),
      ]);
      setDetail(detail);
      setSavedRequirementCount(reqs.length);
      setSavedMandatoryCount(reqs.filter((r) => r.mandatory).length);
    } catch {
      // Preserve current header state on error
    }
  }, [id]);

  const outletContext = useMemo<EvaluationLayoutContext>(
    () => ({
      evaluationDetail,
      savedRequirementCount,
      savedMandatoryCount,
      refresh,
    }),
    [evaluationDetail, savedRequirementCount, savedMandatoryCount, refresh]
  );

  const title = evaluationDetail?.title || '';
  const shortTitle = title.includes('—') ? title.split('—')[0].trim() : title;
  const category = evaluationDetail?.category || '';

  const tabs = [
    { name: 'Requirements', path: `/evaluations/${id}/requirements` },
    { name: 'Comparison', path: `/evaluations/${id}/comparison` },
    { name: 'Recommendation', path: `/evaluations/${id}/recommendation` },
  ];

  return (
    <div className="space-y-6 text-left">
      {/* Header section: Breadcrumb -> Title -> Meta */}
      <div className="space-y-1.5">
        <nav className="flex items-center text-xs text-muted">
          <Link
            to="/evaluations"
            className="hover:text-text transition-colors"
          >
            Evaluations
          </Link>
          <span className="mx-1.5">/</span>
          <span className="truncate">{shortTitle || 'Evaluation'}</span>
        </nav>

        <h1 className="text-page-title text-text font-semibold tracking-tight">
          {title || 'Evaluation'}
        </h1>

        <p className="text-body text-muted">
          Mumbai · {category ? `${category} · ` : ''}
          {savedRequirementCount} requirement{savedRequirementCount === 1 ? '' : 's'} (
          {savedMandatoryCount} mandatory)
        </p>
      </div>

      {/* Tabs navigation row */}
      <div className="border-b border-border flex items-center gap-8 -mb-px">
        {tabs.map((tab) => (
          <NavLink
            key={tab.name}
            to={tab.path}
            className={({ isActive }) =>
              cn(
                'pb-3 text-sm font-medium transition-colors border-b-2 -mb-px',
                isActive
                  ? 'border-accent text-navy font-semibold'
                  : 'border-transparent text-muted hover:text-text'
              )
            }
          >
            {tab.name}
          </NavLink>
        ))}
      </div>

      {/* Tab Content */}
      <div className="pt-2">
        <Outlet context={outletContext} />
      </div>
    </div>
  );
};
