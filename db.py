"""Camada de acesso ao banco SQLite do app de finanças pessoais.

Tudo que fala SQL vive aqui. As rotas do app.py só chamam estas funções.
Nível júnior: funções curtas, nomes claros, sem ORM e sem mágica.
"""

import sqlite3
from datetime import datetime

from flask import current_app, g

ESQUEMA = """
CREATE TABLE IF NOT EXISTS receitas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    valor TEXT NOT NULL,
    categoria TEXT NOT NULL,
    criado_em TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS despesas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    valor TEXT NOT NULL,
    categoria TEXT NOT NULL,
    criado_em TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS investimentos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    valor TEXT NOT NULL,
    categoria TEXT NOT NULL,
    ativo TEXT NOT NULL DEFAULT '',
    criado_em TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS metas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL,
    valor_total TEXT NOT NULL,
    tipo TEXT NOT NULL,
    criado_em TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS orcamentos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL,
    valor TEXT NOT NULL,
    categoria TEXT NOT NULL,
    criado_em TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS configuracoes (
    chave TEXT PRIMARY KEY,
    valor TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_receitas_data ON receitas (criado_em);
CREATE INDEX IF NOT EXISTS idx_despesas_data ON despesas (criado_em);
CREATE INDEX IF NOT EXISTS idx_investimentos_data ON investimentos (criado_em);
"""

# Tabelas que o app grava, com as colunas permitidas em cada uma.
COLUNAS = {
    "receitas": ("valor", "categoria", "criado_em"),
    "despesas": ("valor", "categoria", "criado_em"),
    "investimentos": ("valor", "categoria", "ativo", "criado_em"),
    "metas": ("nome", "valor_total", "tipo", "criado_em"),
    "orcamentos": ("nome", "valor", "categoria", "criado_em"),
}


def get_db():
    """Abre (uma vez por requisição) a conexão com o banco."""
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def fechar_db(_erro=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    """Cria o schema se ainda não existir. Roda na inicialização do app."""
    db = get_db()
    db.executescript(ESQUEMA)
    db.commit()


def init_app(app):
    app.teardown_appcontext(fechar_db)


def inserir(tabela, dados):
    """Insere um registro e devolve o id criado."""
    if tabela not in COLUNAS:
        raise ValueError("Tabela desconhecida: %s" % tabela)

    colunas = [c for c in COLUNAS[tabela] if c in dados]
    sql = "INSERT INTO %s (%s) VALUES (%s)" % (
        tabela,
        ", ".join(colunas),
        ", ".join("?" for _ in colunas),
    )
    db = get_db()
    cursor = db.execute(sql, [dados[c] for c in colunas])
    db.commit()
    return cursor.lastrowid


def listar(tabela, prefixo_data=None):
    """Lista registros, opcionalmente filtrados por 'AAAA' ou 'AAAA-MM'."""
    if tabela not in COLUNAS:
        raise ValueError("Tabela desconhecida: %s" % tabela)

    sql = "SELECT * FROM %s" % tabela
    parametros = []
    if prefixo_data:
        sql += " WHERE criado_em LIKE ?"
        parametros.append(prefixo_data + "%")
    sql += " ORDER BY criado_em DESC, id DESC"
    return get_db().execute(sql, parametros).fetchall()


def obter_config(chave, padrao=None):
    linha = get_db().execute(
        "SELECT valor FROM configuracoes WHERE chave = ?", (chave,)
    ).fetchone()
    return linha["valor"] if linha else padrao


def obter_configuracoes():
    """Devolve todas as configurações como dicionário chave -> valor."""
    linhas = get_db().execute("SELECT chave, valor FROM configuracoes").fetchall()
    return {linha["chave"]: linha["valor"] for linha in linhas}


def salvar_config(chave, valor):
    db = get_db()
    db.execute(
        "INSERT INTO configuracoes (chave, valor) VALUES (?, ?) "
        "ON CONFLICT(chave) DO UPDATE SET valor = excluded.valor",
        (chave, str(valor)),
    )
    db.commit()


def agora_iso():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
