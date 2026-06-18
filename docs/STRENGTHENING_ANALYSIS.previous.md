# Agents Workshop — Análise de Fortalecimento

> **Para:** agente implementador (Cursor / Claude Code / Gemini CLI)
> **Tipo:** input de implementação — não é roadmap de produto, é diretriz técnica
> **Premissa:** você já tem acesso a `docs/SPEC.md`, `docs/IMPLEMENTATION_PLAN.md` e todo o código de `packages/core`, `packages/cli`, `packages/web`

---

## Como usar este documento

Cada seção descreve **uma capacidade que pode ser adicionada ao Workshop**, com:

- **O quê** — descrição precisa do que precisa existir
- **Por que** — qual gap fecha (sempre vinculado ao estado atual descrito em `SPEC.md`)
- **Onde encaixa** — em qual módulo / arquivo / camada da arquitetura existente
- **Aceitação técnica** — critérios verificáveis para considerar pronto
- **Notas de implementação** — armadilhas conhecidas, dependências, decisões já tomadas em outros lugares do projeto

> **Importante:** não trate este doc como backlog de cards. Implemente o que faz sentido implementar agora, na ordem que faz sentido. Cada seção é independente das outras a menos que dito explicitamente.

---

## Framework conceitual: as 5 camadas de capacidades de agente

A análise abaixo organiza Workshop em 5 camadas. Saber em qual camada uma adição se encaixa ajuda a decidir se a implementação cabe no monorepo atual ou exige novo módulo.

```
┌─────────────────────────────────────────────────┐
│  5. Padrões de uso (SDD, AI-Native Engineering) │
├─────────────────────────────────────────────────┤
│  4. Orquestração e padrões (workflows, multi-)  │
├─────────────────────────────────────────────────┤
│  3. Contexto e memória (Skills, Specs, Rules)   │
├─────────────────────────────────────────────────┤
│  2. Capacidades de ação (Tools, MCP, RAG)       │
├─────────────────────────────────────────────────┤
│  1. Núcleo (modelo, prompt, tipos, eval)        │
└─────────────────────────────────────────────────┘
```

Workshop hoje está forte nas camadas 3, 4 e 5. Tem gaps na camada 1 (eval) e oportunidades na camada 2 (MCP, RAG sobre artifacts).

---

## Estado atual — leitura honesta do código

Antes das sugestões, alinhamento sobre onde Workshop está:

### Pontos fortes já implementados

1. **Discovery estruturado em 4 canais** — `ProjectContext` em §4.5 do SPEC integra objetivo, Q&A, tech panorama e artifacts num único payload. Tratamento de discovery como cidadão de primeira classe é raro no mercado.

2. **`tech_panorama` com `role`** — modelar `target` vs `legacy` vs `must_avoid` vs `tbd` por dimensão captura corretamente que projetos de modernização têm dois stacks simultâneos. Não desfazer essa nuance.

3. **5 prompts com schemas Pydantic explícitos** — output estruturado em todos os pontos de geração. Continuar tratando schemas como contrato versionado.

4. **`llm_runs` como audit log completo** — `prompt_messages_json` + `response_text` + `response_json` + custo computado independente do provider (§6.5). Isso é a fundação para tudo que vem.

5. **16 validators determinísticos** (§9) — DAG cycles, forward-phase deps, paths seguros, etc. Não confiar em LLM para o que pode ser checado por código.

6. **Workflow determinístico, não agente autônomo** — decisão correta para o caso de uso. Workshop é "AI-assisted generator", não "autonomous agent". Manter essa fronteira clara.

7. **3 PoCs reais como few-shot** — Caixa-2, Enel, VLI seedados em `app/seed/reference/`. Continuar usando como exemplos primários nos prompts.

8. **Async via Dramatiq desde MVP** — extração de artefatos sempre assíncrona (§7a + §8). Padrão correto para escalar.

### Gaps relevantes

| Gap | Onde aparece no SPEC |
|---|---|
| Sem golden set / eval automatizado dos 5 prompts | Não mencionado em §7 nem §9 |
| Sem capacidade de expor Workshop via MCP | §3 só lista REST API |
| Artifacts inseridos inline (head/tail truncado a 1 MB) — sem RAG | §4.5 + §16 ("Embedding-based artifact retrieval — naïve head/tail truncation") |
| Drafts executados sequencialmente | §2 mostra fluxo linear |
| Sem second-pass critic sobre drafts | §7 — cada prompt é one-shot |
| Sem reuso de Skills entre projetos | §16 ("Skill marketplace / cross-project reuse" — não-goal MVP) |
| Sem export para Cursor `.cursor/rules/` | §10 só exporta `.agents/` |
| Sem métricas de qualidade do output | §4.2 `llm_runs` tem custo, mas não métricas de saúde do output |

