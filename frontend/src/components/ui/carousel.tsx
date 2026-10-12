import * as React from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";

export interface CarouselApi {
  currentIndex: number;
  totalSlides: number;
  scrollPrev: () => void;
  scrollNext: () => void;
  scrollTo: (index: number) => void;
  canScrollPrev: boolean;
  canScrollNext: boolean;
}

interface CarouselContextProps {
  currentIndex: number;
  totalSlides: number;
  setTotalSlides: React.Dispatch<React.SetStateAction<number>>;
  scrollPrev: () => void;
  scrollNext: () => void;
  scrollTo: (index: number) => void;
  canScrollPrev: boolean;
  canScrollNext: boolean;
  orientation?: "horizontal" | "vertical";
  autoAdvance?: boolean;
  autoAdvanceInterval?: number;
  isPaused: boolean;
  setIsPaused: (paused: boolean) => void;
}

const CarouselContext = React.createContext<CarouselContextProps | null>(null);

export function useCarousel() {
  const context = React.useContext(CarouselContext);
  if (!context) {
    throw new Error("useCarousel must be used within a <Carousel />");
  }
  return context;
}

export interface CarouselProps extends React.HTMLAttributes<HTMLDivElement> {
  orientation?: "horizontal" | "vertical";
  loop?: boolean;
  autoAdvance?: boolean;
  autoAdvanceInterval?: number; // milliseconds, default 5000
  setApi?: (api: CarouselApi) => void;
  reducedMotion?: boolean;
}

const Carousel = React.forwardRef<HTMLDivElement, CarouselProps>(
  (
    {
      orientation = "horizontal",
      loop = true,
      autoAdvance = false,
      autoAdvanceInterval = 5000,
      setApi,
      reducedMotion = false,
      className,
      children,
      onMouseEnter,
      onMouseLeave,
      onFocus,
      onBlur,
      onKeyDown,
      ...props
    },
    ref
  ) => {
    const [currentIndex, setCurrentIndex] = React.useState(0);
    const [totalSlides, setTotalSlides] = React.useState(0);
    const [isPaused, setIsPaused] = React.useState(false);

    const canScrollPrev = loop || currentIndex > 0;
    const canScrollNext = loop || currentIndex < totalSlides - 1;

    const scrollPrev = React.useCallback(() => {
      setCurrentIndex((prev) => {
        if (prev === 0) {
          return loop ? Math.max(0, totalSlides - 1) : 0;
        }
        return prev - 1;
      });
    }, [loop, totalSlides]);

    const scrollNext = React.useCallback(() => {
      setCurrentIndex((prev) => {
        if (prev >= totalSlides - 1) {
          return loop ? 0 : prev;
        }
        return prev + 1;
      });
    }, [loop, totalSlides]);

    const scrollTo = React.useCallback(
      (index: number) => {
        if (index >= 0 && index < totalSlides) {
          setCurrentIndex(index);
        }
      },
      [totalSlides]
    );

    // Expose API
    React.useEffect(() => {
      if (setApi) {
        setApi({
          currentIndex,
          totalSlides,
          scrollPrev,
          scrollNext,
          scrollTo,
          canScrollPrev,
          canScrollNext,
        });
      }
    }, [currentIndex, totalSlides, scrollPrev, scrollNext, scrollTo, canScrollPrev, canScrollNext, setApi]);

    // Auto-advance timer
    React.useEffect(() => {
      if (!autoAdvance || reducedMotion || isPaused || totalSlides <= 1) {
        return;
      }

      const timer = setInterval(() => {
        scrollNext();
      }, autoAdvanceInterval);

      return () => clearInterval(timer);
    }, [autoAdvance, reducedMotion, isPaused, totalSlides, autoAdvanceInterval, scrollNext]);

    // Keyboard navigation
    const handleKeyDown = (event: React.KeyboardEvent<HTMLDivElement>) => {
      if (orientation === "horizontal") {
        if (event.key === "ArrowLeft") {
          event.preventDefault();
          scrollPrev();
        } else if (event.key === "ArrowRight") {
          event.preventDefault();
          scrollNext();
        }
      }
      onKeyDown?.(event);
    };

    // Touch swipe handling
    const touchStartX = React.useRef<number | null>(null);

    const handleTouchStart = (e: React.TouchEvent) => {
      touchStartX.current = e.touches[0].clientX;
    };

    const handleTouchEnd = (e: React.TouchEvent) => {
      if (touchStartX.current === null) return;
      const touchEndX = e.changedTouches[0].clientX;
      const diff = touchStartX.current - touchEndX;
      if (Math.abs(diff) > 40) {
        if (diff > 0) {
          scrollNext();
        } else {
          scrollPrev();
        }
      }
      touchStartX.current = null;
    };

    return (
      <CarouselContext.Provider
        value={{
          currentIndex,
          totalSlides,
          setTotalSlides,
          scrollPrev,
          scrollNext,
          scrollTo,
          canScrollPrev,
          canScrollNext,
          orientation,
          autoAdvance,
          autoAdvanceInterval,
          isPaused,
          setIsPaused,
        }}
      >
        <div
          ref={ref}
          role="region"
          aria-roledescription="carousel"
          tabIndex={0}
          onMouseEnter={(e) => {
            setIsPaused(true);
            onMouseEnter?.(e);
          }}
          onMouseLeave={(e) => {
            setIsPaused(false);
            onMouseLeave?.(e);
          }}
          onFocus={(e) => {
            setIsPaused(true);
            onFocus?.(e);
          }}
          onBlur={(e) => {
            setIsPaused(false);
            onBlur?.(e);
          }}
          onKeyDown={handleKeyDown}
          onTouchStart={handleTouchStart}
          onTouchEnd={handleTouchEnd}
          className={cn("relative focus:outline-none", className)}
          {...props}
        >
          {children}
        </div>
      </CarouselContext.Provider>
    );
  }
);
Carousel.displayName = "Carousel";

