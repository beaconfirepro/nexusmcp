import React, { useState, useEffect, useCallback } from 'react';
import { Plus, Plug } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { base44 } from '@/api/base44Client';
import ApiRow from '@/components/apis/ApiRow';
import ApiFormDialog from '@/components/apis/ApiFormDialog';
import ApiTestDialog from '@/components/apis/ApiTestDialog';

export default function Apis() {
  const [connections, setConnections] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [testing, setTesting] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const page = await base44.entities.ApiConnection.list({ sort: 'slug', limit: 100 });
      setConnections(Array.isArray(page) ? page : page.items || []);
    } catch (err) {
      setError(err.message || 'Failed to load API connections.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const handleSave = async (values) => {
    if (editing) {
      await base44.entities.ApiConnection.update(editing.id, values);
    } else {
      const page = await base44.entities.ApiConnection.filter({ slug: values.slug }, { limit: 1 });
      const existing = Array.isArray(page) ? page : page.items || [];
      if (existing.length) {
        throw new Error(`Slug "${values.slug}" is already in use.`);
      }
      await base44.entities.ApiConnection.create(values);
    }
    setFormOpen(false);
    setEditing(null);
    await load();
  };

  const handleToggle = async (conn, enabled) => {
    setConnections((prev) => prev.map((c) => (c.id === conn.id ? { ...c, enabled } : c)));
    await base44.entities.ApiConnection.update(conn.id, { enabled });
  };

  const handleDelete = async (conn) => {
    if (!window.confirm(`Delete "${conn.name}"? This cannot be undone.`)) return;
    await base44.entities.ApiConnection.delete(conn.id);
    await load();
  };

  const openAdd = () => {
    setEditing(null);
    setFormOpen(true);
  };

  const openEdit = (conn) => {
    setEditing(conn);
    setFormOpen(true);
  };

  return (
    <div className="max-w-3xl space-y-6">
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <Plug className="w-6 h-6 text-primary" />
          <div>
            <h1 className="text-2xl font-heading font-bold">APIs</h1>
            <p className="text-sm text-muted-foreground">
              External APIs exposed to the MCP server as tools.
            </p>
          </div>
        </div>
        <Button onClick={openAdd} className="shrink-0">
          <Plus className="w-4 h-4 mr-1.5" />
          Add an API
        </Button>
      </div>

      {error && (
        <div className="rounded-lg border border-destructive/20 bg-destructive/5 p-3 text-sm text-destructive">
          {error}
        </div>
      )}

      {loading && (
        <p className="text-sm text-muted-foreground">Loading connections…</p>
      )}

      {!loading && !connections.length && !error && (
        <div className="rounded-lg border border-dashed border-border p-8 text-center">
          <p className="text-sm text-muted-foreground">No API connections yet.</p>
          <Button variant="outline" size="sm" className="mt-3" onClick={openAdd}>
            Add your first API
          </Button>
        </div>
      )}

      {!loading && connections.length > 0 && (
        <div className="space-y-2">
          {connections.map((conn) => (
            <ApiRow
              key={conn.id}
              connection={conn}
              onEdit={openEdit}
              onTest={setTesting}
              onDelete={handleDelete}
              onToggle={handleToggle}
            />
          ))}
        </div>
      )}

      <ApiFormDialog
        open={formOpen}
        onOpenChange={(open) => {
          setFormOpen(open);
          if (!open) setEditing(null);
        }}
        initial={editing}
        onSave={handleSave}
      />

      <ApiTestDialog connection={testing} onClose={() => setTesting(null)} />
    </div>
  );
}