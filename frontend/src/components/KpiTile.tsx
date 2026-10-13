import React, { useState, useId, useRef, useEffect, useCallback } from 'react';
import { Info } from 'lucide-react';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import { cn } from '@/lib/utils';

export interface KpiTileProps {
  label: string;
  value: React.ReactNode;
  helpText: string;
  subtext?: React.ReactNode;
  statusAccent?: 'compliant' | 'noncompliant' | 'partial';
  onClick?: () => void;
  active?: boolean;
  className?: string;
  valueClassName?: string;
}

export const KpiTile: React.FC<KpiTileProps> = ({
  label,
  value,
  helpText,
  subtext,
  statusAccent,
  onClick,
  active = false,
  className,
  valueClassName,
}) => {
  const [open, setOpen] = useState<boolean>(false);
  const helpId = useId();
  const triggerRef = useRef<HTMLButtonElement | null>(null);
  const contentRef = useRef<HTMLDivElement | null>(null);
  const valueContainerRef = useRef<HTMLDivElement | null>(null);
  const isPointerDownOnTriggerRef = useRef<boolean>(false);

  const handleOpenChange = useCallback((nextOpen: boolean) => {
    if (!nextOpen && isPointerDownOnTriggerRef.current) {
      return;
    }
    setOpen(nextOpen);
  }, []);

  useEffect(() => {
    if (!open) return;

    const handleOutsideEvent = (event: MouseEvent | TouchEvent | PointerEvent) => {
      const target = event.target as Node | null;
      if (!target) return;
      if (triggerRef.current?.contains(target)) return;
      if (contentRef.current?.contains(target)) return;
      setOpen(false);
    };

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setOpen(false);
      }
    };

    document.addEventListener('pointerdown', handleOutsideEvent);
    document.addEventListener('touchstart', handleOutsideEvent);
    document.addEventListener('keydown', handleKeyDown);
    return () => {
      document.removeEventListener('pointerdown', handleOutsideEvent);
      document.removeEventListener('touchstart', handleOutsideEvent);
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [open]);

  // Shrink value font-size if it exceeds container width so values never clip or ellipsis
  useEffect(() => {
    const el = valueContainerRef.current;
    if (!el) return;

    const adjustSize = () => {
      el.style.fontSize = '';
      const computed = window.getComputedStyle(el);
      let currentPx = parseFloat(computed.fontSize) || 28;
      const minPx = 13;

      while (el.scrollWidth > el.clientWidth && currentPx > minPx) {
        currentPx -= 1;
        el.style.fontSize = `${currentPx}px`;
      }
    };

    adjustSize();

    const ro = new ResizeObserver(() => {
      adjustSize();
    });
    ro.observe(el);

    return () => {
      ro.disconnect();
    };
  }, [value]);

  const handleTileKeyDown = (e: React.KeyboardEvent<HTMLDivElement>) => {
    if (!onClick) return;
    if (e.target !== e.currentTarget) return;
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      onClick();
    }
  };

  const statusAccentStyles: Record<'compliant' | 'noncompliant' | 'partial', string> = {
    compliant: 'border-status-compliant-text/30 bg-status-compliant-bg/50',
    noncompliant: 'border-status-noncompliant-text/30 bg-status-noncompliant-bg/50',
    partial: 'border-status-partial-text/30 bg-status-partial-bg/50',
  };

  return (
    <TooltipProvider delayDuration={150}>
      <div
        role={onClick ? 'button' : undefined}
        tabIndex={onClick ? 0 : undefined}
        aria-pressed={onClick ? active : undefined}
        onClick={onClick}
        onKeyDown={onClick ? handleTileKeyDown : undefined}
        className={cn(
          'rounded-lg border p-4 text-left transition-all flex flex-col justify-between min-w-0',
          onClick &&
            'cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
          active
            ? 'border-navy ring-2 ring-navy bg-surface shadow-sm'
            : statusAccent
            ? statusAccentStyles[statusAccent]
            : cn('border-border bg-background', onClick && 'hover:bg-surface/50'),
          className
        )}
      >
        <div className="flex items-start gap-1 min-w-0">
          <span className="text-xs font-medium text-muted uppercase tracking-wider leading-snug break-words line-clamp-2 min-w-0 flex-1">
            {label}
          </span>
          <Tooltip open={open} onOpenChange={handleOpenChange}>
            <TooltipTrigger asChild>
              <button
                ref={triggerRef}
                type="button"
                aria-label={`What does ${label} mean?`}
                aria-describedby={helpId}
                onPointerDown={(e) => {
                  e.stopPropagation();
                  isPointerDownOnTriggerRef.current = true;
                  window.addEventListener(
                    'pointerup',
                    () => {
                      window.setTimeout(() => {
                        isPointerDownOnTriggerRef.current = false;
                      }, 0);
                    },
                    { once: true }
                  );
                }}
                onPointerUp={(e) => {
                  e.stopPropagation();
                }}
                onTouchStart={(e) => {
                  e.stopPropagation();
                }}
                onClick={(e) => {
                  e.stopPropagation();
                  e.preventDefault();
                  isPointerDownOnTriggerRef.current = false;
                  setOpen((prev) => !prev);
                }}
                onKeyDown={(e) => {
                  e.stopPropagation();
                  if (e.key === 'Escape' && open) {
                    e.preventDefault();
                    setOpen(false);
                  }
                }}
                className="inline-flex items-center justify-center rounded-sm p-0.5 text-muted hover:text-navy focus-visible:text-navy focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring transition-colors shrink-0 mt-0.5"
              >
                <Info className="w-3.5 h-3.5 shrink-0" aria-hidden="true" />
              </button>
            </TooltipTrigger>
            <TooltipContent
              ref={contentRef}
              id={helpId}
              side="top"
              align="start"
              collisionPadding={12}
              onClick={(e) => e.stopPropagation()}
              onPointerDown={(e) => e.stopPropagation()}
              className="max-w-[min(22rem,calc(100vw-1.5rem))] rounded-md border border-border bg-background px-3 py-2 text-xs font-normal leading-snug text-navy shadow-dropdown whitespace-normal"
            >
              {helpText}
            </TooltipContent>
          </Tooltip>
          {!open && (
            <span id={helpId} role="tooltip" className="sr-only">
              {helpText}
            </span>
          )}
        </div>
        <div className="mt-1 min-w-0">
          <div
            ref={valueContainerRef}
            className={cn(
              'text-2xl sm:text-3xl font-bold text-navy tracking-tight whitespace-nowrap overflow-hidden leading-tight',
              statusAccent && value === 'Not stated' && 'text-status-partial-text text-xl sm:text-2xl',
              valueClassName
            )}
          >
            {value}
          </div>
          {subtext && (
            <div
              className={cn(
                'text-xs font-medium mt-1 truncate',
                statusAccent === 'compliant' && 'text-status-compliant-text',
                statusAccent === 'noncompliant' && 'text-status-noncompliant-text',
                statusAccent === 'partial' && 'text-status-partial-text',
                !statusAccent && 'text-muted'
              )}
            >
              {subtext}
            </div>
          )}
        </div>
      </div>
    </TooltipProvider>
  );
};

export default KpiTile;

