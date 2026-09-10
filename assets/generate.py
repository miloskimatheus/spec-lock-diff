#!/usr/bin/env python3
"""Generate every Spec-Lock-Diff README drawing, per theme and per language.

GitHub serves an <img src="*.svg"> as its own document, so it cannot inherit the
page's colours and cannot load a webfont. Every colour is therefore a literal and
every typeface a system stack, and each drawing ships as a light/dark pair that
<picture> switches on prefers-color-scheme.
"""

import io
import os

# Beside this file, so a clone can regenerate the drawings without editing it.
OUT = os.path.dirname(os.path.abspath(__file__))

MONO = '"SFMono-Regular",Menlo,Consolas,"Liberation Mono",monospace'

THEMES = {
    "light": dict(ink="#1f2328", muted="#59636e", faint="#8b949e",
                  pas="#0F6B4F", blk="#A3231A", amb="#8A5A0B",
                  hum="#0B62B8", mac="#A03BB0",
                  c1="#1F4E79", c2="#146B5E", c3="#8A5A0B", c4="#6B4E9E", c5="#8C3357"),
    "dark":  dict(ink="#e6edf3", muted="#8b949e", faint="#6e7681",
                  pas="#4FBE8F", blk="#E58174", amb="#D9A441",
                  hum="#6FB6F5", mac="#DE93EC",
                  c1="#7EA9D6", c2="#4FBBA6", c3="#D9A441", c4="#B9A2E8", c5="#E08BA8"),
}

# Mid-tones for the small heading icons: legible on white and on #0d1117 alike.
ICON = dict(c1="#4E86C7", c2="#2E9E88", c3="#B98420", c4="#9B82D4", c5="#C2607F")

