"""ProposeSkillSet prompt implementation with few-shot examples from seeded data."""

from __future__ import annotations

from app.llm.base import ChatMessage, ChatPrompt
from app.schemas.llm_io import ProposedSkillSet
from app.schemas.views import ProjectContext


class ProposeSkillSetPrompt:
    """Prompt for proposing an initial skill set based on project context.

    Takes a ProjectContext (objective + Q&A + tech choices + artifacts) and
    generates 5-10 skills covering different aspects of the project work.

    Uses few-shot examples from the three reference PoCs:
    - Caixa-2 (SIGLM): Banking modernization with COBOL analysis
    - VLI (CORP): SSIS to Databricks migration
    - Enel (Cronos): Full-stack feature development
    """

    @staticmethod
    def create(context: ProjectContext) -> ChatPrompt[ProposedSkillSet]:
        """Create the ProposeSkillSet prompt with project context.

        Args:
            context: Complete project context from discovery phase

        Returns:
            ChatPrompt ready for LLM execution
        """
        system_prompt = """You are an expert technical project manager specializing in breaking down complex software projects into reusable skills.

Your task is to analyze a project and propose a comprehensive skill set that covers all aspects of the work. Each skill should be:

**Skill Types:**
- **context**: Domain knowledge, architecture, conventions (1-2 per project)
- **analyzer**: Code/data analysis, discovery tools (2-4 per project)
- **authoring**: Creating new code/features (2-4 per project)
- **procedure**: Step-by-step operational tasks (1-3 per project)

**Skill Quality Guidelines:**
- Skills should be **reusable** across similar cards/tasks
- Each skill covers a **distinct capability** with clear boundaries
- Skills should **reference each other** when they build on related work
- Slugs should be **project-prefixed** and descriptive (e.g., "banking-cobol-analyzer")
- Descriptions must include **when to invoke** the skill (trigger scenarios)

**Coverage Strategy:**
- Start with **context** skills for domain knowledge
- Add **analyzer** skills for discovery/assessment work
- Include **authoring** skills for implementation work
- Add **procedure** skills for deployment/operational tasks
- Ensure skills cover the full project lifecycle

Generate 5-10 skills that comprehensively address the project objective."""

        user_message = ProposeSkillSetPrompt._build_user_message(context)

        return ChatPrompt(
            system=system_prompt,
            messages=[
                ChatMessage(role="user", content=user_message)
            ],
            response_schema=ProposedSkillSet
        )

    @staticmethod
    def _build_user_message(context: ProjectContext) -> str:
        """Build the user message with project context and few-shot examples."""

        # Start with project context
        message_parts = [
            f"**Project Objective**: {context.objective}",
            ""
        ]

        # Add Q&A context if available
        if context.qa:
            message_parts.append("**Discovery Q&A:**")
            for question, answer in context.qa.items():
                message_parts.append(f"- **{question}**: {answer}")
            message_parts.append("")

        # Add tech choices if available
        if context.tech_choices_by_dimension:
            message_parts.append("**Technology Choices:**")
            for dimension, choices in context.tech_choices_by_dimension.items():
                choice_names = [choice.tech_item_name or choice.tech_item_slug or "TBD" for choice in choices]
                message_parts.append(f"- **{dimension}**: {', '.join(choice_names)}")
            message_parts.append("")

        # Add artifact summaries if available
        if context.artifact_summaries:
            message_parts.append("**Uploaded Artifacts:**")
            for artifact in context.artifact_summaries:
                excerpt = artifact.content_md_excerpt or "No content extracted"
                truncated_note = " (truncated)" if artifact.content_md_truncated else ""
                message_parts.append(f"- **{artifact.filename}**: {excerpt}{truncated_note}")
            message_parts.append("")

        # Add context notes if available
        if context.context_notes_md:
            message_parts.append("**Additional Context:**")
            message_parts.append(context.context_notes_md)
            message_parts.append("")

        # Add few-shot examples
        message_parts.extend([
            "**Examples from similar projects:**",
            "",
            ProposeSkillSetPrompt._get_few_shot_examples(),
            "",
            "Based on this project context, propose a comprehensive skill set that covers all aspects of the work from discovery through implementation to deployment."
        ])

        return "\n".join(message_parts)

    @staticmethod
    def _get_few_shot_examples() -> str:
        """Get generic few-shot examples covering major software development dimensions."""
        return """**Example 1: Legacy Banking System Modernization**
*Objective: Modernize COBOL-based financial system to microservices architecture*

```json
{
  "skills": [
    {
      "slug": "banking-domain-context",
      "name": "Banking Domain Context",
      "description": "Canonical knowledge base for financial systems - regulatory requirements, transaction processing patterns, data models, and legacy integration patterns. Use when working with financial data, compliance requirements, or banking workflows.",
      "kind": "context",
      "rationale": "Financial domain has complex regulations and business rules that need centralized documentation",
      "sibling_refs": ["legacy-cobol-analyzer", "microservices-decomposer"]
    },
    {
      "slug": "legacy-cobol-analyzer",
      "name": "Legacy COBOL Business Rules Extractor",
      "description": "Extract business logic from legacy COBOL programs and translate to modern specifications. Use when analyzing mainframe code for modernization or business rule documentation.",
      "kind": "analyzer",
      "rationale": "Legacy systems contain decades of business logic that must be preserved during modernization",
      "sibling_refs": ["banking-domain-context", "microservices-decomposer"]
    }
  ],
  "coverage_notes": "Covers financial domain knowledge and legacy code analysis for modernization projects",
  "gaps": ["Cloud deployment patterns", "Security compliance automation"]
}
```

**Example 2: Cloud-Native Microservices Platform**
*Objective: Build scalable e-commerce platform using microservices and Kubernetes*

```json
{
  "skills": [
    {
      "slug": "microservices-decomposer",
      "name": "Microservices Architecture Designer",
      "description": "Analyze monolithic applications and design microservices architecture using DDD patterns. Use when breaking down large applications or designing service boundaries.",
      "kind": "analyzer",
      "rationale": "Microservices require careful domain modeling and service boundary definition",
      "sibling_refs": ["cloud-deployment-orchestrator", "observability-implementer"]
    },
    {
      "slug": "cloud-deployment-orchestrator",
      "name": "Cloud Deployment Orchestrator",
      "description": "Design and implement cloud-native deployment pipelines using Docker, Kubernetes, and CI/CD. Use when deploying microservices to cloud platforms.",
      "kind": "procedure",
      "rationale": "Cloud deployments require orchestration of multiple services with proper scaling and monitoring",
      "sibling_refs": ["microservices-decomposer", "observability-implementer"]
    }
  ],
  "coverage_notes": "Covers microservices design and cloud deployment for scalable applications",
  "gaps": ["Message queue integration", "Data consistency patterns"]
}
```

**Example 3: AI-Powered Development Platform**
*Objective: Create intelligent code analysis and generation system*

```json
{
  "skills": [
    {
      "slug": "ai-code-analyzer",
      "name": "AI-Powered Code Analyzer",
      "description": "Use LLMs to analyze codebases, extract patterns, generate documentation, and suggest improvements. Use when analyzing legacy systems or generating technical documentation.",
      "kind": "analyzer",
      "rationale": "AI can process large codebases faster than manual analysis and identify complex patterns",
      "sibling_refs": ["intelligent-test-generator", "code-quality-auditor"]
    },
    {
      "slug": "intelligent-test-generator",
      "name": "Intelligent Test Suite Generator",
      "description": "Generate comprehensive test suites using AI analysis of code paths and business logic. Use when adding test coverage or validating complex business rules.",
      "kind": "authoring",
      "rationale": "AI can identify edge cases and generate tests that humans might miss",
      "sibling_refs": ["ai-code-analyzer", "code-quality-auditor"]
    }
  ],
  "coverage_notes": "Covers AI-driven development tools and intelligent automation",
  "gaps": ["Model deployment pipelines", "Real-time code suggestions"]
}
```

**Example 4: Full-Stack Web Application**
*Objective: Build modern React/Node.js application with authentication and real-time features*

```json
{
  "skills": [
    {
      "slug": "fullstack-feature-architect",
      "name": "Full-Stack Feature Architect",
      "description": "Design and implement end-to-end features spanning React frontend, Node.js backend, and PostgreSQL database. Use when adding new user-facing functionality.",
      "kind": "authoring",
      "rationale": "Modern web apps require coordinated changes across multiple technology layers",
      "sibling_refs": ["api-security-implementer", "realtime-communication-designer"]
    },
    {
      "slug": "api-security-implementer",
      "name": "API Security & Auth Implementer",
      "description": "Implement OAuth2, JWT, role-based access control, and API security best practices. Use when adding authentication or securing API endpoints.",
      "kind": "procedure",
      "rationale": "Security must be implemented consistently across all application entry points",
      "sibling_refs": ["fullstack-feature-architect", "compliance-auditor"]
    }
  ],
  "coverage_notes": "Covers modern web development and security implementation",
  "gaps": ["Performance optimization", "Monitoring and alerting"]
}
```

**Example 5: Enterprise Data Platform**
*Objective: Build event-driven data processing platform with real-time analytics*

```json
{
  "skills": [
    {
      "slug": "event-architecture-designer",
      "name": "Event-Driven Architecture Designer",
      "description": "Design event streaming architectures using Apache Kafka, event sourcing, and CQRS patterns. Use when building real-time data processing or reactive systems.",
      "kind": "authoring",
      "rationale": "Event-driven systems require careful design of event schemas and processing pipelines",
      "sibling_refs": ["data-pipeline-orchestrator", "observability-implementer"]
    },
    {
      "slug": "observability-implementer",
      "name": "Observability Stack Implementer",
      "description": "Implement comprehensive monitoring, logging, and tracing using OpenTelemetry, Prometheus, and Grafana. Use when adding observability to distributed systems.",
      "kind": "procedure",
      "rationale": "Distributed systems require sophisticated monitoring to diagnose issues and ensure reliability",
      "sibling_refs": ["event-architecture-designer", "performance-optimizer"]
    }
  ],
  "coverage_notes": "Covers event-driven architecture and comprehensive system observability",
  "gaps": ["Data governance policies", "Real-time ML inference"]
}
```"""
