CREATE TABLE finance_records (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  owner TEXT NOT NULL,
  tipo TEXT NOT NULL CHECK (tipo IN ('receitas', 'despesas', 'investimentos', 'metas', 'orcamentos')),
  valor NUMERIC(12, 2) NOT NULL CHECK (valor > 0),
  categoria TEXT NOT NULL DEFAULT '',
  nome TEXT NOT NULL DEFAULT '',
  ativo TEXT NOT NULL DEFAULT '',
  criado_em TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX finance_records_owner_date ON finance_records (owner, criado_em DESC);
CREATE TABLE finance_settings (
  owner TEXT NOT NULL,
  chave TEXT NOT NULL,
  valor TEXT NOT NULL,
  PRIMARY KEY (owner, chave)
);
