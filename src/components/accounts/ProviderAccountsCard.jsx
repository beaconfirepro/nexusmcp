import React from 'react';
import { Plus } from 'lucide-react';
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
                <div className="flex items-center justify-between gap-2">
                  <span className="flex items-center gap-2 min-w-0">
                    <span className={`w-2.5 h-2.5 rounded-full shrink-0 ${DOT[indicator]}`} />
                    <code className="text-xs truncate">
                      {providerKey}:{alias}
                    </code>
                  </span>
                  <span className="text-xs text-muted-foreground shrink-0">
                    {STATUS_LABEL[indicator]}
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