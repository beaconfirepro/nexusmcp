import React, { useState, useEffect, useCallback } from 'react';
import { Activity, RefreshCw, CheckCircle2, XCircle, Server } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { base44 } from '@/api/base44Client';

const SERVICES = [
  { name: 'Connecteam', type: 'API Key' },
  { name: 'QuickBooks Online', type: 'OAuth' },
  { name: 'HubSpot', type: 'Private App' },
  { name: 'SharePoint', type: 'Graph OAuth' },
  { name: 'Outlook Mail', type: 'Graph OAuth' },
  { name: 'Outlook Calendar', type: 'Graph OAuth' },
  { name: 'Gmail', type: 'Google OAuth' },
  { name: 'Google Calendar', type: 'Google OAuth' },
];

export default function McpStatus() {
  const [serverUrl, setServerUrl] = useState(() => localStorage.getItem('mcp_server_url') || '');
  const [urlInput, setUrlInput] = useState(serverUrl);
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(false);

  const checkHealth = useCallback(async (url) => {
    if (!url) return;
    setLoading(true);
    try {
      const resp = await base44.functions.invoke('mcpHealth', { url });
      setStatus(resp.data);
    } catch (err) {
      setStatus({ healthy: false, message: err.message, checked_at: new Date().toISOString() });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (serverUrl) checkHealth(serverUrl);
  }, [serverUrl, checkHealth]);

  const handleSave = () => {
    const cleaned = urlInput.replace(/\/+$/, '');
    localStorage.setItem('mcp_server_url', cleaned);
    setServerUrl(cleaned);
    checkHealth(cleaned);
  };

  const healthy = status?.healthy;
  const lastChecked = status?.checked_at
    ? new Date(status.checked_at).toLocaleTimeString()
    : null;

  return (
    <div className="min-h-screen bg-background flex items-center justify-center p-4">
      <div className="w-full max-w-2xl space-y-6">
        <div className="flex items-center gap-3">
          <Server className="w-7 h-7 text-foreground" />
          <div>
            <h1 className="text-2xl font-heading font-bold">MCP Server Status</h1>
            <p className="text-sm text-muted-foreground">Multi-Account MCP Server health monitor</p>
          </div>
        </div>

        {/* Server URL + health badge */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center justify-between">
              <span>Server Connection</span>
              {status && (
                <span className={`flex items-center gap-1.5 text-sm font-normal ${healthy ? 'text-primary' : 'text-destructive'}`}>
                  {healthy ? <CheckCircle2 className="w-4 h-4" /> : <XCircle className="w-4 h-4" />}
                  {healthy ? 'Healthy' : 'Offline'}
                </span>
              )}
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="flex gap-2">
              <Input
                placeholder="https://your-mcp-server.azurecontainerapps.io"
                value={urlInput}
                onChange={(e) => setUrlInput(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleSave()}
              />
              <Button onClick={handleSave} variant="default" className="shrink-0">
                Save
              </Button>
            </div>
            {status?.server?.version && (
              <p className="text-xs text-muted-foreground">Version {status.server.version}</p>
            )}
            {status?.message && !healthy && (
              <p className="text-xs text-destructive">{status.message}</p>
            )}
            {lastChecked && (
              <div className="flex items-center justify-between">
                <p className="text-xs text-muted-foreground">Last checked: {lastChecked}</p>
                <Button variant="ghost" size="sm" onClick={() => checkHealth(serverUrl)} disabled={loading || !serverUrl}>
                  <RefreshCw className={`w-4 h-4 mr-1.5 ${loading ? 'animate-spin' : ''}`} />
                  Refresh
                </Button>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Services list */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Activity className="w-4 h-4" />
              Connected Services
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
              {SERVICES.map((s) => (
                <div key={s.name} className="flex items-center justify-between rounded-lg border border-border px-3 py-2">
                  <span className="text-sm font-medium">{s.name}</span>
                  <span className="text-xs text-muted-foreground">{s.type}</span>
                </div>
              ))}
            </div>
            <p className="text-xs text-muted-foreground mt-3">
              Use the <code className="text-xs bg-muted px-1 py-0.5 rounded">check_provider_connectivity</code> MCP tool for an authenticated deep health check.
            </p>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}