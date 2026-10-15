import React, { useState, useEffect, useRef } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import {
  TableProperties,
  ShieldAlert,
  IndianRupee,
  HelpCircle,
  SlidersHorizontal,
  Printer,
  Briefcase,
  Calculator,
  ShieldCheck,
  ChevronLeft,
  ChevronRight,
  ArrowUp,
} from 'lucide-react';
import { useAuth } from '@/lib/auth/AuthContext';
import { ROLE_LABELS } from '@/lib/auth/roles';
import { Button } from '@/components/ui/button';
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from '@/components/ui/accordion';
import {
  Carousel,
  CarouselContent,
  CarouselItem,
  CarouselPrevious,
  CarouselNext,
  CarouselDots,
} from '@/components/ui/carousel';
import { FindingStatusBadge } from '@/components/status/FindingStatusBadge';
import { MandatoryTag } from '@/components/status/MandatoryTag';
import { cn } from '@/lib/utils';

// Hook to detect prefers-reduced-motion
function usePrefersReducedMotion() {
  const [prefersReducedMotion, setPrefersReducedMotion] = useState(() => {
    if (typeof window === 'undefined') return false;
    return window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  });

  useEffect(() => {
    const mediaQuery = window.matchMedia('(prefers-reduced-motion: reduce)');
    const handler = (e: MediaQueryListEvent) => setPrefersReducedMotion(e.matches);
    mediaQuery.addEventListener('change', handler);
    return () => mediaQuery.removeEventListener('change', handler);
  }, []);

  return prefersReducedMotion;
}

// Reveal component for viewport entry animations
interface RevealProps {
  children: React.ReactNode;
  className?: string;
  delay?: number;
  reducedMotion?: boolean;
}

const Reveal: React.FC<RevealProps> = ({
  children,
  className,
  delay = 0,
  reducedMotion = false,
}) => {
  const [inView, setInView] = useState(reducedMotion);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (reducedMotion) {
      setInView(true);
      return;
    }

    const currentRef = ref.current;
    if (!currentRef) return;

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setInView(true);
          observer.unobserve(entry.target);
        }
      },
      { threshold: 0.1, rootMargin: '0px 0px -40px 0px' }
    );

    observer.observe(currentRef);

    return () => {
      observer.disconnect();
    };
  }, [reducedMotion]);

  if (reducedMotion) {
    return <div className={className}>{children}</div>;
  }

  return (
    <div
      ref={ref}
      style={{
        transitionDelay: `${delay}ms`,
      }}
      className={cn(
        'transition-all duration-500 ease-out',
        inView ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-4',
        className
      )}
    >
      {children}
    </div>
  );
};

