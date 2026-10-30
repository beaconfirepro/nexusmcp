import React from 'react';
import { NavLink, Outlet } from 'react-router-dom';
import { Activity, Plug, LogOut, Server } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useAuth } from '@/lib/AuthContext';
import { base44 } from '@/api/base44Client';

const NAV_ITEMS = [
  { to: '/status', label: 'Status', icon: Activity },
  { to: '/apis', label: 'APIs', icon: Plug },
];

export default function DashboardLayout() {
  const { user } = useAuth();

  return (
    <div className="min-h-screen bg-background md:flex">
      <aside className="border-b md:border-b-0 md:border-r border-border bg-card md:w-60 md:min-h-screen flex flex-col">
        <div className="px-4 py-4 flex items-center gap-2">
          <Server className="w-5 h-5 text-primary" />
          <span className="font-heading font-bold text-lg">NexusMCP</span>
        </div>
        <nav className="px-2 flex md:flex-col gap-1">
          {NAV_ITEMS.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                `flex items-center gap-2 rounded-md px-3 py-2 text-sm font-medium transition-colors ${
                  isActive
                    ? 'bg-primary text-primary-foreground'
                    : 'text-muted-foreground hover:bg-muted hover:text-foreground'
                }`
              }
            >
              <Icon className="w-4 h-4" />
              {label}
            </NavLink>
          ))}
        </nav>
        <div className="md:mt-auto px-4 py-4 flex flex-col gap-2">
          {user?.email && (
            <p className="text-xs text-muted-foreground truncate">{user.email}</p>
          )}
          <Button
            variant="outline"
            size="sm"
            onClick={() => base44.auth.logout('/login')}
            className="w-fit"
          >
            <LogOut className="w-4 h-4 mr-1.5" />
            Logout
          </Button>
        </div>
      </aside>
      <main className="flex-1 min-w-0 p-4 md:p-8">
        <Outlet />
      </main>
    </div>
  );
}