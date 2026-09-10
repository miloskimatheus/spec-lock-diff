# `tools/` — os gates determinísticos do Spec-Lock-Diff

[English](README.md) · **Português (pt-BR)**

> **Trabalho em andamento.** Estas ferramentas são a primeira implementação de
> referência do Spec-Lock-Diff, mínima e propositalmente pequena. Elas vão
> mudar. Adapte ao seu warehouse, ao seu CI e ao seu time — isso é esperado,
> não é desvio. E se você melhorar alguma coisa, traga a melhoria de volta:
> abra um *Field report* ou um PR. Estamos construindo isso juntos.

Três comandos. Um arquivo. Sem modelo, sem rede, sem warehouse. Tudo aqui
implementa uma frase do [README do framework](../README.pt-br.md); onde o README
não diz nada, estas ferramentas não fazem nada.

**Conteúdo**

1. [O que tem nesta pasta](#1-o-que-tem-nesta-pasta)
2. [Prepare seu ambiente](#2-prepare-seu-ambiente)
3. [Os três comandos](#3-os-três-comandos)
4. [O contrato do `diff.json`](#4-o-contrato-do-diffjson)
5. [Templates](#5-templates)
6. [Schemas](#6-schemas)
7. [Formato de saída e códigos de saída](#7-formato-de-saída-e-códigos-de-saída)
8. [Tabela de cobertura](#8-tabela-de-cobertura)
9. [O que a v0 não faz](#9-o-que-a-v0-não-faz)
10. [Como contribuir](#10-como-contribuir)

---

## 1. O que tem nesta pasta

| Caminho | O que é |
| --- | --- |
| `slp.py` | A ferramenta inteira: três comandos, vinte e nove regras, um arquivo que se lê de uma sentada. |
| `schemas/spec.schema.json` | Como uma `meta.spec` precisa ser (README §3 Etapa A). |
| `schemas/pre_registration.schema.json` | Como um `meta.pre_registration` precisa ser (README §3 Etapa B). |
| `schemas/diff.schema.json` | Como um `diff.json` precisa ser — a única interface com o que quer que meça o seu diff. |
| `templates/CODEOWNERS` | Os paths protegidos do Controle 5A, prontos para copiar. |
| `templates/AGENTS.md` | As 8 regras do agente da Etapa C, cada uma ao lado do mecanismo que a impõe. |
| `templates/ci.yml` | Um workflow de exemplo do GitHub Actions ligando os três comandos. |
| `tests/conftest.py` | O harness de teste: roda um comando, monta um repositório a partir de árvores de fixture, lê a expectativa de uma fixture. |
| `tests/test_cli.py` | O ponto de entrada em si: argumentos, leitura de arquivos, códigos de saída. |
| `tests/test_schemas.py` | Cada schema contra suas fixtures válidas e inválidas. |
| `tests/test_check.py`, `test_gate.py`, `test_compare.py` | Um teste por pasta de fixture de cada comando. |
| `tests/test_templates.py` | Os templates contra o README que eles copiam. |
| `tests/test_harness.py` | O próprio harness, porque um harness que mente faz todos os outros testes mentirem junto. |
| `tests/test_meta.py` | As ferramentas sobre as ferramentas: referências, cobertura, dependências, determinismo, tamanho. |
| `tests/fixtures/` | Cada caso, como arquivos de verdade. Uma pasta por caso, cada uma com um `README.txt`. |

---

## 2. Prepare seu ambiente

1. **Python 3.9 ou mais novo**, e **git 2.20 ou mais novo**. Confira com
   `python3 --version` e `git --version`. A maioria das distribuições Linux traz
   `python3` e nenhum `python`; todo comando deste documento está escrito
   `python` por brevidade, então, se a sua é uma delas, leia `python3` em todos
   eles — inclusive no `templates/ci.yml` e no `templates/AGENTS.md`, onde os
   mesmos comandos estão ligados ao CI.
2. **PyYAML e jsonschema 4 ou mais novo.** Se o dbt está instalado, você já tem
   os dois. Se não: `pip install "pyyaml" "jsonschema>=4"`. O piso não é
   enfeite — os schemas são JSON Schema draft 2020-12, e o validador dele
   chegou no jsonschema 4.0. No 3.x as ferramentas não caem para um draft mais
   velho; elas não sobem. Essas duas bibliotecas são tudo o que elas usam.
3. **Copie `tools/` para a raiz do seu repositório dbt**, ao lado do
   `dbt_project.yml`.
4. **Copie os templates para o lugar deles:**
   ```bash
   cp tools/templates/CODEOWNERS .github/CODEOWNERS
   cp tools/templates/AGENTS.md  AGENTS.md
   cp tools/templates/ci.yml     .github/workflows/ci.yml
   ```
   Depois edite cada linha que os arquivos marcam como sua, e troque
   `@your-org/data-platform` pelo time que aprova.
5. **Ligue a branch protection** na `main`: exigir pull request, exigir review
   de Code Owners, e listar `ci` e `diff` como required checks — esses são os
   nomes dos jobs no `ci.yml`.
6. **Confira que roda:**
   ```bash
   python tools/slp.py --version
   ```
7. **Opcional, e vale a pena:** `pip install pytest && pytest tools/tests -q`.
   Cerca de duzentos e oitenta testes, alguns segundos, sem rede. Se passam, os
   gates da sua máquina são os gates do CI.

---

## 3. Os três comandos

```
python tools/slp.py check   [--project-dir .] [--marts-path models/marts]
python tools/slp.py gate    --base <git ref> [--head HEAD] [--project-dir .] [--marts-path ...]
python tools/slp.py compare <diff.json> [<diff.json> ...] [--base <git ref>] [--project-dir .] [--marts-path ...]
python tools/slp.py --version
```

### `check`

**O que é.** O `check` lê todos os arquivos de modelo em `models/` e diz se
cada modelo em `models/marts/` tem spec completa, pré-registro válido (se
tiver um) e teste de unicidade na primary key.

**Por que o framework precisa dele.** Princípio 1: "O humano **decide antes**,
escrevendo a spec." Etapa A: "PR não pode avançar sem spec preenchida."
Regra 1: "Sem spec, para e pergunta." Regra 2: "O agente cria um teste de
unicidade na primary_key da spec."

**Como funciona.** Carrega os arquivos yml, acha a `meta.spec` de cada modelo
(ou `config.meta.spec`), valida contra `schemas/spec.schema.json`, verifica as
poucas coisas que um schema não vê — as colunas da primary key existem? a query
de reconciliação existe? as colunas sensíveis e as marcações `meta.sensitive`
concordam? — e imprime uma linha por problema. Também lista os arquivos `.sql`
dos caminhos de marts, para que um modelo que ninguém declarou num yml não
passe por falta do que cobrar (`S4`); nunca lê o que há dentro deles, nunca
chama o git e nunca toca no warehouse.

**Onde olha.** Em `models/marts/`, porque é ali que o README §3 Etapa A torna a
spec obrigatória. Se os seus marts moram em outro lugar, diga com
`--marts-path`, e repita a flag para mais de um diretório:

```
python tools/slp.py check --marts-path models/core --marts-path models/finance
```

Passe os mesmos caminhos para o `gate` e para o `compare`. Um caminho que não é
um diretório é erro (exit 2), não aprovação — uma ferramenta apontada para uma
pasta que não existe não acha nada de errado em nada, e isso se lê exatamente
como uma rodada limpa. É também por isso que a linha de resumo separa os dois
números: **quantos modelos foram cobrados pelo framework**, e quantos foram
lidos ao todo. Só o primeiro é cobertura.

Um modelo conta como modelo de marts quando **o `.sql` que o produz** mora num
caminho de marts — não quando o yml que o documenta mora. Um projeto que mantém
um único `models/schema.yml` para tudo, que é o que o `dbt init` monta, é dbt
comum; decidir pelo caminho do yml teria isentado todo modelo desse projeto de
`S1`, `T1` e `G7` enquanto o `check` imprimia `OK`.

**Quando roda.** Etapa A, enquanto o Autor escreve a spec. Etapa C, antes de o
agente commitar. Etapa D, no CI, a cada push.

**Como usar.**

```
$ python tools/slp.py check
slp check: OK (1 model in models/marts/, of 1 model read)
```

```
$ python tools/slp.py check
BLOCK	models/marts/fct_orders.yml	fct_orders	no uniqueness test on primary key [order_id]; accepted forms: unique, unique_combination_of_columns, dbt_utils.unique_combination_of_columns	[T1]
slp check: 1 block - BLOCKED
```

As duas saídas são copiadas de `tests/fixtures/check/spec_ok` e
`tests/fixtures/check/pk_single_missing`; você pode rodar as duas com
`--project-dir`. As mensagens saem em inglês: elas são lidas em log de CI, onde
o inglês é a língua franca, e o mesmo texto aparece em qualquer time.

**O que conta como teste.** A `T1` só aceita um teste de unicidade que possa
reprovar o build. Um teste `enabled: false`, ou `severity: warn`, ou estreitado
por `where`, `error_if`, `warn_if`, `fail_calc` ou `limit` roda e reporta
aprovação faça o dado o que fizer — um `unique` com `where: "1 = 0"` não olha
linha nenhuma. O framework torna esse teste obrigatório; um teste obrigatório
que não pode reprovar é um quadradinho marcado, então o `check` diz qual desses
casos encontrou:

```
BLOCK	models/marts/fct_orders.yml	fct_orders	the uniqueness test on primary key [order_id] cannot fail the build: it sets where	[T1]
```

Isso é `T1` e não uma regra do `gate` de propósito: o `gate` compara um teste
com a versão anterior dele mesmo, e um teste escrito assim num modelo novo não
tem versão anterior para ser mais fraco que ela.

**Como mudar.** Para exigir um campo novo na spec, adicione ao
`schemas/spec.schema.json` com uma `description` escrita como exigência — essa
description é a frase que a ferramenta imprime — e adicione uma fixture válida e
uma inválida em `tests/fixtures/schemas/spec/`. Para aceitar outra forma de
teste de unicidade, adicione o nome em `ACCEPTED_PK_TESTS`, dentro de
`check_pk_test`, e adicione uma fixture que passa em `tests/fixtures/check/`.
Para adicionar uma verificação, escreva uma função cuja docstring comece pela
seção do README que ela impõe, acrescente em `CHECK_RULES`, adicione uma fixture
que bloqueia e uma que passa, e adicione uma linha na
[tabela de cobertura](#8-tabela-de-cobertura). Se o que você quer não está no
README do framework, abra antes uma issue de *Framework improvement*.

### `gate`

**O que é.** O `gate` compara esta branch com o ponto onde ela começou e
bloqueia o PR se alguma coisa que julga o código foi enfraquecida: um teste, um
unit test, uma query de reconciliação, um pin de pacote ou a própria spec.

**Por que o framework precisa dele.** Controle 5B: "Um script que roda no CI nos
commits feitos pelo bot … analisa os diffs e **bloqueia o PR**." Regra 3:
"Teste falhou = código errado. Se um teste falha, o agente corrige o código.
Nunca o contrário."

**Como funciona.** Pergunta ao git o merge-base entre `--base` e `--head` — não
a ponta da `main`, para que uma branch que andou não pareça a sua branch
removendo coisas —, lê os arquivos como eles estão naquele commit e como estão
no `head`, e compara dois inventários. Um data test é identificado pelo modelo,
pela coluna, pelo nome e pelos argumentos — e um unit test pelo modelo e pelo
nome, porque o dbt só os torna únicos dentro de um modelo e dois marts podem ter
cada um o seu `cancelled_orders_are_excluded`. Então mover um teste para outro
arquivo ou renomear `tests:` para `data_tests:` não muda nada, enquanto encolher
os valores de um `accepted_values` muda tudo. Uma coluna que carrega dois testes
de mesmo nome — dois `relationships`, vários `accepted_values` — tem cada um
comparado em separado, config e tudo, e o finding diz de qual deles está
falando. Quando dois deles carregam também os *mesmos argumentos*, e diferem só
na config — dois `dbt_utils.expression_is_true` na mesma expressão, com um
`where` cada —, o par é guardado como um saco sob uma chave só e comparado como
um: quantos eram, quantos são, e quais configs estão no segundo saco e não no
primeiro. Numerá-los seria errado justamente no caso que importa, porque tirar o
primeiro de dois passa o número dele para o segundo, e isso se lê como edição de
config em vez de teste removido. Para as três regras que precisam de histórico
— `G7`, `I1`, `I4` —, ele caminha pelos commits com `--first-parent`, do mais
antigo para o mais novo.
Tudo o que um commit tem é lido por um único `git cat-file --batch`, então um
pull request custa cerca de dois processos de git por commit em vez de um por
arquivo por commit — 150 modelos numa branch de 30 commits gastavam vinte
segundos só abrindo processos antes de qualquer regra olhar para alguma coisa.

**Quando roda.** Etapa C, antes de o agente commitar (`--base main`). Etapa D,
no CI, a cada push, com o base e o head do PR.

**Como usar.**

```
$ python tools/slp.py gate --base main
slp gate: OK (no changes)
```

```
$ python tools/slp.py gate --base main
BLOCK	models/marts/fct_orders.yml	fct_orders	test 'unique' on fct_orders.order_id exists on main but not in this PR	[G1]
slp gate: 1 block - BLOCKED
```

No CI, passe as duas pontas explicitamente, e faça checkout do histórico
inteiro — a caminhada precisa dos commits:

```yaml
- uses: actions/checkout@v4
  with:
    fetch-depth: 0
- run: |
    python tools/slp.py gate \
      --base ${{ github.event.pull_request.base.sha }} \
      --head ${{ github.event.pull_request.head.sha }}
```

**O pré-registro não é opcional.** A Etapa B é onde o agente se compromete com
intervalos antes de ver qualquer resultado, e até a `G8` nada fazia isso
acontecer. O `check` validava um pré-registro só quando achava um; nenhuma regra
do `gate` procurava pela ausência dele; e a `C7` percorre os modelos que *têm*
um, então um modelo sem pré-registro não é um modelo que o `compare` reporta
como faltante — é um modelo de que o `compare` nunca ouviu falar. Apagar a
previsão saía mais barato que errar nela. A `G8` bloqueia quando o `.sql` de um
modelo de marts mudou na branch e não há `meta.pre_registration` para segurar os
números dele — ou o que há é o que a `main` já tinha.

**Um pré-registro pertence a um pull request** (README §3 Etapa B, *de quem
é*). Depois do merge ele fica no yml como registro do que foi previsto, então a
próxima mudança naquele modelo encontra um já ali — escrito para outra mudança,
contra outra produção. Até a 0.4.0 essa previsão herdada satisfazia a `G8`,
fazia a `C7` exigir diff de todo modelo que alguém um dia pré-registrou, e
transformava o ato honesto de substituí-la numa edição contada pela `I1`. Agora
um pré-registro idêntico ao do merge-base conta como ausente: a `G8` bloqueia
nele, a `I1` começa a contar do primeiro commit cujo pré-registro difere do da
`main`, e o `compare --base` se recusa a ler números contra ele (`C0`) e não
pede o diff dele (`C7`).

O escopo é o `.sql` de propósito: a Etapa B diz que o agente declara o que
espera *antes de escrever qualquer código*, então o gatilho é o código mudar.
Adicionar um teste, escrever uma descrição ou documentar uma coluna não pede
intervalo. Uma mudança feita só no yml que mesmo assim move números — uma
materialização, um `config` — é uma lacuna, e está na
[seção 9](#9-o-que-a-v0-não-faz).

**O que um teste adicionado pela branch pode ser.** A `G2` e a `G3` comparam um
teste com o eu anterior dele, e um teste escrito nesta branch não tem nenhum —
então o caminho por fora das duas sempre foi adicionar o teste no mesmo PR. A
`G3` cobra de um teste novo a mesma linha que de um antigo: `enabled: false`,
uma `severity` que não é `error`, um `error_if`, um `warn_if`, um `fail_calc` ou
um `limit` bloqueiam, porque nenhum deles tem leitura em que o teste possa
falhar. O `where` é o que pode ter: pode ser recorte honesto — uma coluna só
preenchida depois de uma data de backfill — ou podem ser exatamente as linhas
que teriam falhado. Nenhuma máquina distingue as duas coisas, então a `I3`
imprime e quem faz a terceira leitura da Etapa E decide. É o mesmo predicado que
a `T1` usa, e a `T1` recusa um `where` de saída, porque está julgando o único
teste que o framework torna obrigatório e não um que o agente escolheu somar.

**O que o yml não mostra.** Toda regra acima lê o yml do modelo, e o dbt deixa
o mesmo enfraquecimento ser escrito onde nenhum yml muda. Um `{% test unique %}`
adicionado em `tests/generic/` ou `macros/` substitui o `unique` nativo em todo
lugar onde ele é declarado, porque o dbt resolve macros do projeto antes das
dele; um teste singular em `tests/` carrega `severity`, `enabled`, `error_if` e
o resto dentro do próprio `{{ config() }}`. Então a `G9` bloqueia qualquer
mudança na branch a um caminho protegido do Controle 5A — `.github/`,
`.pre-commit-config.yaml`, `CODEOWNERS`, `AGENTS.md`, `dbt_project.yml`,
`macros/`, `models/semantic/`, `docs/profile/`, `tools/` — e qualquer arquivo
adicionado em `tests/generic/`. Caminhos com regra própria ficam com ela, para
que uma mudança seja um achado só: os arquivos de pacote são `G6`,
`analyses/reconciliation_*` é `G5`, um arquivo de teste que já existia é `G1`.
A `G10` lê o `config()` de todo teste singular que a branch adiciona e bloqueia
um que não pode falhar, com o mesmo predicado que `T1` e `G3` usam. O
CODEOWNERS continua fazendo um humano aprovar esses caminhos; o gate faz deles
um check vermelho, para que a aprovação não seja a única coisa de pé, e nos
pull requests do próprio agente ninguém precise reparar. Um humano que precise
mudar um deles faz isso num pull request próprio — que é o parágrafo seguinte.

**Escopo do gate.** O gate julga o PR inteiro, não "os commits do agente". Não
existe identidade de bot para configurar, e autor de commit é texto que
qualquer um escreve. O que decorre disso: num PR de agente ninguém enfraquece um
teste — nem o agente, nem um humano. Um humano que precisa mudar um teste faz
isso **antes de o agente começar**, como parte de escrever a spec, ou num PR
separado.

**Como mudar.** Uma regra é uma função: uma docstring que começa pela frase do
README que ela impõe, um id de regra e uma lista de findings. Acrescente em
`GATE_RULES`, adicione uma pasta de fixture que bloqueia e uma com `_ok_` no
nome que passa em `tests/fixtures/gate/`, e adicione uma linha na tabela de
cobertura. As pastas de fixture são a suíte de testes: o `test_gate.py` itera
sobre elas e nunca precisa ser editado.

### `compare`

**O que é.** O `compare` lê os números que o seu diff mediu e confronta cada um
com o intervalo que o pré-registro declarou antes de qualquer código existir.

**Por que o framework precisa dele.** Etapa E, passo 3: "Cada número do diff é
comparado automaticamente com os intervalos declarados no pré-registro."
Etapa B: "o agente se compromete com intervalos *antes* de ver os resultados. Se
os números caírem fora do intervalo, o PR é bloqueado automaticamente — o agente
não pode 'ajustar' sua previsão depois."

**Como funciona.** Lê um ou mais arquivos `diff.json`, valida cada um contra
`schemas/diff.schema.json`, encontra o modelo no seu projeto, revalida que o
pré-registro dele é válido, e então compara: delta de linhas, PKs removidas,
colunas alteradas, cada métrica e — para modelos críticos — a reconciliação
contra a tolerância. Ele não produz o diff e não roda a query de reconciliação:
essas duas coisas tocam o warehouse, e estas ferramentas não tocam.

Depois faz uma coisa que os arquivos não têm como pedir: procura no projeto os
modelos que têm pré-registro e cujos números nunca apareceram, e bloqueia nesses
(`C7`). Passe todos os diffs que o build produziu numa chamada só —
`compare diff/*.json`, não uma chamada por arquivo — porque uma regra sobre o
que *falta* só enxerga o que lhe foi entregue.

Passe `--base <git ref>` — a branch que o pull request mira, como o
`templates/ci.yml` faz — e ele lê o pré-registro que cada modelo tinha no
merge-base, o mesmo ponto contra o qual o `gate` compara. Um que continua
idêntico a ele é a previsão da `main`, não deste pull request: a `C7` não pede o
diff dele, e um diff medido contra ele é recusado (`C0`). Sem `--base`, todo
pré-registro do projeto conta como sendo deste pull request. Isso é mais
estrito, nunca mais frouxo — a `C7` pede diff de cada um, e um herdado é
comparado em vez de recusado — então uma rodada local sem a flag pode bloquear
por um modelo em que você nunca tocou. Passe a flag.

**Quando roda.** Etapa E, uma vez por PR, depois do build completo.

**Como usar.**

```
$ python tools/slp.py compare diff.json
INFO	diff.json	fct_orders	measured over order_date from 2025-01-01 to 2025-01-31	[C0]
INFO	diff.json	fct_orders	declared as a data_change, because: include status partially_shipped, previously excluded incorrectly	[I2]
INFO	diff.json	fct_orders	row_delta 8400, declared 0..12000 (a band 12000 wide)	[I2]
INFO	diff.json	fct_orders	removed_pks 0, declared at most 0	[I2]
INFO	diff.json	fct_orders	metric gross_revenue moved 0.42 percent, declared 0.0..0.8 (a band 0.8 wide)	[I2]
INFO	diff.json	fct_orders	altered columns measured [gross_revenue], declared [gross_revenue]	[I2]
slp compare: 6 infos - OK
```

```
$ python tools/slp.py compare diff.json
BLOCK	diff.json	fct_orders	metric gross_revenue moved 2.5 percent, pre-registration allows 0.0..0.8	[C4]
INFO	diff.json	fct_orders	declared as a data_change, because: include status partially_shipped, previously excluded incorrectly	[I2]
INFO	diff.json	fct_orders	row_delta 8400, declared 0..12000 (a band 12000 wide)	[I2]
slp compare: 1 block, 6 infos - BLOCKED
```

Toda mensagem diz os dois números: o que foi medido e o que foi prometido — e a
`I2` diz **tenha bloqueado alguma coisa ou não**. É esse o ponto dela. A Etapa E
passo 5 faz três perguntas ao Autor, e a segunda é *"O pré-registro é estreito o
suficiente para poder falhar? A razão justifica o intervalo?"* Um `row_delta` de
8.400 dentro de uma faixa de 12.000 é uma revisão diferente dos mesmos 8.400
dentro de uma faixa de 200, e uma rodada que imprime só `OK` não te dá como
distinguir as duas. Então o `compare` imprime a razão declarada, cada número, a
faixa declarada para ele, e a largura dessa faixa — que é a largura de que o
README fala quando diz que `{min: -999999, max: 999999}` é inútil.

Também avisa quando o diff não traz `window`, porque o README §3 Etapa E passo 2
chama de essencial a janela fechada e idêntica dos dois lados, e nada aqui
consegue verificar isso — a segunda linha dessa saída é a ferramenta dizendo
qual das próprias promessas ela não consegue cumprir por você.

A `I2` nunca muda o exit code. A `I1` também não. O que elas dizem tem de ser
*lido*, e é por isso que o `templates/ci.yml` joga as duas no resumo do job.

**Como mudar.** Mesma forma do gate: uma função, uma docstring com a frase do
README, um id de regra, acrescentada em `COMPARE_RULES`, com uma fixture que
bloqueia e uma que passa em `tests/fixtures/compare/` e uma linha na tabela de
cobertura. Se você quer comparar algo que o diff ainda não carrega, comece pelo
schema — e se o README do framework não pede aquele número, abra uma issue antes
de escrever a regra.

---

## 4. O contrato do `diff.json`

Um arquivo por modelo. As chaves espelham o pré-registro de propósito, para que
a comparação seja chave a chave.

| Chave | Tipo | Obrigatória | Significado |
| --- | --- | --- | --- |
| `model` | string | sim | o modelo dbt em que estes números foram medidos |
| `row_delta` | inteiro | sim | linhas no build do PR menos linhas em produção, dentro da janela |
| `removed_pks` | inteiro ≥ 0 | sim | primary keys presentes em produção e ausentes no build do PR |
| `altered_columns` | lista de strings | sim | colunas com pelo menos uma linha casada por PK cujo valor difere |
| `metrics` | objeto de `{delta_pct: número ou null, value: número}` | sim (pode ser `{}`) | uma medição por métrica; `value` quando a produção não tem o modelo |
| `reconciliation` | `{model_value, external_value}` | não | modelos críticos |
| `window` | `{column, start, end}` | não | impressa pelo `compare` para quem revisa |
| `extra` | objeto | não | qualquer outra coisa que você queira carregar; ignorada |

**A unidade e o sinal de `delta_pct`.** Pontos percentuais, escritos como número
simples, calculados como `(pr − prod) / prod × 100`.

> Produção soma 1.000.000,00 de `gross_revenue` na janela. O build do PR soma
> 1.008.000,00. Então `delta_pct` é
> `(1008000 − 1000000) / 1000000 × 100 = 0.8` — o número **0.8**, não 0.008 e
> não 80. Um pré-registro de `{min: 0.0, max: 0.8}` aceita, no limite. Se o
> build do PR somar *menos* que produção, o número é negativo. Quando produção é
> 0 a porcentagem não existe: escreva `null`, e o `compare` bloqueia, porque um
> número que ninguém consegue avaliar não é um número que alguém aprovou.

**Um modelo que a produção não tem.** O primeiro caso do framework — um agente
constrói um mart novo a partir de uma spec — não tem lado de produção, então não
há percentual a prever e `delta_pct` é `null` para toda métrica. Até a 0.4.0
isso era um bloqueio `C4` sem saída a não ser `metrics: {}` na spec, o que
tirava a substância do diff exatamente dos modelos para os quais ele existe.
Agora o pré-registro declara o próprio valor, `value: {min, max}`, escrito em
torno do número da `external_validation`, e o diff carrega `value`, o valor da
métrica no build do PR dentro da janela; o `compare` confronta um com o outro
(`C4`), imprime na `I2`, e bloqueia uma métrica pré-registrada por percentual
nesse modelo com uma mensagem que diz qual dos dois escrever. `row_delta` passa
a ser a própria contagem de linhas, e `altered_columns` é `[]` dos dois lados,
porque não há linhas casadas por chave primária para diferir.

**De onde vêm os números.** De qualquer coisa determinística: Recce,
`dbt-audit-helper` em modo sumário, ou o seu próprio SQL. A janela precisa ser
fechada e idêntica dos dois lados — se produção tem dado até ontem e o build do
PR até hoje, "hoje" aparece como diferença falsa. Um ponto de partida, adapte à
vontade:

```sql
-- YOU: seus schemas, seu modelo, sua janela, suas métricas.
with prod as (
    select * from analytics.fct_orders
    where order_date >= date '2025-01-01' and order_date < date '2025-02-01'
),
pr as (
    select * from ci_pr_42_full.fct_orders
    where order_date >= date '2025-01-01' and order_date < date '2025-02-01'
),
matched as (
    select
        prod.order_id       as prod_key,
        pr.order_id         as pr_key,
        prod.gross_revenue  as prod_gross_revenue,
        pr.gross_revenue    as pr_gross_revenue
    from prod
    left join pr on prod.order_id = pr.order_id   -- a primary_key da spec
)
select
    (select count(*) from pr) - (select count(*) from prod)         as row_delta,
    sum(case when pr_key is null then 1 else 0 end)                 as removed_pks,
    sum(case when pr_key is not null
              and prod_gross_revenue is distinct from pr_gross_revenue
             then 1 else 0 end)                                     as gross_revenue_changed,
    100.0 * ((select sum(gross_revenue) from pr)
             - (select sum(gross_revenue) from prod))
          / nullif((select sum(gross_revenue) from prod), 0)         as gross_revenue_delta_pct
from matched
```

Uma linha sai, um `diff.json` entra: coloque `gross_revenue` em
`altered_columns` quando `gross_revenue_changed > 0`, e
`gross_revenue_delta_pct` — que o `nullif` já transforma em `null` quando
produção é 0 — em `metrics.gross_revenue.delta_pct`. Para primary key de várias
colunas, faça o join por todas elas. Para um modelo crítico, adicione em
`reconciliation` os dois números que a sua query de reconciliação devolveu.

O contrato recomendado para a própria query de reconciliação é uma linha com
`metric, model_value, external_value`, para que a mesma query possa ser lida por
um humano e por quem escreve o JSON.

---

## 5. Templates

### `templates/CODEOWNERS`

**O que é.** A lista de paths protegidos do Controle 5A como um arquivo que você
copia.

**Por que o framework precisa dele.** Controle 5A: "o git exige aprovação humana
para estes paths". Princípio 2: um limite escrito e torcido para funcionar não é
um controle; uma branch protection é.

**Como funciona.** O git se recusa a fazer merge de um PR que toca um desses
paths até que um dono aprove. Funciona tendo o agente lido o `AGENTS.md` ou não.

**Quando roda.** Uma vez, quando a Plataforma prepara o repositório; depois, em
todo PR, para sempre.

**Como usar.** Copie para `.github/CODEOWNERS`, troque
`@your-org/data-platform`, liste seus modelos incrementais e seus diretórios
críticos onde o arquivo pede, e ligue "Require review from Code Owners".

**Como mudar.** O arquivo segue a tabela do README linha a linha, e o
`test_templates.py` falha se uma linha sumir. Ele acrescenta três paths que a
tabela não lista — `tools/` e, comentados, `models/staging/` e `.claude/` — cada
um com o motivo ao lado. Para acrescentar outro, escreva a linha e o motivo.

### `templates/AGENTS.md`

**O que é.** As oito regras da Etapa C, em menos de uma página, cada uma ao lado
do mecanismo que a impõe.

**Por que o framework precisa dele.** Etapa C: "Cada regra abaixo deve ter um
mecanismo de infraestrutura que a impõe. A regra em texto existe apenas para que
o agente entenda a intenção; o mecanismo existe para que a regra funcione mesmo
que o agente a ignore."

**Como funciona.** Não funciona. É a primeira linha do arquivo: nada ali é um
controle. Ele conta ao agente o que as máquinas ao redor vão fazer, para que o
agente não gaste um PR descobrindo.

**Quando roda.** Etapa C, lido pelo agente antes de ele escrever qualquer coisa.

**Como usar.** Copie para `AGENTS.md` na raiz do repositório, mantenha a lista
de paths protegidos idêntica ao seu CODEOWNERS, e proteja o próprio arquivo.

**Como mudar.** As oito regras são copiadas palavra por palavra do README e o
`test_templates.py` compara; se você quer uma regra diferente, mude o README
primeiro. Tudo depois da tabela — o que rodar antes de commitar, no que não
tocar, quando parar e chamar um humano — é seu para adaptar.

### `templates/ci.yml`

**O que é.** Um workflow de exemplo do GitHub Actions com dois jobs, `ci` e
`diff`, que liga os três comandos às Etapas D e E do framework.

**Por que o framework precisa dele.** Etapa D: "Um pipeline de CI que roda
automaticamente toda vez que o agente dá push … Deve completar em menos de 15
minutos." Etapa E: "Roda uma vez por PR, quando o PR é marcado como
ready-for-review."

**Como funciona.** O `ci` faz checkout do histórico inteiro, roda `check` e
`gate`, e builda o que mudou numa janela de amostra. O `diff` espera o `ci`,
builda com dado completo, produz o diff e roda o `compare`. Os dois jogam a
saída no job summary, para o Autor ler os achados sem abrir o log.

**Quando roda.** A cada push num PR; o `diff` só depois que o PR sai de rascunho.

**Como usar.** Copie para `.github/workflows/ci.yml` e resolva as linhas
marcadas: seu adapter, sua autenticação no warehouse, seus artefatos de
produção, seu build completo, seu diff. Cada um desses passos sai com erro até
você escrevê-lo — um template entregue sem edição falha fechado. Por fim, liste
`ci` e `diff` como required checks na branch protection.

**Como mudar.** É um exemplo, não um contrato; as únicas partes das quais outras
coisas dependem são os dois nomes de job e os três comandos do `slp.py`. Se você
usa GitLab, Buildkite ou Jenkins, mantenha esses e traduza o resto.

---

## 6. Schemas

Os três são JSON Schema draft 2020-12, e todo campo carrega uma `description`
escrita como exigência — porque essa description é o que a ferramenta imprime
quando o campo está errado. Um schema que se lê como documentação e uma
mensagem de erro que se lê como frase são o mesmo texto.

### `schemas/spec.schema.json`

**O que é.** O formato da `meta.spec`: seis campos obrigatórios, mais três
quando `tier: critical`.
**Por quê.** README §3 Etapa A. O formato da spec é invenção do framework; um
schema transforma um exemplo em contrato.
**Como.** O `check` valida contra ele toda spec que encontra.
**Quando.** Etapas A, C e D.
**Usar.** Nada a fazer — o `check` usa.
**Mudar.** Adicione o campo, escreva a description como exigência, adicione uma
fixture válida e uma inválida em `tests/fixtures/schemas/spec/`. Regras entre
campos ("esta coluna precisa existir") não moram aqui; vão em
`check_spec_consistency`.

### `schemas/pre_registration.schema.json`

**O que é.** O formato do `meta.pre_registration`.
**Por quê.** README §3 Etapa B e Regra 6: "Intervalos abertos (sem min ou max)
são inválidos." O schema é onde isso deixa de ser uma frase.
**Como.** O `check` valida; o `compare` revalida antes de comparar qualquer
número.
**Quando.** Etapas B, C, D e E.
**Usar.** Nada a fazer.
**Mudar.** Igual ao anterior. Repare no `if/then`: uma `refactoring` prende
todos os números em zero.

### `schemas/diff.schema.json`

**O que é.** O formato do `diff.json` que a sua automação escreve.
**Por quê.** README §3 Etapa E, passo 2 lista o que o diff publica. Isto é essa
lista, como contrato.
**Como.** O `compare` valida cada arquivo antes de ler um único número dele.
**Quando.** Etapa E.
**Usar.** O que produz o seu diff precisa escrever neste formato. Veja a
[seção 4](#4-o-contrato-do-diffjson).
**Mudar.** Se você adiciona uma chave, adicione aqui e diga o que ela significa;
o `compare` rejeita chaves que não conhece, e é isso que impede um typo de ser
lido como "nada mudou".

---

## 7. Formato de saída e códigos de saída

Uma linha por achado, separada por tabulação, e depois uma linha de resumo. Tudo
no stdout; erros que param a ferramenta vão para o stderr.

```
BLOCK	models/marts/orders.yml	fct_orders	test 'unique' on fct_orders.order_id exists on main but not in this PR	[G1]
INFO	models/marts/orders.yml	fct_orders	pre-registration was modified 2 times after it was first written	[I1]
slp gate: 1 block, 1 info - BLOCKED
```

| Severidade | Significado |
| --- | --- |
| `BLOCK` | Tem coisa errada. Faz o código de saída ser 1. |
| `INFO` | Algo que quem revisa precisa ver. Nunca muda o código de saída. |

| Código | Significado | O que o CI faz |
| --- | --- | --- |
| 0 | Nada a relatar | passa |
| 1 | Pelo menos um `BLOCK` | falha |
| 2 | A ferramenta não conseguiu fazer o trabalho dela: arquivo que não abre, yml que não parseia, argumento errado, não é um repositório git | falha |

O código 2 é falha, nunca aprovação. O que não pode ser lido não pode ser
aprovado: uma aprovação silenciosa é exatamente a falha que este framework
existe para evitar.

Os achados são ordenados por arquivo, depois modelo, depois o que bloqueia
antes do que só informa, depois id da regra — e empates mantêm a ordem em que a
regra os produziu, porque uma regra com várias coisas a dizer normalmente tem
uma ordem de leitura para elas. A da `I2` é a ordem em que a Etapa E pede que
os números sejam lidos. Os mesmos arquivos na entrada dão as mesmas linhas na
saída, na mesma ordem, em qualquer máquina.

Quatro regras só informam e nunca mudam o exit code: a `I1`, o contador de
alterações do pré-registro; a `I2`, os números em si; a `I3`, um filtro num
teste que esta branch adiciona; e a `C5`, que diz numa linha o que uma
refatoração prometeu e o que se moveu. As três primeiras nasceram para informar,
por isso os ids começam com `I`. A `C5` nasceu para bloquear e deixou de
bloquear: os intervalos de uma refatoração são fixados em zero pelo schema,
então a `C1` até a `C4` já recusam qualquer número que ela pudesse pegar, e
bloquear duas vezes por um problema faz o revisor contar dois. O meta-teste **M2** confere essa promessa contra
o código-fonte, para que uma regra não ganhe um `BLOCK` em silêncio. O que elas
dizem existe para ser *lido*, e é por isso que o `templates/ci.yml` joga os dois
comandos no resumo do job.

**Como ler uma rodada.** Três perguntas, nesta ordem.

1. **Saiu com 2?** Então nada foi julgado. Um arquivo que não deu para ler, yml
   que não deu para parsear, um `--marts-path` que não é diretório. Resolva
   isso primeiro; um exit 2 não diz nada sobre o código.
2. **Tem algum `BLOCK`?** Cada um diz o que foi medido e o que foi prometido, e
   termina num id de regra que você acha na
   [tabela de cobertura](#8-tabela-de-cobertura). Um bloqueio do `gate` quase
   nunca é coisa para contornar: é um teste que ficou mais fraco, e a Regra 3
   do framework diz que quem muda é o código.
3. **Aí leia as linhas `INFO`.** Elas nunca mudam o exit code, e é justamente
   por isso que são fáceis de pular e valem não pular. A `I1` diz quantas vezes
   o pré-registro foi editado depois de escrito — um número que o README pede
   que o Autor veja. A `I2` é o diff em si: cada número ao lado da faixa
   declarada para ele, e a largura dessa faixa. A `I3` é um teste que a branch
   adicionou com um `where`, que nenhuma máquina distingue de recorte honesto —
   você distingue. A `C5` é uma linha dizendo o que uma refatoração prometeu e o
   que se moveu, quando a `C1` até a `C4` já bloquearam pelo mesmo motivo.

Uma rodada que não bloqueia nada não é a mesma coisa que uma rodada que não
achou nada para olhar. `slp check: OK (3 models in models/marts/, of 40 models
read)` é uma afirmação de cobertura; leia o primeiro número. `slp compare: OK
(1 file)` num pull request que pré-registrou dois modelos agora é impossível
(`C7`), e essa é a forma da maior parte do que esta ferramenta existe para
fazer: um verde que quer dizer *"eu não olhei"* é a falha que o framework
existe para impedir.

**Onde as ferramentas procuram as coisas.** O dbt 1.10 moveu `meta` para dentro
de `config`, então as duas grafias são lidas. Se as duas estiverem presentes
para a mesma coisa, isso é erro (saída 2, "ambiguous: defined twice") — a
ferramenta não adivinha qual você quis dizer.

| Coisa | Clássico | dbt 1.10+ |
| --- | --- | --- |
| spec | `models[].meta.spec` | `models[].config.meta.spec` |
| pré-registro | `models[].meta.pre_registration` | `models[].config.meta.pre_registration` |
| marcação de coluna sensível | `columns[].meta.sensitive` | `columns[].config.meta.sensitive` |
| data tests | `tests:` | `data_tests:` |

---

## 8. Tabela de cobertura

Uma linha por regra: a frase do README que ela impõe, a fixture em que a regra
dispara e a fixture em que ela fica calada. O meta-teste **M2** falha se uma
regra não tem linha aqui, ou se uma linha aponta para uma fixture que não existe
ou que não faz o que a linha diz. Toda regra bloqueia, menos as quatro em
`INFO_RULES` — a `I1`, contador de alterações do pré-registro; a `I2`, os
números em si; a `I3`, um filtro num teste que esta branch adiciona; e a `C5`, a
promessa da refatoração numa linha —, que só informam. O README pede que o que elas dizem esteja *visível*, não que pare o
PR, e o **M2** confere isso contra o código-fonte, para que nenhuma das três
ganhe um `BLOCK` em silêncio.

| README | Regra | Fixture em que dispara | Fixture em que fica calada |
| --- | --- | --- | --- |
| §3 Etapa A — "PR não pode avançar sem spec preenchida" | `S1` | `check/marts_no_spec` | `check/spec_ok` |
| §3 Etapa A — os seis campos obrigatórios e o formato deles | `S2` | `check/spec_invalid_tier` | `check/spec_ok` |
| §3 Etapa A — a spec nomeia colunas deste modelo, e uma query de reconciliação que existe | `S3` | `check/sensitive_mismatch` | `check/spec_ok` |
| §3 Etapa A — um arquivo de modelo que nenhum yml declara não tem spec a cobrar | `S4` | `check/sql_without_yml` | `check/spec_ok` |
| §3 Etapa B — o formato do pré-registro | `P1` | `check/prereg_open_interval` | `check/prereg_ok` |
| §3 Etapa B, Regra 6 — intervalos fechados, e as métricas da spec | `P2` | `check/prereg_min_gt_max` | `check/prereg_ok` |
| §2 Regra 2 — "cria um teste de unicidade na primary_key da spec" | `T1` | `check/pk_single_missing` | `check/pk_single_unique` |
| §2 Controle 5B — "Teste removido" | `G1` | `gate/G1_removed_unique` | `gate/G1_ok_test_added` |
| §2 Controle 5B — "Cláusula WHERE ou exclusão adicionada a um teste" | `G2` | `gate/G2_where_added` | `gate/G2_ok_where_removed` |
| §2 Controle 5B — "severity rebaixada (ex: error → warn)" | `G3` | `gate/G3_error_to_warn` | `gate/G3_ok_warn_to_error` |
| §2 Controle 5B — "valor esperado (expect) alterado em teste existente" | `G4` | `gate/G4_expect_changed` | `gate/G4_ok_new_unit_test` |
| §2 Controle 5B — "analyses/reconciliation_* alterado no mesmo PR do modelo" | `G5` | `gate/G5_recon_and_sql_changed` | `gate/G5_ok_recon_only` |
| §2 Controle 5B — "Pin de pacote alterado" | `G6` | `gate/G6_version_bumped` | `gate/G6_ok_untouched` |
| §1 Princípio 1, §3 Etapa A — a spec é decidida antes do código | `G7` | `gate/G7_existing_spec_edited` | `gate/G7_ok_new_spec_untouched` |
| §3 Etapa C — "não pode começar sem um pré-registro válido" | `G8` | `gate/G8_sql_changed_no_prereg` | `gate/G8_ok_prereg_present` |
| §2 Controle 5A, §3 Etapa C Regra 8 — "Não edite paths protegidos" | `G9` | `gate/G9_generic_test_added` | `gate/G9_ok_untouched` |
| §2 Controle 5B — "Teste adicionado que não pode falhar", para um teste singular em `tests/` | `G10` | `gate/G10_singular_born_warn` | `gate/G10_ok_singular_plain` |
| §3 Etapa B — "um contador de alterações é incrementado no PR" | `I1` | `gate/I1_two_edits` | `gate/I1_ok_written_once` |
| §2 Controle 5B — "`WHERE` ou cláusula de exclusão adicionada a um teste", para um teste que esta branch adiciona | `I3` | `gate/I3_new_test_with_where` | `gate/I3_ok_new_test_plain` |
| §3 Etapa A — "os 6 campos precisam ser lidos e aprovados pelo humano antes de qualquer linha de código" | `I4` | `gate/I4_spec_first_written_on_branch` | `gate/I4_ok_spec_from_main` |
| §3 Etapa E passo 3 — o diff e o pré-registro precisam ser legíveis | `C0` | `compare/C0_no_prereg` | `compare/C1_inside` |
| §3 Etapa E passo 3 — "um número está fora do intervalo declarado" | `C1` | `compare/C1_row_delta_above_max` | `compare/C1_inside` |
| §3 Etapa E passo 3 — linhas que existem em produção e não na versão nova | `C2` | `compare/C2_removed_pks_over` | `compare/C1_inside` |
| §3 Etapa E passo 3 — "uma coluna apresenta diferença mas não está em altered_columns" | `C3` | `compare/C3_undeclared_column` | `compare/C1_inside` |
| §3 Etapa E passo 3 — cada métrica contra o intervalo declarado para ela | `C4` | `compare/C4_metric_outside` | `compare/C1_inside` |
| §3 Etapa E passo 3 — "o tipo é refactoring mas algum delta não é zero", numa linha | `C5` | `compare/C5_refactoring_nonzero` | `compare/C1_inside` |
| §3 Etapa E passo 4 — "se a diferença for maior que a tolerância, o PR é bloqueado" | `C6` | `compare/C6_over` | `compare/C6_ok_within` |
| §3 Etapa E passo 3 — todo modelo pré-registrado é comparado, não só aqueles cujos números apareceram | `C7` | `compare/C7_prereg_without_diff` | `compare/C1_inside` |
| §3 Etapa E passo 5 — "O pré-registro é estreito o suficiente para poder falhar? A razão justifica o intervalo?" | `I2` | `compare/C1_inside` | `compare/C0_no_prereg` |

---

## 9. O que a v0 não faz

Tudo abaixo faz parte do framework e **não** é imposto por estas ferramentas.
Parte é imposta pelas configurações da sua plataforma, parte é regra para
humanos, e parte simplesmente ainda não foi construída. Saber qual é qual é o
ponto desta lista.

| Não é imposto aqui | Por quê, e o que fazer a respeito |
| --- | --- |
| A tranca em si: roles do warehouse, masking, limites de gasto, perfis estatísticos | Os Controles 1 a 4 são configuração de plataforma, não script. `REVOKE USAGE ON SCHEMA raw` é o controle; nenhum Python substitui isso. README §2. |
| O teste de contagem mínima da Regra 2 | O nome do teste varia por time (`dbt_utils.expression_is_true`, um teste singular, um pacote). Adicione o nome você mesmo, perto de `ACCEPTED_PK_TESTS`, ou peça numa issue. README §2 Regra 2. |
| Gerar o perfil estatístico do Controle 4 | Ele lê o warehouse. Gere num job agendado e proteja `docs/profile/` com CODEOWNERS. README §2 Controle 4. |
| Ciclo de vida dos datasets: dropar os schemas `ci_pr_<n>_full` | Faxina de warehouse. Um job agendado, não um gate. README §3 Etapa E. |
| "O pré-registro é imutável a partir do momento em que a etapa D começa" | Isso exige estado fora do git — o CI precisa lembrar quando rodou pela primeira vez. O `gate` conta as alterações e imprime a contagem (`I1`), que é o que o README pede que o Autor veja. README §3 Etapa B. |
| Rodar a query de reconciliação | Ela lê o warehouse com dado completo. Seu CI roda e escreve os dois números no `diff.json`; o `compare` lê (`C6`). README §3 Etapa E passo 4. |
| Produzir o diff | É específico do warehouse. Recce, dbt-audit-helper ou o seu SQL; as ferramentas exigem o formato, não o método. README §3 Etapa E passo 2. |
| Um modelo alterado só no yml, de um jeito que move números | A `G8` pede pré-registro quando o `.sql` de um modelo muda, porque a Etapa B amarra o intervalo a escrever código. Uma materialização trocada, um `config` editado, um `+where` posto só no yml podem mover números com o `.sql` intocado, e a `G8` não vai pedir. README §3 Etapa B. |
| Um schema yml escrito com jinja | O dbt renderiza yml com jinja antes de ler; estas ferramentas usam um parser YAML puro. Um `{% for %}` que gera entradas de modelo, ou um `{{ ... }}` sem aspas num valor, é ilegível aqui, e um arquivo ilegível é exit 2 para a rodada inteira — fail closed, mas a rodada fica parada até o arquivo mudar. A mensagem diz que a causa é jinja, para o leitor não caçar um typo que não existe. Mantenha yml gerado fora dos caminhos de marts, ou renderize num passo de pre-commit. README §3 Etapa A. |
| `compare` sem `--base` | Ele não consegue distinguir um pré-registro escrito para este pull request de um que a `main` já tinha, então todos os do projeto contam como deste PR: a `C7` pede diff de todo modelo pré-registrado, e um herdado é comparado em vez de recusado. Mais estrito, nunca mais frouxo — mas uma rodada local pode bloquear por um modelo em que você nunca tocou. Passe `--base`, como o `templates/ci.yml` faz. README §3 Etapa B. |
| O `gate` não confere se o `--marts-path` existe | O `check` e o `compare` leem o diretório do projeto, então um caminho que não é diretório é exit 2 — "nothing to check is not OK". O `gate` lê o git e nunca olha, então `gate --marts-path models/martz` percorre a branch, não acha yml de modelo nenhum e imprime `OK`. Um typo num dos dois lugares em que a flag é escrita — o workflow de CI e o `AGENTS.md` pedem que sejam idênticos — vira um rebaixamento silencioso em vez de um erro. Até ser corrigido, mantenha a flag num lugar só e copie. README §3 Etapa A. |
| Um projeto dbt que não está na raiz do repositório git | O `gate` pede caminhos ao `git ls-tree` e depois o conteúdo ao `git cat-file`; o primeiro responde relativo ao diretório atual e o segundo lê a partir da raiz do repositório, então, num subdiretório `dbt/`, toda leitura falha e o comando é exit 2. Fail closed, então não é aprovação silenciosa — mas o `gate` simplesmente não roda nesse layout, e o `--project-dir` não salva. O `spec.reconciliation_query` e a entrada de `analyses/` no `CODEOWNERS` discordam sobre a raiz no mesmo layout. README §2 Controle 5B. |
| A `T1` recusa um teste de unicidade *mais forte* que a primary key | O `unique_combination_of_columns` aceito precisa nomear exatamente a `primary_key` da spec. Um `unique` numa das colunas de uma chave de duas é uma afirmação mais estrita e ainda assim se lê como "no uniqueness test on primary key". Acrescente a forma que você usa a `ACCEPTED_PK_TESTS`, ou escreva também o teste que a regra pede. README §2 Regra 2. |
| O que uma mudança no `dbt_project.yml` ou numa macro *faz* | A `G9` bloqueia qualquer mudança no `dbt_project.yml` ou em `macros/` na branch, então `data_tests: {+severity: warn}` não entra num pull request do agente sem ser visto. O gate continua não lendo nenhum dos dois: um pull request humano que mude um deles é do CODEOWNERS julgar, e não será o gate a dizer o que a mudança faz com os testes. README §2 Controle 5B, Regra 3. |
| Uma spec **apagada** | A `G7` dispara quando uma spec *muda*; uma spec removida por inteiro não aciona regra nenhuma do `gate`, e o `check` pega só o sintoma (`S1`, "model has no meta.spec"), que se lê como um modelo que nunca teve uma. Um pré-registro apagado junto com uma mudança no modelo agora é `G8`; um apagado sozinho, com o modelo intocado, ainda não aciona nada. README §3 Etapa A, Etapa B. |
| Evasão da `G7`, da `I1` e da `I4` pelo formato do histórico | As três regras leem o histórico da branch, então as três dependem do formato dele. A caminhada usa `--first-parent`, que pula trabalho feito numa branch lateral e mesclado: uma spec criada *e* editada dentro de uma branch dessas passa pela `G7`, e a contagem da `I1` fica subestimada. Um histórico reescrito é pior, e é o que agentes fazem por hábito: `commit --amend`, um rebase, um squash apagam os commits intermediários de vez, então, para uma spec escrita pela primeira vez na branch, a `G7` não tem contra o que comparar, a `I1` reporta zero e a `I4` aponta para o commit reescrito. Mesmo conteúdo, três veredictos conforme a topologia, o que combina mal com o Princípio 3. Nada do que o gate consegue ler avisa que um histórico foi reescrito, então a trava precisa avisar: o README §2 Controle 1 agora pede que force-push seja bloqueado em toda branch, o que é um ruleset. Com ele, preserve os commits do pull request e leia a `I1` como piso; sem ele, `G7`, `I1` e `I4` são consultivas. Uma spec que já existia na `main` está segura de qualquer jeito, porque é o merge-base que a `G7` usa. README §3 Etapa B. |
| Cada edge da spec virar um unit test (Regra 2) | Os `known_edges` da spec são validados como texto e nada confere que cada um virou um unit test com fixture sintética. Uma spec com cinco edges e nenhum unit test passa no `check`. README §2 Regra 2. |
| Se uma tolerância ou uma âncora conseguem falhar | `reconciliation_tolerance: "999%"` e `external_validation: "TODO"` satisfazem o schema. O mesmo argumento que o schema do pré-registro faz sobre intervalos abertos vale para eles; o schema ainda não faz esse argumento. README §3 Etapa A. |
| Detectar dado real em fixtures (Regra 7) | Estas ferramentas só verificam as próprias fixtures (meta-teste M6). Para o seu repositório use gitleaks com regras para e-mail e CPF, como o README §3 Etapa D descreve. |
| Modo identidade de bot: julgar só os commits do agente | Não existe identidade de bot para configurar, e autor de commit é texto que qualquer um escreve. O gate julga o PR inteiro; veja [Escopo do gate](#gate). |
| O hook `PreToolUse` que recusa escrita em paths protegidos | É específico do agente e opcional. README §2 Controle 5B, "Opcional (camada extra de proteção)". |
| Julgar linguagem natural: se um grain é *bom*, se um motivo justifica um intervalo | Princípio 3: um LLM nunca é o juiz final. Isso são as três leituras do humano na Etapa E, passo 5. |

---

## 10. Como contribuir

- **Uma regra por pull request.** Uma regra é uma função, uma docstring que
  começa pela frase do README que ela impõe, um id de regra, uma fixture que
  bloqueia, uma fixture que passa e uma linha na tabela de cobertura. Os
  meta-testes falham se você esquecer uma das três últimas.
- **README primeiro.** Estas ferramentas só podem impor algo que o README do
  framework diz. Se a sua regra precisa que o README mude, abra uma issue de
  *Framework improvement* e mude o README antes. Sem frase, sem regra.
- **Fixtures são sintéticas.** Só dado inventado. E-mails terminam em
  `@example.com`; CPFs inventados precisam falhar o próprio dígito verificador.
  O meta-teste M6 confere, e o checklist de PR do repositório proíbe dado real
  de qualquer forma.
- **As duas línguas.** `tools/README.md` e `tools/README.pt-br.md` são o mesmo
  documento. Se você muda a substância de um, mude o outro, ou diga no PR que
  não conseguiu.
- **Um arquivo.** Toda a lógica mora no `slp.py`, e o meta-teste **M8** o limita
  em três lugares: a **maquinaria compartilhada** de que toda regra depende,
  **cada regra** isolada, e o arquivo inteiro como travessão largo. O que ele
  conta são as linhas que precisam ser *entendidas* — código, sem linhas em
  branco, comentários e docstrings — porque, sob um limite que conta prosa, o
  jeito mais barato de ganhar espaço é apagar a explicação que torna o arquivo
  legível.

  Antes era um número só, e esse número deixou de medir a promessa para a qual
  foi escrito. Ninguém lê vinte e quatro regras de uma vez; lê-se a maquinaria
  uma vez e depois uma regra por vez. Sob um limite único, cada regra competia
  com todas as outras, então ele tinha virado em silêncio um limite de
  *quantidade de regras* vestido de limite de legibilidade — e, na primeira vez
  em que a correção precisou de espaço, a única saída honesta que ele oferecia
  era apagar um portão. Separado, a pressão fica onde deve: maquinaria
  compartilhada é o que todo mundo paga, e uma regra longa demais para ser lida
  sozinha são duas regras, com dois ids e dois fixtures. Os números são medidos
  de novo a cada release; um deles só sobe quando o pull request diz o que foi
  comprado com ele.

Veja o [CONTRIBUTING.md](../CONTRIBUTING.md) e os templates de issue em
`.github/ISSUE_TEMPLATE/`.
