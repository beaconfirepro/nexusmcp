import React, { useState, useEffect, useCallback, useRef } from 'react';
import { Activity, RefreshCw, CheckCircle2, XCircle, Server, AlertCircle, LogOut } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { base44 } from '@/api/base44Client';

const handleLogout = () => {
  base44.auth.logout('/login');
};
import ProviderCard from '@/components/mcp/ProviderCard';

const PROVIDER_NAMES = ['connecteam', 'qbo', 'hubspot', 'microsoft', 'google'];

const DEFAULT_SERVER_URL = 'https://multi-mcp.gentleplant-1d0fa284.eastus.azurecontainerapps.io';

export default function McpStatus() {
  const [serverUrl, setServerUrl] = useState(() => localStorage.getItem('mcp_server_url') || DEFAULT_SERVER_URL);
  const [urlInput, setUrlInput] = useState(serverUrl);
  const [healthStatus, setHealthStatus] = useState(null);
  const [providerStatus, setProviderStatus] = useState(null);
  const [loadingHealth, setLoadingHealth] = useState(false);
  const [loadingStatus, setLoadingStatus] = useState(false);
  const [statusError, setStatusError] = useState(null);
  const intervalRef = useRef(null);

  const checkHealth = useCallback(async (url) => {
    if (!url) return;
    setLoadingHealth(true);
    try {
      const resp = await base44.functions.invoke('mcpHealth', { url });
      setHealthStatus(resp.data);
    } catch (err) {
      setHealthStatus({ healthy: false, message: err.message, checked_at: new Date().toISOString() });
    } finally {
      setLoadingHealth(false);
    }
  }, []);

  const checkProviderStatus = useCallback(async (url) => {
    if (!url) return;
    setLoadingStatus(true);
    setStatusError(null);
    try {
      const resp = await base44.functions.invoke('mcpStatus', { url });
      const data = resp.data;
      if (data?.ok === false) {
        setStatusError(data.error || `Server returned status ${data.status}`);
        setProviderStatus(null);
      } else if (data?.providers) {
        setProviderStatus(data);
      } else {
        setStatusError(data?.error || 'Unexpected response from server.');
        setProviderStatus(null);
      }
    } catch (err) {
      setStatusError(err.message || 'Failed to reach MCP server.');
      setProviderStatus(null);
    } finally {
      setLoadingStatus(false);
    }
  }, []);

  useEffect(() => {
    if (serverUrl) {
      checkHealth(serverUrl);
      checkProviderStatus(serverUrl);
    }
  }, [serverUrl, checkHealth, checkProviderStatus]);

  // Auto-refresh provider status every 60s
  useEffect(() => {
    if (intervalRef.current) clearInterval(intervalRef.current);
    if (!serverUrl) return;
    intervalRef.current = setInterval(() => checkProviderStatus(serverUrl), 60000);
    return () => { if (intervalRef.current) clearInterval(intervalRef.current); };
  }, [serverUrl, checkProviderStatus]);

  const handleSave = () => {
    const cleaned = urlInput.replace(/\/+$/, '');
    localStorage.setItem('mcp_server_url', cleaned);
    setServerUrl(cleaned);
    checkHealth(cleaned);
    checkProviderStatus(cleaned);
  };

  const healthy = healthStatus?.healthy;
  const lastHealthCheck = healthStatus?.checked_at
    ? new Date(healthStatus.checked_at).toLocaleTimeString()
    : null;
  const providers = providerStatus?.providers || {};
  const providerCheckedAt = providerStatus?.checked_at;

  return (
    <div className="min-h-screen bg-background flex items-center justify-center p-4">
      <div className="w-full max-w-2xl space-y-6">
        <div className="flex items-center gap-3">
          <Server className="w-7 h-7 text-foreground" />
          <div className="flex-1">
            <h1 className="text-2xl font-heading font-bold">MCP Server Status</h1>
            <p className="text-sm text-muted-foreground">Multi-Account MCP Server health monitor</p>
          </div>
          <Button variant="ghost" size="sm" onClick={handleLogout} className="shrink-0">
            <LogOut className="w-4 h-4 mr-1.5" />
            Logout
          </Button>
        </div>

        {/* Server URL + health badge */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center justify-between">
              <span>Server Connection</span>
              {healthStatus && (
                <span className={`flex items-center gap-1.5 text-sm font-normal ${healthy ? 'text-primary' : 'text-destructive'}`}>
                  {healthy ? <CheckCircle2 className="w-4 h-4" /> : <XCircle className="w-4 h-4" />}
                  {healthy ? 'Healthy' : 'Offline'}
                </span>
              )}
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="flex gap-2">
              <select
                className="shrink-0 rounded-md border border-input bg-background px-3 text-sm h-9"
                value={urlInput === DEFAULT_SERVER_URL ? DEFAULT_SERVER_URL : ''}
                onChange={(e) => { setUrlInput(e.target.value); }}
              >
                <option value={DEFAULT_SERVER_URL}>Production (East US)</option>
                <option value="">Custom…</option>
              </select>
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
            {healthStatus?.server?.version && (
              <p className="text-xs text-muted-foreground">Version {healthStatus.server.version}</p>
            )}
            {healthStatus?.message && !healthy && (
              <p className="text-xs text-destructive">{healthStatus.message}</p>
            )}
            {lastHealthCheck && (
              <div className="flex items-center justify-between">
                <p className="text-xs text-muted-foreground">Last checked: {lastHealthCheck}</p>
                <Button variant="ghost" size="sm" onClick={() => checkHealth(serverUrl)} disabled={loadingHealth || !serverUrl}>
                  <RefreshCw className={`w-4 h-4 mr-1.5 ${loadingHealth ? 'animate-spin' : ''}`} />
                  Refresh
                </Button>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Provider status */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center justify-between">
              <span className="flex items-center gap-2">
                <Activity className="w-4 h-4" />
                Provider Status
              </span>
              <Button variant="ghost" size="sm" onClick={() => checkProviderStatus(serverUrl)} disabled={loadingStatus || !serverUrl}>
                <RefreshCw className={`w-4 h-4 mr-1.5 ${loadingStatus ? 'animate-spin' : ''}`} />
                Refresh
              </Button>
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {!serverUrl && (
              <p className="text-sm text-muted-foreground">Save a server URL to check provider status.</p>
            )}
            {serverUrl && loadingStatus && !providerStatus && !statusError && (
              <div className="flex items-center justify-center py-8">
                <RefreshCw className="w-5 h-5 animate-spin text-muted-foreground" />
              </div>
            )}
            {statusError && (
              <div className="flex items-start gap-2 rounded-lg border border-destructive/20 bg-destructive/5 p-3">
                <AlertCircle className="w-4 h-4 text-destructive shrink-0 mt-0.5" />
                <p className="text-xs text-destructive">{statusError}</p>
              </div>
            )}
            {providerStatus && !statusError && (
              <>
                <div className="space-y-2">
                  {PROVIDER_NAMES.map((name) => (
                    <ProviderCard
                      key={name}
                      name={name}
                      data={providers[name]}
                      checkedAt={providerCheckedAt}
                    />
                  ))}
                </div>
                {providerCheckedAt && (
                  <p className="text-xs text-muted-foreground text-right">
                    Last checked: {new Date(providerCheckedAt).toLocaleTimeString()}
                  </p>
                )}
              </>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}