Deno.serve(async (req) => {
  try {
    const body = await req.json();
    const { url } = body;
    if (!url || (!url.startsWith('http://') && !url.startsWith('https://'))) {
      return Response.json({ error: 'Missing or invalid url' }, { status: 400 });
    }

    const baseUrl = url.replace(/\/+$/, '');
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 5000);

    try {
      const resp = await fetch(`${baseUrl}/health`, { signal: controller.signal });
      clearTimeout(timeout);
      const data = await resp.json();
      return Response.json({ healthy: resp.ok, server: data, checked_at: new Date().toISOString() });
    } catch (fetchErr) {
      clearTimeout(timeout);
      return Response.json({ healthy: false, message: fetchErr.message, checked_at: new Date().toISOString() });
    }
  } catch (error) {
    return Response.json({ error: error.message }, { status: 500 });
  }
});