const CarouselContent = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement>
>(({ className, children, ...props }, ref) => {
  const { currentIndex, setTotalSlides } = useCarousel();

  React.useEffect(() => {
    const count = React.Children.count(children);
    setTotalSlides(count);
  }, [children, setTotalSlides]);

  return (
    <div ref={ref} className="overflow-hidden w-full">
      <div
        className={cn(
          "flex transition-transform duration-500 ease-out",
          className
        )}
        style={{
          transform: `translateX(-${currentIndex * 100}%)`,
        }}
        {...props}
      >
        {children}
      </div>
    </div>
  );
});
CarouselContent.displayName = "CarouselContent";

const CarouselItem = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement>
>(({ className, ...props }, ref) => {
  return (
    <div
      ref={ref}
      role="group"
      aria-roledescription="slide"
      className={cn("min-w-0 shrink-0 grow-0 basis-full", className)}
      {...props}
    />
  );
});
CarouselItem.displayName = "CarouselItem";

const CarouselPrevious = React.forwardRef<
  HTMLButtonElement,
  React.ComponentProps<typeof Button>
>(({ className, variant = "secondary", size = "icon-sm", ...props }, ref) => {
  const { scrollPrev, canScrollPrev } = useCarousel();

  return (
    <Button
      ref={ref}
      type="button"
      variant={variant}
      size={size}
      className={cn("h-8 w-8 rounded-full", className)}
      disabled={!canScrollPrev}
      onClick={scrollPrev}
      aria-label="Previous slide"
      {...props}
    >
      <ChevronLeft className="h-4 w-4" />
      <span className="sr-only">Previous slide</span>
    </Button>
  );
});
CarouselPrevious.displayName = "CarouselPrevious";

const CarouselNext = React.forwardRef<
  HTMLButtonElement,
  React.ComponentProps<typeof Button>
>(({ className, variant = "secondary", size = "icon-sm", ...props }, ref) => {
  const { scrollNext, canScrollNext } = useCarousel();

  return (
    <Button
      ref={ref}
      type="button"
      variant={variant}
      size={size}
      className={cn("h-8 w-8 rounded-full", className)}
      disabled={!canScrollNext}
      onClick={scrollNext}
      aria-label="Next slide"
      {...props}
    >
      <ChevronRight className="h-4 w-4" />
      <span className="sr-only">Next slide</span>
    </Button>
  );
});
CarouselNext.displayName = "CarouselNext";

const CarouselDots = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement>
>(({ className, ...props }, ref) => {
  const { currentIndex, totalSlides, scrollTo } = useCarousel();

  if (totalSlides <= 1) return null;

  return (
    <div
      ref={ref}
      className={cn("flex items-center gap-1.5", className)}
      {...props}
    >
      {Array.from({ length: totalSlides }).map((_, index) => {
        const isActive = index === currentIndex;
        return (
          <button
            key={index}
            type="button"
            onClick={() => scrollTo(index)}
            aria-label={`Go to slide ${index + 1}`}
            className={cn(
              "h-2 rounded-full transition-all focus:outline-none focus-visible:ring-2 focus-visible:ring-accent",
              isActive ? "w-6 bg-accent" : "w-2 bg-border hover:bg-muted"
            )}
          />
        );
      })}
    </div>
  );
});
CarouselDots.displayName = "CarouselDots";

export {
  type CarouselContextProps,
  Carousel,
  CarouselContent,
  CarouselItem,
  CarouselPrevious,
  CarouselNext,
  CarouselDots,
};
