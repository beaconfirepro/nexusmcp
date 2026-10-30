import React, { useEffect, useState } from 'react';
import { AlertCircle, RefreshCw, Users } from 'lucide-react';
import { base44 } from '@/api/base44Client';
import ProviderAccountsCard from '@/components/accounts/ProviderAccountsCard';
import AddAccountDialog from '@/components/accounts/AddAccountDialog';

const PROVIDERS = [
  { key: 'microsoft', title: 'Microsoft', subtitle: 'Outlook + SharePoint', addable: true },
  { key: 'google', title: 'Google', subtitle: 'Gmail + Calendar' },
  { key: 'qbo', title: 'QuickBooks', subtitle: 'QuickBooks Online' },
  { key: 'hubspot', title: 'HubSpot', subtitle: 'HubSpot CRM' },
  { key: 'helm', title: 'Helm', subtitle: 'Helm Public API v1' },
];

export default function Accounts() {
  const [providers, setProviders] = useState({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [dialogOpen, setDialogOpen] = useState(false);

  useEffect(() => {
    let active = true;

    (async () => {
      try {
        const resp = await base44.functions.invoke('mcpStatus', {});
        const data = resp.data;
        if (!active) return;

        if (data?.ok === false) {
          setError(
            data.status === 401
              ? 'The server rejected STATUS_TOKEN. Verify it matches the value configured on the server.'
              : data.error || `Server returned status ${data.status}`
          );
        } else if (data?.providers) {
          setProviders(data.providers);
        } else {
          setError(data?.error || 'Unexpected response from server.');
        }
      } catch (err) {
        if (active) setError(err.message || 'Failed to reach MCP server.');
      } finally {
        if (active) setLoading(false);
      }
    })();

    return () => {
      active = false;
    };
  }, []);

  return (
    <div className="max-w-2xl space-y-6">
      <div className="flex items-center gap-3">
        <Users className="w-6 h-6 text-primary" />
        <div>
          <h1 className="text-2xl font-heading font-bold">Accounts</h1>
          <p className="text-sm text-muted-foreground">
            Connected provider accounts available to the MCP server
          </p>
        </div>
      </div>

      {error && (
        <div className="flex items-start gap-2 rounded-lg border border-destructive/20 bg-destructive/5 p-3">
          <AlertCircle className="w-4 h-4 text-destructive shrink-0 mt-0.5" />
          <p className="text-xs text-destructive">{error}</p>
        </div>
      )}

      {loading ? (
        <div className="flex items-center justify-center py-12">
          <RefreshCw className="w-5 h-5 animate-spin text-muted-foreground" />
        </div>
      ) : (
        <div className="space-y-3">
          {PROVIDERS.map(({ key, title, subtitle, addable }) => (
            <ProviderAccountsCard
              key={key}
              providerKey={key}
              title={title}
              subtitle={subtitle}
              accounts={providers[key]?.accounts}
              addDisabled={!addable}
              onAdd={addable ? () => setDialogOpen(true) : undefined}
            />
          ))}
        </div>
      )}

      <AddAccountDialog
        open={dialogOpen}
        onOpenChange={setDialogOpen}
        providerKey="microsoft"
      />
    </div>
  );
}