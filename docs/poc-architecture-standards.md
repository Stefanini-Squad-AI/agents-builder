# Requisitos Mínimos de Arquitetura para PoCs
> Referência de uso interno — independente de linguagem ou cliente  
> Baseada em padrões observados em projetos enterprise reais

---

## Como Usar Este Documento

Este documento define o **piso arquitetural** para cada categoria de PoC — o mínimo que precisa estar presente para que a entrega seja tecnicamente credível num contexto enterprise.

Cada categoria tem:
- **O que é obrigatório** — não negociável independente de prazo
- **O que é recomendado** — adiciona credibilidade sem mudar o escopo
- **O que pode ser adiado** — com justificativa explícita e documentada
- **A pergunta que o cliente vai fazer** — e como a arquitetura já responde

> **Regra geral:** Uma PoC pode ser simples. Não pode ser frágil, opaca ou insegura. A diferença entre "simples" e "frágil" é o que este documento define.

---

## Categorias

| # | Categoria | Quando usar |
|---|---|---|
| 1 | API / Serviço Backend | Expor lógica de negócio via HTTP |
| 2 | Sistema Full-Stack | Backend + frontend com fluxo de usuário |
| 3 | Event-Driven / Mensageria | Comunicação assíncrona entre sistemas |
| 4 | Modernização de Legado | Análise, migração ou documentação de sistemas antigos |
| 5 | IA / Automação Inteligente | LLMs, agentes, RAG, automação com IA |
| 6 | Pipeline de Dados / ETL | Ingestão, transformação e carga de dados |
| 7 | Infraestrutura / Deploy | IaC, pipelines CI/CD, containerização |
| 8 | Migração Assistida por IA | IA acelerada por contexto compartilhado para migração de tecnologia |

---

## 1. API / Serviço Backend

**Contexto típico:** demonstrar que um serviço pode integrar dois sistemas, expor uma lógica de negócio ou servir como camada de abstração.

### Obrigatório

```
estrutura/
├── src/
│   ├── api/          # controllers / routes — só roteamento, sem lógica
│   ├── services/     # lógica de negócio
│   ├── models/       # entidades e DTOs
│   └── config/       # configuração por ambiente
├── tests/
│   ├── unit/
│   └── integration/
├── .env.example      # NUNCA commitar .env com valores reais
└── README.md         # como rodar localmente em < 5 minutos
```

- **Separação de camadas** — controller não contém lógica; service não conhece o framework HTTP
- **Configuração por variável de ambiente** — zero valores hardcoded para URLs, credenciais ou timeouts
- **Ao menos um teste por caminho feliz e um por caminho de erro** em cada endpoint exposto
- **Contrato explícito** — OpenAPI/Swagger ou equivalente gerado/mantido manualmente; a API precisa ser descritível sem ler o código
- **Health endpoint** — `GET /health` retornando status e dependências críticas
- **Tratamento de erro padronizado** — respostas de erro com estrutura consistente (`{ "error": "...", "code": "..." }`) em todos os endpoints

### Recomendado

- Versionamento de API (`/v1/`, `/v2/`) mesmo que só exista v1 — demonstra que evolução foi considerada
- Logging estruturado (JSON) com `requestId` ou `correlationId` rastreável entre chamadas
- Autenticação real (OAuth2, API Key, JWT) — nunca `if token == "test123"`
- Testes de contrato validando que a implementação bate com o OpenAPI spec

### Pode ser adiado (com justificativa)

- Persistência em banco real → pode usar in-memory ou JSON file, **documentando claramente no README**
- Rate limiting e throttling → documentar como requisito de produção não implementado na PoC
- Paginação → implementar se o volume de dados for relevante para o demo; caso contrário, documentar

### A pergunta que o cliente vai fazer

> *"E se a dependência externa cair? E se mandarmos 1000 requisições simultâneas?"*

**Como a arquitetura já responde:** health endpoint expõe estado das dependências; timeouts configuráveis por variável de ambiente; estrutura de service permite injetar mocks facilmente para demonstrar resiliência.

---

## 2. Sistema Full-Stack

**Contexto típico:** demonstrar um fluxo de usuário completo, desde a interface até a persistência, geralmente para validar UX e lógica de negócio juntas.

### Obrigatório

```
projeto/
├── backend/
│   ├── src/
│   │   ├── routes/
│   │   ├── services/
│   │   └── models/
│   └── README.md
├── frontend/
│   ├── src/
│   │   ├── components/   # componentes reutilizáveis, sem lógica de negócio
│   │   ├── pages/        # composição de componentes por rota
│   │   └── services/     # chamadas de API isoladas aqui
│   └── README.md
├── docker-compose.yml    # sobe tudo com um comando
└── .env.example
```

- **Frontend não faz chamadas de API espalhadas no código de componente** — toda comunicação com backend vai por uma camada `services/` ou equivalente
- **Estado de UI separado de estado de domínio** — dados do servidor não ficam mixados com estado de formulário ou navegação
- **Docker Compose funcional** — `docker compose up` sobe frontend, backend e banco sem configuração manual
- **Variáveis de ambiente para a URL do backend** — nunca `fetch("http://localhost:3001/...")` hardcoded no código de produção

