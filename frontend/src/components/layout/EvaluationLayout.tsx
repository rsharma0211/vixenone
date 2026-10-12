import React, { useEffect, useState } from 'react';
import { NavLink, Outlet, useParams, Link } from 'react-router-dom';
import { mockEvaluations } from '@/lib/mockData';
import { apiClient } from '@/lib/api/client';
import { cn } from '@/lib/utils';

export const EvaluationLayout: React.FC = () => {
  const { id } = useParams<{ id: string }>();

  const [evaluation, setEvaluation] = useState(() =>
    mockEvaluations.find((ev) => ev.id === id) || mockEvaluations[0]
  );

  useEffect(() => {
    if (id) {
      apiClient.getEvaluation(id)
        .then((detail) => {
          setEvaluation((prev) => ({
            ...prev,
            id: detail.id,
            name: detail.title,
            name_short: detail.title.split('—')[0]?.trim() || detail.title,
            contract_type: detail.category,
            total_requirements: detail.requirements_count,
          }));
        })
        .catch(() => {});
    }
  }, [id]);

  const tabs = [
    { name: 'Requirements', path: `/evaluations/${evaluation.id}/requirements` },
    { name: 'Comparison', path: `/evaluations/${evaluation.id}/comparison` },
    { name: 'Recommendation', path: `/evaluations/${evaluation.id}/recommendation` },
  ];

  return (
    <div className="space-y-6">
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
          <span className="truncate">{evaluation.name_short}</span>
        </nav>

        <h1 className="text-page-title text-text font-semibold tracking-tight">
          {evaluation.name}
        </h1>

        <p className="text-body text-muted">
          {evaluation.location} · {evaluation.contract_type} ·{' '}
          {evaluation.total_requirements} requirements ({evaluation.mandatory_requirements} mandatory)
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
                "pb-3 text-sm font-medium transition-colors border-b-2 -mb-px",
                isActive
                  ? "border-accent text-navy font-semibold"
                  : "border-transparent text-muted hover:text-text"
              )
            }
          >
            {tab.name}
          </NavLink>
        ))}
      </div>

      {/* Tab Content */}
      <div className="pt-2">
        <Outlet context={{ evaluation }} />
      </div>
    </div>
  );
};
