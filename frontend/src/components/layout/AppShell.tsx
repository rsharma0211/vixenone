import React, { useState, useEffect, createContext, useContext } from 'react';
import { Outlet } from 'react-router-dom';
import { Header } from '@/components/layout/Header';
import { Sidebar } from '@/components/layout/Sidebar';
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
} from '@/components/ui/sheet';
import { cn } from '@/lib/utils';
import { AskVixenWidget } from '@/components/chat/AskVixenWidget';

interface DrawerContextType {
  openDrawer: (title?: string, content?: React.ReactNode) => void;
  closeDrawer: () => void;
  isOpen: boolean;
}

const DrawerContext = createContext<DrawerContextType>({
  openDrawer: () => {},
  closeDrawer: () => {},
  isOpen: false,
});

export const useDrawer = () => useContext(DrawerContext);

export const AppShell: React.FC = () => {
  const [collapsed, setCollapsed] = useState<boolean>(() => {
    try {
      const saved = localStorage.getItem('vixenone_sidebar_collapsed');
      return saved ? JSON.parse(saved) : false;
    } catch {
      return false;
    }
  });

  const [drawerOpen, setDrawerOpen] = useState<boolean>(false);
  const [drawerTitle, setDrawerTitle] = useState<string>('Drawer title');
  const [drawerContent, setDrawerContent] = useState<React.ReactNode>(null);

  useEffect(() => {
    try {
      localStorage.setItem(
        'vixenone_sidebar_collapsed',
        JSON.stringify(collapsed)
      );
    } catch {
      // Ignore storage errors in restrictive environments
    }
  }, [collapsed]);

  const toggleSidebar = () => {
    setCollapsed((prev) => !prev);
  };

  const openDrawer = (title = 'Drawer title', content: React.ReactNode = null) => {
    setDrawerTitle(title);
    setDrawerContent(content);
    setDrawerOpen(true);
  };

  const closeDrawer = () => {
    setDrawerOpen(false);
  };

  return (
    <DrawerContext.Provider value={{ openDrawer, closeDrawer, isOpen: drawerOpen }}>
      <div className="min-h-screen bg-background text-text flex flex-col">
        <Header onToggleSidebar={toggleSidebar} />
        <Sidebar collapsed={collapsed} />

        <main
          className={cn(
            "flex-1 transition-all duration-200 pt-14 print:pt-0 print:ml-0",
            collapsed ? "ml-16" : "ml-60"
          )}
        >
          <div
            className={cn(
              "w-full transition-all duration-200 print:p-0 print:max-w-none",
              collapsed
                ? "px-10 pt-8 pb-12"
                : "max-w-[1200px] mx-auto px-6 pt-8 pb-12"
            )}
          >
            <Outlet />
          </div>
        </main>

        {/* Global 520px Drawer (L4) */}
        <Sheet open={drawerOpen} onOpenChange={setDrawerOpen}>
          <SheetContent side="right" className="w-[520px] max-w-[90vw] overflow-y-auto">
            <SheetHeader>
              <SheetTitle>{drawerTitle}</SheetTitle>
              <SheetDescription className="sr-only">
                Evaluation detail drawer
              </SheetDescription>
            </SheetHeader>
            <div className="py-6">
              {drawerContent || (
                <div className="flex items-center justify-center min-h-[300px] text-muted text-sm border border-dashed border-border rounded-lg">
                  Drawer content
                </div>
              )}
            </div>
          </SheetContent>
        </Sheet>

        {/* Floating Ask Vixen Widget */}
        <AskVixenWidget />
      </div>
    </DrawerContext.Provider>
  );
};
