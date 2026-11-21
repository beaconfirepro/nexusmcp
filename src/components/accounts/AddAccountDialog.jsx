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

const slugify = (value) =>
  value
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 32)
    .replace(/-+$/g, '');

const ACCESS_OPTIONS = [
  { value: 'read_only', label: 'Read only', hint: 'Reports and queries only' },
  { value: 'read_write', label: 'Read and write', hint: 'Can also create and change records' },
];

export default function AddAccountDialog({ open, onOpenChange, provider = 'microsoft' }) {
  const isQbo = provider === 'qbo';
  const [name, setName] = useState('');
  const [alias, setAlias] = useState('');
  const [mode, setMode] = useState('read_only');
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (open) {
      setName('');
      setAlias('');
      setMode('read_only');
      setError(null);
      setBusy(false);
    }
  }, [open]);

  const qboAlias = slugify(name);
  const valid = isQbo ? Boolean(name.trim()) && ALIAS_RE.test(qboAlias) : ALIAS_RE.test(alias);

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
      window.location.href = isQbo
        ? `${baseUrl}/connect/qbo?alias=${encodeURIComponent(qboAlias)}&name=${encodeURIComponent(
            name.trim()
          )}&mode=${mode}`
        : `${baseUrl}/connect/${provider}?alias=${encodeURIComponent(alias)}`;
    } catch (err) {
      setError(err.message || 'Could not start the connection.');
      setBusy(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>{isQbo ? 'Add a QuickBooks account' : 'Add a Microsoft account'}</DialogTitle>
          <DialogDescription>
            {isQbo
              ? 'Name this company and choose what the agent may do with it, then continue to the Nexus approval page and QuickBooks sign-in.'
              : 'Name this account, then continue to the Nexus approval page and Microsoft sign-in.'}
          </DialogDescription>
        </DialogHeader>
        <form
          className="space-y-2"
          onSubmit={(e) => {
            e.preventDefault();
            handleContinue();
          }}
        >
          {isQbo ? (
            <>
              <Label htmlFor="account-name">Account name</Label>
              <Input
                id="account-name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Acme Books"
                maxLength={60}
                autoComplete="off"
                autoFocus
              />
              <p className="text-xs text-muted-foreground">
                The agent picks this account by this name.
                {qboAlias ? ` Saved as qbo:${qboAlias}.` : ''}
              </p>
              <Label className="pt-2">Access</Label>
              <div className="grid grid-cols-2 gap-2">
                {ACCESS_OPTIONS.map((option) => (
                  <button
                    key={option.value}
                    type="button"
                    onClick={() => setMode(option.value)}
                    className={`rounded-md border px-3 py-2 text-left transition-colors ${
                      mode === option.value
                        ? 'border-primary bg-primary/10'
                        : 'border-input hover:bg-muted'
                    }`}
                  >
                    <span className="block text-sm font-medium">{option.label}</span>
                    <span className="block text-xs text-muted-foreground">{option.hint}</span>
                  </button>
                ))}
              </div>
            </>
          ) : (
            <>
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
                This is the name you'll pass as account, e.g. {provider}:work2
              </p>
              {alias && !ALIAS_RE.test(alias) && (
                <p className="text-xs text-destructive">
                  Lowercase letters, numbers, dashes and underscores only, starting with a letter
                  or number.
                </p>
              )}
            </>
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