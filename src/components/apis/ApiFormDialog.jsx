import React, { useEffect, useState } from 'react';
import { Loader2 } from 'lucide-react';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Switch } from '@/components/ui/switch';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';

const EMPTY = {
  name: '',
  slug: '',
  base_url: '',
  auth_type: 'bearer',
  header_name: '',
  secret: '',
  enabled: true,
  description: '',
};

const SLUG_RE = /^[a-z][a-z0-9_]{1,30}$/;

export default function ApiFormDialog({ open, onOpenChange, initial, onSave }) {
  const [form, setForm] = useState(EMPTY);
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!open) return;
    setError('');
    setSaving(false);
    setForm(
      initial
        ? {
            name: initial.name || '',
            slug: initial.slug || '',
            base_url: initial.base_url || '',
            auth_type: initial.auth_type || 'bearer',
            header_name: initial.header_name || '',
            secret: '',
            enabled: initial.enabled !== false,
            description: initial.description || '',
          }
        : EMPTY
    );
  }, [open, initial]);

  const set = (key, value) => setForm((f) => ({ ...f, [key]: value }));

  const submit = async (e) => {
    e.preventDefault();
    setError('');

    const values = {
      name: form.name.trim(),
      slug: form.slug.trim(),
      base_url: form.base_url.trim(),
      auth_type: form.auth_type,
      header_name: form.auth_type === 'header' ? form.header_name.trim() : '',
      enabled: form.enabled,
      description: form.description.trim(),
    };
    if (!values.name) return setError('Name is required.');
    if (!SLUG_RE.test(values.slug)) {
      return setError('Slug must start with a lowercase letter and use only a-z, 0-9 or _ (2-31 characters).');
    }
    if (!values.base_url.startsWith('https://')) {
      return setError('Base URL must start with https://');
    }
    if (values.auth_type === 'header' && !values.header_name) {
      return setError('Header name is required for header auth (e.g. X-API-KEY).');
    }
    const secret = form.secret.trim();
    if (secret) values.secret = secret;
    else if (!initial) values.secret = '';

    setSaving(true);
    try {
      await onSave(values);
    } catch (err) {
      setError(err?.response?.data?.error || err.message || 'Failed to save.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{initial ? 'Edit API' : 'Add an API'}</DialogTitle>
          <DialogDescription>
            {initial
              ? 'Update this connection. The secret is never shown again once saved.'
              : 'Register an external API the MCP server can call as a tool.'}
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={submit} className="space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label htmlFor="api-name">Name</Label>
              <Input
                id="api-name"
                value={form.name}
                onChange={(e) => set('name', e.target.value)}
                placeholder="Stripe Customers"
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="api-slug">Slug (tool name)</Label>
              <Input
                id="api-slug"
                value={form.slug}
                onChange={(e) => set('slug', e.target.value)}
                placeholder="stripe_customers"
                className="font-mono"
              />
            </div>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="api-base-url">Base URL</Label>
            <Input
              id="api-base-url"
              value={form.base_url}
              onChange={(e) => set('base_url', e.target.value)}
              placeholder="https://api.example.com"
              className="font-mono"
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label>Auth type</Label>
              <Select value={form.auth_type} onValueChange={(v) => set('auth_type', v)}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="bearer">Bearer</SelectItem>
                  <SelectItem value="header">Header</SelectItem>
                  <SelectItem value="none">None</SelectItem>
                </SelectContent>
              </Select>
            </div>
            {form.auth_type === 'header' && (
              <div className="space-y-1.5">
                <Label htmlFor="api-header-name">Header name</Label>
                <Input
                  id="api-header-name"
                  value={form.header_name}
                  onChange={(e) => set('header_name', e.target.value)}
                  placeholder="X-API-KEY"
                  className="font-mono"
                />
              </div>
            )}
          </div>

          {form.auth_type !== 'none' && (
            <div className="space-y-1.5">
              <Label htmlFor="api-secret">{initial ? 'Replace key' : 'Secret'}</Label>
              <Input
                id="api-secret"
                type="password"
                value={form.secret}
                onChange={(e) => set('secret', e.target.value)}
                placeholder={
                  initial
                    ? 'Leave blank to keep the current key'
                    : 'API key or token'
                }
                autoComplete="new-password"
              />
              {initial?.secret && (
                <p className="text-xs text-muted-foreground">
                  Current key ••••{initial.secret.slice(-4)}
                </p>
              )}
            </div>
          )}

          <div className="space-y-1.5">
            <Label htmlFor="api-description">Description</Label>
            <Textarea
              id="api-description"
              value={form.description}
              onChange={(e) => set('description', e.target.value)}
              placeholder="What this API is used for"
              rows={2}
            />
          </div>

          <div className="flex items-center justify-between rounded-md border border-border px-3 py-2">
            <Label htmlFor="api-enabled" className="cursor-pointer">Enabled</Label>
            <Switch
              id="api-enabled"
              checked={form.enabled}
              onCheckedChange={(v) => set('enabled', v)}
            />
          </div>

          {error && <p className="text-sm text-destructive">{error}</p>}

          <div className="flex justify-end gap-2">
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={saving}>
              {saving && <Loader2 className="w-4 h-4 mr-1.5 animate-spin" />}
              {initial ? 'Save changes' : 'Add API'}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}