import React from 'react';
import { Plus, Trash2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';

const DOT = {
  green: 'bg-green-500',
  amber: 'bg-amber-500',
  red: 'bg-red-500',
};

const STATUS_LABEL = {
  green: 'Reachable',
  amber: 'Not Seeded',
  red: 'Error',
};

function getIndicator(account) {
  if (account?.reachable) return 'green';
  if (!account?.seeded) return 'amber';
  return 'red';
}

export default function ProviderAccountsCard({
  providerKey,
  title,
  subtitle,
  accounts,
  onAdd,
  onRemove,
  addDisabled = false,
}) {
  const entries = Object.entries(accounts || {});

  return (
    <Card>
      <CardHeader className="py-3 flex flex-row items-center justify-between space-y-0 gap-3">
        <div className="min-w-0">
          <CardTitle className="text-base">{title}</CardTitle>
          <p className="text-xs text-muted-foreground truncate">{subtitle}</p>
        </div>
        <Button
          size="sm"
          variant={addDisabled ? 'outline' : 'default'}
          disabled={addDisabled}
          onClick={onAdd}
          className="shrink-0"
        >
          <Plus className="w-4 h-4 mr-1.5" />
          {addDisabled ? 'Coming soon' : 'Add an account'}
        </Button>
      </CardHeader>
      <CardContent className="text-sm space-y-1.5">
        {entries.length === 0 ? (
          <p className="text-xs text-muted-foreground">No accounts connected.</p>
        ) : (
          entries.map(([alias, account]) => {
            const indicator = getIndicator(account);
            return (
              <div key={alias} className="rounded-md border px-2 py-1.5 space-y-1">
                <div className="flex items-start justify-between gap-2">
                  <span className="flex items-start gap-2 min-w-0">
                    <span className={`w-2.5 h-2.5 rounded-full shrink-0 mt-1.5 ${DOT[indicator]}`} />
                    <span className="min-w-0">
                      <span className="block text-sm truncate">{account?.name || alias}</span>
                      <code className="block text-[11px] text-muted-foreground truncate">
                        {providerKey}:{alias}
                      </code>
                    </span>
                  </span>
                  <span className="flex items-center gap-2 shrink-0">
                    {providerKey === 'qbo' && account?.access_mode && (
                      <span className="text-[11px] rounded-full border px-2 py-0.5 text-muted-foreground">
                        {account.access_mode === 'read_only' ? 'Read only' : 'Read & write'}
                      </span>
                    )}
                    <span className="text-xs text-muted-foreground">
                      {STATUS_LABEL[indicator]}
                    </span>
                    {onRemove && account?.seeded && (
                      <button
                        type="button"
                        onClick={() => onRemove(alias)}
                        title="Remove account"
                        className="text-muted-foreground hover:text-destructive transition-colors"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    )}
                  </span>
                </div>
                {account?.error && (
                  <p className="text-xs text-destructive break-words">{account.error}</p>
                )}
              </div>
            );
          })
        )}
      </CardContent>
    </Card>
  );
}