### Recomendado

- Tratamento de loading e erro em toda chamada assíncrona — o demo não pode travar em tela branca
- Feedback visual claro para ações do usuário (confirmações, erros, estados de carregamento)
- Responsividade básica — mesmo que o cliente veja no desktop, a ausência de responsividade é percebida como descuido
- Separação de ambientes no Docker Compose (dev com hot-reload, prod com build otimizado)

### Pode ser adiado (com justificativa)

- Autenticação completa → pode usar sessão simples ou token fixo, **documentado como requisito de produção**
- Testes de frontend → cobrir pelo menos os serviços (camada de API client) com testes unitários
- Internacionalização → documentar se for requisito do cliente

### A pergunta que o cliente vai fazer

> *"Consigo rodar isso aqui agora, na minha máquina?"*

**Como a arquitetura já responde:** `docker compose up` funciona; `.env.example` com todos os valores necessários; README com pré-requisitos e tempo estimado de setup.

---

## 3. Event-Driven / Mensageria

**Contexto típico:** demonstrar integração assíncrona entre sistemas, processamento de eventos ou desacoplamento de fluxos críticos.

### Obrigatório

```
projeto/
├── producer/         # serviço que publica eventos
├── consumer/         # serviço que consome e processa
├── shared/
│   └── events/       # contratos de evento (schemas JSON/Avro/etc.)
├── docker-compose.yml  # inclui o broker (Kafka, RabbitMQ, etc.)
└── docs/
    └── event-catalog.md  # inventário de tópicos/filas, formato, produtores, consumidores
```

- **Contratos de evento explícitos e versionados** — o schema do evento precisa existir como artefato (`schema.json`, classe, Avro, etc.), não apenas implícito no código
- **Metadados obrigatórios em todo evento:** `eventId`, `eventType`, `timestamp`, `correlationId`, `sourceSystem`, `version`
- **Idempotência no consumidor** — o mesmo evento processado duas vezes não pode causar efeito duplicado; documentar se não for implementado e por quê
- **Dead Letter Queue (DLQ) configurada** — eventos com falha de processamento precisam ir a algum lugar; mesmo que não haja UI para inspecionar, a fila precisa existir
- **Docker Compose com o broker incluso** — a PoC precisa rodar sem depender de infraestrutura externa

### Recomendado

- Retry com backoff exponencial antes de enviar para DLQ
- Padrão **Outbox** quando o evento precisa ser publicado atomicamente com uma escrita em banco — documenta a intenção mesmo que não seja implementado na PoC
- Monitoramento básico de lag de consumidor (painel no Docker Compose, ex: Kafdrop para Kafka)
- Testes de integração que publicam um evento real e verificam o estado resultante

### Pode ser adiado (com justificativa)

- Schema Registry → documentar como requisito de produção para garantir compatibilidade de schema
- Particionamento e replicação Kafka → defaults são suficientes para PoC; documentar configuração de produção
- Testes de carga → descrever a estratégia esperada, não implementar

### A pergunta que o cliente vai fazer

> *"O que acontece se o consumidor cair no meio de um processamento? E se o mesmo evento chegar duas vezes?"*

**Como a arquitetura já responde:** DLQ configurada captura eventos não processados; idempotência documentada (implementada ou com plano explícito); `correlationId` permite rastrear o fluxo de ponta a ponta nos logs.

---

## 4. Modernização de Legado

**Contexto típico:** analisar um sistema existente (sem documentação) para produzir um plano de migração, documentação técnica ou PoC da arquitetura alvo.

### Obrigatório

```
projeto/
├── legacy/           # artefatos do sistema original (código, schemas, configs)
├── analysis/
│   ├── inventory.md      # inventário de componentes, dependências, volumes
│   ├── business-rules.md # regras de negócio extraídas do código
│   ├── gaps.md           # o que falta, o que está quebrado, o que está desabilitado
│   └── risks.md          # riscos classificados por severidade
├── target/           # PoC da arquitetura alvo (quando aplicável)
└── migration/
    └── strategy.md   # abordagem de migração: fases, dependências, rollback
```

- **Inventário antes de qualquer código** — listar o que existe antes de propor o que deveria existir
- **Regras de negócio documentadas separadamente do código** — o cliente precisa validar as regras; ele não lê código
- **Classificação explícita de riscos** — cada risco com severidade, probabilidade, mitigação e dono
- **Estratégia de migração com fases** — não "migrar tudo de uma vez"; definir o que vai primeiro, critérios de go/no-go, estratégia de rollback
- **Testes de regressão descritos** — mesmo que não implementados, documentar como validar que o sistema alvo se comporta igual ao legado

### Recomendado

