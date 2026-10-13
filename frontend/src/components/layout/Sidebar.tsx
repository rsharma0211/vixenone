import React, { useEffect, useState } from 'react';
import { NavLink, useLocation, useNavigate } from 'react-router-dom';
import { List, Plus, Settings, HelpCircle } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Separator } from '@/components/ui/separator';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import { apiClient } from '@/lib/api/client';
import { getEvaluationEntryPath } from '@/lib/evaluationRouting';
import type { EvaluationSummaryResponse } from '@/lib/types';

interface SidebarProps {
  collapsed: boolean;
}

export const Sidebar: React.FC<SidebarProps> = ({ collapsed }) => {
  const location = useLocation();
  const navigate = useNavigate();

  const [recentEvaluations, setRecentEvaluations] = useState<EvaluationSummaryResponse[]>([]);

  useEffect(() => {
    let isMounted = true;
    apiClient.listEvaluations()
      .then((data) => {
        if (isMounted && data.evaluations) {
          setRecentEvaluations(data.evaluations.slice(0, 3));
        }
      })
      .catch(() => {
        // Silently ignore sidebar recent fetch errors
      });
    return () => {
      isMounted = false;
    };
  }, [location.pathname]);

  // Check if current route is an evaluation and which one
  const match = location.pathname.match(/\/evaluations\/([^/]+)/);
  const currentEvaluationId = match ? match[1] : null;

  const isEvaluationsActive =
    location.pathname === '/evaluations' ||
    (location.pathname.startsWith('/evaluations/') && !location.pathname.startsWith('/evaluations/new'));

  const isSettingsActive = location.pathname === '/settings';

  return (
    <TooltipProvider delayDuration={200}>
      <aside
        className={cn(
          "fixed top-14 left-0 bottom-0 bg-surface border-r border-border z-30 transition-all duration-200 flex flex-col justify-between select-none",
          collapsed ? "w-16" : "w-60"
        )}
      >
        {/* Top Section */}
        <div className="p-3 space-y-4">
          {/* New evaluation action */}
          {collapsed ? (
            <Tooltip>
              <TooltipTrigger asChild>
                <button
                  type="button"
                  onClick={() => navigate('/evaluations/new')}
                  className="w-10 h-10 mx-auto rounded-lg bg-accent text-navy font-semibold flex items-center justify-center hover:bg-accent-hover transition-colors shadow-sm focus:outline-none focus:ring-2 focus:ring-ring"
                >
                  <Plus className="w-5 h-5 stroke-[2.5]" />
                </button>
              </TooltipTrigger>
              <TooltipContent side="right">New evaluation</TooltipContent>
            </Tooltip>
          ) : (
            <Button
              variant="primary"
              onClick={() => navigate('/evaluations/new')}
              className="w-full justify-center gap-1.5 font-semibold"
            >
              <Plus className="w-4 h-4 stroke-[2.5]" />
              <span>New evaluation</span>
            </Button>
          )}

          {/* Navigation Items */}
          <nav className="space-y-1">
            {collapsed ? (
              <Tooltip>
                <TooltipTrigger asChild>
                  <NavLink
                    to="/evaluations"
                    className={cn(
                      "w-10 h-10 mx-auto rounded-lg flex items-center justify-center transition-colors",
                      isEvaluationsActive
                        ? "bg-muted-surface text-navy font-semibold"
                        : "text-muted hover:bg-surface hover:text-text"
                    )}
                  >
                    <List className="w-5 h-5" />
                  </NavLink>
                </TooltipTrigger>
                <TooltipContent side="right">Evaluations</TooltipContent>
              </Tooltip>
            ) : (
              <NavLink
                to="/evaluations"
                className={cn(
                  "flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm transition-colors",
                  isEvaluationsActive
                    ? "bg-muted-surface text-navy font-semibold"
                    : "text-text hover:bg-background"
                )}
              >
                <List className="w-4 h-4" />
                <span>Evaluations</span>
              </NavLink>
            )}
          </nav>

          {/* RECENT Section (Expanded only) */}
          {!collapsed && recentEvaluations.length > 0 && (
            <div className="pt-2 space-y-1.5">
              <div className="px-3 text-xs font-medium text-muted uppercase tracking-wider">
                Recent
              </div>
              <div className="space-y-0.5">
                {recentEvaluations.map((ev) => {
                  const isOpen =
                    currentEvaluationId === ev.id ||
                    (currentEvaluationId === null &&
                      location.pathname.includes(ev.id));
                  return (
                    <button
                      key={ev.id}
                      type="button"
                      onClick={() => navigate(getEvaluationEntryPath(ev))}
                      title={ev.title || ev.name}
                      className={cn(
                        "w-full text-left px-3 py-1.5 rounded-md text-xs truncate transition-colors block",
                        isOpen
                          ? "text-navy font-semibold bg-background"
                          : "text-text hover:bg-background/80"
                      )}
                    >
                      {ev.name_short || ev.title || ev.name}
                    </button>
                  );
                })}
              </div>
            </div>
          )}
        </div>

        {/* Bottom Pinned Section */}
        <div className="p-3">
          <Separator className="mb-2" />
          <div className="space-y-1">
            {collapsed ? (
              <>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <NavLink
                      to="/settings"
                      aria-label="Settings"
                      className={cn(
                        "w-10 h-10 mx-auto rounded-lg flex items-center justify-center transition-colors",
                        isSettingsActive
                          ? "bg-muted-surface text-navy font-semibold"
                          : "text-muted hover:bg-background hover:text-text"
                      )}
                    >
                      <Settings className="w-5 h-5" />
                    </NavLink>
                  </TooltipTrigger>
                  <TooltipContent side="right">Settings</TooltipContent>
                </Tooltip>

                <Tooltip>
                  <TooltipTrigger asChild>
                    <button
                      type="button"
                      aria-label="Help"
                      className="w-10 h-10 mx-auto rounded-lg flex items-center justify-center text-muted hover:bg-background hover:text-text transition-colors"
                    >
                      <HelpCircle className="w-5 h-5" />
                    </button>
                  </TooltipTrigger>
                  <TooltipContent side="right">Help</TooltipContent>
                </Tooltip>
              </>
            ) : (
              <>
                <NavLink
                  to="/settings"
                  className={cn(
                    "w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm transition-colors",
                    isSettingsActive
                      ? "bg-muted-surface text-navy font-semibold"
                      : "text-muted hover:bg-background hover:text-text"
                  )}
                >
                  <Settings className="w-4 h-4" />
                  <span>Settings</span>
                </NavLink>
                <button
                  type="button"
                  className="w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm text-muted hover:bg-background hover:text-text transition-colors"
                >
                  <HelpCircle className="w-4 h-4" />
                  <span>Help</span>
                </button>
              </>
            )}
          </div>
        </div>
      </aside>
    </TooltipProvider>
  );
};
