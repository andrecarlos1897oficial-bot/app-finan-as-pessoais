"""Controle Financeiro Pessoal - Flask + HTML5/CSS3/JS puro.

Nível júnior: rotas curtas, validação explícita no servidor e SQL isolado em db.py.
Execução local: python app.py  ->  http://127.0.0.1:5001
"""

import csv
import io
import os
import re
import secrets
from datetime import datetime
from decimal import Decimal, InvalidOperation

from flask import (
    Flask,
    Response,
    abort,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

import db as banco

# ---------------------------------------------------------------------------
# Listas fixas (whitelist). O navegador escolhe; o servidor valida.
# ---------------------------------------------------------------------------

CATEGORIAS_RECEITA = [
    "Salário", "Transferência PIX", "Amigo", "Família", "Freelance",
    "Empréstimo", "Reembolso", "Presente", "Dividendos", "Venda Online",
    "Restituição de IR",
]

CATEGORIAS_DESPESA = [
    "Restaurante", "Mercado", "Moradia/Contas", "Transporte", "Combustível",
    "Público", "Saúde", "Educação", "Vestuário", "Lazer", "Pets", "Presentes",
]

CATEGORIAS_INVESTIMENTO = [
    "Ações", "CDB/RDB", "FIIs", "Tesouro Direto", "Previdência Privada",
    "ETFs", "Investimento Exterior", "Renda Fixa", "Commodities", "Imóveis",
    "Negócios", "Ativos Alternativos",
]

TIPOS_META = [
    "Casa Própria", "Viagem dos Sonhos", "Comprar Carro", "Educação/Filhos",
    "Casamento", "Aposentadoria", "Investir em Negócio", "Fundo de Emergência",
    "Formação/Cursos", "Mascote", "Doação", "Outros",
]

CATEGORIAS_ORCAMENTO = [
    "Mercado", "Restaurante", "Transporte/Combustível", "Contas/Moradia",
    "Saúde", "Educação", "Lazer", "Vestuário", "Pets", "Presentes", "Viagem",
    "Manutenção",
]

# Cores do gráfico de rosca (paleta definida no DESIGN_SPEC.md).
CORES_ROSCA = {
    "Receitas": "#2ECC71",
    "Despesas": "#E74C3C",
    "Metas": "#9B59B6",
    "Reservas": "#F1C40F",
}

VALOR_MAXIMO = Decimal("1000000000")  # limite de sanidade: R$ 1 bilhão
CIRCUNFERENCIA_ROSCA = 402.12  # 2 * pi * 64 (raio do SVG no template)


class ErroValidacao(ValueError):
    """Erro de validação com mensagem já pronta em pt-BR."""


# ---------------------------------------------------------------------------
# Validação e sanitização (tudo no servidor)
# ---------------------------------------------------------------------------

FORMATO_MILHAR = re.compile(r"^\d{1,3}(\.\d{3})+(,\d{1,2})?$")
FORMATO_VIRGULA = re.compile(r"^\d{1,9}(,\d{1,2})?$")
FORMATO_PONTO = re.compile(r"^\d{1,9}(\.\d{1,2})?$")


def parse_valor(texto):
    """Converte texto digitado em Decimal, aceitando 1.234,56 e 1234.56."""
    if texto is None:
        raise ErroValidacao("Informe um valor.")

    limpo = str(texto).strip()
    if limpo.startswith("R$"):
        limpo = limpo[2:].strip()
    if not limpo:
        raise ErroValidacao("Informe um valor.")

    if FORMATO_MILHAR.match(limpo):
        normalizado = limpo.replace(".", "").replace(",", ".")
    elif FORMATO_VIRGULA.match(limpo):
        normalizado = limpo.replace(",", ".")
    elif FORMATO_PONTO.match(limpo):
        normalizado = limpo
    else:
        raise ErroValidacao("Valor inválido. Use apenas números, como 1500,00.")

    try:
        valor = Decimal(normalizado)
    except InvalidOperation:
        raise ErroValidacao("Valor inválido. Use apenas números, como 1500,00.")

    if valor <= 0:
        raise ErroValidacao("O valor precisa ser maior que zero.")
    if valor > VALOR_MAXIMO:
        raise ErroValidacao("Valor acima do limite permitido.")

    return valor.quantize(Decimal("0.01"))


def limpar_texto(texto, rotulo, maximo=60, obrigatorio=True):
    """Remove caracteres de controle, normaliza espaços e limita o tamanho."""
    if texto is None:
        texto = ""
    valor = re.sub(r"[\x00-\x1f\x7f]", " ", str(texto))
    valor = " ".join(valor.split())
    if not valor and obrigatorio:
        raise ErroValidacao("Informe %s." % rotulo)
    if len(valor) > maximo:
        raise ErroValidacao("%s deve ter no máximo %d caracteres." % (rotulo, maximo))
    return valor


def escolher_categoria(valor, permitidas, rotulo="uma categoria"):
    if valor not in permitidas:
        raise ErroValidacao("Escolha %s da lista." % rotulo)
    return valor


def formatar_brl(valor):
    """1234.5 -> 'R$ 1.234,50' (usado em mensagens e no CSV)."""
    texto = "{:,.2f}".format(Decimal(valor))
    return "R$ " + texto.replace(",", "X").replace(".", ",").replace("X", ".")


def formatar_decimal(valor):
    """1234.5 -> '1.234,50' (sem o prefixo R$)."""
    return "{:,.2f}".format(Decimal(valor)).replace(",", "X").replace(".", ",").replace("X", ".")


PREFIXO_FORMULA_CSV = re.compile(r"^[\s\x00-\x1f\x7f]*[=+\-@]")


def proteger_celula_csv(valor):
    """Impede que texto exportado seja interpretado como fórmula por planilhas."""
    texto = str(valor)
    if PREFIXO_FORMULA_CSV.match(texto):
        return "'" + texto
    return texto


# ---------------------------------------------------------------------------
# Agregações do dashboard
# ---------------------------------------------------------------------------

def somar(linhas, campo="valor"):
    total = Decimal("0")
    for linha in linhas:
        total += Decimal(linha[campo])
    return total


def por_categoria(linhas, campo="valor"):
    totais = {}
    for linha in linhas:
        categoria = linha["categoria"]
        totais[categoria] = totais.get(categoria, Decimal("0")) + Decimal(linha[campo])
    return totais


def montar_rosca(receitas, despesas, investimentos, metas):
    """Monta os quatro segmentos do gráfico de rosca."""
    medidas = [
        ("Receitas", somar(receitas)),
        ("Despesas", somar(despesas)),
        ("Metas", somar(metas, "valor_total")),
        ("Reservas", somar(investimentos)),
    ]
    total = sum(valor for _, valor in medidas if valor > 0)

    segmentos = []
    acumulado = 0.0
    for nome, valor in medidas:
        if valor <= 0 or total <= 0:
            continue
        percentual = float(valor / total * 100)
        comprimento = percentual / 100 * CIRCUNFERENCIA_ROSCA
        segmentos.append({
            "nome": nome,
            "valor": valor,
            "valor_texto": formatar_brl(valor),
            "percentual": round(percentual, 1),
            "percentual_texto": ("%.1f" % percentual).replace(".", ","),
            "cor": CORES_ROSCA[nome],
            "comprimento": round(comprimento, 2),
            "offset": round(-acumulado, 2),
        })
        acumulado += comprimento

    return segmentos, total


def montar_mini_barras(receitas, despesas):
    total_receitas = somar(receitas)
    total_despesas = somar(despesas)
    maior = max(total_receitas, total_despesas, Decimal("1"))

    def largura(valor):
        if valor <= 0:
            return 2.0
        return round(float(valor / maior * 100), 1)

    return [
        {"rotulo": "Receitas", "valor": total_receitas, "valor_texto": formatar_brl(total_receitas),
         "barra": largura(total_receitas), "cor": CORES_ROSCA["Receitas"]},
        {"rotulo": "Despesas", "valor": total_despesas, "valor_texto": formatar_brl(total_despesas),
         "barra": largura(total_despesas), "cor": CORES_ROSCA["Despesas"]},
    ]


# ---------------------------------------------------------------------------
# Aplicação
# ---------------------------------------------------------------------------

def carregar_ou_criar_secret_key(caminho_fallback):
    """SECRET_KEY vem do ambiente. Sem ambiente, um arquivo local fora do código."""
    chave = os.environ.get("FINANCAS_SECRET_KEY")
    if chave:
        return chave

    try:
        if os.path.exists(caminho_fallback):
            with open(caminho_fallback, "r", encoding="utf-8") as arquivo:
                chave = arquivo.read().strip()
                if chave:
                    return chave
        chave = secrets.token_hex(32)
        os.makedirs(os.path.dirname(caminho_fallback), exist_ok=True)
        with open(caminho_fallback, "w", encoding="utf-8") as arquivo:
            arquivo.write(chave)
        return chave
    except OSError:
        # Último recurso: chave efêmera (sessões caem ao reiniciar).
        return secrets.token_hex(32)


def create_app(config_teste=None):
    app = Flask(__name__)

    instancia = os.path.join(os.path.dirname(os.path.abspath(__file__)), "instance")
    os.makedirs(instancia, exist_ok=True)

    app.config.update(
        SECRET_KEY=carregar_ou_criar_secret_key(os.path.join(instancia, "secret_key.txt")),
        DATABASE=os.environ.get("FINANCAS_DB", os.path.join(instancia, "financas.sqlite")),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=False,  # local em http; ligue atrás de HTTPS
        MAX_CONTENT_LENGTH=64 * 1024,
        APP_NOME="Minhas Finanças",
    )
    if config_teste:
        app.config.update(config_teste)

    banco.init_app(app)
    with app.app_context():
        banco.init_db()

    # ------------------------------------------------------------------
    # CSRF: token na sessão, enviado em campo oculto e conferido no POST
    # ------------------------------------------------------------------

    @app.before_request
    def preparar_csrf():
        if "csrf_token" not in session:
            session["csrf_token"] = secrets.token_urlsafe(32)
        if request.method == "POST":
            enviado = request.form.get("csrf_token", "")
            esperado = session.get("csrf_token", "")
            if not esperado or not secrets.compare_digest(enviado, esperado):
                abort(400, description="Sessão expirada ou formulário inválido. Recarregue a página.")

    @app.context_processor
    def injetar_globais():
        agora = datetime.now()
        return {
            "csrf_token": session.get("csrf_token", ""),
            "agora": agora,
            "data_hora": agora.strftime("%d/%m/%Y %H:%M"),
            "config": banco.obter_configuracoes(),
            "app_nome": app.config["APP_NOME"],
            "formatar_brl": formatar_brl,
        }

    # ------------------------------------------------------------------
    # Headers de segurança em toda resposta
    # ------------------------------------------------------------------

    @app.after_request
    def headers_de_seguranca(resposta):
        resposta.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; font-src 'self'; connect-src 'self'; "
            "base-uri 'none'; form-action 'self'; frame-ancestors 'none'"
        )
        resposta.headers["X-Content-Type-Options"] = "nosniff"
        resposta.headers["X-Frame-Options"] = "DENY"
        resposta.headers["Referrer-Policy"] = "no-referrer"
        resposta.headers["Permissions-Policy"] = (
            "geolocation=(), microphone=(), camera=(), payment=()"
        )
        return resposta

    # ------------------------------------------------------------------
    # Rotas
    # ------------------------------------------------------------------

    @app.route("/")
    def dashboard():
        periodo = request.args.get("periodo", "mensal")
        if periodo not in ("mensal", "anual"):
            periodo = "mensal"

        agora = datetime.now()
        prefixo = agora.strftime("%Y-%m") if periodo == "mensal" else agora.strftime("%Y")

        receitas = banco.listar("receitas", prefixo)
        despesas = banco.listar("despesas", prefixo)
        investimentos = banco.listar("investimentos", prefixo)
        metas = banco.listar("metas", prefixo)

        segmentos, total_rosca = montar_rosca(receitas, despesas, investimentos, metas)
        total_receitas = somar(receitas)
        total_despesas = somar(despesas)

        return render_template(
            "dashboard.html",
            tela="resumo",
            periodo=periodo,
            rotulo_periodo=("Resumo de %s" % agora.strftime("%m/%Y")) if periodo == "mensal"
            else ("Resumo de %d" % agora.year),
            segmentos=segmentos,
            total_rosca=total_rosca,
            total_rosca_texto=formatar_brl(total_rosca),
            tem_dados=bool(segmentos),
            total_receitas=formatar_brl(total_receitas),
            total_despesas=formatar_brl(total_despesas),
            saldo=formatar_brl(total_receitas - total_despesas),
            saldo_positivo=(total_receitas - total_despesas) >= 0,
            mini_barras=montar_mini_barras(receitas, despesas),
            ultimos_receitas=receitas[:3],
            ultimos_despesas=despesas[:3],
        )

    @app.route("/extratos/<tipo>")
    def extratos(tipo):
        """Exibe extratos detalhados por tipo."""
        if tipo not in ("receitas", "despesas", "metas", "reservas"):
            abort(404)

        periodo = request.args.get("periodo", "mensal")
        if periodo not in ("mensal", "anual"):
            periodo = "mensal"

        agora = datetime.now()
        prefixo = agora.strftime("%Y-%m") if periodo == "mensal" else agora.strftime("%Y")

        if tipo == "receitas":
            itens = banco.listar("receitas", prefixo)
            total = somar(itens)
            titulo = "Extrato de Receitas"
            template = "extrato_receitas.html"
        elif tipo == "despesas":
            itens = banco.listar("despesas", prefixo)
            total = somar(itens)
            titulo = "Extrato de Despesas"
            template = "extrato_despesas.html"
        elif tipo == "metas":
            itens = banco.listar("metas", prefixo)
            total = somar(itens, "valor_total")
            titulo = "Extrato de Metas"
            template = "extrato_metas.html"
        else:  # reservas
            itens = banco.listar("investimentos", prefixo)
            total = somar(itens)
            titulo = "Extrato de Reservas"
            template = "extrato_reservas.html"

        return render_template(
            template,
            tela="extrato",
            tipo=tipo,
            periodo=periodo,
            titulo=titulo,
            itens=itens,
            total=total,
            total_texto=formatar_brl(total),
            agora=agora,
        )

    @app.route("/adicionar")
    def adicionar():
        return render_template("adicionar.html", tela="adicionar")

    @app.route("/receitas/nova", methods=["GET", "POST"])
    def nova_receita():
        if request.method == "POST":
            try:
                valor = parse_valor(request.form.get("valor"))
                categoria = escolher_categoria(
                    request.form.get("categoria"), CATEGORIAS_RECEITA
                )
                banco.inserir("receitas", {
                    "valor": str(valor),
                    "categoria": categoria,
                    "criado_em": banco.agora_iso(),
                })
                flash("Receita de %s salva em %s." % (formatar_brl(valor), categoria), "sucesso")
                return redirect(url_for("nova_receita"))
            except ErroValidacao as erro:
                flash(str(erro), "erro")

        return render_template(
            "receitas_nova.html", tela="adicionar",
            categorias=CATEGORIAS_RECEITA,
        )

    @app.route("/despesas/nova", methods=["GET", "POST"])
    def nova_despesa():
        if request.method == "POST":
            try:
                valor = parse_valor(request.form.get("valor"))
                categoria = escolher_categoria(
                    request.form.get("categoria"), CATEGORIAS_DESPESA
                )
                banco.inserir("despesas", {
                    "valor": str(valor),
                    "categoria": categoria,
                    "criado_em": banco.agora_iso(),
                })
                flash("Despesa de %s salva em %s." % (formatar_brl(valor), categoria), "sucesso")
                return redirect(url_for("nova_despesa"))
            except ErroValidacao as erro:
                flash(str(erro), "erro")

        return render_template(
            "despesas_nova.html", tela="adicionar",
            categorias=CATEGORIAS_DESPESA,
        )

    @app.route("/investimentos/novo", methods=["GET", "POST"])
    def novo_investimento():
        if request.method == "POST":
            try:
                valor = parse_valor(request.form.get("valor"))
                categoria = escolher_categoria(
                    request.form.get("categoria"), CATEGORIAS_INVESTIMENTO
                )
                ativo = limpar_texto(
                    request.form.get("ativo"), "o nome do ativo",
                    maximo=80, obrigatorio=False,
                )
                banco.inserir("investimentos", {
                    "valor": str(valor),
                    "categoria": categoria,
                    "ativo": ativo,
                    "criado_em": banco.agora_iso(),
                })
                flash("Aporte de %s confirmado em %s." % (formatar_brl(valor), categoria), "sucesso")
                return redirect(url_for("novo_investimento"))
            except ErroValidacao as erro:
                flash(str(erro), "erro")

        return render_template(
            "investimentos_novo.html", tela="adicionar",
            categorias=CATEGORIAS_INVESTIMENTO,
        )

    @app.route("/metas/nova", methods=["GET", "POST"])
    def nova_meta():
        if request.method == "POST":
            try:
                nome = limpar_texto(request.form.get("nome"), "o nome da meta", maximo=60)
                valor = parse_valor(request.form.get("valor_total"))
                tipo = escolher_categoria(request.form.get("tipo"), TIPOS_META, "um tipo")
                banco.inserir("metas", {
                    "nome": nome,
                    "valor_total": str(valor),
                    "tipo": tipo,
                    "criado_em": banco.agora_iso(),
                })
                flash("Meta \"%s\" criada com objetivo de %s." % (nome, formatar_brl(valor)), "sucesso")
                return redirect(url_for("nova_meta"))
            except ErroValidacao as erro:
                flash(str(erro), "erro")

        return render_template("metas_nova.html", tela="adicionar", tipos=TIPOS_META)

    @app.route("/orcamentos/novo", methods=["GET", "POST"])
    def novo_orcamento():
        if request.method == "POST":
            try:
                nome = limpar_texto(request.form.get("nome"), "o nome do orçamento", maximo=60)
                valor = parse_valor(request.form.get("valor"))
                categoria = escolher_categoria(
                    request.form.get("categoria"), CATEGORIAS_ORCAMENTO
                )
                banco.inserir("orcamentos", {
                    "nome": nome,
                    "valor": str(valor),
                    "categoria": categoria,
                    "criado_em": banco.agora_iso(),
                })
                flash("Orçamento \"%s\" de %s confirmado." % (nome, formatar_brl(valor)), "sucesso")
                return redirect(url_for("novo_orcamento"))
            except ErroValidacao as erro:
                flash(str(erro), "erro")

        return render_template(
            "orcamentos_novo.html", tela="adicionar",
            categorias=CATEGORIAS_ORCAMENTO,
        )

    @app.route("/perfil", methods=["GET", "POST"])
    def perfil():
        if request.method == "POST":
            try:
                nome = limpar_texto(request.form.get("nome"), "seu nome", maximo=60)
                email = limpar_texto(request.form.get("email"), "seu e-mail", maximo=120)
                if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
                    raise ErroValidacao("Informe um e-mail válido.")
                banco.salvar_config("perfil_nome", nome)
                banco.salvar_config("perfil_email", email)
                flash("Perfil atualizado.", "sucesso")
                return redirect(url_for("perfil"))
            except ErroValidacao as erro:
                flash(str(erro), "erro")

        nome = banco.obter_config("perfil_nome", "")
        email = banco.obter_config("perfil_email", "")
        return render_template(
            "perfil.html", tela="perfil", perfil_nome=nome, perfil_email=email,
            google_configurado=bool(os.environ.get("GOOGLE_CLIENT_ID")),
        )

    @app.route("/perfil/google")
    def google_login():
        """Botão oficial; a integração real exige credenciais do usuário."""
        return render_template(
            "google_pendente.html", tela="perfil",
            google_configurado=bool(os.environ.get("GOOGLE_CLIENT_ID")),
        )

    @app.route("/perfil/logout", methods=["POST"])
    def logout():
        session.clear()
        flash("Você saiu da conta.", "sucesso")
        return redirect(url_for("perfil"))

    @app.route("/configuracoes", methods=["GET", "POST"])
    def configuracoes():
        if request.method == "POST":
            try:
                tema = request.form.get("tema", "escuro")
                if tema not in ("escuro", "claro"):
                    raise ErroValidacao("Tema inválido.")
                moeda = request.form.get("moeda", "BRL")
                if moeda != "BRL":
                    raise ErroValidacao("Somente BRL (R$) está disponível nesta versão.")
                notificacoes = "sim" if request.form.get("notificacoes") == "sim" else "nao"
                banco.salvar_config("tema", tema)
                banco.salvar_config("moeda", moeda)
                banco.salvar_config("notificacoes", notificacoes)
                flash("Configurações salvas.", "sucesso")
                return redirect(url_for("configuracoes"))
            except ErroValidacao as erro:
                flash(str(erro), "erro")

        return render_template(
            "configuracoes.html", tela="configuracoes",
            tema=banco.obter_config("tema", "escuro"),
            moeda=banco.obter_config("moeda", "BRL"),
            notificacoes=banco.obter_config("notificacoes", "sim"),
        )

    @app.route("/exportar/csv")
    def exportar_csv():
        """CSV real com todos os registros. Gerado em memória, sem arquivo temporário."""
        saida = io.StringIO()
        escritor = csv.writer(saida, delimiter=";", lineterminator="\r\n")
        escritor.writerow(["tipo", "descricao", "categoria", "valor", "criado_em"])

        for linha in banco.listar("receitas"):
            escritor.writerow([
                proteger_celula_csv("receita"), "",
                proteger_celula_csv(linha["categoria"]),
                formatar_decimal(linha["valor"]),
                proteger_celula_csv(linha["criado_em"]),
            ])
        for linha in banco.listar("despesas"):
            escritor.writerow([
                proteger_celula_csv("despesa"), "",
                proteger_celula_csv(linha["categoria"]),
                formatar_decimal(linha["valor"]),
                proteger_celula_csv(linha["criado_em"]),
            ])
        for linha in banco.listar("investimentos"):
            escritor.writerow([
                proteger_celula_csv("investimento"),
                proteger_celula_csv(linha["ativo"]),
                proteger_celula_csv(linha["categoria"]),
                formatar_decimal(linha["valor"]),
                proteger_celula_csv(linha["criado_em"]),
            ])
        for linha in banco.listar("metas"):
            escritor.writerow([
                proteger_celula_csv("meta"),
                proteger_celula_csv(linha["nome"]),
                proteger_celula_csv(linha["tipo"]),
                formatar_decimal(linha["valor_total"]),
                proteger_celula_csv(linha["criado_em"]),
            ])
        for linha in banco.listar("orcamentos"):
            escritor.writerow([
                proteger_celula_csv("orcamento"),
                proteger_celula_csv(linha["nome"]),
                proteger_celula_csv(linha["categoria"]),
                formatar_decimal(linha["valor"]),
                proteger_celula_csv(linha["criado_em"]),
            ])

        conteudo = "\ufeff" + saida.getvalue()  # BOM para o Excel abrir acentos
        nome = "financas-%s.csv" % datetime.now().strftime("%Y-%m-%d")
        return Response(
            conteudo,
            mimetype="text/csv; charset=utf-8",
            headers={"Content-Disposition": "attachment; filename=%s" % nome},
        )

    @app.route("/exportar/pdf")
    def exportar_pdf():
        """Não implementado de propósito: não simulamos PDF."""
        return (
            "Exportação em PDF ainda não está implementada nesta versão. "
            "Use a exportação em CSV.",
            501,
            {"Content-Type": "text/plain; charset=utf-8"},
        )

    @app.errorhandler(400)
    def erro_400(erro):
        return render_template(
            "erro.html", tela="", codigo=400,
            mensagem=getattr(erro, "description", "Requisição inválida."),
        ), 400

    @app.errorhandler(404)
    def erro_404(_erro):
        return render_template(
            "erro.html", tela="", codigo=404,
            mensagem="Página não encontrada.",
        ), 404

    return app


# Objeto de aplicação de nível superior para servidores WSGI (ex.: Vercel, Gunicorn)
app = create_app()


if __name__ == "__main__":
    aplicacao = create_app()
    # Debug só quando FINANCAS_DEBUG=1. Bind estrito em localhost.
    aplicacao.run(
        host="127.0.0.1",
        port=int(os.environ.get("FINANCAS_PORT", "5001")),
        debug=os.environ.get("FINANCAS_DEBUG") == "1",
    )
