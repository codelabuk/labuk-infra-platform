const AppConfig = {
  apiBase: () => document.getElementById('apiUrl').value.replace(/\/$/, ''),
  defaultNamespace: 'spark',
  historyServerUrl: 'http://localhost:32080',

  async load() {
    try {
      const res = await fetch(
        `${this.apiBase()}/api/config`,
        { signal: AbortSignal.timeout(3000) }
      );
      const cfg = await res.json();
      this.defaultNamespace   = cfg.defaultNamespace;
      this.historyServerUrl   = cfg.historyServerUrl;

      // update namespace dropdown from config
      const sel = document.getElementById('nsSelect');
      sel.innerHTML = '';
      cfg.namespaces.forEach(n => {
        const o = document.createElement('option');
        o.value = n; o.textContent = n;
        if (n === cfg.defaultNamespace) o.selected = true;
        sel.appendChild(o);
      });

      // set history iframe — use proxy route so X-Frame-Options is bypassed
      const frame = document.getElementById('historyFrame');
      if (frame) frame.src = '/proxy/history/';

    } catch (_) {
      // offline — keep defaults, iframe stays as localhost fallback
      const frame = document.getElementById('historyFrame');
      if (frame) frame.src = 'http://localhost:32080';
    }
  }
};