import React, { useEffect, useState, useMemo, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Plus,
  Search,
  MoreHorizontal,
  FileText,
  AlertCircle,
  Trash2,
  ExternalLink,
} from 'lucide-react';
import { apiClient } from '@/lib/api/client';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { LifecycleStatus } from '@/components/status/LifecycleStatus';
import type {
  EvaluationsListResponse,
  EvaluationSummaryResponse,
  EvaluationKPIs,
} from '@/lib/types';

type KpiFilter = 'total' | 'needs_action' | 'analysed' | 'open_clarifications' | null;

export const EvaluationsListPage: React.FC = () => {
  const navigate = useNavigate();

  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [evaluations, setEvaluations] = useState<EvaluationSummaryResponse[]>([]);
  const [kpis, setKpis] = useState<EvaluationKPIs>({
    total: 0,
    needs_action: 0,
    analysed: 0,
    open_clarifications: 0,
  });

  // Filter & Search states
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [activeKpiTile, setActiveKpiTile] = useState<KpiFilter>(null);

  // Delete modal state
  const [evalToDelete, setEvalToDelete] = useState<EvaluationSummaryResponse | null>(null);
  const [deleting, setDeleting] = useState<boolean>(false);

  const fetchEvaluations = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const data: EvaluationsListResponse = await apiClient.listEvaluations();
      setEvaluations(data.evaluations || []);
      setKpis(data.kpis);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to load evaluations');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchEvaluations();
  }, [fetchEvaluations]);

  const handleTileClick = (filter: KpiFilter) => {
    if (activeKpiTile === filter) {
      setActiveKpiTile(null);
      setStatusFilter('all');
    } else {
      setActiveKpiTile(filter);
      if (filter === 'needs_action') {
        setStatusFilter('needs_action');
      } else if (filter === 'analysed') {
        setStatusFilter('analysed');
      } else {
        setStatusFilter('all');
      }
    }
  };

  const handleRowClick = (ev: EvaluationSummaryResponse) => {
    if (ev.status === 'draft') {
      navigate(`/evaluations/${ev.id}/upload`);
    } else if (ev.status === 'requirements_review') {
      navigate(`/evaluations/${ev.id}/requirements`);
    } else {
      // analysed or stale
      navigate(`/evaluations/${ev.id}/comparison`);
    }
  };

  const handleDeleteConfirm = async () => {
    if (!evalToDelete) return;
    try {
      setDeleting(true);
      await apiClient.deleteEvaluation(evalToDelete.id);
      setEvalToDelete(null);
      await fetchEvaluations();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to delete evaluation');
    } finally {
      setDeleting(false);
    }
  };

  // Filtered evaluations
  const filteredEvaluations = useMemo(() => {
    return evaluations.filter((ev) => {
      // 1. Text search query
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase().trim();
        const matchesName = (ev.title || ev.name).toLowerCase().includes(q);
        const matchesCategory = ev.category.toLowerCase().includes(q);
        if (!matchesName && !matchesCategory) return false;
      }

      // 2. Status filter
      if (statusFilter === 'draft' && ev.status !== 'draft') return false;
      if (statusFilter === 'requirements_review' && ev.status !== 'requirements_review') return false;
      if (statusFilter === 'analysed' && ev.status !== 'analysed') return false;
      if (statusFilter === 'stale' && ev.status !== 'stale') return false;
      if (
        statusFilter === 'needs_action' &&
        ev.status !== 'requirements_review' &&
        ev.status !== 'stale'
      ) {
        return false;
      }

      // 3. Active KPI tile filter
      if (activeKpiTile === 'needs_action') {
        if (ev.status !== 'requirements_review' && ev.status !== 'stale') return false;
      } else if (activeKpiTile === 'analysed') {
        if (ev.status !== 'analysed') return false;
      } else if (activeKpiTile === 'open_clarifications') {
        // Show evaluations that have been analysed or are in review
        if (ev.status !== 'analysed' && ev.status !== 'stale') return false;
      }

      return true;
    });
  }, [evaluations, searchQuery, statusFilter, activeKpiTile]);

  // Format date
  const formatDate = (dateStr: string) => {
    try {
      const d = new Date(dateStr);
      return d.toLocaleDateString('en-GB', {
        day: '2-digit',
        month: 'short',
        year: 'numeric',
      });
    } catch {
      return dateStr;
    }
  };

  if (loading) {
    return (
      <div className="space-y-6 text-left">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-page-title text-text font-semibold tracking-tight">
              Evaluations
            </h1>
            <p className="text-body text-muted">
              Compare vendor proposals against your requirements.
            </p>
          </div>
          <Button variant="primary" disabled className="gap-1.5 font-semibold">
            <Plus className="w-4 h-4 stroke-[2.5]" />
            <span>New evaluation</span>
          </Button>
        </div>

        {/* Loading Skeleton */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="h-24 rounded-lg border border-border bg-background p-4 animate-pulse" />
          ))}
        </div>
        <div className="h-64 rounded-lg border border-border bg-background p-12 text-center text-muted text-sm flex items-center justify-center">
          Loading evaluations...
        </div>
      </div>
    );
  }

  if (error && evaluations.length === 0) {
    return (
      <div className="space-y-6 text-left">
        <div>
          <h1 className="text-page-title text-text font-semibold tracking-tight">
            Evaluations
          </h1>
          <p className="text-body text-muted">
            Compare vendor proposals against your requirements.
          </p>
        </div>
        <div className="rounded-lg border border-status-noncompliant-text/30 bg-status-noncompliant-bg p-6 text-center text-sm space-y-3">
          <div className="flex items-center justify-center gap-2 text-status-noncompliant-text font-medium">
            <AlertCircle className="w-5 h-5" />
            <span>Failed to load evaluations: {error}</span>
          </div>
          <Button variant="outline" size="sm" onClick={fetchEvaluations}>
            Try again
          </Button>
        </div>
      </div>
    );
  }

  // S2-empty state when total evaluations count is 0
  if (evaluations.length === 0) {
    return (
      <div className="space-y-6 text-left">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-page-title text-text font-semibold tracking-tight">
              Evaluations
            </h1>
            <p className="text-body text-muted">
              Compare vendor proposals against your requirements.
            </p>
          </div>
        </div>

        <div className="py-24 text-center max-w-md mx-auto space-y-4">
          <div className="w-12 h-12 rounded-lg bg-surface flex items-center justify-center mx-auto text-muted border border-border">
            <FileText className="w-6 h-6 stroke-[1.5]" />
          </div>
          <div className="space-y-1">
            <h2 className="text-lg font-semibold text-text">No evaluations yet</h2>
            <p className="text-sm text-muted leading-relaxed">
              Upload a requirements document and 2–3 vendor proposals to get an evidence-backed comparison.
            </p>
          </div>
          <div className="pt-2">
            <Button
              variant="primary"
              onClick={() => navigate('/evaluations/new')}
              className="gap-1.5 font-semibold"
            >
              <Plus className="w-4 h-4 stroke-[2.5]" />
              <span>New evaluation</span>
            </Button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6 text-left">
      {/* Page Title Row */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-page-title text-text font-semibold tracking-tight">
            Evaluations
          </h1>
          <p className="text-body text-muted">
            Compare vendor proposals against your requirements.
          </p>
        </div>
        <Button
          variant="primary"
          onClick={() => navigate('/evaluations/new')}
          className="gap-1.5 font-semibold"
        >
          <Plus className="w-4 h-4 stroke-[2.5]" />
          <span>New evaluation</span>
        </Button>
      </div>

      {error && (
        <div className="rounded-lg border border-status-noncompliant-text/30 bg-status-noncompliant-bg px-4 py-3 text-sm text-status-noncompliant-text flex items-center gap-2">
          <AlertCircle className="w-4 h-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* 4 KPI Tiles */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[
          { id: 'total', label: 'Evaluations', value: kpis.total },
          { id: 'needs_action', label: 'Needs action', value: kpis.needs_action },
          { id: 'analysed', label: 'Analysed', value: kpis.analysed },
          { id: 'open_clarifications', label: 'Open clarifications', value: kpis.open_clarifications },
        ].map((tile) => {
          const isTileActive = activeKpiTile === tile.id;
          return (
            <button
              key={tile.id}
              type="button"
              onClick={() => handleTileClick(tile.id as KpiFilter)}
              className={`rounded-lg border p-4 text-left transition-all ${
                isTileActive
                  ? 'border-navy ring-2 ring-navy bg-surface shadow-sm'
                  : 'border-border bg-background hover:bg-surface/50'
              }`}
            >
              <div className="text-xs font-medium text-muted uppercase tracking-wider">
                {tile.label}
              </div>
              <div className="text-2xl sm:text-3xl font-bold text-navy mt-1 tracking-tight">
                {tile.value}
              </div>
            </button>
          );
        })}
      </div>

      {/* Toolbar */}
      <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-3 pt-2">
        <div className="relative w-full sm:w-80">
          <Search className="absolute left-3 top-2.5 h-4 w-4 text-muted pointer-events-none" />
          <Input
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search evaluations"
            className="pl-9 h-9"
          />
        </div>

        <div className="w-full sm:w-48">
          <select
            value={statusFilter}
            onChange={(e) => {
              setStatusFilter(e.target.value);
              setActiveKpiTile(null);
            }}
            aria-label="Filter evaluations by status"
            className="flex h-9 w-full rounded-lg border border-border bg-background px-3 py-1 text-sm text-text focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring focus-visible:border-ring"
          >
            <option value="all">Status: All</option>
            <option value="draft">Status: Draft</option>
            <option value="requirements_review">Status: Requirements review</option>
            <option value="analysed">Status: Analysed</option>
            <option value="stale">Status: Stale</option>
            <option value="needs_action">Status: Needs action</option>
          </select>
        </div>
      </div>

      {/* Table */}
      <div className="rounded-lg border border-border bg-background shadow-sm overflow-hidden">
        <table className="w-full border-collapse text-left">
          <thead>
            <tr className="border-b border-border bg-surface text-table-header text-muted">
              <th className="py-3 px-4 w-[40%] font-medium">NAME</th>
              <th className="py-3 px-4 w-[18%] font-medium">CATEGORY</th>
              <th className="py-3 px-4 w-[7%] font-medium text-right">VENDORS</th>
              <th className="py-3 px-4 w-[22%] font-medium">STATUS</th>
              <th className="py-3 px-4 w-[10%] font-medium">UPDATED</th>
              <th className="py-3 px-4 w-[3%] font-medium text-center">···</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {filteredEvaluations.length === 0 ? (
              <tr>
                <td colSpan={6} className="py-8 text-center text-sm text-muted">
                  No evaluations match the selected filter.
                </td>
              </tr>
            ) : (
              filteredEvaluations.map((ev) => {
                const isDraft = ev.status === 'draft';
                const subline = isDraft
                  ? 'Mumbai · Not extracted yet'
                  : `Mumbai · ${ev.total_requirements || 0} requirements`;

                // Map lifecycle status string to LifecycleStatus component prop
                const lifecycleProp =
                  ev.status === 'draft'
                    ? 'Draft'
                    : ev.status === 'requirements_review'
                    ? 'Requirements review'
                    : ev.status === 'analysed'
                    ? 'Analysed'
                    : 'Stale';

                return (
                  <tr
                    key={ev.id}
                    onClick={() => handleRowClick(ev)}
                    className="hover:bg-surface/60 transition-colors cursor-pointer group"
                  >
                    {/* Name column */}
                    <td className="py-3.5 px-4">
                      <div className="space-y-0.5">
                        <div className="text-sm font-semibold text-text group-hover:text-navy group-hover:underline truncate max-w-md">
                          {ev.title || ev.name}
                        </div>
                        <div className="text-xs text-muted">
                          {subline}
                        </div>
                      </div>
                    </td>

                    {/* Category */}
                    <td className="py-3.5 px-4 text-sm text-muted truncate">
                      {ev.category}
                    </td>

                    {/* Vendors count */}
                    <td className="py-3.5 px-4 text-sm text-text font-medium text-right">
                      {ev.vendors_count}
                    </td>

                    {/* Status */}
                    <td className="py-3.5 px-4">
                      <LifecycleStatus status={lifecycleProp} />
                    </td>

                    {/* Updated */}
                    <td className="py-3.5 px-4 text-xs text-muted whitespace-nowrap">
                      {formatDate(ev.updated_at)}
                    </td>

                    {/* Actions menu */}
                    <td
                      className="py-3.5 px-4 text-center"
                      onClick={(e) => e.stopPropagation()}
                    >
                      <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                          <button
                            type="button"
                            aria-label="Evaluation options"
                            className="p-1 rounded-md text-muted hover:text-text hover:bg-surface transition-colors"
                          >
                            <MoreHorizontal className="w-4 h-4" />
                          </button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end">
                          <DropdownMenuItem onClick={() => handleRowClick(ev)}>
                            <ExternalLink className="w-3.5 h-3.5 mr-2" />
                            <span>Open</span>
                          </DropdownMenuItem>
                          <DropdownMenuItem
                            onClick={() => setEvalToDelete(ev)}
                            className="text-status-noncompliant-text focus:text-status-noncompliant-text"
                          >
                            <Trash2 className="w-3.5 h-3.5 mr-2" />
                            <span>Delete</span>
                          </DropdownMenuItem>
                        </DropdownMenuContent>
                      </DropdownMenu>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>

        {/* Count under table */}
        <div className="border-t border-border bg-background px-4 py-2.5 text-xs text-muted">
          {filteredEvaluations.length} evaluation{filteredEvaluations.length === 1 ? '' : 's'}
        </div>
      </div>

      {/* Delete Confirmation Dialog */}
      <Dialog open={evalToDelete !== null} onOpenChange={(open) => !open && setEvalToDelete(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete evaluation</DialogTitle>
            <DialogDescription>
              Are you sure you want to delete &ldquo;
              {evalToDelete ? evalToDelete.title || evalToDelete.name : ''}
              &rdquo;? All uploaded documents and analysis findings for this evaluation will be permanently removed.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setEvalToDelete(null)}
              disabled={deleting}
            >
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={handleDeleteConfirm}
              disabled={deleting}
            >
              {deleting ? 'Deleting...' : 'Delete evaluation'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default EvaluationsListPage;
