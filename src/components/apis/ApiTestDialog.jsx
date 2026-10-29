import React, { useEffect, useState } from 'react';
import { Loader2, FlaskConical } from 'lucide-react';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { base44 } from '@/api/base44Client';

export default function ApiTestDialog({ connection, onClose }) {
  const [path, setPath] = useState('/');
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    setPath('/');
    setResult(null);
    setError('');
    setLoading(false);
  }, [connection]);

  const run = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    setResult(null);
    try {
      const resp = await base44.functions.invoke('testApiConnection', {
        id: connection.id,
        path,
      });
      setResult(resp.data);
    } catch (err) {
      setError(err?.response?.data?.error || err.message || 'Test failed.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Dialog open={!!connection} onOpenChange={(open) => { if (!open) onClose(); }}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Test {connection?.slug}</DialogTitle>
          <DialogDescription>
            Sends a GET request using this connection's stored authentication.
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={run} className="space-y-3">
          <div className="space-y-1.5">
            <Label htmlFor="test-path">Path</Label>
            <Input
              id="test-path"
              value={path}
              onChange={(e) => setPath(e.target.value)}
              placeholder="/"
              className="font-mono"
            />
          </div>
          <Button type="submit" disabled={loading} className="w-full">
            {loading ? (
              <>
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                Running…
              </>
            ) : (
              <>
                <FlaskConical className="w-4 h-4 mr-2" />
                Run test
              </>
            )}
          </Button>
        </form>

        {error && <p className="text-sm text-destructive">{error}</p>}

        {result && (
          <div className="space-y-2">
            <p className="text-sm">
              Status:{' '}
              <span className="font-mono font-semibold">
                {result.status ?? 'no response'}
              </span>
            </p>
            {result.error && <p className="text-sm text-destructive">{result.error}</p>}
            {result.body !== undefined && (
              <pre className="text-xs bg-muted rounded-md p-3 overflow-auto max-h-64 whitespace-pre-wrap break-all">
                {result.body || '(empty body)'}
              </pre>
            )}
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}