---

# Sugestões de fortalecimento

## W-01 — Golden set e eval automatizado dos 5 prompts

### O quê

Conjunto versionado de inputs/outputs esperados para cada um dos 5 prompts (`ProposeSkillSet`, `DraftSkillBody`, `ProposeBacklog`, `DraftCard`, `SuggestTechStack`). Pipeline que executa o conjunto e mede regressão quando o prompt muda.

### Por que

`SPEC.md §7` define schemas precisos mas não define **o que é um output bom**. Hoje, alterar `propose_backlog.py` é especulação — não há sinal automático se a mudança piorou o resultado em casos conhecidos.

### Onde encaixa

```
packages/core/app/
├── prompts/
│   ├── propose_skill_set.py
│   └── ...
├── eval/                          # NOVO
│   ├── __init__.py
│   ├── fixtures/                  # input/output golden por prompt
│   │   ├── propose_skill_set/
│   │   │   ├── ref-siglm.input.json
│   │   │   ├── ref-siglm.expected.json
│   │   │   └── ...
│   ├── runners.py                 # executa fixtures contra prompt atual
│   ├── metrics.py                 # similaridade estrutural, cobertura de campos
│   └── reports.py                 # markdown report com diff
└── tests/
    └── eval/
        └── test_prompts.py        # roda no pytest com marker @pytest.mark.eval
```

Adicionar comando CLI: `workshop eval run [--prompt KIND]`.

### Aceitação técnica

- Cada um dos 5 prompts tem **mínimo 3 fixtures** ancoradas nas 3 PoCs seedadas.
- `workshop eval run` executa todas as fixtures e produz relatório markdown com:
  - Taxa de aderência ao schema (parsing success rate)
  - Cobertura de campos críticos (skill_slugs preenchidos, depends_on válidos, etc.)
  - Diff estrutural entre expected e actual (sem comparar bytewise — comparar set de slugs, hierarquia de fases, etc.)
- Marker pytest `@pytest.mark.eval` que rodam só quando explicitamente pedidos (são caros — chamam LLM real).
- Modo `--mock` que usa fixtures cacheadas em vez de LLM real, para CI rápido.

### Notas de implementação

- **Não medir bytewise.** Output de LLM é variável. Compare propriedades estruturais.
- **LLM-as-judge é aceitável** para subjetividade (`"a rationale_md faz sentido para o objetivo?"`) mas só **depois** dos checks determinísticos.
- Considerar usar **Ragas** ou **DeepEval** se a complexidade crescer; para começar, código próprio em `eval/metrics.py` é suficiente.
- Métrica obrigatória para `ProposeBacklog`: % de cards com `depends_on_codes` resolvíveis no próprio output.
- Métrica obrigatória para `DraftCard`: presença e tamanho mínimo de cada seção markdown.

### Dependências

Nenhuma. Pode ser implementado isoladamente.

---

## W-02 — Workshop como MCP server

### O quê

Expor as capacidades atuais (`ProposeSkillSet`, `DraftSkillBody`, `ProposeBacklog`, `DraftCard`, `SuggestTechStack`, `Validate`, `Export`) como ferramentas MCP que Cursor, Claude Desktop, Gemini CLI consomem sem precisar passar pelo export de arquivos.

### Por que

`SPEC.md §1` posiciona Workshop como gerador de contrato `.agents/` consumido por agentes externos. Hoje o fluxo exige: gerar no Workshop → exportar → commitar no repo do projeto alvo → agente consome. Com MCP, agentes consultariam o Workshop **diretamente** via protocolo padrão.

Cursor 0.45+ tem suporte nativo a MCP. Claude Desktop também. Anthropic publicou SDK Python oficial.

### Onde encaixa

```
packages/
├── core/                          # existente
├── cli/                           # existente
├── web/                           # existente
└── mcp_server/                    # NOVO
    ├── pyproject.toml
    ├── workshop_mcp/
    │   ├── __init__.py
    │   ├── server.py              # MCP server entrypoint (stdio + sse)
    │   ├── tools/                 # tools expostas
    │   │   ├── propose_skills.py
    │   │   ├── draft_skill.py
    │   │   ├── propose_backlog.py
    │   │   ├── draft_card.py
    │   │   ├── suggest_tech.py
    │   │   ├── validate.py
    │   │   └── export.py
    │   ├── resources/             # MCP resources
    │   │   ├── list_projects.py
    │   │   ├── get_project.py
    │   │   ├── get_skill.py
    │   │   └── get_card.py
    │   └── prompts/               # MCP prompts (templates)
    │       └── new_project.py
    └── tests/
```

