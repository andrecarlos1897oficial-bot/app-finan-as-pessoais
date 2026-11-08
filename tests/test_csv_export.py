import csv
import io
import os
import tempfile
import unittest

import db as banco
from app import create_app, proteger_celula_csv


class ProtecaoFormulaCsvTest(unittest.TestCase):
    def test_protege_prefixos_de_formula(self):
        for prefixo in ("=", "+", "-", "@"):
            with self.subTest(prefixo=prefixo):
                texto = prefixo + "1+1"
                self.assertEqual(proteger_celula_csv(texto), "'" + texto)

    def test_protege_formula_apos_espacos_e_controles(self):
        for prefixo in ("  =", "\t+", "\r\n-", "\x00@", "\x01  ="):
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
                "SECRET_KEY": "test-secret",
            })
            with app.app_context():
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


if __name__ == "__main__":
    unittest.main()