L = {
    "en": {
        "risk1a": "wrong results", "risk1b": "that look right",
        "risk2a": "leakage of", "risk2b": "sensitive data",
        "risk3a": "unexpected", "risk3b": "financial costs",
        "risks_alt": "Three risks: wrong results that look right, leakage of sensitive data, unexpected financial costs",

        "platform": "PLATFORM",
        "plat1": "prepare and protect the ecosystem",
        "plat2": "before releasing the agent inside it",
        "agent": "AGENT", "agent_sub": "pre-registration · code · tests",
        "human": "HUMAN", "author": "Author", "author_or": "Author or Partner",
        "writes": "writes the spec", "reads": "reads the diff",
        "roles_alt": "A human writes the spec, the agent runs inside an enclosure built by the Platform, a human reads the diff",

        "p1a": "In SQL, a bug returns a", "p1b": "plausible wrong number",
        "p2a": "Limits must live in", "p2b": "the infrastructure",
        "p3a": "Checks must be", "p3b": "deterministic",
        "e1": "DECIDE BEFORE · CHECK AFTER", "e2": "CONTROLS, NOT INSTRUCTIONS",
        "e3": "GATES THAT NEVER VARY",
        "framework": "THE FRAMEWORK",
        "from1": "from 1", "from2": "from 2", "from13": "from 1 + 3",
        "mani_alt": "The three principles feed the framework: principle 1 shapes Spec and Diff, principle 2 shapes Lock, principle 3 shapes Diff",

        "stops": "STOPS",
        "ct1": "Identity", "cs1": "own role, own bot",
        "cw1": ["if the agent tries", "to act with your", "access"],
        "ct2": "Data access", "cs2": "no raw, masked marts",
        "cw2": ["if sensitive data", "would reach code,", "tests or the LLM"],
        "ct3": "Spending caps", "cs3": "daily cap → suspend",
        "cw3": ["if a runaway query", "starts draining", "the budget"],
        "ct4": "Profiles", "cs4": "statistics, not rows",
        "cw4": ["if the agent would", "ever see a real", "customer row"],
        "ct5": "Protected paths", "cs5": "CODEOWNERS + gate",
        "cw5": ["if the agent tries", "to weaken the tests", "that judge it"],
        "ctrl_alt": "The five controls and what each one stops",

        "perm_title": "AGENT PERMISSION, BY DATA LAYER",
        "layer1": "raw", "layer1s": "no access",
        "layer2": "staging + marts", "layer2s": "read, masked",
        "layer3": "production", "layer3s": "no write",
        "layer4": "ci_pr_&lt;n&gt;", "layer4s": "read + write",
        "perm_alt": "Agent permission by data layer: no access to raw, masked read on staging and marts, no write to production, read and write in its own PR schema",

        "locked": "LOCKED BY THE PLATFORM",
        "sA": "Spec", "sB": "Pre-registration", "sC": "Code",
        "sD": "Automatic CI", "sE": "Diff + human review",
        "decides": "the human decides", "onlyreads": "the human only reads",
        "bA": ["no spec,", "no advance"], "bC": ["needs a valid", "pre-registration"],
        "bD": ["any failure", "blocks"], "bE": ["outside the interval,", "or off tolerance"],
        "canstop": "THESE TWO CAN STOP THE MERGE",
        "proc_alt": "Stage A is human, stages B C and D run locked inside the platform, stage E returns to a human who only reads the automated diff",

        "cmds_head": "WHICH COMMAND RUNS WHEN",
        "q_check": "is there a spec, and can its test fail?",
        "q_gate": "did this branch weaken anything that judges the code?",
        "q_compare": "do the numbers match what was promised?",
        "cmds_alt": "check runs at stages A, C and D; gate at stages C and D; compare at stage E",

        "prereg_head": "DECLARED IN STAGE B, BEFORE ANY CODE WAS WRITTEN",
        "band_ok": "DECLARED INTERVAL — WOULD PASS",
        "measured": "measured by the diff: 15000",
        "minlbl": "min 0", "maxlbl": "max 12000",
        "blocked": "PR BLOCKED",
        "why1": "The number landed outside the interval",
        "why2": "the agent committed to — so the merge stops.",
        "prereg_alt": "The agent declared a row delta between 0 and 12000 before writing code; the diff measured 15000, outside the band, so the PR is blocked",

        "diff_head": "DIFF  fct_orders   prod → pr-142",
        "diff_by": "GENERATED BY CI · DETERMINISTIC",
        "diff_win": "event_time window identical on both sides",
        "d_out": "✗ outside {min 0, max 12000}",
        "d_in1": "✓ within {0.0, 0.8}", "d_in2": "✓ within {max 0}",
        "diff_why": "row_count left the interval the agent declared in stage B.",
        "diff_alt": "Automated diff output comparing production to the pull request, each number checked against its pre-registered interval, ending in PR blocked",
    },
    "pt": {
        "risk1a": "resultados errados", "risk1b": "que parecem certos",
        "risk2a": "vazamento de", "risk2b": "dados sensíveis",
        "risk3a": "custos financeiros", "risk3b": "inesperados",
        "risks_alt": "Três riscos: resultados errados que parecem certos, vazamento de dados sensíveis, custos financeiros inesperados",

        "platform": "PLATAFORMA",
        "plat1": "prepara e protege o ecossistema",
        "plat2": "antes de soltar o agente dentro dele",
        "agent": "AGENTE", "agent_sub": "pré-registro · código · testes",
        "human": "HUMANO", "author": "Autor", "author_or": "Autor ou Parceiro",
        "writes": "escreve a spec", "reads": "lê o diff",
        "roles_alt": "Um humano escreve a spec, o agente roda dentro de um cercado construído pela Plataforma, um humano lê o diff",

        "p1a": "Em SQL, bug devolve", "p1b": "número plausível errado",
        "p2a": "Limites devem viver na", "p2b": "infraestrutura",
        "p3a": "Verificações devem ser", "p3b": "determinísticas",
        "e1": "DECIDE ANTES · CONFERE DEPOIS", "e2": "CONTROLES, NÃO INSTRUÇÕES",
        "e3": "GATES QUE NUNCA VARIAM",
        "framework": "O FRAMEWORK",
        "from1": "do 1", "from2": "do 2", "from13": "do 1 + 3",
        "mani_alt": "Os três princípios alimentam o framework: o princípio 1 molda Spec e Diff, o 2 molda Lock, o 3 molda Diff",

        "stops": "BLOQUEIA",
        "ct1": "Identidade", "cs1": "role própria, bot próprio",
        "cw1": ["se o agente tentar", "agir com o seu", "acesso"],
        "ct2": "Acesso a dados", "cs2": "sem raw, marts mascarados",
        "cw2": ["se dado sensível", "for chegar no código,", "testes ou no LLM"],
        "ct3": "Tetos de gasto", "cs3": "teto diário → desliga",
        "cw3": ["se uma query solta", "começar a drenar", "o orçamento"],
        "ct4": "Perfis", "cs4": "estatística, não linhas",
        "cw4": ["se o agente fosse", "ver uma linha real", "de cliente"],
        "ct5": "Paths protegidos", "cs5": "CODEOWNERS + gate",
        "cw5": ["se o agente tentar", "enfraquecer os testes", "que o julgam"],
        "ctrl_alt": "Os cinco controles e o que cada um bloqueia",

        "perm_title": "PERMISSÃO DO AGENTE, POR CAMADA DE DADOS",
        "layer1": "raw", "layer1s": "nenhum acesso",
        "layer2": "staging + marts", "layer2s": "leitura mascarada",
        "layer3": "produção", "layer3s": "sem escrita",
        "layer4": "ci_pr_&lt;n&gt;", "layer4s": "leitura + escrita",
        "perm_alt": "Permissão do agente por camada: nenhum acesso a raw, leitura mascarada em staging e marts, sem escrita em produção, leitura e escrita no schema do próprio PR",

        "locked": "TRANCADO PELA PLATAFORMA",
        "sA": "Spec", "sB": "Pré-registro", "sC": "Código",
        "sD": "CI automático", "sE": "Diff + review humano",
        "decides": "o humano decide", "onlyreads": "o humano só lê",
        "bA": ["sem spec,", "não avança"], "bC": ["exige pré-registro", "válido"],
        "bD": ["qualquer falha", "bloqueia"], "bE": ["fora do intervalo,", "ou da tolerância"],
        "canstop": "ESTES DOIS PODEM PARAR O MERGE",
        "proc_alt": "A etapa A é humana, as etapas B C e D rodam trancadas dentro da plataforma, a etapa E volta para um humano que apenas lê o diff automático",

        "cmds_head": "QUAL COMANDO RODA QUANDO",
        "q_check": "existe spec, e o teste dela pode falhar?",
        "q_gate": "este branch enfraqueceu algo que julga o código?",
        "q_compare": "os números batem com o que foi prometido?",
        "cmds_alt": "check roda nas etapas A, C e D; gate nas etapas C e D; compare na etapa E",

        "prereg_head": "DECLARADO NA ETAPA B, ANTES DE QUALQUER CÓDIGO",
        "band_ok": "INTERVALO DECLARADO — PASSARIA",
        "measured": "medido pelo diff: 15000",
        "minlbl": "min 0", "maxlbl": "max 12000",
        "blocked": "PR BLOQUEADO",
        "why1": "O número caiu fora do intervalo com que",
        "why2": "o agente se comprometeu — o merge para.",
        "prereg_alt": "O agente declarou um delta de linhas entre 0 e 12000 antes de escrever código; o diff mediu 15000, fora da faixa, então o PR é bloqueado",

        "diff_head": "DIFF  fct_orders   prod → pr-142",
        "diff_by": "GERADO PELO CI · DETERMINÍSTICO",
        "diff_win": "janela de event_time idêntica nos dois lados",
        "d_out": "✗ fora de {min 0, max 12000}",
        "d_in1": "✓ dentro de {0.0, 0.8}", "d_in2": "✓ dentro de {max 0}",
        "diff_why": "row_count saiu do intervalo declarado pelo agente na etapa B.",
        "diff_alt": "Saída automática do diff comparando produção com o pull request, cada número conferido contra seu intervalo pré-registrado, terminando em PR bloqueado",
    },
}


