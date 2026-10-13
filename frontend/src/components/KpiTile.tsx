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
  onClick?: () => void;
  active?: boolean;
  className?: string;
}

export const KpiTile: React.FC<KpiTileProps> = ({
  label,
  value,
  helpText,
  onClick,
  active = false,
  className,
}) => {
  const [open, setOpen] = useState<boolean>(false);
  const helpId = useId();
  const triggerRef = useRef<HTMLButtonElement | null>(null);
  const contentRef = useRef<HTMLDivElement | null>(null);
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

  const handleTileKeyDown = (e: React.KeyboardEvent<HTMLDivElement>) => {
    if (!onClick) return;
    if (e.target !== e.currentTarget) return;
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      onClick();
    }
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
          'rounded-lg border p-4 text-left transition-all',
          onClick &&
            'cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
          active
            ? 'border-navy ring-2 ring-navy bg-surface shadow-sm'
            : cn('border-border bg-background', onClick && 'hover:bg-surface/50'),
          className
        )}
      >
        <div className="flex items-center gap-1.5">
          <span className="text-xs font-medium text-muted uppercase tracking-wider">
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
                className="inline-flex items-center justify-center rounded-sm p-0.5 text-muted hover:text-navy focus-visible:text-navy focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring transition-colors"
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
        <div className="text-2xl sm:text-3xl font-bold text-navy mt-1 tracking-tight">
          {value}
        </div>
      </div>
    </TooltipProvider>
  );
};

export default KpiTile;
