import React, { useState, useEffect, useCallback, useRef } from 'react';
import { Activity, RefreshCw, CheckCircle2, XCircle, AlertCircle } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { base44 } from '@/api/base44Client';
import ProviderCard from '@/components/mcp/ProviderCard';

const PROVIDER_NAMES = ['connecteam', 'qbo', 'hubspot', 'microsoft', 'google'];

export default function McpStatus() {
  const [serverUrl, setServerUrl] = useState('');
  const [healthStatus, setHealthStatus] = useState(null);
  const [providerStatus, setProviderStatus] = useState(null);
  const [loadingHealth, setLoadingHealth] = useState(false);
  const [loadingStatus, setLoadingStatus] = useState(false);
  const [statusError, setStatusError] = useState(null);
  const intervalRef = useRef(null);

  const checkHealth = useCallback(async () => {
    setLoadingHealth(true);
    try {
      const resp = await base44.functions.invoke('mcpHealth', {});
      setHealthStatus(resp.data);
    } catch (err) {
      setHealthStatus({ healthy: false, message: err.message, checked_at: new Date().toISOString() });
    } finally {
      setLoadingHealth(false);
    }
  }, []);

  const checkProviderStatus = useCallback(async () => {
    setLoadingStatus(true);
    setStatusError(null);
    try {
      const resp = await base44.functions.invoke('mcpStatus', {});
      const data = resp.data;
      if (data?.ok === false) {
        if (data.status === 401) {
          setStatusError('The server rejected STATUS_TOKEN. Verify it matches the value configured on the server.');
        } else {
          setStatusError(data.error || `Server returned status ${data.status}`);
        }
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
    base44.functions
      .invoke('mcpConfig', {})
      .then((resp) => setServerUrl(resp.data?.mcp_base_url || ''))
      .catch(() => setServerUrl(''));
    checkHealth();
    checkProviderStatus();
  }, [checkHealth, checkProviderStatus]);

  // Auto-refresh provider status every 60s
  useEffect(() => {
    intervalRef.current = setInterval(checkProviderStatus, 60000);
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [checkProviderStatus]);

  const healthy = healthStatus?.healthy;
  const lastHealthCheck = healthStatus?.checked_at
    ? new Date(healthStatus.checked_at).toLocaleTimeString()
    : null;
  const providers = providerStatus?.providers || {};
  const providerCheckedAt = providerStatus?.checked_at;

  return (
    <div className="max-w-2xl space-y-6">
      <div className="flex items-center gap-3">
        <Activity className="w-6 h-6 text-primary" />
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
            {healthStatus && (
              <span className={`flex items-center gap-1.5 text-sm font-normal ${healthy ? 'text-primary' : 'text-destructive'}`}>
                {healthy ? <CheckCircle2 className="w-4 h-4" /> : <XCircle className="w-4 h-4" />}
                {healthy ? 'Healthy' : 'Offline'}
              </span>
            )}
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div>
            <p className="text-xs font-medium text-muted-foreground mb-1">Server URL</p>
            <code className="block text-xs break-all bg-muted rounded-md px-3 py-2">
              {serverUrl || 'Not configured (set MCP_BASE_URL in Secrets)'}
            </code>
          </div>
          {healthStatus?.server?.version && (
            <p className="text-xs text-muted-foreground">Version {healthStatus.server.version}</p>
          )}
          {healthStatus?.message && !healthy && (
            <p className="text-xs text-destructive">{healthStatus.message}</p>
          )}
          <div className="flex items-center justify-between">
            {lastHealthCheck && (
              <p className="text-xs text-muted-foreground">Last checked: {lastHealthCheck}</p>
            )}
            <Button variant="ghost" size="sm" onClick={checkHealth} disabled={loadingHealth}>
              <RefreshCw className={`w-4 h-4 mr-1.5 ${loadingHealth ? 'animate-spin' : ''}`} />
              Refresh
            </Button>
          </div>
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
            <Button variant="ghost" size="sm" onClick={checkProviderStatus} disabled={loadingStatus}>
              <RefreshCw className={`w-4 h-4 mr-1.5 ${loadingStatus ? 'animate-spin' : ''}`} />
              Refresh
            </Button>
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          {loadingStatus && !providerStatus && !statusError && (
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
  );
}