def svg(w, h, alt, body):
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" '
        f'width="{w}" height="{h}" role="img" aria-label="{alt}" '
        f'font-family=\'{MONO}\'>\n<title>{alt}</title>\n{body}\n</svg>\n'
    )


# ── wordmark ────────────────────────────────────────────────────────────────
def wordmark(t, _):
    i = t["ink"]
    return svg(660, 120, "Spec · Lock · Diff", f'''
<g stroke="{i}" fill="none" stroke-width="1.4" opacity=".85"><path d="M0 22h660M0 98h660"/></g>
<g stroke="{i}" fill="none" stroke-width="1" stroke-dasharray="2 3" opacity=".42"><path d="M179 22v76M330 22v76M482 22v76"/></g>
<g stroke="{i}" fill="none" stroke-width="1.4" opacity=".85">
<path d="M173 16v12M185 16v12M324 16v12M336 16v12M476 16v12M488 16v12"/>
<path d="M173 92v12M185 92v12M324 92v12M336 92v12M476 92v12M488 92v12"/></g>
<text x="330" y="70" text-anchor="middle" font-size="36" font-weight="600" letter-spacing="-.5" fill="{i}">SPEC · LOCK · DIFF</text>''')


# ── the three risks ─────────────────────────────────────────────────────────
def risks(t, s):
    i, b = t["ink"], t["blk"]
    cols = [(1, 26, 233, "i.", s["risk1a"], s["risk1b"]),
            (323, 348, 555, "ii.", s["risk2a"], s["risk2b"]),
            (645, 670, 877, "iii.", s["risk3a"], s["risk3b"])]
    icons = [
        'M2 20l7 7 15-17" stroke-linecap="round" stroke-linejoin="round"/><path d="M0 33h30" stroke-dasharray="3 3',
        'M1 15s6-10 14-10 14 10 14 10-6 10-14 10S1 15 1 15z"/><circle cx="15" cy="15" r="4" fill="none"/><path d="M3 30L27 2" stroke-linecap="round',
        'M1 30L10 18l7 7L29 2" stroke-linecap="round" stroke-linejoin="round"/><path d="M22 2h7v7" stroke-linecap="round" stroke-linejoin="round',
    ]
    out = []
    for n, (bx, tx, ix, num, a, bb) in enumerate(cols):
        out.append(f'<rect x="{bx}" y="1" width="294" height="160" fill="none" stroke="{b}" stroke-width="1.6"/>')
        out.append(f'<text x="{tx}" y="44" font-size="16" font-weight="600" fill="{b}">{num}</text>')
        out.append(f'<g transform="translate({ix} 25)" stroke="{b}" stroke-width="2.2" fill="none"><path d="{icons[n]}"/></g>')
        out.append(f'<text x="{tx}" y="106" font-size="21" font-weight="600" fill="{i}">{a}</text>')
        out.append(f'<text x="{tx}" y="136" font-size="21" font-weight="600" fill="{i}">{bb}</text>')
    return svg(942, 162, s["risks_alt"], "\n".join(out))


