# Minhas Finanças — Controle Financeiro Pessoal

Aplicação local de controle financeiro: Flask + SQLite no back-end, HTML5/CSS3/JS puro
no front-end (sem framework, sem build step). Interface mobile-first, tema escuro
grafite com acentos azul-petróleo.

## Plano de implementação (o que foi feito e por quê)

1. **Persistência real**: SQLite criado na inicialização, com camada de acesso isolada
   em `db.py`. Nenhum dado fica só em memória.
2. **Valores em `Decimal` no servidor**: o formulário envia texto; o servidor converte,
   valida faixas e grava. O dashboard recalcula totais e percentuais a partir do banco.
3. **CSRF + sanitização**: token por sessão em todo POST, texto normalizado e limitado,
   categorias validadas contra listas fixas (whitelist).
4. **Design dark grafite/petróleo**: tokens em `static/style.css`, layout de 360–430 px
   centralizado no desktop, barra inferior fixa com ação central destacada.
5. **Gráfico de rosca e mini barras**: SVG gerado no template a partir dos percentuais
   calculados no servidor; nada de biblioteca de gráficos.
6. **Revisão**: QA e Cibersegurança revisam antes da entrega (ver seção Pendências).

## Como rodar

```bash
cd C:\Users\andre\OpenBot\Shared\financas-pessoais
pip install flask
python app.py
```

Abra <http://127.0.0.1:5001>.

Variáveis de ambiente opcionais:

| Variável | Efeito |
| --- | --- |
| `FINANCAS_SECRET_KEY` | Chave de sessão. Sem ela, uma chave é gerada em `instance/secret_key.txt`. |
| `FINANCAS_DB` | Caminho do arquivo SQLite (padrão `instance/financas.sqlite`). |
| `FINANCAS_PORT` | Porta (padrão `5001`). |
| `FINANCAS_DEBUG` | `1` liga o modo debug (padrão desligado). |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` | Previstas para a futura integração Google. |

## Testes

```bash
python -m unittest discover -v
```

35 testes cobrem rotas, criação de cada tipo de lançamento, dashboard com dados,
valores inválidos, categoria fora da lista, CSRF, cálculo dos percentuais, exportação
CSV, configurações, perfil e ausência de JavaScript inline.

## Estrutura

```
financas-pessoais/
├── app.py                  # rotas, validação, agregações e headers de segurança
├── db.py                   # schema SQLite e acesso a dados
├── templates/
│   ├── base.html           # layout, navegação inferior, avisos
│   ├── dashboard.html      # resumo, rosca SVG, mini barras
│   ├── adicionar.html      # grade de ações
│   ├── receitas_nova.html
│   ├── despesas_nova.html
│   ├── investimentos_novo.html
│   ├── metas_nova.html
│   ├── orcamentos_novo.html
│   ├── perfil.html
│   ├── configuracoes.html
│   ├── google_pendente.html
│   └── erro.html
├── static/
│   ├── style.css
│   └── app.js              # formatação de valor, aviso, animação; o app roda sem ele
├── tests/test_app.py
└── README.md
```

## Regra do gráfico de rosca

Os seis segmentos não contam o mesmo valor duas vezes:

- **Salário** e **Freelance**: receitas dessas duas categorias.
- **Receitas**: todas as demais entradas do período.
- **Despesas**: soma das saídas do período.
- **Metas**: soma do valor total das metas criadas no período.
- **Reservas**: soma dos aportes de investimento no período.

O percentual de cada segmento é calculado sobre a soma dos seis. A alternância
Anual/Mensal recarrega a página com `?periodo=anual|mensal`, então o estado fica na URL.

## Segurança

- `SECRET_KEY` fora do código, debug desligado por padrão, bind em `127.0.0.1`.
- Sessão com cookie `HttpOnly` e `SameSite=Lax`.
- CSRF em todos os formulários POST, comparado com `secrets.compare_digest`.
- CSP `script-src 'self'` (sem `unsafe-inline` para scripts); `style-src` aceita
  `unsafe-inline` porque o SVG usa cores e larguras inline calculadas no servidor.
- `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `Referrer-Policy`,
  `Permissions-Policy`.
- Sem segredo no repositório; `instance/` guarda banco e chave local.

## Limitações conhecidas (honestas)

- **Login Google não implementado**: o botão tem a identidade visual e uma página
  explicando o que falta. Não há simulação de login.
- **Exportação PDF pendente**: o botão está desabilitado na interface e a rota
  `/exportar/pdf` responde `501` com mensagem clara. Só o CSV funciona de verdade.
- **Notificações**: a preferência é salva, mas nenhum aviso é enviado.
- **Tema claro**: existe como preferência e paleta básica; o foco do design é o escuro.
- **Sem autenticação real**: o app é local e de usuário único; o "perfil" é apenas
  um nome e e-mail salvos. Não use em rede pública sem adicionar autenticação.
- **Sem multi-moeda**: apenas BRL.
- **Sem edição/exclusão** de lançamentos nesta versão; apenas criação e leitura.
