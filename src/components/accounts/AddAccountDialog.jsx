import React, { useEffect, useState } from 'react';
import { base44 } from '@/api/base44Client';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';

const ALIAS_RE = /^[a-z0-9][a-z0-9_-]{0,31}$/;

export default function AddAccountDialog({ open, onOpenChange, providerKey }) {
  const [alias, setAlias] = useState('');
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (open) {
      setAlias('');
      setError(null);
      setBusy(false);
    }
  }, [open]);

  const valid = ALIAS_RE.test(alias);

  const handleContinue = async () => {
    if (!valid || busy) return;
    setBusy(true);
    setError(null);
    try {
      const resp = await base44.functions.invoke('mcpConfig', {});
      const baseUrl = (resp.data?.mcp_base_url || '').replace(/\/+$/, '');
      if (!baseUrl) {
        throw new Error('MCP server URL is not configured (set MCP_BASE_URL in Secrets).');
      }
      window.location.href = `${baseUrl}/connect/${providerKey}?alias=${encodeURIComponent(alias)}`;
    } catch (err) {
      setError(err.message || 'Could not start the connection.');
      setBusy(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Add a Microsoft account</DialogTitle>
          <DialogDescription>
            Name this account, then continue to the Nexus approval page and Microsoft sign-in.
          </DialogDescription>
        </DialogHeader>
        <form
          className="space-y-2"
          onSubmit={(e) => {
            e.preventDefault();
            handleContinue();
          }}
        >
          <Label htmlFor="account-alias">Account name</Label>
          <Input
            id="account-alias"
            value={alias}
            onChange={(e) => setAlias(e.target.value)}
            placeholder="work2"
            autoComplete="off"
            autoFocus
          />
          <p className="text-xs text-muted-foreground">
            This is the name you'll pass as account, e.g. {providerKey}:work2
          </p>
          {alias && !valid && (
            <p className="text-xs text-destructive">
              Lowercase letters, numbers, dashes and underscores only, starting with a letter or
              number.
            </p>
          )}
          {error && <p className="text-xs text-destructive">{error}</p>}
        </form>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={busy}>
            Cancel
          </Button>
          <Button onClick={handleContinue} disabled={!valid || busy}>
            {busy ? 'Redirecting…' : 'Continue'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}