# ── roles: human -> platform[agent] -> human ────────────────────────────────
def roles(t, s):
    i, h, m = t["ink"], t["hum"], t["mac"]
    return svg(942, 208, s["roles_alt"], f'''
<rect x="317" y="14" width="308" height="180" fill="none" stroke="{i}" stroke-width="2" opacity=".8"/>
<text x="471" y="40" text-anchor="middle" font-size="10" letter-spacing="2" fill="{i}" opacity=".55">{s["platform"]}</text>
<text x="471" y="60" text-anchor="middle" font-size="10.5" fill="{i}" opacity=".72">{s["plat1"]}</text>
<text x="471" y="76" text-anchor="middle" font-size="10.5" fill="{i}" opacity=".72">{s["plat2"]}</text>

<rect x="347" y="94" width="248" height="84" fill="none" stroke="{m}" stroke-width="1.8" stroke-dasharray="5 3"/>
<text x="471" y="132" text-anchor="middle" font-size="19" font-weight="600" letter-spacing="1.4" fill="{m}">{s["agent"]}</text>
<text x="471" y="158" text-anchor="middle" font-size="10.5" fill="{m}" opacity=".85">{s["agent_sub"]}</text>

<g fill="none" stroke="{h}" stroke-width="2">
<rect x="1" y="76" width="256" height="84"/><rect x="685" y="76" width="256" height="84"/>
<path d="M273 118h28M641 118h28"/><path d="M293 113l8 5-8 5M661 113l8 5-8 5"/></g>

<text x="129" y="108" text-anchor="middle" font-size="19" font-weight="600" letter-spacing="1.4" fill="{h}">{s["human"]}</text>
<text x="129" y="131" text-anchor="middle" font-size="13" fill="{h}">{s["author"]}</text>
<text x="129" y="150" text-anchor="middle" font-size="10.5" fill="{h}" opacity=".8">{s["writes"]}</text>
<text x="813" y="108" text-anchor="middle" font-size="19" font-weight="600" letter-spacing="1.4" fill="{h}">{s["human"]}</text>
<text x="813" y="131" text-anchor="middle" font-size="13" fill="{h}">{s["author_or"]}</text>
<text x="813" y="150" text-anchor="middle" font-size="10.5" fill="{h}" opacity=".8">{s["reads"]}</text>''')


# ── manifesto network ───────────────────────────────────────────────────────
def manifesto(t, s):
    i = t["ink"]
    return svg(942, 430, s["mani_alt"], f'''
<defs><marker id="a" viewBox="0 0 9 9" refX="8" refY="4.5" markerWidth="8" markerHeight="8" orient="auto">
<path d="M0 0 L9 4.5 L0 9 z" fill="{i}"/></marker></defs>

<g fill="none" stroke="{i}" stroke-width="1.6" opacity=".7">
<rect x="9" y="7" width="286" height="86"/><rect x="647" y="7" width="286" height="86"/>
<rect x="328" y="338" width="286" height="86"/></g>

<text x="34" y="62" font-size="34" font-weight="600" fill="{i}" opacity=".28">1</text>
<text x="80" y="46" font-size="12.5" font-weight="600" fill="{i}">{s["p1a"]}</text>
<text x="80" y="66" font-size="12.5" font-weight="600" fill="{i}">{s["p1b"]}</text>
<text x="672" y="62" font-size="34" font-weight="600" fill="{i}" opacity=".28">2</text>
<text x="718" y="46" font-size="12.5" font-weight="600" fill="{i}">{s["p2a"]}</text>
<text x="718" y="66" font-size="12.5" font-weight="600" fill="{i}">{s["p2b"]}</text>
<text x="353" y="393" font-size="34" font-weight="600" fill="{i}" opacity=".28">3</text>
<text x="399" y="377" font-size="12.5" font-weight="600" fill="{i}">{s["p3a"]}</text>
<text x="399" y="397" font-size="12.5" font-weight="600" fill="{i}">{s["p3b"]}</text>

<text x="152" y="117" text-anchor="middle" font-size="10" letter-spacing="1.2" fill="{i}" opacity=".55">{s["e1"]}</text>
<text x="790" y="117" text-anchor="middle" font-size="10" letter-spacing="1.2" fill="{i}" opacity=".55">{s["e2"]}</text>
<text x="471" y="326" text-anchor="middle" font-size="10" letter-spacing="1.2" fill="{i}" opacity=".55">{s["e3"]}</text>

<g fill="none" stroke="{i}" stroke-width="1.5" opacity=".55" marker-end="url(#a)">
<path d="M152 128 L325 164"/><path d="M790 128 L617 164"/><path d="M471 306 L471 264"/></g>

<rect x="331" y="152" width="280" height="104" fill="none" stroke="{i}" stroke-width="2.2"/>
<path d="M331 186h280" stroke="{i}" stroke-width="1.4" opacity=".55" fill="none"/>
<path d="M424 186v70M517 186v70" stroke="{i}" stroke-width="1" opacity=".4" fill="none"/>
<text x="471" y="175" text-anchor="middle" font-size="10.5" letter-spacing="2.4" fill="{i}" opacity=".6">{s["framework"]}</text>
<g text-anchor="middle" fill="{i}" font-size="14" font-weight="600">
<text x="377" y="215">SPEC</text><text x="470" y="215">LOCK</text><text x="563" y="215">DIFF</text></g>
<g text-anchor="middle" fill="{i}" opacity=".5" font-size="10">
<text x="377" y="238">{s["from1"]}</text><text x="470" y="238">{s["from2"]}</text><text x="563" y="238">{s["from13"]}</text></g>''')


