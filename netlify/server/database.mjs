import { getDatabase } from '@netlify/database';

export function createStore() {
  const db = getDatabase();
  return {
    async list(owner, prefix = '') {
      const rows = await db.sql`
        SELECT *, to_char(criado_em AT TIME ZONE 'UTC', 'YYYY-MM-DD HH24:MI:SS') AS criado_em
        FROM finance_records
        WHERE owner = ${owner}
          AND to_char(criado_em AT TIME ZONE 'UTC', 'YYYY-MM-DD') LIKE ${prefix + '%'}
        ORDER BY criado_em DESC, id DESC`;
      return rows.map(row => ({ ...row, valor_total: row.valor, tipo_meta: row.categoria }));
    },
    async insert(owner, tipo, data) {
      await db.sql`
        INSERT INTO finance_records (owner, tipo, valor, categoria, nome, ativo)
        VALUES (${owner}, ${tipo}, ${data.valor}, ${data.categoria}, ${data.nome || ''}, ${data.ativo || ''})`;
    },
    async settings(owner) {
      const rows = await db.sql`SELECT chave, valor FROM finance_settings WHERE owner = ${owner}`;
      return Object.fromEntries(rows.map(row => [row.chave, row.valor]));
    },
    async saveSettings(owner, data) {
      await db.sql`
        INSERT INTO finance_settings (owner, chave, valor)
        VALUES ${db.sql.values(Object.entries(data).map(([key, value]) => [owner, key, value]))}
        ON CONFLICT (owner, chave) DO UPDATE SET valor = EXCLUDED.valor`;
    },
  };
}
