import React, { useState } from 'react';
import { ChevronDown, ChevronRight } from 'lucide-react';
import { Card, CardContent, CardHeader } from '@/components/ui/card';

const STATUS_COLORS = {
  green: 'bg-green-500',
  amber: 'bg-amber-500',
  red: 'bg-red-500',
};

function getIndicator(data) {
  if (data?.reachable) return 'green';
  if (!data?.seeded) return 'amber';
  return 'red';
}

function AccountDetails({ data, checkedAt }) {
  const expiresAt = data?.expires_at
    ? new Date(data.expires_at).toLocaleString()
    : 'N/A';

  return (
    <div className="space-y-3">
      <div>
        <p className="text-xs font-medium text-muted-foreground mb-1">Scopes</p>
        {data?.scopes?.length ? (
          <div className="flex flex-wrap gap-1">
            {data.scopes.map((s) => (
              <code key={s} className="text-xs bg-muted px-1.5 py-0.5 rounded">{s}</code>
            ))}
          </div>
        ) : (
          <p className="text-xs text-muted-foreground">None</p>
        )}
      </div>
      <div className="flex justify-between">
        <span className="text-xs text-muted-foreground">Token expiry:</span>
        <span className="text-xs">{expiresAt}</span>
      </div>
      <div className="flex justify-between">
        <span className="text-xs text-muted-foreground">Last checked:</span>
        <span className="text-xs">{checkedAt ? new Date(checkedAt).toLocaleTimeString() : 'N/A'}</span>
      </div>
      {data?.error && (
        <p className="text-xs text-destructive border border-destructive/20 rounded p-2 bg-destructive/5">{data.error}</p>
      )}
    </div>
  );
}

function AccountRow({ alias, data, checkedAt }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="border rounded-md p-2 space-y-2">
      <button className="flex items-center justify-between w-full text-left" onClick={() => setOpen(!open)}>
        <span className="flex items-center gap-2">
          <span className={`w-2.5 h-2.5 rounded-full ${STATUS_COLORS[getIndicator(data)]}`} />
          <code className="text-xs">{alias}</code>
        </span>
        <span className="text-xs text-muted-foreground">
          {data?.reachable ? 'Reachable' : !data?.seeded ? 'Not Seeded' : 'Error'}
        </span>
      </button>
      {open && <AccountDetails data={data} checkedAt={checkedAt} />}
    </div>
  );
}

export default function ProviderCard({ name, data, checkedAt }) {
  const [expanded, setExpanded] = useState(false);
  const accounts = data?.accounts && Object.keys(data.accounts).length > 1 ? Object.entries(data.accounts) : null;
  // With several accounts the header reflects the worst one, not just 'main'.
  const rank = { green: 0, amber: 1, red: 2 };
  const color = accounts
    ? accounts.map(([, a]) => getIndicator(a)).reduce((w, c) => (rank[c] > rank[w] ? c : w), 'green')
    : getIndicator(data);
  const okCount = accounts ? accounts.filter(([, a]) => a?.reachable).length : 0;
  const summary = accounts
    ? `${okCount}/${accounts.length} accounts reachable`
    : data?.reachable ? 'Reachable' : !data?.seeded ? 'Not Seeded' : 'Error';

  return (
    <Card>
      <CardHeader className="py-3">
        <button
          className="flex items-center justify-between w-full text-left"
          onClick={() => setExpanded(!expanded)}
        >
          <span className="flex items-center gap-2">
            {expanded
              ? <ChevronDown className="w-4 h-4 text-muted-foreground" />
              : <ChevronRight className="w-4 h-4 text-muted-foreground" />}
            <span className={`w-3 h-3 rounded-full ${STATUS_COLORS[color]}`} />
            <span className="font-medium capitalize">{name}</span>
          </span>
          <span className="text-xs text-muted-foreground">{summary}</span>
        </button>
      </CardHeader>
      {expanded && (
        <CardContent className="pt-0 text-sm">
          {accounts ? (
            <div className="space-y-2">
              {accounts.map(([alias, a]) => (
                <AccountRow key={alias} alias={alias} data={a} checkedAt={checkedAt} />
              ))}
            </div>
          ) : (
            <AccountDetails data={data} checkedAt={checkedAt} />
          )}
        </CardContent>
      )}
    </Card>
  );
}