# ── the five controls ───────────────────────────────────────────────────────
CTRL_ICONS = [
    '<circle cx="9" cy="9" r="7"/><path d="M14 14l11 11M21 21l4 4M25 17l4 4" stroke-linecap="round"/>',
    '<path d="M1 11s5-9 13-9 13 9 13 9-5 9-13 9S1 11 1 11z"/><circle cx="14" cy="11" r="3.5"/><path d="M3 23L25 -1" stroke-linecap="round"/>',
    '<path d="M2 22a12 12 0 1 1 24 0" stroke-linecap="round"/><path d="M14 22l8-8" stroke-linecap="round"/><path d="M0 26h28" stroke-linecap="round"/>',
    '<path d="M0 24h28" stroke-linecap="round"/><path d="M4 24V13M11 24V2M18 24V16M25 24V8" stroke-linecap="round"/>',
    '<path d="M14 1l12 4.6v8.2C26 20 21 24.6 14 26.4 7 24.6 2 20 2 13.8V5.6z"/><path d="M8.4 13.6l3.8 3.8 7.4-7.4" stroke-linecap="round" stroke-linejoin="round"/>',
]


def controls(t, s):
    i = t["ink"]
    out = []
    for n in range(5):
        x = 1 + n * 192
        col = t[f"c{n+1}"]
        tx = x + 20
        iy = 22 if n in (0, 4) else (24 if n in (1, 2) else 26)
        out.append(f'<rect x="{x}" y="1" width="172" height="216" fill="none" stroke="{col}" stroke-width="1.6"/>')
        out.append(f'<g transform="translate({tx} {iy})" fill="none" stroke="{col}" stroke-width="1.8">{CTRL_ICONS[n]}</g>')
        out.append(f'<text x="{x+152}" y="42" text-anchor="end" font-size="26" font-weight="600" fill="{col}" opacity=".32">{n+1}</text>')
        out.append(f'<text x="{tx}" y="94" font-size="13" font-weight="600" fill="{i}">{s[f"ct{n+1}"]}</text>')
        out.append(f'<text x="{tx}" y="112" font-size="10" fill="{i}" opacity=".6">{s[f"cs{n+1}"]}</text>')
        out.append(f'<path d="M{tx} 132h132" stroke="{col}" stroke-width="1" opacity=".5" fill="none"/>')
        out.append(f'<text x="{tx}" y="153" font-size="10" letter-spacing="1.6" font-weight="600" fill="{col}">{s["stops"]}</text>')
        for k, line in enumerate(s[f"cw{n+1}"]):
            out.append(f'<text x="{tx}" y="{176 + k*16}" font-size="10" fill="{i}" opacity=".78">{line}</text>')
    return svg(942, 218, s["ctrl_alt"], "\n".join(out))


