import React from 'react';
import { PanelLeft, ChevronDown, User as UserIcon, LogOut } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '@/lib/auth/AuthContext';
import { ROLE_LABELS, UserRole } from '@/lib/auth/roles';
import { Avatar, AvatarFallback } from '@/components/ui/avatar';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';

interface HeaderProps {
  onToggleSidebar: () => void;
}

export const Header: React.FC<HeaderProps> = ({ onToggleSidebar }) => {
  const navigate = useNavigate();
  const { profile, user, initials, signOut } = useAuth();

  const displayName = profile?.display_name || user?.displayName || user?.email?.split('@')[0] || 'User';
  const roleLabel = profile?.role && profile.role in ROLE_LABELS
    ? ROLE_LABELS[profile.role as UserRole]
    : ROLE_LABELS.facilities_manager;

  const handleSignOut = async () => {
    await signOut();
    navigate('/sign-in');
  };

  return (
    <header className="fixed top-0 left-0 right-0 h-14 bg-background border-b border-border z-40 px-4 flex items-center justify-between select-none">
      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={onToggleSidebar}
          aria-label="Toggle sidebar"
          className="w-9 h-9 flex items-center justify-center rounded-lg text-text hover:bg-surface border border-transparent hover:border-border transition-colors"
        >
          <PanelLeft className="w-5 h-5 text-muted hover:text-text" />
        </button>

        <div className="flex items-center">
          <span className="text-base font-semibold text-text tracking-tight">
            VixenOne
          </span>
          <span className="w-1.5 h-1.5 rounded-full bg-accent inline-block ml-1" />
        </div>
      </div>

      <div className="flex items-center">
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <button
              type="button"
              className="flex items-center gap-3 p-1.5 rounded-lg hover:bg-surface transition-colors focus:outline-none focus:ring-1 focus:ring-accent"
            >
              <Avatar className="h-8 w-8">
                <AvatarFallback>{initials}</AvatarFallback>
              </Avatar>
              <div className="text-left hidden sm:block">
                <div className="text-xs font-semibold text-text leading-tight">
                  {displayName}
                </div>
                <div className="text-[11px] text-muted leading-tight">
                  {roleLabel}
                </div>
              </div>
              <ChevronDown className="w-3.5 h-3.5 text-muted hidden sm:block" />
            </button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-48">
            <DropdownMenuItem className="cursor-pointer gap-2">
              <UserIcon className="w-4 h-4 text-muted" />
              <span>Profile</span>
            </DropdownMenuItem>
            <DropdownMenuItem
              onClick={handleSignOut}
              className="cursor-pointer gap-2 text-status-noncompliant-text focus:text-status-noncompliant-text focus:bg-status-noncompliant-bg"
            >
              <LogOut className="w-4 h-4 text-status-noncompliant-text" />
              <span>Sign out</span>
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </header>
  );
};