- Suite de testes comparativos (legado vs. novo) para fluxos críticos de negócio
- Análise de qualidade de dados antes de migrar — volume, nulos, duplicatas, inconsistências
- Glossário de termos do domínio — sistemas legados acumulam vocabulário implícito que precisa ser explicitado
- Diagrama de dependências entre componentes (quem chama quem, o que é bloqueante)

### Pode ser adiado (com justificativa)

- Implementação completa da arquitetura alvo → a PoC pode ser apenas a análise + um módulo como prova de conceito técnica
- Performance testing → descrever a metodologia; executar apenas se for critério de aceite do cliente
- Migração de dados históricos → separar da migração de código; cada uma tem riscos e estratégias distintas

### A pergunta que o cliente vai fazer

> *"Como garantimos que o sistema novo faz exatamente o que o antigo fazia? E o que acontece se der errado no meio da migração?"*

**Como a arquitetura já responde:** `business-rules.md` permite validação humana das regras extraídas; estratégia de migração em fases com rollback explícito; testes de regressão descritos para cada fase.

---

## 5. IA / Automação Inteligente

**Contexto típico:** demonstrar uso de LLMs, agentes, RAG ou automação inteligente para resolver um problema específico de negócio.

### Obrigatório

```
projeto/
├── src/
│   ├── prompts/          # prompts versionados como artefatos de código
│   ├── chains/ ou agents/
│   ├── tools/            # ferramentas disponíveis para o agente
│   └── evaluation/       # critérios e dados de avaliação
├── examples/
│   ├── inputs/           # entradas de exemplo
│   └── expected-outputs/ # saídas esperadas para comparação
├── .env.example          # chaves de API nunca no código
└── EVALUATION.md         # como medir se o sistema funciona bem
```

- **Prompts como código** — prompts versionados em arquivos, não interpolados inline no código; mudança de prompt = commit
- **Separação entre o problema e o modelo** — a lógica de negócio não pode depender de um modelo específico; abstração mínima que permita trocar o provider
- **Exemplos de entrada e saída esperada** — o demo precisa de casos concretos que demonstrem o comportamento; não depender de improvisação ao vivo
- **`EVALUATION.md` obrigatório** — definir critérios de sucesso antes da demo: o que é uma resposta boa, o que é aceitável, o que é falha
- **Tratamento de falha de modelo** — timeout, resposta inválida, rate limit: o sistema não pode travar ou retornar stack trace para o usuário

### Recomendado

- Logging de todas as chamadas ao modelo (input, output, tokens, latência) — fundamental para debug e custo
- Cache de respostas para demonstrações repetidas (evita latência e custo desnecessário durante o demo)
- Separação entre prompts de sistema, contexto e instrução do usuário — facilita experimentação e ajuste
- Testes automatizados dos casos de exemplo (`evaluation/`) com comparação de saída esperada vs. real

### Pode ser adiado (com justificativa)

- Fine-tuning → documentar quando seria adequado e por quê a abordagem de prompting foi escolhida na PoC
- Guardrails completos → implementar os críticos para o domínio (ex: não vazar dados sensíveis); documentar os demais
- Streaming de resposta → implementar se a latência for parte do demo; caso contrário, pode ser síncrono

### A pergunta que o cliente vai fazer

> *"Como você sabe que isso funciona? O que acontece quando o modelo alucina?"*

**Como a arquitetura já responde:** `EVALUATION.md` define o que é sucesso; `examples/expected-outputs/` demonstra comportamento validado; tratamento de falha de modelo não expõe erros brutos; logging permite auditoria.

---

## 6. Pipeline de Dados / ETL

**Contexto típico:** demonstrar ingestão, transformação e carga de dados entre sistemas, com garantia de qualidade e rastreabilidade.

### Obrigatório

```
projeto/
├── ingestion/        # leitura da fonte
├── transformation/   # regras de transformação
├── load/             # escrita no destino
├── quality/
│   └── checks.sql    # queries de validação de qualidade de dados
├── config/
│   └── pipeline.yaml # configuração do pipeline por ambiente
└── docs/
    ├── data-flow.md      # diagrama: fonte → transformação → destino
    ├── business-rules.md # regras aplicadas em cada etapa
    └── data-quality.md   # critérios de qualidade e thresholds de rejeição
```

- **Diagrama de fluxo de dados** — fonte, transformações, destino, dependências: sem isso o cliente não consegue validar o que está sendo feito
- **Regras de negócio separadas da implementação** — transformações documentadas em linguagem humana, não apenas em código
- **Checagens de qualidade de dados** — ao menos: contagem de linhas, nulos em colunas obrigatórias, duplicatas em chaves primárias, valores fora de range
- **Modos de execução documentados** — incremental vs. full reload: quando cada um roda, como são controlados, o que muda
- **Idempotência** — rodar o pipeline duas vezes não pode duplicar dados no destino; documentar a estratégia (DELETE + INSERT, MERGE, UPSERT)
- **Logging de execução** — registrar início, fim, volume processado, erros por etapa

### Recomendado