# ── agent permission by data layer ──────────────────────────────────────────
def permissions(t, s):
    i, p, b, a = t["ink"], t["pas"], t["blk"], t["amb"]
    return svg(942, 178, s["perm_alt"], f'''
<text x="471" y="13" text-anchor="middle" font-size="9.5" letter-spacing="2.2" fill="{i}" opacity=".5">{s["perm_title"]}</text>
<rect x="371" y="25" width="200" height="36" fill="none" stroke="{i}" stroke-width="1.4" opacity=".75"/>
<text x="471" y="48" text-anchor="middle" font-size="12.5" font-weight="600" fill="{i}">agent_ci</text>
<g fill="none" stroke="{i}" stroke-width="1.25" opacity=".5"><path d="M471 61v16M119 77h704M119 77v14M354 77v14M589 77v14M823 77v14"/></g>

<circle cx="119" cy="111" r="15" fill="none" stroke="{b}" stroke-width="2"/>
<path d="M113 105l12 12M125 105l-12 12" fill="none" stroke="{b}" stroke-width="2.2" stroke-linecap="round"/>
<circle cx="354" cy="111" r="15" fill="none" stroke="{a}" stroke-width="2"/>
<path d="M354 96a15 15 0 0 1 0 30z" fill="{a}"/>
<circle cx="589" cy="111" r="15" fill="none" stroke="{b}" stroke-width="2"/>
<path d="M583 105l12 12M595 105l-12 12" fill="none" stroke="{b}" stroke-width="2.2" stroke-linecap="round"/>
<circle cx="823" cy="111" r="15" fill="none" stroke="{p}" stroke-width="2"/>
<path d="M816 111.5l5 5 9-9.5" fill="none" stroke="{p}" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/>

<g font-size="12.5" font-weight="600" text-anchor="middle" fill="{i}">
<text x="119" y="153">{s["layer1"]}</text><text x="354" y="153">{s["layer2"]}</text>
<text x="589" y="153">{s["layer3"]}</text><text x="823" y="153">{s["layer4"]}</text></g>
<g font-size="11" text-anchor="middle" fill="{i}" opacity=".62">
<text x="119" y="171">{s["layer1s"]}</text><text x="354" y="171">{s["layer2s"]}</text>
<text x="589" y="171">{s["layer3s"]}</text><text x="823" y="171">{s["layer4s"]}</text></g>''')


# ── the development process, A -> E ─────────────────────────────────────────
def process(t, s):
    i, h, m, b = t["ink"], t["hum"], t["mac"], t["blk"]
    return svg(942, 250, s["proc_alt"], f'''
<defs><marker id="p" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="7" markerHeight="7" orient="auto">
<path d="M0 0 L8 4 L0 8 z" fill="{i}" fill-opacity=".5"/></marker></defs>

<rect x="191" y="7" width="516" height="146" fill="none" stroke="{i}" stroke-width="2" opacity=".75"/>
<text x="449" y="27" text-anchor="middle" font-size="10" letter-spacing="2" fill="{i}" opacity=".6">{s["locked"]}</text>

<g fill="none" stroke="{h}" stroke-width="2.2"><rect x="1" y="45" width="146" height="66"/><rect x="751" y="45" width="190" height="66"/></g>
<text x="74" y="77" text-anchor="middle" font-size="22" font-weight="600" fill="{h}">A</text>
<text x="74" y="99" text-anchor="middle" font-size="11.5" fill="{h}">{s["sA"]}</text>
<text x="846" y="77" text-anchor="middle" font-size="22" font-weight="600" fill="{h}">E</text>
<text x="846" y="99" text-anchor="middle" font-size="11.5" fill="{h}">{s["sE"]}</text>

<g fill="none" stroke="{m}" stroke-width="2" stroke-dasharray="5 3">
<rect x="207" y="45" width="144" height="66"/><rect x="377" y="45" width="144" height="66"/><rect x="547" y="45" width="144" height="66"/></g>
<g text-anchor="middle" fill="{m}">
<text x="279" y="77" font-size="22" font-weight="600">B</text><text x="449" y="77" font-size="22" font-weight="600">C</text>
<text x="619" y="77" font-size="22" font-weight="600">D</text>
<text x="279" y="99" font-size="11.5">{s["sB"]}</text><text x="449" y="99" font-size="11.5">{s["sC"]}</text>
<text x="619" y="99" font-size="11.5">{s["sD"]}</text></g>

<g fill="none" stroke="{i}" stroke-width="1.4" opacity=".5" marker-end="url(#p)">
<path d="M157 78h24"/><path d="M357 78h14"/><path d="M527 78h14"/><path d="M717 78h24"/></g>

<g fill="none" stroke="{h}" stroke-width="1.4" opacity=".7"><path d="M1 129h146M751 129h190"/></g>
<text x="74" y="146" text-anchor="middle" font-size="11" font-weight="600" fill="{h}">{s["decides"]}</text>
<text x="846" y="146" text-anchor="middle" font-size="11" font-weight="600" fill="{h}">{s["onlyreads"]}</text>

<g fill="none" stroke="{i}" stroke-width="1" stroke-dasharray="2 3" opacity=".28">
<path d="M74 161v14M279 161v14M449 161v14M619 161v14M846 161v14"/></g>
<g font-size="9.5" text-anchor="middle" fill="{i}" opacity=".55">
<text x="74" y="189">{s["bA"][0]}</text><text x="74" y="201">{s["bA"][1]}</text><text x="279" y="189">—</text>
<text x="449" y="189">{s["bC"][0]}</text><text x="449" y="201">{s["bC"][1]}</text></g>
<g font-size="9.5" text-anchor="middle" fill="{b}">
<text x="619" y="189">{s["bD"][0]}</text><text x="619" y="201">{s["bD"][1]}</text>
<text x="846" y="189">{s["bE"][0]}</text><text x="846" y="201">{s["bE"][1]}</text></g>

<g fill="none" stroke="{b}" stroke-width="1.4" opacity=".8"><path d="M547 221v10M941 221v10M547 226h394"/></g>
<text x="744" y="245" text-anchor="middle" font-size="9.5" letter-spacing="1.2" fill="{b}">{s["canstop"]}</text>''')


