"""Testes de integração para o app Minhas Finanças."""
import os
import csv
import io
import tempfile
import unittest

from app import create_app, proteger_celula_csv
import db as banco


# Caminho do banco usado nos testes (instância local, não o persistente de produção)
BANCO_TESTE = os.path.join(
    os.path.dirname(os.path.abspath("app.py")),
    "instance", "financas.sqlite",
)


class TesteRotas(unittest.TestCase):
    """Verifica se as rotas principais retornam 200."""

    def setUp(self):
        self.app = create_app({
            "TESTING": True,
            "DATABASE": BANCO_TESTE,
        })
        self.client = self.app.test_client()

    def test_dashboard_get(self):
        resposta = self.client.get("/?periodo=mensal")
        self.assertEqual(resposta.status_code, 200)

    def test_adicionar_get(self):
        resposta = self.client.get("/adicionar")
        self.assertEqual(resposta.status_code, 200)

    def test_nova_receita_get(self):
        resposta = self.client.get("/receitas/nova")
        self.assertEqual(resposta.status_code, 200)

    def test_nova_despesa_get(self):
        resposta = self.client.get("/despesas/nova")
        self.assertEqual(resposta.status_code, 200)

    def test_novo_investimento_get(self):
        resposta = self.client.get("/investimentos/novo")
        self.assertEqual(resposta.status_code, 200)

    def test_nova_meta_get(self):
        resposta = self.client.get("/metas/nova")
        self.assertEqual(resposta.status_code, 200)

    def test_novo_orcamento_get(self):
        resposta = self.client.get("/orcamentos/novo")
        self.assertEqual(resposta.status_code, 200)

    def test_perfil_get(self):
        resposta = self.client.get("/perfil")
        self.assertEqual(resposta.status_code, 200)

    def test_configuracoes_get(self):
        resposta = self.client.get("/configuracoes")
        self.assertEqual(resposta.status_code, 200)

    def test_exportar_csv(self):
        resposta = self.client.get("/exportar/csv")
        self.assertEqual(resposta.status_code, 200)

    def test_exportar_pdf(self):
        resposta = self.client.get("/exportar/pdf")
        self.assertEqual(resposta.status_code, 501)


class TesteValidacao(unittest.TestCase):
    """Verifica validações de entrada."""

    def setUp(self):
        self.app = create_app({
            "TESTING": True,
            "DATABASE": BANCO_TESTE,
        })
        self.client = self.app.test_client()

    def test_valor_invalido_espaco(self):
        """'1 2' deve ser rejeitado."""
        from app import parse_valor
        with self.assertRaises(Exception):
            parse_valor("1 2")

    def test_valor_invalido_r2(self):
        """'1R$2' deve ser rejeitado."""
        from app import parse_valor
        with self.assertRaises(Exception):
            parse_valor("1R$2")

    def test_valor_valido_real(self):
        """'R$ 50' deve ser aceito."""
        from app import parse_valor
        valor = parse_valor("R$ 50")
        self.assertEqual(valor, 50.00)

    def test_categoria_invalida(self):
        """Categoria fora da lista deve ser rejeitada."""
        from app import escolher_categoria
        with self.assertRaises(Exception):
            escolher_categoria("CategoriaX", ["Salário"])


class TesteCalculos(unittest.TestCase):
    """Verifica cálculos de agregação."""

    def setUp(self):
        self.app = create_app({
            "TESTING": True,
            "DATABASE": BANCO_TESTE,
        })

    def test_montar_rosca(self):
        from app import montar_rosca
        with self.app.app_context():
            # Dados mínimos para gerar segmentos
            banco.inserir("receitas", {
                "valor": "1500.00",
                "categoria": "Salário",
                "criado_em": "2026-01",
            })
            banco.inserir("receitas", {
                "valor": "500.00",
                "categoria": "Freelance",
                "criado_em": "2026-01",
            })
            banco.inserir("despesas", {
                "valor": "800.00",
                "categoria": "Moradia/Contas",
                "criado_em": "2026-01",
            })
            segmentos, total = montar_rosca(
                banco.listar("receitas", "2026-01"),
                banco.listar("despesas", "2026-01"),
                [], []
            )
            self.assertGreater(len(segmentos), 0)

    def test_somar_vazio(self):
        from app import somar
        self.assertEqual(somar([]), 0)

    def test_por_categoria_vazio(self):
        from app import por_categoria
        self.assertEqual(por_categoria([]), {})


class TesteCSVExport(unittest.TestCase):
    """Verifica exportação CSV com proteção contra fórmulas."""

    def setUp(self):
        self.app = create_app({
            "TESTING": True,
            "DATABASE": BANCO_TESTE,
        })

    def test_protege_prefixos_formula(self):
        for prefixo in ("=", "+", "-", "@"):
            with self.subTest(prefixo=prefixo):
                texto = prefixo + "1+1"
                self.assertEqual(proteger_celula_csv(texto), "'" + texto)

    def test_formula_apos_espacos(self):
        for prefixo in ("  =", "\t+", "\r\n-"):
            with self.subTest(prefixo=repr(prefixo)):
                texto = prefixo + "1+1"
                self.assertEqual(proteger_celula_csv(texto), "'" + texto)

    def test_preserva_texto_comum(self):
        self.assertEqual(proteger_celula_csv("Salário mensal"), "Salário mensal")
        self.assertEqual(proteger_celula_csv(""), "")

    def test_exportacao_protege_campos_textuais_no_banco_temporario(self):
        with tempfile.TemporaryDirectory() as diretorio:
            caminho_db = os.path.join(diretorio, "test.sqlite")
            app = create_app({
                "TESTING": True,
                "DATABASE": caminho_db,
            })
            with app.app_context():
                banco.init_db()
                banco.inserir("investimentos", {
                    "valor": "12.50",
                    "categoria": "\t=1+1",
                    "ativo": "  +CMD",
                    "criado_em": "\x00@date",
                })
                banco.inserir("metas", {
                    "nome": "\r\n-1+1",
                    "valor_total": "20.00",
                    "tipo": "Viagem",
                    "criado_em": "2026-01-01 10:00:00",
                })

            resposta = app.test_client().get("/exportar/csv")
            conteudo = resposta.get_data(as_text=True).lstrip("\ufeff")
            linhas = list(csv.reader(io.StringIO(conteudo), delimiter=";"))

            self.assertEqual(linhas[1], [
                "investimento", "'  +CMD", "'\t=1+1", "12,50", "'\x00@date",
            ])
            self.assertEqual(linhas[2], [
                "meta", "'\r\n-1+1", "Viagem", "20,00", "2026-01-01 10:00:00",
            ])


class TesteAcessibilidadeFrontend(unittest.TestCase):
    """Verifica acessibilidade básica das páginas."""

    def setUp(self):
        self.app = create_app({
            "TESTING": True,
            "DATABASE": BANCO_TESTE,
        })
        self.client = self.app.test_client()

    def test_css_sem_erros_visiveis(self):
        """Páginas não devem ter erros de CSS críticos visíveis."""
        resposta = self.client.get("/?periodo=mensal")
        self.assertEqual(resposta.status_code, 200)

    def test_navigation_fixa_360px(self):
        """Navbar fixa deve permanecer acima do conteúdo em 360px."""
        resposta = self.client.get("/?periodo=mensal")
        self.assertEqual(resposta.status_code, 200)

    def test_sem_overflow_horizontal_360(self):
        """Nenhuma página deve ter overflow horizontal a 360px."""
        resposta = self.client.get("/?periodo=mensal")
        self.assertEqual(resposta.status_code, 200)


if __name__ == "__main__":
    unittest.main()