- Reconciliação de volumes entre fonte e destino após cada execução
- Soft delete em vez de delete físico quando dados históricos têm valor
- Estratégia de reprocessamento documentada — como reexecutar para um intervalo específico sem afetar dados fora do intervalo
- Testes com amostras de dados reais (ou realistas) que cobrem casos extremos

### Pode ser adiado (com justificativa)

- Orquestração completa (Airflow, prefect) → pode ser script Python/SQL com scheduler simples; documentar a migração esperada para produção
- Particionamento de tabelas → descrever a estratégia para produção; implementar na PoC apenas se volume for relevante para o demo
- CDC (Change Data Capture) → documentar quando seria adequado; descrever alternativa usada na PoC

### A pergunta que o cliente vai fazer

> *"E se o pipeline rodar duas vezes? E se a fonte tiver dados sujos?"*

**Como a arquitetura já responde:** idempotência documentada e implementada; checagens de qualidade rejeitam ou isolam dados inválidos antes de chegar ao destino; logging de execução permite diagnóstico.

---

## 7. Infraestrutura / Deploy

**Contexto típico:** demonstrar containerização, CI/CD, IaC ou estratégia de deploy para uma solução.

### Obrigatório

```
projeto/
├── docker/
│   ├── Dockerfile          # build multi-stage: build → runtime
│   └── docker-compose.yml  # ambiente completo local
├── infra/
│   ├── *.yaml / *.tf / *.bicep  # IaC — Kubernetes, Terraform, ARM, Bicep
│   └── environments/
│       ├── dev/
│       └── prod/           # configurações separadas por ambiente
├── .github/workflows/ ou azure-pipelines.yml
│   └── pipeline.yaml       # CI: build → test → push image → deploy
└── docs/
    ├── runbook.md           # como operar: deploy, rollback, escalar
    └── secrets-management.md  # onde ficam os segredos, como são injetados
```

- **Dockerfile com build multi-stage** — imagem de build separada da imagem de runtime; imagem final sem ferramentas de build
- **Nenhuma credencial ou URL hardcoded** — toda configuração por variável de ambiente ou referência a secret manager
- **Pipeline CI/CD com pelo menos: build → test → push** — mesmo que o deploy seja manual na PoC
- **`runbook.md`** — como fazer deploy, como fazer rollback, como escalar: se só você sabe como operar, a PoC não demonstra maturidade operacional
- **Health checks nos containers** — Kubernetes ou Docker Compose precisam saber se o serviço está pronto para receber tráfego

### Recomendado

- Estratégia de deploy explícita: rolling update, blue-green ou canary — documentar qual foi escolhida e por quê
- Separação entre ConfigMaps (config não sensível) e Secrets (credenciais) no Kubernetes
- Scans de vulnerabilidade na imagem Docker (Trivy, Grype) — mesmo que não sejam bloqueantes na PoC
- Lint e validação de IaC no pipeline (ex: `terraform validate`, `kubectl --dry-run`)

### Pode ser adiado (com justificativa)

- Network Policies Kubernetes → documentar como requisito de hardening para produção
- Monitoramento completo (Prometheus + Grafana) → health endpoint é suficiente para PoC; documentar stack de observabilidade alvo
- Autoscaling (HPA) → documentar thresholds e métricas esperadas; implementar se escala for critério de aceite

### A pergunta que o cliente vai fazer

> *"Como fazemos um rollback se algo der errado? Quem mais consegue operar isso?"*

**Como a arquitetura já responde:** `runbook.md` documenta o processo de rollback; pipeline versionado no repositório; configuração externalizada permite que qualquer membro do time opere sem acesso ao código.

---

## 8. Migração Assistida por IA

**Contexto típico:** demonstrar que IA acelerada por contexto compartilhado reduz esforço de migração, ou provar que um padrão de migração específico funciona com assistência de agente. Diferente da Categoria 5 (IA genérica), esta é sobre migração — o contexto acumula por item e flui entre interações.

> **Referência arquitetural:** `context-management-universal.md` — abstrações core (migration_item, migration_integration, item_cluster), dois paradigmas de contexto (acumulativo + conversacional), technology profiles, hybrid knowledge architecture.

### Obrigatório

```
projeto/
├── context/
│   ├── project_manifest.yaml      # mapeamento source→target, restrições
│   └── technology_profiles/       # YAML por tecnologia fonte
│       └── <source_tech>.yaml
├── agents/
│   ├── prompts/                   # prompts versionados como código
│   ├── tools/                     # MCP tools disponíveis para o agente
│   └── evaluation/                # golden sets + critérios de avaliação
├── migration/
│   ├── items/                     # migration_items — inventário do que será migrado
│   ├── integrations/              # migration_integrations — conexões entre items
│   └── strategy.md                # fases, dependências, rollback
├── knowledge/                     # knowledge store — cresce conforme items são migrados
│   ├── decisions/                 # PostgreSQL — decisões resolvidas
│   └── patterns/                  # Vector DB — embeddings de (decision + diff + rationale)
├── examples/
│   ├── inputs/                    # items de exemplo para demo
│   └── expected-outputs/          # saídas esperadas — antes/depois
├── .env.example
└── EVALUATION.md                  # como medir se o contexto compartilhado ajuda
```

