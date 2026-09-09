# Spec-Lock-Diff

[English](README.md) · **Português (pt-BR)**

<p align="center">
  <img src="assets/spec-lock-diff.png" alt="Two people flanking a padlock containing a robot, over a line chart" width="560">
</p>

Um framework para desenvolvimento com dbt usando agentes de IA. O objetivo é reduzir os riscos que surgem quando um agente escreve SQL, resultados errados que parecem certos, vazamento de dados pessoais e custos financeiros inesperados.

O framework se resume em três fases:

- **Spec** — O humano define, em detalhes estruturados, o que o modelo dbt deve fazer _antes_ de qualquer código ser escrito.
- **Lock** — Restrições determinísticas. Limites de custo, acesso e comportamento ficam na infraestrutura (warehouse, CI, permissões), não em instruções de texto para o agente.
- **Diff** — Depois que o agente termina, o humano confere e revisa _números_ (diferenças entre produção e a versão nova), não código.

---

## Índice

0. [Papéis — quem faz o quê](#0-pap%C3%A9is--quem-faz-o-qu%C3%AA)
1. [Manifesto — 3 princípios](#1-manifesto--3-princ%C3%ADpios)
2. [Setup inicial — 5 controles obrigatórios](#2-setup-inicial--5-controles-obrigat%C3%B3rios)
3. [Fluxo de cada PR — 5 etapas](#3-fluxo-de-cada-pr--5-etapas)
4. [Depois do merge](#4-depois-do-merge)

---

## 0. Papéis — quem faz o quê

Este framework define quatro papéis, cada um assume um papel por PR.

| Papel          | Quem é                   | O que faz                                                                                     |
| -------------- | ------------------------ | --------------------------------------------------------------------------------------------- |
| **Plataforma** | Time infra/plataforma    | Configura os 5 controles do Setup (seção 2) uma única vez. Faz a manutenção semanal (seção 4). |
| **Autor**      | Um humano da equipe      | Escreve a spec do modelo. Aciona o agente. Lê o diff. É o responsável pelo PR.                |
| **Parceiro**   | Outro humano (≠ Autor)   | Aprova PRs de modelos críticos.                                                               |
| **Agente**     | A IA (LLM + ferramentas) | Escreve código, testes e o pré-registro numérico.                                             |

---

## 1. Manifesto — 3 princípios

Três itens que justificam _por que_ o framework existe. Todas as regras decorrem deles.

### Princípio 1: Em SQL, bug não dá erro — dá número plausível (errado)

Quando você erra um `JOIN` em Python, geralmente o programa quebra. Quando você erra um `JOIN` em SQL, é comum que a query rode normalmente e retorna um número que parece razoável mas que na verdade está errado. 

Por isso o humano decide _antes_ (escrevendo a spec) e confere _depois_ (lendo o diff numérico). O humano não faz nada entre esses dois momentos — o agente trabalha sozinho no meio.

### Princípio 2: Limites devem ser configurados na infraestrutura

Escrever "não acesse dados sensíveis" em um arquivo `AGENTS.md` não impede o agente de acessar dados sensíveis. Isso é uma instrução, não um controle. O agente pode ignorar, esquecer ou interpretar diferente.

Controle de verdade é exxige negar permisões no banco de dados, um resource monitor que desliga o warehouse, uma branch protection que impede push em `main`. Se o agente tentar violar, o sistema bloqueia — independentemente do que o prompt diz.

### Princípio 3: As verificações devem ser determinísticas

Tudo bem o agente ser imprevisível ao gerar código — LLMs são estocásticos por natureza. Mas todo gate de verificação (testes, diffs, reconciliações) precisa ser determinístico. A mesma entrada deve sempre produzir o mesmo resultado.

Um LLM não deve ser o juiz final de "o código está correto?". Quem julga são testes automatizados, diffs numéricos e olhos humanos.

---

## 2. Setup inicial — 5 controles obrigatórios

**Quem executa:** Plataforma. **Quando:** Uma única vez, antes do primeiro PR com agente. **Regra:** Nenhum PR com agente pode rodar antes que todos os 5 controles estejam implementados.

---

### Controle 1: Identidade própria para o agente

**O que é:** O agente precisa ter sua própria identidade separada no warehouse e no git, com permissões restritas.

**Por que existe:** Se o agente usa as credenciais de um humano, ele herda todas as permissões desse humano. Se ele roda como admin, pode fazer qualquer coisa. Uma identidade separada com permissões mínimas limita o que o agente consegue fazer.

**Como implementar:**

No warehouse (Snowflake, BigQuery ou Databricks):

- Crie uma role chamada `agent_ci` (ou nome equivalente).
- Crie um usuário associado a essa role.
- Este usuário terá as permissões definidas nos controles 2, 3 e 4.

No git (GitHub, GitLab etc.):

- Crie um usuário bot para o agente.
- Este usuário **não pode** aprovar PRs.
- Este usuário **não pode** fazer merge.
- Este usuário **não pode** dar push direto em `main`.

Branch protection na `main` (todas obrigatórias):

- PR obrigatório para qualquer mudança.
- Review de CODEOWNERS obrigatório.
- Aprovações descartadas automaticamente a cada novo push (para que o agente não consiga "passar" uma aprovação antiga após mudar o código).
- Sem bypass para ninguém — inclusive admins.
- Status checks obrigatórios: CI (etapa D) e Diff (etapa E) do fluxo por PR.

---

### Controle 2: Acesso a dados restrito

**O que é:** O agente só vê o que precisa ver, e nunca vê dados sensíveis.

**Por que existe:** Um LLM que acessa dados brutos pode vazar informações pessoais (CPF, e-mail, endereço) no código, nos testes, nos comentários do PR ou até no log de conversação com o provedor do modelo.

**Como implementar:**

| Camada de dados             | Permissão do agente                                                                                                                                           |
| --------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `raw` (dados brutos)        | **Nenhum acesso.** Nem `SELECT`, nem `DESCRIBE`.                                                                                                              |
| Staging e marts de produção | **Leitura com masking.** Colunas sensíveis são mascaradas (veja abaixo).                                                                                      |
| Produção (escrita)          | **Proibido.** O `profiles.yml` do agente não tem target `prod`. Ele não consegue escrever em produção mesmo que tente.                                        |
| Schema de trabalho          | **Leitura e escrita** em um schema exclusivo: `ci_pr_<número_do_PR>`. Criado quando o PR abre, dropado automaticamente quando o PR fecha (merge ou abandono). |

Masking de colunas sensíveis:

- No `.yml` de cada modelo dbt, toda coluna sensível deve ter `meta: {sensivel: true}`, ou mecanismo análogo.
- O masking é aplicado automaticamente pela role `agent_ci` ao consultar essas colunas.
- Implementação por plataforma:
    - **Snowflake:** use o pacote `dbt-snow-mask`.
    - **BigQuery:** use policy tags.
    - **Databricks:** use column masks.

---

### Controle 3: Tetos de gastos

**O que é:** Limites financeiros que desligam o agente automaticamente quando atingidos.

**Por que existe:** Um agente pode gerar queries caras em loop (cross joins acidentais, full scans repetidos, loops infinitos).

**Como implementar:**

Custos de warehouse:

- **Snowflake:** Resource monitor com `FREQUENCY = DAILY` e ação `SUSPEND_IMMEDIATE`. A cota diária deve ser: (cota mensal ÷ 22 dias úteis). Quando atingida, o warehouse é desligado imediatamente.
- **BigQuery:** Cota diária de bytes escaneados no projeto de CI do agente.
- **Databricks:** O sistema de budgets do Databricks só envia alertas (não desliga). Então crie um job que roda a cada hora, consulta o consumo acumulado do dia e desliga o SQL warehouse do agente se estiver acima do teto.

Timeout por query:

- Configure `STATEMENT_TIMEOUT_IN_SECONDS` no usuário e no warehouse do agente. Se uma query demorar mais que o timeout, ela é cancelada automaticamente.

---

### Controle 4: Estatísticas agregadas ao invés de acesso a registros reais

**O que é:** Em vez de permitir que o agente consulte linhas reais dos dados, forneça a ele um resumo estatístico pré-computado de cada modelo.

**Por que existe:** Se o agente roda `SELECT * FROM clientes`, ele vê nomes, e-mails, CPFs — dados reais. Mesmo com masking, quanto menos o agente vê, melhor. Um perfil estatístico dá ao agente informação suficiente para escrever SQL correto, sem expor nenhum dado individual.

**Como implementar:**

Crie um job semanal que:

1. Roda com a role `agent_ci`.
2. Para cada modelo dbt, gera um arquivo em `docs/perfil/<nome_do_modelo>.yml`.
3. Cada arquivo contém, por coluna:
    - Contagem total de linhas.
    - Percentual de nulos.
    - Cardinalidade (quantidade de valores distintos).
    - Top 20 valores **apenas** em colunas marcadas com `meta: {categorica: true}` no `.yml` do modelo. Colunas sem essa tag não exibem valores individuais.
4. O perfil **não contém**: valores mínimos, valores máximos, amostras de dados, exemplos de linhas.

Quando o agente precisa entender a estrutura de um dado, ele consulta `docs/perfil/`. Ele nunca roda queries exploratórias no warehouse.

---

### Controle 5: Paths protegidos e gates anti-fraude

**O que é:** Certos arquivos e diretórios devem ser protegidos para que apenas humanos possam alterá-los. Além disso, um script de CI deve detectar se o agente tentou enfraquecer testes ou contornar proteções.

**Por que existe:** Um agente pode, sem má intenção, remover um teste que está falhando, alterar o resultado esperado de um teste para que ele passe, ou mudar uma config de segurança. Essas mudanças fazem o CI ficar verde, mas escondem bugs. Humanos precisam controlar os arquivos que definem as regras do jogo.

**Como implementar:**

**Parte A — CODEOWNERS (o git exige aprovação humana para estes paths):**

| Path protegido                               | Por que é protegido                                                                                                          |
| -------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------- |
| `.github/`                                   | Workflows de CI. Se o agente mudar o CI, ele controla as regras.                                                             |
| `.pre-commit-config.yaml`                    | Hooks de validação local.                                                                                                    |
| `CODEOWNERS`                                 | O arquivo que define quem aprova o quê.                                                                                      |
| `AGENTS.md`                                  | As regras do agente.                                                                                                         |
| `packages.yml`                               | Dependências do dbt. Um agente poderia pinar uma versão vulnerável.                                                          |
| `dbt_project.yml`                            | Configuração global do projeto.                                                                                              |
| `macros/`                                    | Macros são reutilizadas por vários modelos. Uma mudança afeta tudo.                                                          |
| `tests/`                                     | Testes genéricos.                                                                                                            |
| `analyses/recon_*`                           | Queries de reconciliação. Se o agente mudar a reconciliação no mesmo PR do modelo, ele controla o que está sendo verificado. |
| `models/semantic/`                           | Definições de métricas. Uma métrica errada propaga erro para todos os consumidores.                                          |
| `docs/perfil/`                               | Perfis estatísticos. Se o agente mudar o perfil, ele muda sua própria referência.                                            |
| Modelos incrementais (listar explicitamente) | Modelos incrementais são mais complexos e frágeis.                                                                           |
| Diretórios de modelos críticos               | O dono do CODEOWNERS deve ser o data owner do domínio.                                                                       |

**Parte B — Gate anti-fraude:**

Um script que roda em CI sobre os commits feitos pelo bot. É o único script customizado que o framework exige. Ele analisa os diffs do bot e **bloqueia o PR** se encontrar qualquer uma destas situações:

|Situação detectada|Por que bloqueia|
|---|---|
|Teste removido|Um agente pode remover um teste que está falhando em vez de corrigir o código.|
|`WHERE` ou cláusula de exclusão adicionada a um teste|Uma forma de fazer um teste passar sem corrigir o problema: filtrar os casos que falham.|
|`severity` rebaixada (ex: `error` → `warn`)|Transformar um erro em aviso faz o CI passar, mas o problema continua.|
|Valor `expect` alterado em um teste existente|Se o agente muda o resultado esperado, qualquer resultado vira "correto".|
|`analyses/recon_*` alterado no mesmo PR do modelo|O agente não pode mudar o modelo E a reconciliação que verifica o modelo no mesmo PR. Seria como um aluno escrevendo a prova e a resposta.|
|Pin de pacote alterado|Mudar versões de dependências pode introduzir comportamentos diferentes.|

**Opcional (camada extra de proteção):** Se o agente suportar hooks antes de executar ferramentas (ex: `PreToolUse` no Claude Code), configure um hook que recusa a escrita em paths protegidos na hora — antes mesmo do commit.

---

## 3. Fluxo de cada PR — 5 etapas

Todo PR segue estas 5 etapas na ordem. Cada etapa tem um responsável e uma condição de bloqueio.

| Etapa | Nome                 | Quem executa                 | O que bloqueia o avanço                                                                         |
| ----- | -------------------- | ---------------------------- | ----------------------------------------------------------------------------------------------- |
| **A** | Spec                 | Autor (humano)               | PR não pode avançar sem spec preenchida. Modelos críticos também exigem query de reconciliação. |
| **B** | Pré-registro         | Agente                       | —                                                                                               |
| **C** | Código               | Agente                       | Não pode começar sem pré-registro válido.                                                       |
| **D** | CI automático        | Automação (a cada push)      | Qualquer falha bloqueia. Tempo máximo: ~15 minutos.                                             |
| **E** | Diff + review humano | Automação + Autor + Parceiro | Diff fora do pré-registro bloqueia. Reconciliação fora da tolerância bloqueia.                  |

---

### Etapa A: Spec (Autor)

**O que é:** O Autor (humano) escreve uma especificação declarativa no `.yml` do modelo, dentro do bloco `meta.spec`. A spec define _o que o modelo deve fazer_ — não _como_.

**Onde fica:** No arquivo `.yml` do modelo dbt, dentro de `meta.spec`.

**Quando é obrigatória:** Em todos os modelos dentro de `models/marts/**`. Modelos em staging ou intermediate podem ter spec, mas não é obrigatório.

**Campos da spec (6 campos base + 3 adicionais para modelos críticos):**

```yaml
meta:
  spec:
    # --- 6 campos obrigatórios para todo modelo em marts/ ---

    grain: "uma linha por pedido por dia"
    # O que cada linha representa. É a definição mais importante do modelo.
    # Exemplo: "uma linha por cliente" ou "uma linha por transação por produto".

    primary_key: [order_id, date_day]
    # As colunas que juntas identificam uma linha de forma única.
    # O agente vai gerar um teste de unicidade para esta combinação.

    tier: critico  # Valores possíveis: "critico" ou "padrao"
    # "critico" = modelo que alimenta decisões de negócio, relatórios financeiros
    #             ou dashboards executivos. Exige 3 campos extras (abaixo)
    #             e aprovação de um Parceiro.
    # "padrao" = todo o resto.

    metricas:
      gross_revenue: "soma de order_total antes de descontos e impostos"
    # Cada métrica que o modelo calcula, com definição em linguagem natural.
    # O agente vai usar essas definições para escrever o SQL.
    # O diff (etapa E) vai comparar os valores dessas métricas entre
    # produção e a versão nova.

    bordas_conhecidas:
      - "status='cancelled' → linha excluída"
      - "valor em centavos → dividir por 100"
      - "timestamp em UTC → converter para America/Sao_Paulo"
    # Casos especiais que o Autor já sabe que existem.
    # CADA borda se torna um unit test com fixture sintética.
    # A borda deve descrever o RESULTADO esperado, não a implementação.
    # Exemplo bom: "status='cancelled' → linha excluída"
    # Exemplo ruim: "usar WHERE status != 'cancelled'"

    colunas_sensiveis: [customer_email]
    # Lista de colunas que contêm dados pessoais.
    # O masking do Controle 2 será aplicado a estas colunas.

    # --- 3 campos adicionais, obrigatórios SOMENTE para tier: critico ---

    query_de_reconciliacao: analyses/recon_fct_orders.sql
    # Path de uma query SQL que compara o resultado do modelo com uma
    # fonte de verdade externa (outro sistema, planilha de fechamento etc.).
    # Esta query roda na etapa E com dado completo.

    tolerancia_reconciliacao: "0.1%"
    # A diferença máxima aceitável entre o modelo e a fonte de verdade.
    # Se a diferença for maior que isso, o PR é bloqueado.

    validacao_externa: "gross_revenue 2025-12 = R$ 14.203.118,40 no fechamento contábil"
    # Um número concreto de fora do warehouse que serve como âncora.
    # Isso existe porque a spec também pode errar.
    # Se a spec está errada, todos os testes vão passar (eles testam a spec),
    # mas o resultado final vai divergir do número real.
    # A validação externa pega esse caso.
```

**Regras importantes sobre a spec:**

1. O agente pode rascunhar uma versão inicial da spec a partir do perfil estatístico (Controle 4). Mas os 6 campos devem ser lidos e aprovados pelo humano **antes** de qualquer linha de código ser escrita.

2. A spec também pode estar errada. Um erro na spec é invisível para todos os gates automatizados (porque os testes verificam a spec, não a realidade). É exatamente por isso que o campo `validacao_externa` existe: ele ancora o modelo em um número que vem de fora do warehouse.
---

### Etapa B: Pré-registro (Agente)

**O que é:** Antes de escrever qualquer código, o agente declara quais mudanças numéricas ele _espera_ que aconteçam. Isso é feito em um bloco `pre_registro` no `.yml` do modelo.

**Por que existe:** Sem pré-registro, o agente vê os números do diff e depois inventa uma justificativa. O pré-registro inverte essa ordem: o agente se compromete com intervalos _antes_ de ver os resultados. Se os números caírem fora do intervalo, o PR é bloqueado automaticamente — o agente não consegue "ajustar" sua previsão depois.

**O pré-registro é imutável a partir do momento em que a etapa D (CI) começa.** Se o agente alterar o pré-registro após o CI ter rodado, o CI é reexecutado do zero e um contador de alterações é incrementado no PR (visível para o Autor no review).

**Formato do pré-registro:**

```yaml
pre_registro:
  tipo: mudanca_de_dado
  # Valores possíveis:
  #   "mudanca_de_dado" — a mudança deve alterar resultados numéricos.
  #   "refatoracao" — a mudança NÃO deve alterar nenhum resultado.
  #                   Se tipo é "refatoracao", todo delta DEVE ser 0.
  #                   Qualquer diferença numérica bloqueia o PR.

  motivo: "incluir status='partially_shipped', antes excluído indevidamente"
  # Explicação em uma frase do porquê os números vão mudar.
  # O Autor vai ler isso no review e avaliar se o intervalo faz sentido
  # dado o motivo declarado.

  delta_linhas: {min: 0, max: 12000}
  # Quantas linhas a mais (ou a menos) o modelo terá em relação à produção.
  # REGRA: todo intervalo precisa ter min E max. Intervalo aberto
  # (ex: {min: 0} sem max) é inválido e é rejeitado pelo CI.

  pks_removidas: {max: 0}
  # Quantas chaves primárias (linhas identificadas pela PK da spec)
  # existem em produção mas não existem na versão nova.
  # max: 0 significa "nenhuma linha deve desaparecer".

  colunas_alteradas: [gross_revenue, order_count]
  # Lista exata das colunas cujos valores vão mudar.
  # Se no diff uma coluna que NÃO está nesta lista apresentar diferença,
  # o PR é bloqueado. Isso impede mudanças acidentais em colunas
  # que o agente não pretendia alterar.

  metricas:
    gross_revenue: {delta_pct: {min: 0.0, max: 0.8}}
    # Para cada métrica da spec, o intervalo percentual esperado de variação.
    # Exemplo: gross_revenue deve aumentar entre 0% e 0.8%.
    # Se a variação real for -1% ou +2%, o PR é bloqueado.
```

**Validação:** O pré-registro é validado por JSON Schema no CI (etapa D). Se o formato estiver errado, campos estiverem faltando, ou intervalos estiverem abertos, o CI falha.

---

### Etapa C: Código (Agente)

**O que é:** O agente escreve o código SQL, os testes e tudo que é necessário para implementar a spec. Ele segue 8 regras, documentadas no arquivo `AGENTS.md` (que é protegido pelo Controle 5 — apenas humanos podem alterá-lo).

**As 8 regras do agente:**

Cada regra abaixo deve ter um mecanismo de infraestrutura que a impõe. A regra em texto existe apenas para que o agente entenda a intenção; o mecanismo existe para que a regra funcione mesmo que o agente a ignore.

| #   | Regra                                                                                                                                                                                                                                                                 | Mecanismo que impõe                                                                                             |
| --- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------- |
| 1   | **Sem spec, pare e peça.** Se o modelo não tem spec, o agente não começa. Ele pede ao Autor para escrevê-la.                                                                                                                                                          | CI valida presença da spec (JSON Schema).                                                                       |
| 2   | **Todo modelo tem teste de PK e contagem mínima.** O agente cria um teste de unicidade na primary_key da spec e um teste de contagem mínima de linhas. Cada borda da spec vira um unit test com fixture sintética (dados inventados que representam o caso descrito). | CI valida presença dos testes (JSON Schema + gate anti-fraude).                                                 |
| 3   | **Teste falhou = código errado.** Se um teste falha, o agente corrige o código. Nunca o contrário. O agente nunca enfraquece um teste, altera um `expect`, muda uma macro de teste ou remove uma reconciliação para fazer o CI passar.                                | Gate anti-fraude (Controle 5B) detecta e bloqueia.                                                              |
| 4   | **Métricas ficam em `models/semantic/`.** Métricas são definidas uma única vez, no diretório semântico. Se a métrica que o agente precisa não existe, ele para e pede ao Autor para criá-la.                                                                          | CODEOWNERS protege `models/semantic/`.                                                                          |
| 5   | **Ordem de execução fixa.** O agente segue esta sequência: `dbt compile` → `dbt test --select test_type:unit` → `dbt build`. Se o mesmo comando falhar 3 vezes seguidas, o agente para e chama um humano.                                                             | Regra de 3 falhas no gateway de API.                                                                            |
| 6   | **Pré-registro antes do diff.** O agente deve entregar o pré-registro (etapa B) antes de qualquer diff. Intervalos abertos (sem min ou sem max) são inválidos.                                                                                                        | JSON Schema no CI.                                                                                              |
| 7   | **Nunca leia linhas individuais.** O agente não roda `dbt show`, não faz `SELECT` sem agregação, e nunca cola um valor lido do warehouse em código, teste, fixture ou comentário de PR. Fixtures são sempre sintéticas (inventadas pelo agente).                      | Role `agent_ci` sem acesso a `raw`. Masking em staging/marts. Gate anti-fraude detecta dados reais em fixtures. |
| 8   | **Não edite paths protegidos.** Se a tarefa exige mudar um arquivo protegido (macros, CI, testes genéricos etc.), o agente para e pede ao Autor.                                                                                                                      | CODEOWNERS bloqueia merge sem aprovação humana.                                                                 |

---

### Etapa D: CI automático (a cada push)

**O que é:** Um pipeline de CI que roda automaticamente toda vez que o agente faz push na branch do PR. Deve completar em menos de 15 minutos.

**O que roda (nesta ordem):**

```bash
# 1. Validações estáticas (pre-commit hooks)
pre-commit run --all-files
```

O pre-commit executa:

- **JSON Schema:** valida que a spec, o campo `sensivel`, o pré-registro e os testes obrigatórios existem e estão no formato correto.
- **Gitleaks:** detecta segredos vazados, incluindo regras customizadas para e-mail e CPF.
- **Gate anti-fraude:** o script do Controle 5B roda sobre os commits do bot.

```bash
# 2. Build com amostra
dbt build --select state:modified+ --defer --state ./prod-artifacts --sample "30 days"
```

O build inclui:

- **Fusion em `static_analysis: baseline`** — detecta colunas inexistentes e tipos errados antes de executar qualquer query (análise estática do SQL).
- **Unit tests** gerados a partir das bordas da spec.
- **Teste de unicidade** da primary_key da spec.
- **Teste de contagem mínima** — o limiar é ajustado proporcionalmente à janela de amostra (ex: se a amostra é 30 dias e a tabela tem 365 dias, o limiar mínimo é 30/365 do limiar cheio).
- **Contracts** nos modelos de marts (garantem que colunas e tipos estão corretos).
- **dbt-project-evaluator** — detecta problemas estruturais no projeto.

**Por que rodar hooks no CI se eles já rodam localmente:** Porque `git commit --no-verify` pula todos os hooks locais. Se alguém (ou o agente) usar essa flag, os hooks não rodam. O CI garante que a validação acontece de qualquer forma.

---

### Etapa E: Diff + review humano (uma vez por PR)

**O que é:** Um `dbt build` completo (sem amostra) seguido de um diff numérico entre a versão nova e a produção atual. Roda uma única vez por PR, quando o PR é marcado como ready-for-review.

**O que roda (nesta ordem):**

**Passo 1 — Build com dado completo**

O build roda em um schema separado chamado `ci_pr_<n>_full`:

```bash
# Para modelos padrão: constrói apenas o modelo alterado
dbt build --select state:modified --defer --state ./prod-artifacts

# Para modelos críticos: constrói o modelo alterado E todos os modelos
# que dependem dele (downstream), usando o operador "+"
dbt build --select state:modified+ --defer --state ./prod-artifacts
```

Por que modelos críticos usam `state:modified+` (com o `+`): Sem o `+`, os modelos downstream seriam construídos sobre os dados intermediários de **produção** (via `--defer`), não sobre a versão alterada. O diff mostraria diferenças apenas no modelo alterado, não nos marts que o consomem. Com o `+`, toda a cadeia downstream é reconstruída, e o diff captura o efeito completo da mudança.

**Passo 2 — Data diff agregado**

Usando Recce ou `dbt-audit-helper` em modo resumo (nunca em modo que mostre linhas individuais de colunas sensíveis):

- O diff é calculado sobre uma **janela fechada de `event_time`**, idêntica nos dois lados (produção e versão nova). Isso é essencial: se a produção tem dados até ontem e a versão nova tem dados até hoje, as linhas de "hoje" apareceriam como diferenças falsas.
- O diff publica: contagem de linhas, PKs removidas, colunas com valores alterados, e o valor de cada métrica definida na spec.

**Passo 3 — Comparação com o pré-registro**

Cada número do diff é comparado automaticamente com os intervalos declarados no pré-registro (etapa B). O PR é **bloqueado** se qualquer uma destas condições for verdadeira:

- Um número está fora do intervalo declarado (ex: delta de linhas é 15.000, mas o pré-registro disse `max: 12000`).
- Uma coluna apresenta diferença mas não está na lista `colunas_alteradas` do pré-registro.
- O tipo é `refatoracao` mas algum delta não é zero.

**Passo 4 — Reconciliação (apenas modelos críticos)**

Para modelos com `tier: critico`, a query de reconciliação (`query_de_reconciliacao`) roda em dado completo e compara o resultado com a tolerância declarada (`tolerancia_reconciliacao`). Se a diferença for maior que a tolerância, o PR é **bloqueado**.

Este é o único gate capaz de detectar o caso em que a IA presumiu errado o significado de uma coluna. Se o agente acha que `order_total` é bruto mas na verdade é líquido, os unit tests passam (eles testam o que a spec diz), mas a reconciliação contra o sistema contábil falha.

**Passo 5 — Review humano: três leituras**

O Autor (e o Parceiro, se o modelo for crítico) lê exatamente três coisas.

|#|Pergunta|O que estou procurando|
|---|---|---|
|1|O grain da spec é o grain desejado?|Verificar se a definição de "uma linha" faz sentido para o negócio.|
|2|O pré-registro é estreito o bastante para poder falhar? O motivo justifica o intervalo?|Um pré-registro que diz `delta_linhas: {min: -999999, max: 999999}` é inútil — ele nunca falha. O intervalo deve ser apertado o suficiente para pegar erros reais.|
|3|Os `expect` dos unit tests dizem o mesmo que as bordas da spec?|Verificar se o agente traduziu as bordas da spec corretamente nos testes.|

**Regras de aprovação:**

- Modelo **padrão**: o Autor aprova.
- Modelo **crítico**: um Parceiro (≠ Autor) aprova. O CODEOWNERS impõe isso.
- Macros, modelos incrementais e `models/semantic/`: sempre passam por aprovação humana, independentemente do tier. O CODEOWNERS impõe.

---

## 4. Depois do merge

Depois que o PR é mergeado, dois processos automáticos garantem que o modelo continua correto em produção.

| O que                                                                | Quando roda | Por que                                                                                            |
| -------------------------------------------------------------------- | ----------- | -------------------------------------------------------------------------------------------------- |
| Full-refresh vs. incremental em ambiente paralelo (modelos críticos) | Semanal     | Compara uma reconstrução completa com o resultado incremental. Detecta drift acumulado.            |
| Regeneração de `docs/perfil/`                                        | Semanal     | Mantém os perfis estatísticos (Controle 4) atualizados.                                            |

Outros processos de higiene de dados (freshness, detecção de anomalias, alertas de qualidade) continuam existindo normalmente. Eles não são específicos de desenvolvimento com agentes e estão fora do escopo deste framework.
