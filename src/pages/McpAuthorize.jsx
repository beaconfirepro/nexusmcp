import React, { useState } from 'react';
import { ShieldCheck, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { useAuth } from '@/lib/AuthContext';
import { base44 } from '@/api/base44Client';

export default function McpAuthorize() {
  const { user } = useAuth();
  const params = new URLSearchParams(window.location.search);
  const request = params.get('request') || '';
  const purpose = params.get('purpose') || '';
  const [busy, setBusy] = useState(null);
  const [error, setError] = useState('');

  const approve = async () => {
    setBusy('approve');
    setError('');
    try {
      const resp = await base44.functions.invoke('mcpAuthorize', { request });
      const url = resp.data?.redirect_url;
      if (!url) throw new Error('No redirect URL returned.');
      window.location.href = url;
    } catch (err) {
      setError(err?.response?.data?.error || err.message || 'Approval failed.');
      setBusy(null);
    }
  };

  const deny = async () => {
    setBusy('deny');
    setError('');
    try {
      const resp = await base44.functions.invoke('mcpConfig', {});
      const base = (resp.data?.mcp_base_url || '').replace(/\/+$/, '');
      if (!base) throw new Error('MCP base URL is not configured.');
      window.location.href = `${base}/authorize/bridge?error=access_denied&request=${encodeURIComponent(request)}`;
    } catch (err) {
      setError(err?.response?.data?.error || err.message || 'Could not deny the request.');
      setBusy(null);
    }
  };

  if (!request) {
    return (
      <div className="min-h-screen flex items-center justify-center p-4 bg-background">
        <Card className="w-full max-w-md">
          <CardContent className="p-6 text-sm text-muted-foreground">
            Missing request parameter. Start the connection from your MCP client.
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center p-4 bg-background">
      <Card className="w-full max-w-md">
        <CardContent className="p-6 space-y-5">
          <div className="flex items-center gap-3">
            <ShieldCheck className="w-6 h-6 text-primary shrink-0" />
            <h1 className="text-lg font-heading font-bold">Allow this connection to Nexus?</h1>
          </div>

          {purpose && <p className="text-sm text-muted-foreground">{purpose}</p>}

          <div className="rounded-md bg-muted px-3 py-2 text-sm">
            Signed in as <span className="font-medium">{user?.email}</span>
          </div>

          {error && <p className="text-sm text-destructive">{error}</p>}

          <div className="flex gap-2">
            <Button className="flex-1" onClick={approve} disabled={!!busy}>
              {busy === 'approve' && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}
              Approve
            </Button>
            <Button variant="outline" className="flex-1" onClick={deny} disabled={!!busy}>
              {busy === 'deny' && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}
              Deny
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}