- **Technology profile YAML** — pelo menos um profile para a tecnologia fonte principal; sem isso o agente não tem conhecimento estruturado sobre o que está migrando (ref: `context-management-universal.md` §4)
- **Inventário de migration_items** — listar o que existe antes de migrar; cada item com `id`, `item_type`, `domain`, `source_tech`, `target_tech`, `status`, `complexity`
- **context_snapshot explícito** — antes de cada interação do agente, o contexto acumulativo é destilado e injetado; demonstrar que o agente usa o snapshot (não apenas o prompt)
- **HITL gate em todo write-back** — agente propõe, humano aprova; nenhuma decisão ou código é persistido sem aprovação explícita; log de aprovação com timestamp e aprovador
- **EVALUATION.md com métricas de acumulação** — definir: (1) esforço por item com e sem contexto compartilhado, (2) taxa de reutilização de padrões, (3) redução de tempo entre primeiro e último item do cluster
- **Prompts como código** — versionados em arquivos, não inline; mudança de prompt = commit
- **Tratamento de falha de modelo** — timeout, resposta inválida, rate limit: o sistema não pode travar nem persistir resultado sem aprovação

### Recomendado

- **Dependency graph** — grafo de migration_items + migration_integrations; permite ao agente entender o que é bloqueante antes de propor migração
- **Item clustering** — agrupar items por similaridade (same-tech, same-pattern); agente aprende do representativo, aplica ao cluster
- **Vector DB para pattern library** — busca semântica sobre padrões resolvidos; permite "encontrar migrações similares" mesmo entre domínios diferentes
- **Logging de todas as interações** — input, context_snapshot, output, tokens, latência, decisão humana; fundamental para auditoria e debug
- **Separação entre contexto acumulativo e conversacional** — acumulativo persiste entre items; conversacional é por interação; composição via context_snapshot injection
- **Golden sets por padrão de migração** — não só por agente; cada technology_profile pattern com casos de entrada/saída validados

### Pode ser adiado (com justificativa)

- **Vector DB** → pode usar busca textual em YAML/Postgres na PoC; documentar migração para pgvector/Qdrant para produção
- **Multi-domain** → começar com um domínio (data ou app); documentar como technology profiles de outros domínios seriam adicionados
- **Clustering automático** → clusters podem ser definidos manualmente na PoC; documentar algoritmo de similaridade para produção
- **Dashboard de métricas** → métricas podem ser coletadas em logs/CSV; documentar stack de visualização para produção
- **Fine-tuning** → documentar quando seria adequado e por que prompting + RAG + contexto compartilhado foi escolhido (ref: `context-management-universal.md` §5)

### A pergunta que o cliente vai fazer

> *"Como você sabe que o contexto compartilhado realmente ajuda? Não é só o LLM sendo bom? E se o agente aprender algo errado de um item anterior?"*

**Como a arquitetura já responde:** EVALUATION.md mede esforço com e sem contexto compartilhado (A/B ou before/after); HITL gate impede que decisões erradas se propaguem — humano aprova antes do write-back; technology profiles são declarativos e auditáveis (YAML), não caixa-preta (fine-tuning); logging permite rastrear exatamente que contexto o agente usou para cada decisão.

---

## Elementos Transversais — Presentes em Toda PoC

Independente da categoria, os itens abaixo são **sempre obrigatórios**:

### README funcional

```markdown
## O que é este projeto
[Uma frase]

## Pré-requisitos
[Lista com versões]

## Como rodar localmente
[Comandos exatos — testados antes de commitar]

## Como rodar os testes
[Comando único]

## Decisões de design relevantes
[O que foi escolhido, o que foi descartado e por quê]

## O que está fora do escopo desta PoC
[Explícito — evita perguntas sobre o que "não foi feito"]
```

### `.env.example` completo

- Toda variável de ambiente usada no código deve aparecer aqui com comentário explicando o valor esperado
- Nunca commitar `.env` com valores reais — `.gitignore` deve estar configurado antes do primeiro commit

### Decisões documentadas (mesmo que brevemente)

Qualquer escolha não óbvia precisa de uma linha de justificativa: por que esse banco, por que essa estrutura de pastas, por que esse padrão arquitetural. Um revisor técnico do cliente vai perguntar — a resposta no código é mais convincente do que na hora da apresentação.

### Seção "Fora do escopo"

Documentar explicitamente o que **não** está na PoC e por quê. Isso demonstra que as omissões foram decisões conscientes, não esquecimentos.

### Context Management para Migrações

Quando uma PoC nas **Categorias 4, 5, 6 ou 8** envolve migração de tecnologia assistida por IA, os itens abaixo são **obrigatórios** independente da categoria principal:

