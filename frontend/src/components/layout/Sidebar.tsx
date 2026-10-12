import React from 'react';
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
import { mockEvaluations } from '@/lib/mockData';

interface SidebarProps {
  collapsed: boolean;
}

export const Sidebar: React.FC<SidebarProps> = ({ collapsed }) => {
  const location = useLocation();
  const navigate = useNavigate();

  // Find recent evaluations (first 3 from mockData)
  const recentEvaluations = mockEvaluations.slice(0, 3);

  // Check if current route is an evaluation and which one
  const match = location.pathname.match(/\/evaluations\/([^/]+)/);
  const currentEvaluationId = match ? match[1] : null;

  const isEvaluationsActive =
    location.pathname === '/evaluations' ||
    location.pathname.startsWith('/evaluations/');

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
                  className="w-10 h-10 mx-auto rounded-lg bg-accent text-white flex items-center justify-center hover:bg-accent-hover transition-colors shadow-sm focus:outline-none focus:ring-2 focus:ring-accent"
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
              className="w-full justify-center gap-1.5 font-medium"
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
                        ? "bg-accent-tint text-accent"
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
                    ? "bg-accent-tint text-accent font-medium"
                    : "text-text hover:bg-background"
                )}
              >
                <List className="w-4 h-4" />
                <span>Evaluations</span>
              </NavLink>
            )}
          </nav>

          {/* RECENT Section (Expanded only) */}
          {!collapsed && (
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
                      onClick={() =>
                        navigate(`/evaluations/${ev.id}/requirements`)
                      }
                      title={ev.name}
                      className={cn(
                        "w-full text-left px-3 py-1.5 rounded-md text-xs truncate transition-colors block",
                        isOpen
                          ? "text-accent font-medium bg-background"
                          : "text-text hover:bg-background/80"
                      )}
                    >
                      {ev.name_short}
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
                    <button
                      type="button"
                      aria-label="Settings"
                      className="w-10 h-10 mx-auto rounded-lg flex items-center justify-center text-muted hover:bg-background hover:text-text transition-colors"
                    >
                      <Settings className="w-5 h-5" />
                    </button>
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
                <button
                  type="button"
                  className="w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm text-muted hover:bg-background hover:text-text transition-colors"
                >
                  <Settings className="w-4 h-4" />
                  <span>Settings</span>
                </button>
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
