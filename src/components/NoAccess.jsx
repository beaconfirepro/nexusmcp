import React from 'react';
import { ShieldAlert, LogOut } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { base44 } from '@/api/base44Client';

export default function NoAccess() {
  return (
    <div className="min-h-screen flex items-center justify-center p-4 bg-background">
      <div className="max-w-sm text-center space-y-4">
        <ShieldAlert className="w-10 h-10 mx-auto text-muted-foreground" />
        <h1 className="text-xl font-heading font-bold">You don't have access</h1>
        <p className="text-sm text-muted-foreground">
          This app is limited to invited administrators.
        </p>
        <Button variant="outline" onClick={() => base44.auth.logout('/login')}>
          <LogOut className="w-4 h-4 mr-1.5" />
          Logout
        </Button>
      </div>
    </div>
  );
}