| Requisito | O que | Por quê |
|-----------|-------|---------|
| **Technology profile YAML** | Pelo menos um profile para a tecnologia fonte principal | Sem conhecimento estruturado, o agente redescobre cada item do zero |
| **Inventário de items** | `migration_items` com id, tipo, domínio, status, complexidade | Inventário antes de migrar — mesma regra da Cat 4 |
| **HITL em write-backs** | Agente propõe, humano aprova, log com timestamp | Compliance (HIPAA/LGPD) + evita propagação de erros |
| **context_snapshot visível** | Log ou print do snapshot injetado no agente | Demonstra que o agente usa contexto acumulativo, não só o prompt |
| **Métrica de acumulação** | Esforço por item ao longo do tempo | Prova que contexto compartilhado reduz esforço (não é só "LLM bom") |

**Recomendado quando há migração:**

- Hybrid knowledge architecture (YAML + Postgres + Vector DB) — ref: `context-management-universal.md` §5
- Dependency graph entre items — permite ordem de migração informada
- Item clustering — eficiência exponencial para N items similares
- Cross-domain pattern search — padrões que span data + app + infra (ex: auth migration, config externalization)

### Context Integrity — Regras de Preservação e Uso

Quando contexto é acumulado e injetado em agentes, informações podem ser perdidas, corrompidas ou usadas incorretamente. Estas regras são **obrigatórias** para qualquer PoC nas Categorias 5 ou 8, e **recomendadas** para Cat 4 e 6:

| Regra | O que previne | Obrigatório |
|-------|---------------|-------------|
| **No silent loss** | Decisões aprovadas perdidas por trimming ou falta de persistência | Se humano aprovou, deve ser recuperável na próxima interação |
| **No blind spots** | Agente propõe sem conhecer dependência ou restrição | Nenhuma proposta sem profile + dependências + constraints |
| **No stale state** | Snapshot cacheado de interação anterior; status mudou mas agente não vê | Snapshot sempre reconstruído, nunca reutilizado |
| **No noise** | Excesso de contexto afoga o sinal relevante | Cada token no snapshot deve ser justificável como relevante ao item atual |
| **No bad propagation** | Decisão errada do item A contamina contexto do item B | Todo pattern no snapshot é verified ou explicitamente marcado unverified |
| **No black box** | Agente não consegue explicar que contexto levou à decisão | Toda claim no output deve ser rastreável a uma fonte de contexto |
| **No scope creep** | Agente vê "todo contexto disponível" e propõe mudanças fora do escopo | Contexto limitado por cluster + dependency graph, não "tudo disponível" |
| **No single point of failure** | Vector DB cai = agente para completamente | Contexto degradado > sem contexto > contexto errado |

> **Referência detalhada:** `context-integrity-guidelines.md` — anti-patterns, exemplos por domínio, checklist por regra, estratégias de fallback.

---

## Guia de Decisão Rápida

```
Qual é o objetivo principal desta PoC?
│
├── Expor lógica via HTTP? ──────────────────────────── Categoria 1: API Backend
│
├── Mostrar um fluxo completo com UI? ──────────────── Categoria 2: Full-Stack
│
├── Integrar sistemas de forma assíncrona? ─────────── Categoria 3: Event-Driven
│
├── Entender ou migrar um sistema antigo? ──────────── Categoria 4: Modernização
│
├── Usar IA para resolver um problema de negócio? ──── Categoria 5: IA / Automação
│
├── Mover ou transformar dados entre sistemas? ─────── Categoria 6: ETL / Pipeline
│
├── Demonstrar como implantar ou operar a solução? ─── Categoria 7: Infraestrutura
│
└── Acelerar migração com IA + contexto compartilhado? ─ Categoria 8: Migração Assistida por IA
```

> **Nota:** A maioria das PoCs combina categorias. Nesse caso, aplicar os requisitos obrigatórios de cada categoria envolvida. Os "pode ser adiado" de uma categoria pode compensar o esforço adicional de cobrir múltiplas categorias.

---

## Roadmap de Aprendizado e Evolução

Este documento define o **piso** arquitetural — o mínimo para que uma PoC não seja frágil. Esta seção mapeia o **teto**: o que estudar, formalizar e exercitar para que o time eleve consistentemente o padrão das próprias PoCs do "credível" para o "referência enterprise".

O roadmap é organizado pelas mesmas 7 categorias do documento. Cada item descreve **o gap que costuma aparecer em revisão técnica de cliente** e o que precisa ser aprendido para fechá-lo.

### Categoria 1 — API / Serviço Backend

| Próximo nível | O que aprender / formalizar |
|---|---|
| **Resiliência ponta a ponta** | Circuit breakers (Resilience4j, Polly), bulkheads, retries com backoff exponencial, timeout hierárquico, idempotency keys em endpoints de escrita |
| **Observabilidade real** | OpenTelemetry (traces + métricas + logs correlacionados) — não só `correlationId` em log; instrumentação automática vs. manual; semantic conventions |
| **Contratos como código** | Testes de contrato (Pact, Spring Cloud Contract); breaking change detection automatizado em PR; versionamento semântico de API |
| **AuthN/AuthZ avançado** | OAuth2/OIDC com fluxos corretos por caso (client credentials, auth code + PKCE); RBAC vs. ABAC; políticas externalizadas (OPA/Cedar) |

