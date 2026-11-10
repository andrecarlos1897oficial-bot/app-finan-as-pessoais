import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createApp, parseValor, formatBRL } from '../netlify/server/app.mjs';

test('Brazilian currency validation preserves cents and rejects invalid amounts', () => {
  assert.equal(parseValor('R$ 1.234,56'), '1234.56');
  assert.equal(parseValor('0,01'), '0.01');
  assert.equal(formatBRL('1234.56'), 'R$ 1.234,56');
  for (const amount of ['0', '-1', 'abc', '1,234', '1000000001', '1e5']) assert.throws(() => parseValor(amount));
});

test('pages, financial forms, CSRF, isolation, settings and CSV work through HTTP', async () => {
  // Test double only: production always uses Netlify Database.
  const records = []; const configs = new Map();
  const store = {
    settings: async owner => configs.get(owner) || {},
    saveSettings: async (owner, data) => configs.set(owner, data),
    list: async (owner, prefix = '') => records.filter(row => row.owner === owner && row.criado_em.startsWith(prefix)),
    insert: async (owner, tipo, data) => records.push({ ...data, owner, tipo, valor_total: data.valor, criado_em: new Date().toISOString(), id: records.length + 1 }),
  };
  const server = createApp(store, { secureCookies: false }).listen(0);
  try {
    await new Promise(resolve => server.once('listening', resolve));
    const base = `http://127.0.0.1:${server.address().port}`;
    let cookie = '';
    const request = async (path, form) => {
      const response = await fetch(base + path, { method: form ? 'POST' : 'GET', redirect: 'manual', headers: { cookie, ...(form ? { 'Content-Type': 'application/x-www-form-urlencoded' } : {}) }, body: form ? new URLSearchParams(form) : undefined });
      const set = response.headers.getSetCookie().map(value => value.split(';')[0]);
      const jar = new Map(cookie.split('; ').filter(Boolean).map(item => item.split('=')));
      for (const item of set) { const [key, value] = item.split('='); jar.set(key, value); }
      cookie = [...jar].map(([key, value]) => `${key}=${value}`).join('; ');
      return response;
    };
    const pages = ['/', '/?painel=adicionar', '/?periodo=anual', '/adicionar', '/receitas/nova', '/despesas/nova', '/investimentos/novo', '/metas/nova', '/orcamentos/novo', '/perfil', '/perfil/google', '/configuracoes', '/extratos/receitas', '/extratos/despesas', '/extratos/metas', '/extratos/reservas', '/static/style.css', '/static/app.js'];
    for (const path of pages) {
      const response = await request(path);
      assert.equal(response.status, 200, path);
      assert.ok((await response.text()).length > 100, path);
    }
    assert.equal((await request('/receitas/nova', { valor: '10', categoria: 'Salário' })).status, 400);
    const csrf_token = /name="csrf_token" value="([^"]+)"/.exec(await (await request('/receitas/nova')).text())[1];
    for (const [path, data] of [
      ['/receitas/nova', { valor: '1.234,56', categoria: 'Salário' }],
      ['/despesas/nova', { valor: '34,56', categoria: 'Mercado' }],
      ['/investimentos/novo', { valor: '100', categoria: 'CDB/RDB', ativo: 'Teste' }],
      ['/metas/nova', { valor_total: '5000', nome: '=META', tipo: 'Outros' }],
      ['/orcamentos/novo', { valor: '100', nome: 'Compras', categoria: 'Mercado' }],
    ]) assert.equal((await request(path, { ...data, csrf_token })).status, 303, path);
    assert.equal(records.length, 5);
    const dashboard = await (await request('/')).text();
    assert.ok(dashboard.includes('1.234,56'));
    assert.ok(dashboard.includes('stroke-dasharray'));
    const meta = await (await request('/extratos/metas')).text();
    assert.ok(meta.includes('=META'));
    assert.ok(meta.includes('Outros'));
    assert.ok(meta.includes('5.000,00'));
    const invalid = await request('/receitas/nova', { valor: '10', categoria: 'Invalid', csrf_token });
    assert.ok((await invalid.text()).includes('Escolha uma categoria'));
    assert.equal(records.length, 5);
    assert.equal((await request('/configuracoes', { tema: 'claro', moeda: 'BRL', notificacoes: 'nao', csrf_token })).status, 303);
    assert.ok((await (await request('/')).text()).includes('data-theme="claro"'));
    const csv = await request('/exportar/csv');
    assert.match(csv.headers.get('content-type'), /text\/csv/);
    const content = await csv.text();
    assert.ok(content.includes('1.234,56'));
    assert.ok(content.includes("'=META"));
    const ownCookie = cookie; cookie = '';
    assert.ok(!(await (await request('/exportar/csv')).text()).includes('1.234,56'));
    cookie = ownCookie;
    assert.equal((await request('/nao-existe')).status, 404);
    assert.equal((await request('/extratos/invalido')).status, 404);
  } finally { server.closeAllConnections(); await new Promise(resolve => server.close(resolve)); }
});