# ── which command runs at which stage ───────────────────────────────────────
def commands(t, s):
    """The three commands over the five stages, on process()'s own x geometry."""
    i, m = t["ink"], t["muted"]
    stages = ((1, 146, "A", s["sA"]), (207, 144, "B", s["sB"]), (377, 144, "C", s["sC"]),
              (547, 144, "D", s["sD"]), (751, 190, "E", s["sE"]))
    head = "".join(
        f'<rect x="{x}" y="24" width="{w}" height="52" fill="none" stroke="{i}"'
        f' stroke-width="1.4" opacity=".5"/>'
        f'<text x="{x + w // 2}" y="47" text-anchor="middle" font-size="18"'
        f' font-weight="600" fill="{i}" opacity=".8">{letter}</text>'
        f'<text x="{x + w // 2}" y="66" text-anchor="middle" font-size="10"'
        f' fill="{m}">{name}</text>\n'
        for x, w, letter, name in stages)
    # A bar per command, over the stages it runs in. check runs at A and again at
    # C and D, so its bar is two segments and a dotted line saying they are one
    # command, not two.
    rows = ((110, t["c1"], "check", s["q_check"], ((1, 146), (377, 314)), (149, 375)),
            (164, t["c5"], "gate", s["q_gate"], ((377, 314),), None),
            (218, t["c4"], "compare", s["q_compare"], ((751, 190),), None))
    body = ""
    for y, col, name, question, bars, link in rows:
        body += (f'<text x="1" y="{y}" font-size="13" font-weight="600" fill="{col}">'
                 f'{name}</text>'
                 f'<text x="104" y="{y}" font-size="10.5" fill="{m}">{question}</text>')
        body += "".join(f'<rect x="{x}" y="{y + 8}" width="{w}" height="18" fill="{col}"'
                        f' fill-opacity=".15" stroke="{col}" stroke-width="1.6"/>'
                        for x, w in bars)
        if link:
            body += (f'<path d="M{link[0]} {y + 17}h{link[1] - link[0]}" fill="none"'
                     f' stroke="{col}" stroke-width="1.4" stroke-dasharray="3 4"'
                     f' opacity=".55"/>')
        body += "\n"
    return svg(942, 252, s["cmds_alt"], f'''
<text x="1" y="12" font-size="10" letter-spacing="2" fill="{i}" opacity=".55">{s["cmds_head"]}</text>
{head}{body}''')


# ── pre-registration interval ───────────────────────────────────────────────
def prereg(t, s):
    i, p, b = t["ink"], t["pas"], t["blk"]
    return svg(942, 196, s["prereg_alt"], f'''
<text x="1" y="14" font-size="10" letter-spacing="1.6" fill="{i}" opacity=".55">{s["prereg_head"]}</text>
<text x="1" y="34" font-size="12" font-weight="600" fill="{i}">row_delta: {{min: 0, max: 12000}}</text>
<rect x="201" y="72" width="380" height="30" fill="{p}" opacity=".13"/>
<g fill="none" stroke="{p}" stroke-width="1.8"><path d="M201 64v46M581 64v46"/></g>
<path d="M61 87h820" fill="none" stroke="{i}" stroke-width="1" opacity=".28"/>
<text x="391" y="60" text-anchor="middle" font-size="10" letter-spacing="1.4" fill="{p}">{s["band_ok"]}</text>
<path d="M691 62v50" fill="none" stroke="{b}" stroke-width="2.6"/>
<circle cx="691" cy="87" r="5" fill="{b}"/>
<text x="691" y="54" text-anchor="middle" font-size="11.5" font-weight="600" fill="{b}">{s["measured"]}</text>
<g font-size="10.5" text-anchor="middle" fill="{i}" opacity=".6">
<text x="201" y="126">{s["minlbl"]}</text><text x="581" y="126">{s["maxlbl"]}</text></g>
<rect x="629" y="146" width="124" height="30" fill="none" stroke="{b}" stroke-width="1.6"/>
<text x="691" y="166" text-anchor="middle" font-size="12.5" font-weight="600" letter-spacing="1.4" fill="{b}">{s["blocked"]}</text>
<text x="1" y="166" font-size="10.5" fill="{i}" opacity=".6">{s["why1"]}</text>
<text x="1" y="181" font-size="10.5" fill="{i}" opacity=".6">{s["why2"]}</text>''')