O `mcp_server` chama o `core` (mesmo workspace `uv`), reusando services e schemas.

Adicionar entrypoint no `docker-compose.yml`:

```yaml
mcp:
  build: packages/mcp_server
  command: workshop-mcp serve --transport sse --port 8001
  ports: ["8001:8001"]
  environment:
    - DATABASE_URL=...
    - REDIS_URL=...
```

### Aceitação técnica

- MCP server passa no [MCP Inspector](https://github.com/modelcontextprotocol/inspector) sem erros.
- Cursor configurado com `gentle-config-mcp.json` apontando para o server consegue:
  - Listar projetos existentes (resource)
  - Criar projeto novo via tool `create_project`
  - Disparar `propose_skill_set` para um projeto existente
  - Receber skills propostas e iterar em conversa
- Tools são **idempotentes** — chamar `validate` 5x retorna o mesmo resultado se nada mudou.
- Tools que mutam estado (criar projeto, draft skill) retornam o ID/slug do recurso criado para permitir follow-up calls.

### Notas de implementação

- Usar **Python MCP SDK oficial** (`mcp` pacote PyPI da Anthropic).
- Transport: começar com **stdio** para desenvolvimento local (Claude Desktop), adicionar **SSE** para Cursor remoto.
- **Auth:** MVP usa MCP sem auth (rede interna). Para produção futura, OAuth2 client credentials.
- **Sessão:** cada chamada MCP é stateless — projeto é identificado por `slug` em cada call.
- Não duplicar lógica do `core`. Tools devem ser wrappers finos que chamam services do core.
- Considerar expor também as **3 PoCs seedadas como resources** — agentes podem consultar exemplos via MCP para entender padrões.

### Dependências

- Workshop core estável (P2 completo).
- Decisão: tool MCP recebe inputs no formato dos schemas Pydantic existentes? Sim — reusar schemas de `app/schemas/`.

---

## W-03 — RAG sobre artifacts (substituir head/tail truncation)

### O quê

Substituir a estratégia de `content_md_truncated` (head 500 KB + tail 500 KB) por indexação via embeddings com recuperação por relevância no momento de cada prompt.

### Por que

`SPEC.md §4.2 project_artifacts.content_md_truncated` é solução paliativa. Para PoCs reais (Caixa-2 tem dezenas de programas COBOL, VLI tem pacotes SSIS extensos), 1 MB head/tail perde contexto relevante no meio do arquivo. `SPEC.md §16` já lista como non-goal do MVP — esta sugestão é a evolução natural.

### Onde encaixa

Nova tabela:

```sql
CREATE TABLE artifact_chunks (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  artifact_id UUID NOT NULL REFERENCES project_artifacts(id) ON DELETE CASCADE,
  chunk_index INTEGER NOT NULL,
  content TEXT NOT NULL,
  embedding vector(1536),           -- pgvector extension
  tokens INTEGER NOT NULL,
  metadata JSONB,                   -- {section, page, language, etc.}
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (artifact_id, chunk_index)
);
CREATE INDEX ON artifact_chunks USING ivfflat (embedding vector_cosine_ops);
```

Adicionar ao docker-compose: extensão `pgvector` no Postgres (usar imagem `pgvector/pgvector:pg16`).

Novo job Dramatiq:

```
packages/core/app/jobs/
├── extract_artifact.py            # existente
└── chunk_and_embed_artifact.py    # NOVO
```

Pipeline: `extract_artifact` → ao terminar, dispara `chunk_and_embed_artifact`.

Novo serviço:

```
packages/core/app/services/
└── artifact_retrieval.py          # NOVO
    - search(project_id, query, k=10) -> list[Chunk]
    - hybrid_search(project_id, query, k=10) -> list[Chunk]   # BM25 + dense
```

Modificar `ProjectContext` em §4.5: `artifact_summaries` continua existindo (para visão geral), mas adicionar método `relevant_chunks(query, k)` chamado de dentro de cada prompt antes de montar mensagem.

### Aceitação técnica

- Artefatos maiores que 1 MB são chunkados e indexados sem perder conteúdo do meio.
- Prompts modificados: cada um dos 5 prompts passa a chamar `artifact_retrieval.search(project_id, query=<task-specific-query>)` antes de montar contexto.
- Query por prompt:
  - `ProposeSkillSet` → `"capabilities needed for {objective}"`
  - `DraftSkillBody` → skill name + description
  - `ProposeBacklog` → `"phases and milestones for {objective}"`
  - `DraftCard` → card title + skill names
  - `SuggestTechStack` → dimension name
- Resultado: prompt recebe **chunks relevantes** em vez de head+tail genérico.
- Fallback: se busca retorna < 3 chunks, mantém comportamento antigo (artifact_summaries inline).

### Notas de implementação

- **Modelo de embedding:** começar com `text-embedding-3-small` (OpenAI) por custo. Adicionar suporte a self-hosted (bge-m3 via Ollama) na sequência.
- **Tamanho de chunk:** 500-800 tokens com overlap de 100. Não chunkar por linha — chunkar por seção semântica (markdown headers, parágrafos).
- **Reranking:** começar sem. Se métricas de qualidade de output (W-08) mostrarem ganho marginal, adicionar Cohere Rerank ou BGE Reranker.
- **Re-indexação:** quando artifact é re-extraído (retry), deletar chunks antigos antes de inserir novos.
- Não remover `content_md` da tabela `project_artifacts` — manter como cache para preview na UI.

### Dependências

- pgvector no Postgres (mudar imagem em docker-compose).
- Decisão sobre modelo de embedding (OpenAI vs self-hosted).

---

## W-04 — Agente Critic em cada draft

### O quê

Adicionar segundo prompt LLM após `DraftSkillBody` e `DraftCard` que revisa o output do primeiro antes de salvar. Não substitui — é gate de qualidade adicional.

### Por que

`SPEC.md §7` define cada prompt como one-shot estruturado. Funciona bem na maior parte dos casos, mas para skills com 6+ resources ou cards com critérios de aceite complexos, o primeiro draft frequentemente esquece detalhes. Critic detecta e força revisão.

### Onde encaixa

```
packages/core/app/prompts/
├── propose_skill_set.py
├── draft_skill_body.py
├── critic_skill_body.py           # NOVO
├── propose_backlog.py
├── draft_card.py
├── critic_card.py                 # NOVO
└── suggest_tech_stack.py
```

Modificar `services/skill_drafting.py` e `services/card_drafting.py`:

```python
async def draft_skill_body(skill_id: UUID, with_critic: bool = True) -> SkillBody:
    draft = await llm_service.run(DraftSkillBody, ...)
    if with_critic:
        review = await llm_service.run(CriticSkillBody, draft=draft, ...)
        if review.has_issues:
            # Critic propõe revisão; salvar review como llm_runs
            # Aplicar revisões críticas (rationale registrado)
            draft = apply_critic_revisions(draft, review)
    return persist(draft)
```

### Aceitação técnica

- Cada draft pode ser executado com ou sem critic (CLI flag `--critic/--no-critic`).
- Critic produz output estruturado com:
  ```python
  class CriticReview(BaseModel):
      passes: bool
      severity: Literal["info", "warning", "error"]
      issues: list[Issue]
      suggested_revisions: list[Revision]
      overall_assessment: str
  ```
- Quando critic encontra issue `error`, draft não é salvo automaticamente — UI mostra para revisão humana.
- Quando critic encontra issue `warning`, draft é salvo mas issue fica visível.
- `llm_runs` registra **ambos** os calls (draft + critic) com `kind='draft_*'` e `kind='critic_*'`.

### Notas de implementação

- Critic deve ser **prompt diferente, não temperatura mais alta no mesmo prompt**. Persona explícita: "você é revisor crítico, busca falhas".
- Critic recebe **o draft inteiro como input** + project context.
- Critic não reescreve — propõe revisões. Aplicação das revisões é determinística (substituir seção X por seção Y) ou outro prompt (`ApplyCriticRevisions`) — começar com determinístico.
- Custo: dobra o número de tokens por draft. Tornar opt-out por projeto ou por draft.
- Pode ser adicionado depois de W-01 (golden set) para medir se critic melhora métricas de output.

### Dependências

- Nenhuma técnica. Conceitualmente complementa W-01 (eval).

---

## W-05 — Parallel execution de drafts

### O quê

Executar `DraftSkillBody × N` e `DraftCard × N` em paralelo via Dramatiq quando há múltiplos drafts pendentes, em vez de sequencial.

### Por que

`SPEC.md §2` mostra fluxo linear. Hoje, projeto com 8 skills e 30 cards faz 38 chamadas LLM sequenciais — ~10-15 minutos. Em paralelo (limitado por rate limit do provider) cai para 2-3 minutos.

### Onde encaixa

```
packages/core/app/jobs/
├── extract_artifact.py
├── chunk_and_embed_artifact.py    # se W-03 implementado
├── draft_skill_body.py            # NOVO
├── draft_card.py                  # NOVO
└── _broker.py
```

Adicionar comando CLI:

```
workshop skill draft-all                # draft all skills in parallel
workshop card draft-all [--phase CODE]  # draft all cards in parallel
```

API:

```
POST /api/projects/{slug}/skills/draft-all
POST /api/projects/{slug}/cards/draft-all
```

Resposta: 202 com job_id; cliente polla `/api/jobs/{job_id}` para progresso.

### Aceitação técnica

- Drafts são despachados em paralelo respeitando rate limit configurável (`WORKSHOP_LLM_MAX_CONCURRENT=5` por default).
- Cada draft é um job Dramatiq independente — falha de um não derruba os outros.
- UI mostra progresso em tempo real (skill_1: drafting, skill_2: done, skill_3: queued, ...).
- Resultado é determinístico: ordem final não depende da ordem de conclusão.

### Notas de implementação

- Cuidado com rate limit do Anthropic — Claude tem limite por minuto. `WORKSHOP_LLM_MAX_CONCURRENT` deve respeitar provider.
- Quando `with_critic=true` (W-04), critic roda **após** o draft do mesmo job — não paralelizar critic e draft do mesmo item.
- Não paralelizar drafts dependentes — se Card B depende de Card A (ambos `DraftCard`), e o prompt de B precisa ler o título de A, B só dispara após A terminar.
- Atualmente §7.4 `DraftCard` precisa de `upstream_cards.titles` — verificar se isso introduz dependência forçada. Decisão: drafts não devem depender entre si (cada um lê do banco no momento do disparo).

### Dependências

- Dramatiq já é parte do MVP (§7a). Reuso direto.

---

## W-06 — Métricas de qualidade do output

### O quê

Tabela e endpoint que registram métricas de saúde por projeto, derivadas do output gerado:

- % de cards com `human_gate=true` ao final de cada phase
- Distribuição de story points (média, desvio padrão por phase)
- Profundidade média do DAG
- % de skills `analyzer` com 0 resources (warning condition)
- % de cards com `depends_on` válido
- Razão skills/cards
- % de cobertura de tech_dimensions (quantas dimensões têm choice)

### Por que

`SPEC.md §4.2 llm_runs` registra custo e tokens, mas não diz nada sobre **se o output é bom**. Sem essas métricas, não há sinal contínuo de degradação ou melhoria.

### Onde encaixa

```sql
CREATE TABLE project_quality_snapshots (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  metrics JSONB NOT NULL,           -- dict[metric_name, value]
  triggered_by TEXT NOT NULL,       -- 'draft_complete' | 'export' | 'manual'
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

```
packages/core/app/services/
└── quality_metrics.py             # NOVO
    - compute_snapshot(project_id) -> dict
    - persist_snapshot(project_id, triggered_by)
    - get_history(project_id, limit=10) -> list[Snapshot]
```

Endpoint REST:

```
GET /api/projects/{slug}/quality        # snapshot atual
GET /api/projects/{slug}/quality/history  # série temporal
```

CLI:

```
workshop quality show                  # snapshot atual
workshop quality history               # últimos N snapshots
```

UI: nova aba `/projects/[slug]/quality` com cards de métrica e sparklines de histórico.

### Aceitação técnica

- Snapshot é tirado automaticamente quando: backlog é proposto, card é draftado, projeto é exportado.
- Cada métrica tem **threshold configurável** com classificação `ok` | `warning` | `error`.
- Endpoint retorna snapshot atual + comparação com snapshot anterior (delta).
- UI mostra **alerta visual** quando métrica vira `warning` ou `error`.
- Pelo menos 8 métricas computadas no MVP da feature.

### Notas de implementação

- Snapshots são **somente derivados** — não armazenam dado primário. Podem ser recomputados sempre.
- Manter histórico **com limite** — 100 últimos snapshots por projeto, mais antigos arquivados ou descartados.
- Algumas métricas dependem de output do LLM (`% de cards com depends_on válido`) — outras são parâmetros do projeto (% de tech dimensions cobertas). Ambas valem.

### Dependências

- Idealmente W-01 implementado, mas não bloqueia.

---

## W-07 — Skill marketplace cross-project

### O quê

Capacidade de marcar uma skill como **reutilizável** (template) e importá-la em outro projeto, com adaptação de contexto pelo LLM.

### Por que

`SPEC.md §16` lista "Skill marketplace / cross-project reuse" como non-goal do MVP. Para a Stefanini operando dezenas de projetos similares (modernizações de COBOL, análises de SSIS, etc.), reaproveitar Skills entre projetos é **multiplicador de produtividade**.

### Onde encaixa

```sql
CREATE TABLE skill_templates (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  source_skill_id UUID NOT NULL REFERENCES skills(id),
  source_project_id UUID NOT NULL REFERENCES projects(id),
  name TEXT NOT NULL,
  description TEXT NOT NULL,
  kind TEXT NOT NULL,
  body_md TEXT NOT NULL,
  resources_json JSONB NOT NULL,    -- snapshot de skill_resources
  tags TEXT[],                       -- ['cobol', 'modernization', 'legacy']
  reuse_count INTEGER NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE skills ADD COLUMN imported_from_template_id UUID REFERENCES skill_templates(id);
```

Novo prompt:

```
packages/core/app/prompts/
└── adapt_skill_template.py        # NOVO
```

Operação `AdaptSkillTemplate`: dado `skill_template` + `target_project_context`, gera nova skill adaptada ao projeto destino.

CLI:

```
workshop skill mark-template <skill-slug>           # promover para template
workshop skill templates list [--tags tag1,tag2]    # listar templates
workshop skill templates import <template-id>       # importar para projeto atual
```

### Aceitação técnica

- Marcar skill como template é operação não-destrutiva — skill original continua no projeto.
- Importar template para projeto novo dispara `AdaptSkillTemplate` que ajusta o body para o contexto destino (substituir referências a tech específicas, etc.).
- `reuse_count` é incrementado a cada import.
- Templates aparecem como **catálogo** acessível por todos os projetos do mesmo tenant.
- UI mostra "Esta skill foi importada de [template]" no detalhe da skill.

### Notas de implementação

- **Tags são fundamentais.** Sem tagging, marketplace vira pasta cheia de coisas. Pelo menos: `kind`, `legacy_tech`, `target_tech`, `domain`.
- **Não copiar `skill_resources` por referência** — copiar conteúdo. Template e skill viva podem evoluir independentemente.
- Quando `LLMService.run` adapta template, registrar como `llm_runs.kind='adapt_skill_template'` com referência à `skill_template_id`.
- Marketplace é por tenant no MVP, não global. Cross-tenant exige discussão de governança separada.

### Dependências

- Workshop core estável + multi-projeto funcional. Razoável depois de P2.

---

## W-08 — Cursor Rules export (ao lado de `.agents/`)

### O quê

Adicionar opção de export que gera `.cursor/rules/*.mdc` (formato Cursor Rules) ao lado do `.agents/` tradicional.

### Por que

`SPEC.md §10` exporta `.agents/`. Cursor consome via Skills (formato Anthropic) que ele suporta nativamente. Mas Cursor **também** tem seu próprio formato `.cursor/rules/*.mdc` com vantagens: aplicado automaticamente no escopo certo (glob patterns), aparece no chat sempre, é convenção mais conhecida da comunidade Cursor.

### Onde encaixa

```
packages/core/app/exporters/
├── agents_folder.py               # existente
└── cursor_rules.py                # NOVO
```

Tipo de export adicional em §4.2 `exports.kind`: `'cursor_rules'`.

CLI:

```
workshop export --target cursor-rules --path /abs/path
workshop export --target both --path /abs/path        # .agents/ + .cursor/rules/
```

### Aceitação técnica

- Cada skill vira um arquivo `.cursor/rules/<slug>.mdc` com:
  - Frontmatter `description` igual ao SKILL.md
  - Frontmatter `globs` derivado de skill metadata ou catch-all `**/*`
  - Body markdown idêntico ou ligeiramente adaptado (referências de path)
- Resources de skill viram arquivos em `.cursor/rules/<slug>/`
- Rule files seguem nomenclatura Cursor (`.mdc`, não `.md`)
- Export `both` produz `.agents/` E `.cursor/rules/` no mesmo destino sem conflito

### Notas de implementação

- Validar formato contra docs Cursor atual (formato `.mdc` evoluiu em 2025).
- **Glob inteligente:** se skill tem `kind='analyzer'` e tem resources `*.sql`, sugerir glob `**/*.sql`. Caso contrário, catch-all.
- Considerar também export para Claude Code (`AGENTS.md` na raiz do projeto). Padrão emergente.

### Dependências

- Nenhuma. Pode ser adicionado isoladamente.

---

## W-09 — Versionamento de skills e cards

### O quê

Histórico de mudanças por skill e por card, com possibilidade de reverter para versão anterior e ver diff entre versões.

### Por que

`SPEC.md §16` lista "Card version history (only `updated_at` stored)" como non-goal MVP. Para iteração segura — especialmente quando critic (W-04) ou usuário edita drafts — versionamento permite reverter sem perder o trabalho.

### Onde encaixa

```sql
CREATE TABLE skill_versions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  skill_id UUID NOT NULL REFERENCES skills(id) ON DELETE CASCADE,
  version_no INTEGER NOT NULL,
  name TEXT NOT NULL,
  description TEXT NOT NULL,
  kind TEXT NOT NULL,
  body_md TEXT NOT NULL,
  resources_snapshot JSONB NOT NULL,
  changed_by TEXT NOT NULL,          -- 'user' | 'llm_draft' | 'llm_critic' | 'import'
  llm_run_id UUID REFERENCES llm_runs(id),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (skill_id, version_no)
);

CREATE TABLE card_versions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  card_id UUID NOT NULL REFERENCES cards(id) ON DELETE CASCADE,
  version_no INTEGER NOT NULL,
  title TEXT NOT NULL,
  context_md TEXT,
  task_md TEXT,
  outputs_md TEXT,
  acceptance_criteria_md TEXT,
  changed_by TEXT NOT NULL,
  llm_run_id UUID REFERENCES llm_runs(id),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (card_id, version_no)
);
```

Trigger ou hook em service: a cada update significativo em skill/card, snapshot da versão anterior antes do save.

### Aceitação técnica

- Cada save em skill ou card cria nova versão (ou mantém versão atual se delta é vazio).
- UI mostra timeline de versões com:
  - Quem mudou (`user`, `llm_draft`, `llm_critic`)
  - Quando mudou
  - Diff visual entre versão atual e anterior
- Botão "revert to version N" cria nova versão com o conteúdo da N (não modifica versões anteriores).
- CLI: `workshop skill history <slug>`, `workshop skill revert <slug> --version N`.

### Notas de implementação

- **Não armazenar diff** — armazenar snapshot completo. Storage é barato; reconstruir state via merge de diffs é caro.
- Limitar histórico a **50 versões** por entidade. Versões mais antigas vão para `*_versions_archive` (cold storage) ou são descartadas.
- Versionamento de **resources** dentro de skill: snapshot via `resources_snapshot` JSONB. Não criar tabela separada.
- Considerar não versionar mudanças do critic se passou no review automático — só versionar quando user/critic produz mudança aceita.

### Dependências

- Nenhuma. Independente de outras sugestões.

---

## W-10 — Posicionamento formal como ferramenta SDD

### O quê

Documentação que assume e explica que Workshop é uma ferramenta de **Spec-Driven Development (SDD)**. Aplica vocabulário e referências da comunidade.

### Por que

Workshop **é** uma ferramenta SDD canônica. O `SPEC.md` não usa o termo. Adotar o vocabulário:
1. Conecta o produto com prática nascente que tem comunidade ativa em 2026
2. Facilita marketing e onboarding
3. Permite comparação direta com Microsoft Spec-Kit, GitHub Specs e outras ferramentas adjacentes

### Onde encaixa

Adicionar seção ao `docs/SPEC.md`:

```markdown
## 0. Filosofia: Spec-Driven Development

Agents Workshop é uma ferramenta de **Spec-Driven Development (SDD)** —
o padrão emergente em 2025-2026 onde specs são artefatos versionados de
primeira classe que agentes de IA executam.

### Como Workshop se posiciona em SDD

- **Spec é o ativo principal.** Skills (SKILL.md) + cards Jira = spec executável.
- **Workshop é o ambiente de autoria.** Outros agentes (Cursor, Claude Code, Gemini CLI)
  são o ambiente de execução.
- **Discovery é spec ainda mais primária.** Q&A + tech panorama + objetivo geram
  o ProjectContext que é a base de todas as specs derivadas.

### Referências adjacentes

- [Microsoft Spec-Kit](https://github.com/github/spec-kit) — padrão Microsoft de specs como código
- [Anthropic Skills](https://docs.claude.com/en/docs/agents-and-tools/agent-skills) — formato de SKILL.md
- [Cursor Rules](https://docs.cursor.com/context/rules-for-ai) — formato `.cursor/rules/*.mdc`
- [AGENTS.md](https://agents.md) — convenção emergente para agentes

### Diferenças vs alternativas

| Ferramenta | Posicionamento |
|---|---|
| Microsoft Spec-Kit | Specs leves, foco em dev individual |
| Anthropic Skills | Padrão de skill, sem orquestração de projeto |
| **Agents Workshop** | **Specs estruturadas + discovery + backlog DAG + validators + export multi-formato, para projetos completos** |
```

Adicionar README a `packages/web` com o mesmo framing — homepage do produto deve dizer "SDD tool".

### Aceitação técnica

- `docs/SPEC.md` tem seção 0 com framing SDD.
- README principal usa o termo "Spec-Driven Development" e referencia adjacentes.
- Página `/` da web tem heading que menciona SDD.
- Em `docs/`, novo arquivo `WHAT_IS_SDD.md` com explicação longa para onboarding de novos usuários/devs.

### Notas de implementação

- Não exagerar no jargão. SDD é o framing — o produto continua sendo o produto.
- **Não renomear nada** — "Workshop" é o nome do produto. SDD é a categoria.

### Dependências

- Nenhuma. É documentação.

---

# Priorização sugerida (não-vinculante)

A ordem abaixo otimiza por **valor entregue por esforço**, considerando que algumas sugestões habilitam outras:

| # | Sugestão | Camada | Valor | Esforço |
|---|---|---|---|---|
| 1 | **W-01 — Golden set + eval** | 1 | 🔴 Alto | Médio |
| 2 | **W-10 — Posicionamento SDD** | 5 | 🟡 Médio | Baixo (doc) |
| 3 | **W-08 — Cursor Rules export** | 3 | 🟡 Médio | Baixo |
| 4 | **W-09 — Versionamento** | 3 | 🟡 Médio | Médio |
| 5 | **W-05 — Parallel execution** | 4 | 🟡 Médio | Baixo |
| 6 | **W-04 — Agente Critic** | 4 | 🔴 Alto | Médio |
| 7 | **W-06 — Métricas de qualidade** | 1 | 🟡 Médio | Médio |
| 8 | **W-02 — MCP server** | 2 | 🔴 Alto | Médio-Alto |
| 9 | **W-03 — RAG sobre artifacts** | 2 | 🟡 Médio | Médio-Alto |
| 10 | **W-07 — Skill marketplace** | 3 | 🟡 Médio | Alto |

W-01 vem primeiro porque é **pré-requisito metodológico** — sem ele, todas as outras mudanças que tocam prompts (W-03, W-04) ficam invisíveis em termos de regressão.

W-02 (MCP) é alto valor mas alto esforço — deixar para quando os fundamentos (eval, métricas) estiverem prontos.

---

# O que NÃO está nesta lista (decisões deliberadas)

Coisas que **não** sugiro adicionar agora, mesmo que apareçam em conversas:

- **Multi-agente orquestrado** — Workshop é workflow determinístico, decisão correta. Adicionar orquestração multi-agente complica sem ganho claro.
- **Fine-tuning de modelos para os prompts** — sempre considerar prompting + RAG primeiro. FT vira opção só se eval (W-01) mostrar limite irrecuperável.
- **Streaming de respostas LLM** — `SPEC.md §17 item 8` decidiu por `wait for full structured response`. Manter.
- **Auth/multi-tenant na web UI** — `SPEC.md §16` deixou explícito como non-goal. Não inverter sem motivo de produto claro.
- **Embedding de PPTX/XLSX/OCR** — `SPEC.md §16` deixou para P3+. Aguardar demanda real.

---

# Quando atualizar este documento

Esta análise é foto do estado em maio de 2026. Atualize quando:

- Uma das sugestões W-XX for implementada (move para `IMPLEMENTATION_PLAN.md`).
- O SPEC.md tiver mudanças materiais (nova entidade, novo prompt, nova família de template).
- Surgir nova capacidade de IA relevante (ex: MCP 2.0, novo padrão de skill, etc.) que mude o framing das 5 camadas.

Edits a este arquivo via PR contra a branch principal, como qualquer outro doc.
