"""LLM prompts for the five core workshop operations.

Public API:
    ProposeSkillSetPrompt -> Generate initial skill set for project
    DraftSkillBodyPrompt -> Draft individual skill bodies with resources
    ProposeBacklogPrompt -> Generate phase-based backlog from skills
    DraftCardPrompt -> Draft individual card sections
    SuggestTechStackPrompt -> Suggest technologies for dimensions
"""

from app.prompts.propose_skillset import ProposeSkillSetPrompt

__all__ = [
    "ProposeSkillSetPrompt",
    # Future prompts will be added here as they're implemented
    # "DraftSkillBodyPrompt",
    # "ProposeBacklogPrompt",
    # "DraftCardPrompt",
    # "SuggestTechStackPrompt",
]
