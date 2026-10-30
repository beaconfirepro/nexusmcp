import React from 'react';
import { Pencil, Trash2, FlaskConical } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Switch } from '@/components/ui/switch';

export default function ApiRow({ connection, onEdit, onTest, onDelete, onToggle }) {
  const masked = connection.secret ? `••••${connection.secret.slice(-4)}` : 'No key set';

  return (
    <div className="flex flex-wrap items-center gap-3 rounded-lg border border-border bg-card p-3">
      <div className="flex-1 min-w-[14rem]">
        <div className="flex items-center gap-2 flex-wrap">
          <code className="text-sm font-semibold">{connection.slug}</code>
          <Badge variant="secondary" className="capitalize">{connection.auth_type}</Badge>
          {!connection.enabled && <Badge variant="outline">Disabled</Badge>}
        </div>
        <p className="text-sm mt-0.5">{connection.name}</p>
        <p className="text-xs text-muted-foreground break-all">{connection.base_url}</p>
        <p className="text-xs text-muted-foreground mt-1">
          {masked}
          {connection.auth_type === 'header' && connection.header_name ? ` · ${connection.header_name}` : ''}
        </p>
      </div>
      <Switch
        checked={connection.enabled}
        onCheckedChange={(v) => onToggle(connection, v)}
        aria-label="Enabled"
      />
      <Button variant="outline" size="sm" onClick={() => onTest(connection)}>
        <FlaskConical className="w-4 h-4 mr-1.5" />
        Test
      </Button>
      <Button variant="ghost" size="sm" onClick={() => onEdit(connection)} aria-label="Edit">
        <Pencil className="w-4 h-4" />
      </Button>
      <Button variant="ghost" size="sm" onClick={() => onDelete(connection)} aria-label="Delete">
        <Trash2 className="w-4 h-4 text-destructive" />
      </Button>
    </div>
  );
}