### Categoria 2 — Sistema Full-Stack

| Próximo nível | O que aprender / formalizar |
|---|---|
| **Arquitetura de frontend enterprise** | Micro frontends (Module Federation), design system com tokens, monorepo (Nx/Turborepo), separação clara entre app shell e features |
| **State management consciente** | Quando usar server state (TanStack Query, RTK Query) vs. global client state vs. local; evitar Redux/NgRx por inércia |
| **Acessibilidade (a11y)** | WCAG 2.2 nível AA como baseline; testes automatizados (axe-core); semântica HTML correta antes de ARIA |
| **Testes E2E confiáveis** | Playwright moderno (POM, `getByRole`/`getByLabel`, UI Mode, Trace Viewer); estratégia de dados de teste isolados; CI estável (sem flakiness) |
| **Performance percebida** | Core Web Vitals (LCP, INP, CLS); code splitting; lazy loading consciente; SSR/streaming quando faz diferença real |

### Categoria 3 — Event-Driven / Mensageria

| Próximo nível | O que aprender / formalizar |
|---|---|
| **Outbox + CDC em produção** | Implementar (não só desenhar) Outbox com Debezium; saber quando vale e quando dual-write simples basta |
| **Schema Registry operado** | Avro/Protobuf com compatibility modes (backward, forward, full); evolução de schema sem quebrar consumers |
| **Sagas** | Orquestradas (Temporal, Camunda) vs. coreografadas; compensações; idempotência por etapa |
| **Operação Kafka/RabbitMQ** | Tuning de partições, consumer groups, lag monitoring; quando RabbitMQ resolve melhor do que Kafka (filas de trabalho com prioridade, baixo throughput) |
| **Kafka Streams / KSQL** | Processamento stateful (windowing, joins) sem precisar de Spark/Flink; quando vale subir essa complexidade |

### Categoria 4 — Modernização de Legado

| Próximo nível | O que aprender / formalizar |
|---|---|
| **Strangler Fig executado** | Não só citar — executar uma fatia real em produção, com anti-corruption layer e plano de descomissionamento por componente |
| **Testes de caracterização (Golden Master)** | Capturar comportamento do legado como teste antes de mexer; rodar legado e novo com mesmos inputs e comparar outputs automaticamente |
| **Análise estática em escala** | Ferramentas específicas por legado (CAST, SonarQube + plugins, parser COBOL próprio); métricas de complexidade ciclomática, acoplamento, code smells |
| **Migração de dados com CDC** | Dual-write vs. CDC; estratégia de reconciliação contínua durante coexistência; corte (cutover) com janela mínima |
| **Bounded contexts a partir do legado** | Event Storming aplicado a sistemas sem documentação; extração de contextos por análise de dependência de tabelas/módulos |
| **Contexto acumulativo de migração** | Shared Migration Context — conhecimento que cresce por item; technology profiles YAML; write-back de decisões resolvidas; ref: `context-management-universal.md` |
| **Avaliação com golden sets por padrão** | Não só por agente — cada padrão de migração (ex: "SSIS data flow → Spark") com casos de entrada/saída validados; pipeline de eval automática quando profile muda |
| **Clustering de items similares** | Agrupar componentes por similaridade; aprender do representativo, aplicar ao cluster; medir redução de esforço |

### Categoria 5 — IA / Automação Inteligente

| Próximo nível | O que aprender / formalizar |
|---|---|
| **Avaliação formal (Evals)** | Golden sets versionados por agente/prompt; pipeline de avaliação automática quando prompt muda; métricas por dimensão (correctness, faithfulness, helpfulness) |
| **RAG em produção** | Bancos vetoriais (pgvector, Qdrant, Weaviate); estratégias de chunking por tipo de documento; reranking; avaliação (RAGAS, recall@k, MRR) |
| **Agentes multi-step** | LangGraph / frameworks de tool-use; padrões ReAct, Plan-and-Execute, Reflexion; subagentes com context isolation |
| **Observabilidade LLM** | Langfuse / LangSmith / Phoenix — tokens, custo, latência p95, taxa de falha de tool call, traces multi-agente |
| **HITL por nível de risco** | Tabela explícita: o que o agente executa sozinho, o que notifica, o que exige aprovação nomeada, o que é humano-first |
| **Guardrails** | Detecção de PII, prompt injection, output filtering; ferramentas dedicadas (NeMo Guardrails, Guardrails AI) vs. validação custom |
| **Fine-tuning consciente** | Quando vale LoRA/QLoRA vs. prompt engineering vs. RAG; custo de treino + serving; manutenção de datasets |
| **Context management para agentes** | AgentState (LangGraph) com context_snapshot injection; separação acumulativo vs. conversacional; trimming recency-biased; ref: `context-management-universal.md` §3 e §6 |
| **HITL por nível de risco em migração** | Estender a tabela HITL: executa sozinho (quality gate) / notifica (drift detect) / exige aprovação nomeada (code gen) / humano-first (architecture decisions) |
| **Knowledge architecture hybrid** | YAML (declarativo) + Postgres (queryable) + Vector DB (semantic) — NÃO fine-tuning; imediato, auditável, projetado por item |

