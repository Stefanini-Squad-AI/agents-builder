"""Reference PoC seed content.

Each subdirectory ships one reference project that doubles as a few-shot
exemplar for the LLM prompts and as a working example of the .agents/
contract. Loaded by `seeder.seed_reference_pocs()`.

Directory shape (per project):

    ref-<slug>/
    ├── project.yaml      identity + LLM config (slug, name, objective,
    │                     card_code_prefix, llm_*, etc.)
    ├── qa.yaml           the 7 Q&A answers (first 3 required)
    ├── tech.yaml         tech panorama picks (dimension_slug -> [{item_slug,
    │                     role}, ...]); supports user_added items via
    │                     `{free_form_name, role}`
    ├── phases.yaml       ordered list of phases (code, name, description)
    ├── skills/<slug>.yaml
    │                     one file per skill: name, description, kind, body
    │                     plus optional `resources: [{filename, language,
    │                     content}, ...]`
    └── cards/<code>.yaml
                          one file per card: code, phase_code, title, type,
                          story_points, priority, status, human_gate,
                          human_gate_checklist, skills, depends_on,
                          parallel_with, context, task, outputs,
                          acceptance_criteria, inputs

YAML is chosen over markdown-with-frontmatter for both skills and cards
because the seed loader stays simple (PyYAML only, no custom parser) and
the DB just stores the body_md verbatim. The exporters in Step 1.12 render
DB rows back to the .md-with-frontmatter shape that .agents/ expects.
"""
