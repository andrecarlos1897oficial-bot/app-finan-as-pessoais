import express from 'express';
import cookieParser from 'cookie-parser';
import nunjucks from 'nunjucks';
import Decimal from 'decimal.js';
import { randomBytes, createHash, timingSafeEqual } from 'node:crypto';
import { fileURLToPath } from 'node:url';
import constants from './constants.mjs';

nunjucks.installJinjaCompat();
const root = fileURLToPath(new URL('../../', import.meta.url));
class TemplateLoader extends nunjucks.FileSystemLoader {
  getSource(name) {
    const source = super.getSource(name);
    if (source) source.src = source.src
      .replace('{% with mensagens = get_flashed_messages(with_categories=true) %}', '{% set mensagens = get_flashed_messages(with_categories=true) %}')
      .replace('{% endwith %}', '');
    return source;
  }
}
const templates = new nunjucks.Environment(new TemplateLoader(root + 'templates'), { autoescape: true });
const routes = {
  dashboard: '/', adicionar: '/adicionar', nova_receita: '/receitas/nova',
  nova_despesa: '/despesas/nova', novo_investimento: '/investimentos/novo',
  nova_meta: '/metas/nova', novo_orcamento: '/orcamentos/novo', perfil: '/perfil',
  configuracoes: '/configuracoes', google_login: '/perfil/google', logout: '/perfil/logout',
  exportar_csv: '/exportar/csv', exportar_pdf: '/exportar/pdf', extratos: '/extratos', static: '/static',
};
function urlFor(name, args = {}) {
  const params = { ...args }; delete params.__keywords;
  let path = routes[name];
  if (!path) throw new Error('Unknown route');
  if (params.tipo) { path += '/' + encodeURIComponent(params.tipo); delete params.tipo; }
  if (params.filename) { path += '/' + encodeURIComponent(params.filename); delete params.filename; }
  const query = new URLSearchParams(params).toString();
  return path + (query ? '?' + query : '');
}
export function parseValor(input) {
  let value = String(input ?? '').trim().replace(/^R\$\s*/, '');
  if (/^\d{1,3}(\.\d{3})+(,\d{1,2})?$/.test(value)) value = value.replaceAll('.', '').replace(',', '.');
  else if (/^\d{1,9}(,\d{1,2})?$/.test(value)) value = value.replace(',', '.');
  else if (!/^\d{1,9}(\.\d{1,2})?$/.test(value)) throw new Error('Valor inválido. Use apenas números, como 1500,00.');
  const amount = new Decimal(value);
  if (amount.lte(0) || amount.gt(1000000000)) throw new Error('Informe um valor maior que zero e até R$ 1 bilhão.');
  return amount.toFixed(2);
}
export function formatBRL(value) {
  const [integer, fraction] = new Decimal(value || 0).toFixed(2).split('.');
  return 'R$ ' + integer.replace(/\B(?=(\d{3})+(?!\d))/g, '.') + ',' + fraction;
}
function text(value, label, max = 60, required = true) {
  const cleaned = String(value || '').replace(/[\x00-\x1f\x7f]/g, ' ').replace(/\s+/g, ' ').trim();
  if ((required && !cleaned) || cleaned.length > max) throw new Error(`Informe ${label} com até ${max} caracteres.`);
  return cleaned;
}
const sum = (rows) => rows.reduce((total, row) => total.plus(row.valor), new Decimal(0));
const operations = [
  ['receitas', 'nova_receita', 'receitas_nova.html', constants.CATEGORIAS_RECEITA],
  ['despesas', 'nova_despesa', 'despesas_nova.html', constants.CATEGORIAS_DESPESA],
  ['investimentos', 'novo_investimento', 'investimentos_novo.html', constants.CATEGORIAS_INVESTIMENTO],
  ['metas', 'nova_meta', 'metas_nova.html', constants.TIPOS_META],
  ['orcamentos', 'novo_orcamento', 'orcamentos_novo.html', constants.CATEGORIAS_ORCAMENTO],
];
export function createApp(store, { secureCookies = true } = {}) {
  const app = express();
  app.disable('x-powered-by');
  app.use((req, res, next) => {
    res.set({
      'Content-Security-Policy': "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; connect-src 'self'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'",
      'X-Content-Type-Options': 'nosniff', 'X-Frame-Options': 'DENY',
      'Referrer-Policy': 'no-referrer', 'Permissions-Policy': 'geolocation=(), microphone=(), camera=(), payment=()',
    });
    next();
  });
  app.use('/static', express.static(root + 'static'));
  app.use(express.urlencoded({ extended: false, limit: '64kb' }));
  app.use(cookieParser());
  app.use(async (req, res, next) => {
    res.set('Cache-Control', 'private, no-store');
    const cookieOptions = { httpOnly: true, secure: secureCookies, sameSite: 'lax', path: '/' };
    let visitor = req.cookies.finance_visitor;
    if (!/^[a-f0-9]{64}$/.test(visitor || '')) visitor = randomBytes(32).toString('hex');
    res.cookie('finance_visitor', visitor, { ...cookieOptions, maxAge: 365 * 86400000 });
    req.owner = createHash('sha256').update(visitor).digest('hex');
    let csrf = req.cookies.finance_csrf;
    if (!/^[a-f0-9]{64}$/.test(csrf || '')) {
      csrf = randomBytes(32).toString('hex');
      res.cookie('finance_csrf', csrf, cookieOptions);
    }
    if (req.method === 'POST') {
      const submitted = String(req.body?.csrf_token || '');
      if (!req.cookies.finance_csrf || !/^[a-f0-9]{64}$/.test(submitted) || !timingSafeEqual(Buffer.from(submitted), Buffer.from(csrf))) {
        return res.status(400).send('Sessão expirada ou formulário inválido. Recarregue a página.');
      }
    }
    req.csrf = csrf;
    next();
  });
  const render = async (req, res, template, data = {}, messages = []) => {
    const config = await store.settings(req.owner);
    const now = new Date();
    res.send(templates.render(template, {
      app_nome: 'Minhas Finanças', csrf_token: req.csrf, config,
      data_hora: now.toLocaleString('pt-BR', { timeZone: 'UTC' }),
      agora: { year: now.getUTCFullYear(), strftime: () => `${String(now.getUTCMonth() + 1).padStart(2, '0')}/${now.getUTCFullYear()}` },
      request: { endpoint: Object.keys(routes).find(key => routes[key] === req.path), args: req.query, form: req.body || {} },
      url_for: urlFor, formatar_brl: formatBRL, get_flashed_messages: () => messages,
      ...data,
    }));
  };
  app.get('/', async (req, res) => {
    const periodo = req.query.periodo === 'anual' ? 'anual' : 'mensal';
    const rows = await store.list(req.owner, new Date().toISOString().slice(0, periodo === 'anual' ? 4 : 7));
    const groups = operations.slice(0, 4).map(([tipo]) => rows.filter(row => row.tipo === tipo));
    const amounts = groups.map(sum);
    const total = amounts.reduce((a, b) => a.plus(b), new Decimal(0));
    let offset = 0;
    const segmentos = ['Receitas', 'Despesas', 'Reservas', 'Metas'].flatMap((nome, i) => {
      if (amounts[i].isZero() || total.isZero()) return [];
      const percentage = amounts[i].div(total).mul(100).toNumber();
      const length = percentage / 100 * 402.12;
      const segment = { nome, valor_texto: formatBRL(amounts[i]), percentual_texto: percentage.toFixed(1).replace('.', ','), cor: constants.CORES_ROSCA[nome], comprimento: length, offset: -offset };
      offset += length; return [segment];
    });
    const max = Decimal.max(amounts[0], amounts[1], 1);
    await render(req, res, 'dashboard.html', { tela: 'resumo', periodo, segmentos, tem_dados: segmentos.length > 0,
      total_rosca_texto: formatBRL(total), mini_barras: ['Receitas', 'Despesas'].map((rotulo, i) => ({ rotulo, valor_texto: formatBRL(amounts[i]), barra: amounts[i].isZero() ? 2 : amounts[i].div(max).mul(100).toNumber(), cor: constants.CORES_ROSCA[rotulo] })) });
  });
  app.get('/adicionar', (req, res) => render(req, res, 'adicionar.html', { tela: 'adicionar' }));
  for (const [tipo, endpoint, template, categories] of operations) {
    app.route(routes[endpoint]).get((req, res) => render(req, res, template, { tela: 'adicionar', categorias: categories, tipos: categories }, req.query.salvo === '1' ? [['sucesso', 'Lançamento salvo com sucesso.']] : []))
      .post(async (req, res) => {
        let data;
        try {
          const categoria = tipo === 'metas' ? req.body.tipo : req.body.categoria;
          if (!categories.includes(categoria)) throw new Error('Escolha uma categoria da lista.');
          data = { valor: parseValor(tipo === 'metas' ? req.body.valor_total : req.body.valor), categoria };
          if (['metas', 'orcamentos'].includes(tipo)) data.nome = text(req.body.nome, 'o nome');
          if (tipo === 'investimentos') data.ativo = text(req.body.ativo, 'o nome do ativo', 80, false);
        } catch (error) {
          return render(req, res, template, { tela: 'adicionar', categorias: categories, tipos: categories }, [['erro', error.message]]);
        }
        await store.insert(req.owner, tipo, data);
        return res.redirect(303, routes[endpoint] + '?salvo=1');
      });
  }
  app.get('/extratos/:tipo', async (req, res, next) => {
    const tipo = req.params.tipo;
    if (!['receitas', 'despesas', 'metas', 'reservas'].includes(tipo)) return next();
    const periodo = req.query.periodo === 'anual' ? 'anual' : 'mensal';
    const rows = await store.list(req.owner, new Date().toISOString().slice(0, periodo === 'anual' ? 4 : 7));
    const itens = rows.filter(row => row.tipo === (tipo === 'reservas' ? 'investimentos' : tipo)).map(row => ({ ...row, tipo: row.tipo_meta || row.categoria }));
    await render(req, res, `extrato_${tipo}.html`, { tela: 'extrato', titulo: `Extrato de ${tipo[0].toUpperCase() + tipo.slice(1)}`, tipo, periodo, itens, total_texto: formatBRL(sum(itens)) });
  });
  app.route('/configuracoes').get(async (req, res) => {
    const settings = await store.settings(req.owner);
    return render(req, res, 'configuracoes.html', { tela: 'configuracoes', tema: settings.tema || 'escuro', moeda: 'BRL', notificacoes: settings.notificacoes || 'sim' });
  }).post(async (req, res) => {
    if (!['escuro', 'claro'].includes(req.body.tema) || req.body.moeda !== 'BRL') return res.status(400).send('Configuração inválida.');
    await store.saveSettings(req.owner, { tema: req.body.tema, moeda: 'BRL', notificacoes: req.body.notificacoes === 'sim' ? 'sim' : 'nao' });
    res.redirect(303, '/configuracoes');
  });
  app.get('/perfil', (req, res) => render(req, res, 'perfil.html', { tela: 'perfil', usuario_logado: false }));
  app.get('/perfil/google', (req, res) => render(req, res, 'google_pendente.html', { tela: 'perfil', google_configurado: false }));
  app.post('/perfil/logout', (req, res) => { res.clearCookie('finance_csrf', { path: '/' }); res.redirect(303, '/perfil'); });
  app.get('/exportar/csv', async (req, res) => {
    const rows = await store.list(req.owner);
    const safe = value => {
      let str = String(value || '');
      if (/^[\s\x00-\x1f\x7f]*[=+\-@]/.test(str)) str = "'" + str;
      return '"' + str.replaceAll('"', '""') + '"';
    };
    const types = { receitas: 'receita', despesas: 'despesa', investimentos: 'investimento', metas: 'meta', orcamentos: 'orcamento' };
    const csv = [['tipo', 'descricao', 'categoria', 'valor', 'criado_em'], ...rows.map(row => [types[row.tipo], row.nome || row.ativo, row.categoria, formatBRL(row.valor).slice(3), row.criado_em])];
    res.set('Content-Disposition', `attachment; filename=financas-${new Date().toISOString().slice(0, 10)}.csv`);
    res.type('text/csv').send('\uFEFF' + csv.map(row => row.map(safe).join(';')).join('\r\n') + '\r\n');
  });
  app.get('/exportar/pdf', (req, res) => res.status(501).type('text/plain').send('Exportação em PDF ainda não está implementada nesta versão. Use a exportação em CSV.'));
  app.use((req, res) => { res.status(404); return render(req, res, 'erro.html', { codigo: 404, mensagem: 'Página não encontrada.' }); });
  app.use((error, req, res, next) => {
    if (res.headersSent) return next(error);
    res.status(error.status === 413 ? 413 : 503).type('text/plain').send('Não foi possível concluir a solicitação. Tente novamente em instantes.');
  });
  return app;
}