### Categoria 6 — Pipeline de Dados / ETL

| Próximo nível | O que aprender / formalizar |
|---|---|
| **Orquestração madura** | Airflow / Prefect / Dagster — DAGs com retry, alerting, backfill controlado; observabilidade de pipeline (lineage, métricas por task) |
| **Data quality como contrato** | Great Expectations / Soda — testes de qualidade versionados como código; circuit breaker que para pipeline em falha crítica |
| **Lakehouse moderno** | Delta Lake / Iceberg / Hudi — ACID em data lake; time travel; schema evolution; otimizações (Z-order, compaction) |
| **Governance** | Unity Catalog / Lake Formation; lineage automático; políticas de acesso por coluna/linha; classificação de dados (PII, sensitive) |
| **Streaming-first** | Spark Structured Streaming / Flink — quando batch já não atende; exactly-once semantics; estado gerenciado |
| **dbt para transformações** | Modelagem SQL versionada, testada e documentada; substitui scripts SQL soltos |
| **Data contracts como fonte de contexto** | Contrato Data 4U / dbt manifest como structured spec para agentes; geração de modelos Bronze/Silver/Gold a partir do contrato |
| **Quality gates com contexto compartilhado** | aegis-dq com regras geradas a partir de technology profile + decisions resolvidas; gate evolui conforme migração avança |
| **Lineage como dependency graph** | Graph de migration_items + integrations; alimenta context_snapshot com dependências antes de propor transformação |

### Categoria 7 — Infraestrutura / Deploy

| Próximo nível | O que aprender / formalizar |
|---|---|
| **GitOps real** | ArgoCD / Flux — repositório como fonte da verdade; reconciliação contínua; promoção entre ambientes por PR |
| **Service mesh** | Istio / Linkerd — mTLS automático entre serviços, traffic shifting (canary por percentual), retries e timeouts declarativos |
| **Policy as code** | OPA / Kyverno — políticas de segurança aplicadas no admission controller (sem privileged containers, sem latest tag, etc.) |
| **Supply chain security** | SBOM (Syft), assinatura de imagens (cosign), atestados SLSA; scan de vulnerabilidades bloqueante em pipeline (Trivy, Grype) |
| **Plataforma interna (IDP)** | Backstage / port.io — self-service de criação de serviços com templates que já trazem os padrões deste documento embutidos |
| **FinOps** | Infracost no pipeline (custo de mudança visível em PR); rightsizing automatizado; reserved/spot instances onde faz sentido |
| **Chaos engineering** | Chaos Mesh / Litmus — testes de falha controlados em staging; game days regulares |

### Categoria 8 — Migração Assistida por IA

| Próximo nível | O que aprender / formalizar |
|---|---|
| **Contexto acumulativo em produção** | Shared Migration Context operado — não só desenhado; write-back automático com HITL; reconciliação de decisions entre sessões; ref: `context-management-universal.md` |
| **Technology profiles como código** | Versionados no repositório; PR de profile = PR de conhecimento; review por domain expert; CI que valida schema do profile |
| **Multi-domain com cross-cutting patterns** | Padrões que span data + app + infra (auth, config, secrets, logging); busca semântica entre domínios; cluster inter-domain |
| **Avaliação de acumulação** | Pipeline de eval que mede esforço por item ao longo do tempo; A/B com e sem contexto compartilhado; decay factor calibrado por projeto |
| **MCP servers para migração** | Custom MCP servers (FastMCP) para Databricks, dbt-core, Data 4U; protocolo uniforme para todos os agentes; ref: `mcp-framework-comparison.md` |
| **Observabilidade de contexto** | Traces que mostram: que context_snapshot foi injetado, que patterns foram encontrados, que decisions foram reutilizadas, que foi novo |
| **FinOps para migração** | Custo de LLM por item migrado; custo vs. esforço humano economizado; break-even analysis para justificar investimento em contexto compartilhado |

---

### Princípio de Evolução

Não tentar elevar todas as 8 categorias ao mesmo tempo. **Critério de priorização sugerido:**

1. Olhar as 3 últimas PoCs entregues e identificar **qual pergunta de cliente foi a mais difícil de responder** — essa é a categoria a evoluir primeiro.
2. Para cada categoria escolhida, definir **um item do roadmap por trimestre** com output reutilizável (template, exemplo de referência no repositório, documentação interna).
3. Após cada PoC, atualizar este documento se algum item do roadmap foi exercitado de verdade — ele sai do roadmap e vira parte do "recomendado" da categoria correspondente.

> **Regra:** o que está no roadmap é candidato a virar piso. O que está no piso já foi exercitado em projeto real. Essa separação preserva a credibilidade do documento.