# ── stage E automated diff output ───────────────────────────────────────────
def diff(t, s):
    i, p, b = t["ink"], t["pas"], t["blk"]
    return svg(942, 236, s["diff_alt"], f'''
<g fill="none" stroke="{i}" stroke-width="1.4" opacity=".6">
<rect x="1" y="1" width="940" height="234"/><path d="M1 63h940M1 179h940"/></g>
<text x="19" y="27" font-size="11.5" font-weight="600" fill="{i}">{s["diff_head"]}</text>
<text x="923" y="27" text-anchor="end" font-size="10" letter-spacing="1.4" fill="{i}" opacity=".55">{s["diff_by"]}</text>
<text x="19" y="47" font-size="10" fill="{i}" opacity=".55">{s["diff_win"]}</text>

<g font-size="11.5" fill="{i}" opacity=".85">
<text x="19" y="89">row_count</text><text x="231" y="89">1,284,003 → 1,299,003</text><text x="531" y="89">+15,000</text>
<text x="19" y="119">gross_revenue</text><text x="231" y="119">14,203,118.40 → 14,289,551.02</text><text x="531" y="119">+0.61%</text>
<text x="19" y="149">removed_pks</text><text x="231" y="149">0</text><text x="531" y="149">0</text></g>
<text x="661" y="89" font-size="11.5" font-weight="600" fill="{b}">{s["d_out"]}</text>
<text x="661" y="119" font-size="11.5" font-weight="600" fill="{p}">{s["d_in1"]}</text>
<text x="661" y="149" font-size="11.5" font-weight="600" fill="{p}">{s["d_in2"]}</text>

<rect x="19" y="195" width="124" height="26" fill="none" stroke="{b}" stroke-width="1.6"/>
<text x="81" y="213" text-anchor="middle" font-size="11.5" font-weight="600" letter-spacing="1.2" fill="{b}">{s["blocked"]}</text>
<text x="161" y="213" font-size="11.5" fill="{i}" opacity=".75">{s["diff_why"]}</text>''')


# ── heading icons: one file each, mid-tone for both grounds ─────────────────
def heading_icon(n):
    col = ICON[f"c{n}"]
    off = {1: (7, 7), 2: (6, 9), 3: (6, 8), 4: (6, 8), 5: (8, 7)}[n]
    glyph = [
        '<circle cx="6" cy="6" r="4.6"/><path d="M9.4 9.4l8 8M14.6 14.6l2.6 2.6M17.2 11.8l2.6 2.6" stroke-linecap="round"/>',
        '<path d="M1 7s4-6 9-6 9 6 9 6-4 6-9 6S1 7 1 7z"/><circle cx="10" cy="7" r="2.4"/><path d="M2 14L18 0" stroke-linecap="round"/>',
        '<path d="M1 15a9 9 0 1 1 18 0" stroke-linecap="round"/><path d="M10 15l6-6" stroke-linecap="round"/><path d="M0 18h20" stroke-linecap="round"/>',
        '<path d="M0 17h20" stroke-linecap="round"/><path d="M3 17V9M9 17V2M15 17V12" stroke-linecap="round"/>',
        '<path d="M8 1l7 2.7v5C15 13 11.6 15.8 8 17 4.4 15.8 1 13 1 8.7v-5z"/><path d="M4.6 8.6l2.4 2.4L11.4 6.6" stroke-linecap="round" stroke-linejoin="round"/>',
    ][n - 1]
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32" width="32" height="32" '
            f'role="img" aria-label="Control {n}">\n'
            f'<rect x="1" y="1" width="30" height="30" fill="none" stroke="{col}" stroke-width="1.6"/>\n'
            f'<g transform="translate({off[0]} {off[1]})" fill="none" stroke="{col}" stroke-width="1.8">{glyph}</g>\n</svg>\n')


DRAWINGS = {
    "risks": risks, "roles": roles, "manifesto": manifesto, "controls": controls,
    "permissions": permissions, "process": process,
    "pre-registration": prereg, "diff": diff, "commands": commands,
}

os.makedirs(OUT, exist_ok=True)
written = []

for theme, t in THEMES.items():
    io.open(f"{OUT}/wordmark-{theme}.svg", "w", encoding="utf-8").write(wordmark(t, None))
    written.append(f"wordmark-{theme}.svg")
    for lang, strings in L.items():
        for name, fn in DRAWINGS.items():
            path = f"{OUT}/{name}-{lang}-{theme}.svg"
            io.open(path, "w", encoding="utf-8").write(fn(t, strings))
            written.append(os.path.basename(path))

for n in range(1, 6):
    io.open(f"{OUT}/icon-c{n}.svg", "w", encoding="utf-8").write(heading_icon(n))
    written.append(f"icon-c{n}.svg")

print(f"{len(written)} files written to {OUT}")