export const LandingPage: React.FC = () => {
  const navigate = useNavigate();
  const { user } = useAuth();
  const prefersReducedMotion = usePrefersReducedMotion();

  // Sticky header scrolled state
  const [isScrolled, setIsScrolled] = useState<boolean>(false);

  // Back to top button visibility state (1 viewport height scrolled)
  const [showBackToTop, setShowBackToTop] = useState<boolean>(false);

  // Top anchor ref for accessible focus management
  const topRef = useRef<HTMLDivElement>(null);

  // Active section for scroll spy
  const [activeSection, setActiveSection] = useState<string>('');

  useEffect(() => {
    document.title = 'VixenOne';
  }, []);

  // Scroll spy, sticky header shadow, and back-to-top visibility effect
  useEffect(() => {
    const sectionIds = [
      'how-it-works',
      'features',
      'showcase',
      'who-its-for',
      'pricing',
      'coming-soon',
      'faq',
    ];

    const handleScroll = () => {
      const scrollY = window.scrollY;
      setIsScrolled(scrollY > 0);
      setShowBackToTop(scrollY >= window.innerHeight);

      const scrollPosition = scrollY + 120; // 64px header + offset

      for (let i = sectionIds.length - 1; i >= 0; i--) {
        const id = sectionIds[i];
        const element = document.getElementById(id);
        if (element) {
          const top = element.offsetTop;
          if (scrollPosition >= top) {
            setActiveSection(id);
            return;
          }
        }
      }
      setActiveSection('');
    };

    window.addEventListener('scroll', handleScroll, { passive: true });
    handleScroll();

    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  const scrollToSection = (id: string) => {
    const element = document.getElementById(id);
    if (element) {
      const headerOffset = 72;
      const elementPosition = element.getBoundingClientRect().top;
      const offsetPosition = elementPosition + window.scrollY - headerOffset;

      window.scrollTo({
        top: offsetPosition,
        behavior: prefersReducedMotion ? 'auto' : 'smooth',
      });
    }
  };

  const scrollToTop = () => {
    window.scrollTo({
      top: 0,
      behavior: prefersReducedMotion ? 'auto' : 'smooth',
    });

    const setFocusToTop = () => {
      if (topRef.current) {
        topRef.current.focus({ preventScroll: true });
      }
    };

    if (prefersReducedMotion || window.scrollY === 0) {
      setFocusToTop();
    } else {
      let focused = false;
      const onScrollEnd = () => {
        if (!focused) {
          focused = true;
          window.removeEventListener('scrollend', onScrollEnd);
          setFocusToTop();
        }
      };
      window.addEventListener('scrollend', onScrollEnd, { once: true });
      setTimeout(() => {
        onScrollEnd();
      }, 500);
    }
  };

  // Showcase slides data
  const showcaseSlides = [
    {
      src: '/screenshots/S4.png',
      caption: 'Requirements review — edit what was extracted before analysis',
      alt: 'Requirements review screenshot',
    },
    {
      src: '/screenshots/S5.png',
      caption: 'Vendor comparison — scores, mandatory failures and cost at a glance',
      alt: 'Vendor comparison screenshot',
    },
    {
      src: '/screenshots/S6.png',
      caption: 'Finding detail — the exact quote, page and section behind every status',
      alt: 'Finding detail drawer screenshot',
    },
    {
      src: '/screenshots/S7.png',
      caption: 'Recommendation — weighted scores, open questions and a printable report',
      alt: 'Recommendation and scoring screenshot',
    },
  ];

  // Who it's for cards data
  const roleCards = [
    {
      icon: Briefcase,
      title: ROLE_LABELS.facilities_manager,
      description: 'See exactly which services each vendor includes and excludes.',
    },
    {
      icon: Calculator,
      title: ROLE_LABELS.procurement,
      description: 'Compare true monthly cost, with GST and unknown costs flagged.',
    },
    {
      icon: ShieldCheck,
      title: ROLE_LABELS.approver,
      description: 'One report with the recommendation, mandatory failures and open questions.',
    },
  ];

  // Who it's for mobile carousel state
  const [roleIndex, setRoleIndex] = useState(0);

  return (
    <div className="min-h-screen bg-background text-text flex flex-col overflow-x-clip">
      <div ref={topRef} tabIndex={-1} className="outline-none" aria-hidden="true" />
      {/* 1. STICKY HEADER */}
      <header
        className={cn(
          'sticky top-0 z-50 h-16 w-full bg-background border-b border-border transition-shadow duration-200',
          isScrolled && 'shadow-sm'
        )}
      >
        <div className="max-w-7xl mx-auto h-full px-4 sm:px-6 lg:px-8 flex items-center justify-between">
          {/* Logo */}
          <Link
            to="/"
            onClick={() => window.scrollTo({ top: 0, behavior: prefersReducedMotion ? 'auto' : 'smooth' })}
            className="flex items-center select-none focus:outline-none"
          >
            <img src="/logo.png" alt="VixenOne" className="h-10 w-auto max-w-full object-contain" />
          </Link>

          {/* Centre links */}
          <nav className="hidden md:flex items-center space-x-8 text-sm">
            {[
              { id: 'how-it-works', label: 'How it works' },
              { id: 'features', label: 'Features' },
              { id: 'showcase', label: 'Showcase' },
              { id: 'who-its-for', label: "Who it's for" },
              { id: 'pricing', label: 'Pricing' },
              { id: 'coming-soon', label: 'Coming soon' },
              { id: 'faq', label: 'FAQ' },
            ].map(({ id, label }) => {
              const isActive = activeSection === id;
              return (
                <button
                  key={id}
                  type="button"
                  onClick={() => scrollToSection(id)}
                  className={cn(
                    'transition-colors py-1 focus:outline-none focus-visible:ring-1 focus-visible:ring-ring rounded',
                    isActive
                      ? 'text-navy font-semibold border-b-2 border-accent'
                      : 'text-muted hover:text-navy'
                  )}
                >
                  {label}
                </button>
              );
            })}
          </nav>

          {/* Right side CTA: Sign in & Sign up OR Open app */}
          <div className="flex items-center gap-3">
            {user ? (
              <Button
                variant="primary"
                size="sm"
                onClick={() => navigate('/evaluations')}
              >
                Open app
              </Button>
            ) : (
              <>
                <Link
                  to="/sign-in"
                  className="text-sm font-medium text-text hover:text-navy transition-colors px-2 py-1"
                >
                  Sign in
                </Link>
                <Button
                  variant="primary"
                  size="sm"
                  onClick={() => navigate('/sign-up')}
                >
                  Sign up
                </Button>
              </>
            )}
          </div>
        </div>
      </header>

      <main className="flex-1">
        {/* 1. HERO SECTION */}
        <section id="hero" className="py-16 md:py-24 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-12 items-center">
            {/* Left Column: Headline and Actions */}
            <div className="lg:col-span-6 space-y-6">
              <Reveal delay={0} reducedMotion={prefersReducedMotion}>
                <div className="inline-flex items-center rounded-full bg-accent text-navy text-xs font-semibold px-3 py-1 select-none">
                AI powered business operation platform
                </div>
              </Reveal>

              <Reveal delay={60} reducedMotion={prefersReducedMotion}>
                <h1 className="text-4xl sm:text-5xl font-bold text-text tracking-tight leading-[1.12]">
                  Compare vendor proposals on evidence, not instinct.
                </h1>
              </Reveal>

              <Reveal delay={120} reducedMotion={prefersReducedMotion}>
                <p className="text-lg text-muted leading-relaxed max-w-xl">
                  Upload your requirements and 2–3 proposals. VixenOne shows what each vendor committed to, what's missing, what it really costs, and what to ask next.
                </p>
              </Reveal>

              <Reveal delay={180} reducedMotion={prefersReducedMotion}>
                <div className="flex flex-wrap items-center gap-4 pt-2">
                  <Button
                    variant="primary"
                    size="lg"
                    onClick={() => navigate('/sign-up')}
                  >
                    Sign up
                  </Button>
                  <Button
                    variant="secondary"
                    size="lg"
                    onClick={() => scrollToSection('how-it-works')}
                  >
                    See how it works
                  </Button>
                </div>
              </Reveal>
            </div>

            {/* Right Column: Framed Preview Card */}
            <div className="lg:col-span-6">
              <Reveal delay={120} reducedMotion={prefersReducedMotion}>
                <div className="rounded-lg border border-border bg-background shadow-sm overflow-hidden transition-all duration-200 hover:-translate-y-[2px] hover:border-slate-300 motion-reduce:hover:translate-y-0">
                  <div className="overflow-x-auto">
                    <table className="w-full text-left border-collapse min-w-[500px]">
                      <thead>
                        <tr className="border-b border-border bg-surface text-table-header text-muted font-medium uppercase tracking-wider">
                          <th className="py-3 px-4 w-[40%]">REQUIREMENT</th>
                          <th className="py-3 px-3 w-[20%]">BRIGHTNEST</th>
                          <th className="py-3 px-3 w-[20%]">SHUBH</th>
                          <th className="py-3 px-3 w-[20%]">URBANKLEEN</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-border text-sm">
                        {/* REQ-01 */}
                        <tr className="hover:bg-surface/50 transition-colors">
                          <td className="py-3.5 px-4">
                            <div className="flex items-center gap-1.5 flex-wrap">
                              <span className="font-medium text-text text-xs sm:text-sm">REQ-01 12 staff on site</span>
                              <MandatoryTag />
                            </div>
                          </td>
                          <td className="py-3.5 px-3">
                            <FindingStatusBadge status="Compliant" />
                          </td>
                          <td className="py-3.5 px-3">
                            <FindingStatusBadge status="Compliant" />
                          </td>
                          <td className="py-3.5 px-3">
                            <FindingStatusBadge status="Not evidenced" needsReview={true} />
                          </td>
                        </tr>

                        {/* REQ-02 */}
                        <tr className="hover:bg-surface/50 transition-colors">
                          <td className="py-3.5 px-4">
                            <div className="flex items-center gap-1.5 flex-wrap">
                              <span className="font-medium text-text text-xs sm:text-sm">REQ-02 Washroom cleaning 2 h</span>
                              <MandatoryTag />
                            </div>
                          </td>
                          <td className="py-3.5 px-3">
                            <FindingStatusBadge status="Compliant" />
                          </td>
                          <td className="py-3.5 px-3">
                            <FindingStatusBadge status="Compliant" />
                          </td>
                          <td className="py-3.5 px-3">
                            <FindingStatusBadge status="Partially compliant" />
                          </td>
                        </tr>

                        {/* REQ-03 */}
                        <tr className="hover:bg-surface/50 transition-colors">
                          <td className="py-3.5 px-4">
                            <div className="flex items-center gap-1.5 flex-wrap">
                              <span className="font-medium text-text text-xs sm:text-sm">REQ-03 Consumables included</span>
                              <MandatoryTag />
                            </div>
                          </td>
                          <td className="py-3.5 px-3">
                            <FindingStatusBadge status="Non-compliant" />
                          </td>
                          <td className="py-3.5 px-3">
                            <FindingStatusBadge status="Compliant" />
                          </td>
                          <td className="py-3.5 px-3">
                            <FindingStatusBadge status="Not evidenced" />
                          </td>
                        </tr>

                        {/* REQ-07 */}
                        <tr className="hover:bg-surface/50 transition-colors">
                          <td className="py-3.5 px-4">
                            <div className="flex items-center gap-1.5 flex-wrap">
                              <span className="font-medium text-text text-xs sm:text-sm">REQ-07 Monthly pest control</span>
                            </div>
                          </td>
                          <td className="py-3.5 px-3">
                            <FindingStatusBadge status="Partially compliant" />
                          </td>
                          <td className="py-3.5 px-3">
                            <FindingStatusBadge status="Compliant" />
                          </td>
                          <td className="py-3.5 px-3">
                            <FindingStatusBadge status="Compliant" />
                          </td>
                        </tr>
                      </tbody>
                    </table>
                  </div>
                </div>
              </Reveal>
            </div>
          </div>
        </section>

        {/* 2. HOW IT WORKS */}
        <section id="how-it-works" className="bg-surface py-20 border-y border-border scroll-mt-[72px]">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 space-y-10">
            <Reveal delay={0} reducedMotion={prefersReducedMotion}>
              <div className="space-y-2">
                <span className="text-navy text-xs font-semibold tracking-wider uppercase block">
                  HOW IT WORKS
                </span>
                <h2 className="text-2xl sm:text-3xl font-bold text-text tracking-tight">
                  From documents to a defensible decision
                </h2>
              </div>
            </Reveal>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              {/* Step 1 */}
              <Reveal delay={0} reducedMotion={prefersReducedMotion}>
                <div className="rounded-lg border border-border bg-background p-6 space-y-4 h-full transition-all duration-200 hover:-translate-y-[2px] hover:border-slate-300 motion-reduce:hover:translate-y-0">
                  <div className="w-8 h-8 rounded-full bg-accent text-white flex items-center justify-center font-semibold text-sm">
                    1
                  </div>
                  <div className="space-y-1.5">
                    <h3 className="text-base font-semibold text-text">Upload</h3>
                    <p className="text-sm text-muted leading-relaxed">
                      One requirements document and 2–3 vendor proposals, PDF or Word.
                    </p>
                  </div>
                </div>
              </Reveal>

              {/* Step 2 */}
              <Reveal delay={60} reducedMotion={prefersReducedMotion}>
                <div className="rounded-lg border border-border bg-background p-6 space-y-4 h-full transition-all duration-200 hover:-translate-y-[2px] hover:border-slate-300 motion-reduce:hover:translate-y-0">
                  <div className="w-8 h-8 rounded-full bg-accent text-white flex items-center justify-center font-semibold text-sm">
                    2
                  </div>
                  <div className="space-y-1.5">
                    <h3 className="text-base font-semibold text-text">Review evidence</h3>
                    <p className="text-sm text-muted leading-relaxed">
                      Every requirement checked against each proposal, with the exact quote and page.
                    </p>
                  </div>
                </div>
              </Reveal>

              {/* Step 3 */}
              <Reveal delay={120} reducedMotion={prefersReducedMotion}>
                <div className="rounded-lg border border-border bg-background p-6 space-y-4 h-full transition-all duration-200 hover:-translate-y-[2px] hover:border-slate-300 motion-reduce:hover:translate-y-0">
                  <div className="w-8 h-8 rounded-full bg-accent text-white flex items-center justify-center font-semibold text-sm">
                    3
                  </div>
                  <div className="space-y-1.5">
                    <h3 className="text-base font-semibold text-text">Decide</h3>
                    <p className="text-sm text-muted leading-relaxed">
                      Weighted scores, risks, true monthly cost and the questions to ask before signing.
                    </p>
                  </div>
                </div>
              </Reveal>
            </div>
          </div>
        </section>

        {/* 3. FEATURES */}
        <section id="features" className="py-20 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 space-y-10 scroll-mt-[72px]">
          <Reveal delay={0} reducedMotion={prefersReducedMotion}>
            <div className="space-y-2">
              <span className="text-navy text-xs font-semibold tracking-wider uppercase block">
                FEATURES
              </span>
              <h2 className="text-2xl sm:text-3xl font-bold text-text tracking-tight">
                Everything a fair comparison needs
              </h2>
            </div>
          </Reveal>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {[
              {
                icon: TableProperties,
                title: 'Compliance matrix',
                description: 'Requirement × vendor, with evidence behind every cell.',
              },
              {
                icon: ShieldAlert,
                title: 'Risk detection',
                description: 'Exclusions, omissions, ambiguity, contradictions, unknown costs.',
              },
              {
                icon: IndianRupee,
                title: 'True cost in INR',
                description: 'Monthly base, GST shown separately, hidden costs flagged.',
              },
              {
                icon: HelpCircle,
                title: 'Clarification questions',
                description: 'Ready-to-send questions for every gap.',
              },
              {
                icon: SlidersHorizontal,
                title: 'Adjustable scoring',
                description: 'Change the weights, see the ranking update.',
              },
              {
                icon: Printer,
                title: 'Printable report',
                description: 'One clean report for approvers.',
              },
            ].map(({ icon: Icon, title, description }, index) => (
              <Reveal
                key={title}
                delay={index * 60}
                reducedMotion={prefersReducedMotion}
              >
                <div className="rounded-lg border border-border bg-background p-6 space-y-3 h-full transition-all duration-200 hover:-translate-y-[2px] hover:border-slate-300 motion-reduce:hover:translate-y-0">
                  <div className="w-10 h-10 rounded-lg bg-muted-surface flex items-center justify-center text-navy">
                    <Icon className="w-5 h-5 stroke-[2]" />
                  </div>
                  <div className="space-y-1">
                    <h3 className="text-base font-semibold text-text">{title}</h3>
                    <p className="text-sm text-muted leading-relaxed">{description}</p>
                  </div>
                </div>
              </Reveal>
            ))}
          </div>
        </section>

        {/* 4. SHOWCASE */}
        <section id="showcase" className="bg-surface py-20 border-y border-border scroll-mt-[72px]">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 space-y-8">
            <Reveal delay={0} reducedMotion={prefersReducedMotion}>
              <div className="text-center space-y-2">
                <span className="text-navy text-xs font-semibold tracking-wider uppercase block">
                  SHOWCASE
                </span>
                <h2 className="text-2xl sm:text-3xl font-bold text-text tracking-tight">
                  See it in action
                </h2>
              </div>
            </Reveal>

            <Reveal delay={60} reducedMotion={prefersReducedMotion}>
              <div className="max-w-5xl mx-auto">
                <Carousel
                  autoAdvance={true}
                  autoAdvanceInterval={5000}
                  loop={true}
                  reducedMotion={prefersReducedMotion}
                  className="w-full"
                >
                  <CarouselContent>
                    {showcaseSlides.map((slide, index) => (
                      <CarouselItem key={index}>
                        <div className="space-y-4">
                          <div className="rounded-lg border border-border bg-background shadow-sm overflow-hidden">
                            <img
                              src={slide.src}
                              alt={slide.alt}
                              loading="lazy"
                              className="w-full h-auto object-contain max-h-[640px] mx-auto select-none"
                            />
                          </div>
                          <p className="text-sm text-muted text-center font-normal px-4">
                            {slide.caption}
                          </p>
                        </div>
                      </CarouselItem>
                    ))}
                  </CarouselContent>

                  {/* Carousel navigation controls (arrows + dots) */}
                  <div className="flex items-center justify-center gap-4 mt-6">
                    <CarouselPrevious />
                    <CarouselDots />
                    <CarouselNext />
                  </div>
                </Carousel>
              </div>
            </Reveal>
          </div>
        </section>

        {/* 5. WHO IT'S FOR */}
        <section id="who-its-for" className="py-20 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 space-y-10 scroll-mt-[72px]">
          <Reveal delay={0} reducedMotion={prefersReducedMotion}>
            <div className="space-y-2">
              <span className="text-navy text-xs font-semibold tracking-wider uppercase block">
                WHO IT'S FOR
              </span>
              <h2 className="text-2xl sm:text-3xl font-bold text-text tracking-tight">
                Built for the people who sign off
              </h2>
            </div>
          </Reveal>

          {/* Wide screens: all 3 visible */}
          <div className="hidden md:grid md:grid-cols-3 gap-6">
            {roleCards.map(({ icon: Icon, title, description }, index) => (
              <Reveal
                key={title}
                delay={index * 60}
                reducedMotion={prefersReducedMotion}
              >
                <div className="rounded-lg border border-border bg-background p-6 space-y-3 h-full transition-all duration-200 hover:-translate-y-[2px] hover:border-slate-300 motion-reduce:hover:translate-y-0">
                  <div className="w-10 h-10 rounded-lg bg-muted-surface flex items-center justify-center text-navy">
                    <Icon className="w-5 h-5 stroke-[2]" />
                  </div>
                  <div className="space-y-1">
                    <h3 className="text-base font-semibold text-text">{title}</h3>
                    <p className="text-sm text-muted leading-relaxed">{description}</p>
                  </div>
                </div>
              </Reveal>
            ))}
          </div>

          {/* Mobile carousel version for role cards */}
          <div className="block md:hidden space-y-4">
            <div className="rounded-lg border border-border bg-background p-6 space-y-3">
              {React.createElement(roleCards[roleIndex].icon, {
                className: 'w-6 h-6 text-navy stroke-[2]',
              })}
              <div className="space-y-1">
                <h3 className="text-base font-semibold text-text">
                  {roleCards[roleIndex].title}
                </h3>
                <p className="text-sm text-muted leading-relaxed">
                  {roleCards[roleIndex].description}
                </p>
              </div>
            </div>

            <div className="flex items-center justify-center gap-2">
              <Button
                variant="secondary"
                size="icon-sm"
                className="h-7 w-7 rounded-full"
                onClick={() => setRoleIndex((prev) => (prev === 0 ? roleCards.length - 1 : prev - 1))}
              >
                <ChevronLeft className="h-3.5 w-3.5" />
              </Button>
              <div className="flex items-center gap-1.5">
                {roleCards.map((_, idx) => (
                  <button
                    key={idx}
                    type="button"
                    onClick={() => setRoleIndex(idx)}
                    className={cn(
                      'h-2 rounded-full transition-all',
                      idx === roleIndex ? 'w-6 bg-accent' : 'w-2 bg-border'
                    )}
                  />
                ))}
              </div>
              <Button
                variant="secondary"
                size="icon-sm"
                className="h-7 w-7 rounded-full"
                onClick={() => setRoleIndex((prev) => (prev === roleCards.length - 1 ? 0 : prev + 1))}
              >
                <ChevronRight className="h-3.5 w-3.5" />
              </Button>
            </div>
          </div>
        </section>

        {/* 6. PRINCIPLE BAND */}
        <section className="bg-text text-white py-16 px-4 sm:px-6 lg:px-8">
          <div className="max-w-4xl mx-auto text-center space-y-3">
            <Reveal delay={0} reducedMotion={prefersReducedMotion}>
              <h2 className="text-2xl sm:text-3xl font-bold tracking-tight text-white">
                Evidence, not opinions.
              </h2>
            </Reveal>
            <Reveal delay={60} reducedMotion={prefersReducedMotion}>
              <p className="text-sm sm:text-base text-slate-300 max-w-2xl mx-auto leading-relaxed">
                VixenOne never just names a winner. It shows what was promised, what is unknown, and what must be clarified.
              </p>
            </Reveal>
          </div>
        </section>

        {/* PRICING */}
        <section id="pricing" className="py-20 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 space-y-8 scroll-mt-[72px]">
          <Reveal delay={0} reducedMotion={prefersReducedMotion}>
            <div className="space-y-2">
              <h2 className="text-2xl sm:text-3xl font-bold text-text tracking-tight">
                Pricing
              </h2>
            </div>
          </Reveal>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <Reveal delay={0} reducedMotion={prefersReducedMotion}>
              <div className="rounded-lg border border-border bg-background p-6 pr-14 sm:pr-6 flex flex-col justify-between space-y-6 h-full transition-all duration-200 hover:-translate-y-[2px] hover:border-slate-300 motion-reduce:hover:translate-y-0">
                <div className="space-y-2">
                  <h3 className="text-base font-semibold text-text">Per evaluation</h3>
                  <p className="text-sm text-muted">₹499 per evaluation + GST</p>
                </div>
                <Button
                  variant="primary"
                  className="w-full"
                  onClick={() => navigate('/sign-up')}
                >
                  Get started
                </Button>
              </div>
            </Reveal>

            <Reveal delay={60} reducedMotion={prefersReducedMotion}>
              <div className="rounded-lg border border-border bg-background p-6 pr-14 sm:pr-6 flex flex-col justify-between space-y-6 h-full transition-all duration-200 hover:-translate-y-[2px] hover:border-slate-300 motion-reduce:hover:translate-y-0">
                <div className="space-y-2">
                  <h3 className="text-base font-semibold text-text">Monthly</h3>
                  <p className="text-sm text-muted">₹999 per month + GST</p>
                  <p className="text-sm text-muted">Unlimited evaluations</p>
                </div>
                <Button
                  variant="primary"
                  className="w-full"
                  onClick={() => navigate('/sign-up')}
                >
                  Get started
                </Button>
              </div>
            </Reveal>

            <Reveal delay={120} reducedMotion={prefersReducedMotion}>
              <div className="rounded-lg border border-border bg-background p-6 pr-14 sm:pr-6 flex flex-col justify-between space-y-6 h-full transition-all duration-200 hover:-translate-y-[2px] hover:border-slate-300 motion-reduce:hover:translate-y-0">
                <div className="space-y-2">
                  <h3 className="text-base font-semibold text-text">Enterprise</h3>
                  <p className="text-sm text-muted">Contact us</p>
                </div>
                <Button variant="primary" asChild className="w-full">
                  <a href="mailto:hello@webitmore.com">Contact us</a>
                </Button>
              </div>
            </Reveal>
          </div>
        </section>

        {/* COMING SOON */}
        <section id="coming-soon" className="bg-surface py-20 border-y border-border scroll-mt-[72px]">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 space-y-8">
            <Reveal delay={0} reducedMotion={prefersReducedMotion}>
              <div className="space-y-2">
                <h2 className="text-2xl sm:text-3xl font-bold text-text tracking-tight">
                  Coming soon
                </h2>
                <p className="text-sm sm:text-base text-muted">
                  What we're building next.
                </p>
              </div>
            </Reveal>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {[
                {
                  title: 'Bidding — vendors bid against the RFQ',
                  summary: 'Vendors submit priced bids against your RFQ inside VixenOne.',
                },
                {
                  title: 'Vendor onboarding and background verification',
                  summary: 'Collect vendor documents and verify background before you engage.',
                },
                {
                  title: 'Facility & Service Management',
                  summary: 'Track day-to-day services once a vendor is appointed.',
                },
                {
                  title: 'Disaster Management',
                  summary: 'Plan and coordinate facility response during emergencies.',
                },
                {
                  title: 'Approval Matrix',
                  summary: 'Route recommendations to the right approvers by value and category.',
                },
                {
                  title: 'AI chat feature',
                  summary: 'Ask questions about your evaluations in plain English.',
                },
              ].map((item, index) => (
                <Reveal
                  key={item.title}
                  delay={index * 60}
                  reducedMotion={prefersReducedMotion}
                  className="h-full"
                >
                  <div className="rounded-lg border border-border bg-background p-6 h-full transition-all duration-200 hover:-translate-y-[2px] hover:border-slate-300 motion-reduce:hover:translate-y-0 space-y-2">
                    <p className="text-sm font-medium text-text">{item.title}</p>
                    <p className="text-sm text-muted">{item.summary}</p>
                  </div>
                </Reveal>
              ))}
            </div>
          </div>
        </section>

        {/* 7. FAQ */}
        <section id="faq" className="py-20 max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 space-y-8 scroll-mt-[72px]">
          <Reveal delay={0} reducedMotion={prefersReducedMotion}>
            <div className="space-y-2">
              <span className="text-navy text-xs font-semibold tracking-wider uppercase block">
                FAQ
              </span>
              <h2 className="text-2xl sm:text-3xl font-bold text-text tracking-tight">
                Questions
              </h2>
            </div>
          </Reveal>

          <Reveal delay={60} reducedMotion={prefersReducedMotion}>
            <Accordion type="single" collapsible defaultValue="item-0" className="w-full">
              <AccordionItem value="item-0">
                <AccordionTrigger className="text-left font-medium text-text hover:text-navy">
                  Which documents can I upload?
                </AccordionTrigger>
                <AccordionContent className="text-muted leading-relaxed">
                  PDF or Word, up to 10 MB and 30 pages each: one requirements document and 2–3 vendor proposals.
                </AccordionContent>
              </AccordionItem>

              <AccordionItem value="item-1">
                <AccordionTrigger className="text-left font-medium text-text hover:text-navy">
                  Does VixenOne choose the vendor for me?
                </AccordionTrigger>
                <AccordionContent className="text-muted leading-relaxed">
                  No. It shows evidence, risks, cost and scores, and suggests a next step — or says when there isn't enough information to recommend.
                </AccordionContent>
              </AccordionItem>

              <AccordionItem value="item-2">
                <AccordionTrigger className="text-left font-medium text-text hover:text-navy">
                  How are scores calculated?
                </AccordionTrigger>
                <AccordionContent className="text-muted leading-relaxed">
                  Five weighted criteria: mandatory compliance, service coverage, cost comparability, SLA, unresolved risks. You can change the weights. Mandatory failures are always shown separately.
                </AccordionContent>
              </AccordionItem>

              <AccordionItem value="item-3">
                <AccordionTrigger className="text-left font-medium text-text hover:text-navy">
                  Can I edit the extracted requirements?
                </AccordionTrigger>
                <AccordionContent className="text-muted leading-relaxed">
                  Yes. Edit, add or remove them before analysis. Edits after analysis mark results stale until you re-run.
                </AccordionContent>
              </AccordionItem>

              <AccordionItem value="item-4">
                <AccordionTrigger className="text-left font-medium text-text hover:text-navy">
                  Can I share the results?
                </AccordionTrigger>
                <AccordionContent className="text-muted leading-relaxed">
                  Yes. Print or save the report as PDF, and copy the clarification questions to send to vendors.
                </AccordionContent>
              </AccordionItem>
            </Accordion>
          </Reveal>
        </section>

        {/* 8. FINAL CTA CARD */}
        <section className="py-12 px-4 sm:px-6 lg:px-8">
          <div className="max-w-4xl mx-auto">
            <Reveal delay={0} reducedMotion={prefersReducedMotion}>
              <div className="rounded-2xl border border-accent/20 bg-accent-tint/60 p-10 sm:p-14 text-center space-y-6 shadow-sm">
                <h2 className="text-2xl sm:text-3xl font-bold text-text tracking-tight">
                  Ready to compare your next proposals?
                </h2>
                <div>
                  <Button
                    variant="primary"
                    size="lg"
                    onClick={() => navigate('/sign-up')}
                  >
                    Sign up
                  </Button>
                </div>
              </div>
            </Reveal>
          </div>
        </section>
      </main>

      {/* 9. FOOTER */}
      <footer className="border-t border-border bg-background py-8 pb-20 sm:pb-8">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex flex-col sm:flex-row items-center sm:justify-between gap-4">
          <div className="flex items-center select-none">
            <img src="/logo.png" alt="VixenOne" className="h-10 w-auto max-w-full object-contain" />
          </div>
          <p className="text-xs text-muted pr-14 sm:pr-0">
            Powered by{' '}
            <a
              href="https://webitmore.com"
              target="_blank"
              rel="noopener noreferrer"
              className="text-text hover:text-navy underline-offset-4 hover:underline"
            >
              webITmore Technologies LLP
            </a>
          </p>
        </div>
      </footer>

      {/* 10. BACK TO TOP BUTTON */}
      <button
        type="button"
        onClick={scrollToTop}
        aria-label="Back to top"
        className={cn(
          'fixed bottom-6 right-4 sm:right-6 z-40',
          'flex h-10 w-10 items-center justify-center rounded-full',
          'bg-background border border-border text-navy shadow-sm',
          'hover:bg-surface transition-all duration-200',
          'focus:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2',
          'print:hidden',
          showBackToTop
            ? 'opacity-100 translate-y-0 pointer-events-auto visible'
            : 'opacity-0 translate-y-2 pointer-events-none invisible'
        )}
      >
        <ArrowUp className="h-5 w-5 text-navy" aria-hidden="true" />
      </button>
    </div>
  );
};

export default LandingPage;
