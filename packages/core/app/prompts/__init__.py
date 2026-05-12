"""LLM prompts for the five core workshop operations.

Public API:
    ProposeSkillSetPrompt -> Generate initial skill set for project
    DraftSkillBodyPrompt -> Draft individual skill bodies with resources
    ProposeBacklogPrompt -> Generate phase-based backlog from skills
    DraftCardPrompt -> Draft individual card sections
    SuggestTechStackPrompt -> Suggest technologies for dimensions
"""

from app.prompts.draft_card import DraftCardPrompt
from app.prompts.draft_skillbody import DraftSkillBodyPrompt
from app.prompts.propose_backlog import ProposeBacklogPrompt
from app.prompts.propose_skillset import ProposeSkillSetPrompt
from app.prompts.suggest_tech_stack import SuggestTechStackPrompt

__all__ = [
    "DraftCardPrompt",
    "DraftSkillBodyPrompt",
    "ProposeBacklogPrompt",
    "ProposeSkillSetPrompt",
    "SuggestTechStackPrompt",
]
