"""Skill loader service for discovering and loading pre-built skills.

Skills are stored as SKILL.md files in the skills/ directory.
Each skill directory may also contain a resources/ subdirectory.
"""

from __future__ import annotations

from pathlib import Path
from dataclasses import dataclass, field
import re


@dataclass
class Skill:
    """A pre-built skill for AI agents."""
    
    id: str
    name: str
    description: str
    content: str
    path: str
    has_resources: bool = False
    
    # Parsed sections (optional)
    when_to_use: str = ""
    capabilities: list[str] = field(default_factory=list)
    

class SkillLoader:
    """Discovers and loads skills from the skills directory."""
    
    def __init__(self, skills_dir: Path | None = None):
        if skills_dir is None:
            # Default to the skills directory (parent of this file)
            skills_dir = Path(__file__).parent
        self.skills_dir = skills_dir
    
    def list_skills(self) -> list[Skill]:
        """List all available skills."""
        skills = []
        
        if not self.skills_dir.exists():
            return skills
        
        for skill_dir in sorted(self.skills_dir.iterdir()):
            if not skill_dir.is_dir():
                continue
            
            skill_file = skill_dir / "SKILL.md"
            if not skill_file.exists():
                continue
            
            skill = self._load_skill(skill_dir)
            if skill:
                skills.append(skill)
        
        return skills
    
    def get_skill(self, skill_id: str) -> Skill | None:
        """Get a specific skill by ID."""
        skill_dir = self.skills_dir / skill_id
        if not skill_dir.exists():
            return None
        
        return self._load_skill(skill_dir)
    
    def _load_skill(self, skill_dir: Path) -> Skill | None:
        """Load a skill from a directory."""
        skill_file = skill_dir / "SKILL.md"
        if not skill_file.exists():
            return None
        
        content = skill_file.read_text(encoding="utf-8")
        
        # Parse header (first line starting with #)
        lines = content.split("\n")
        name = skill_dir.name  # Default to directory name
        description = ""
        
        for i, line in enumerate(lines):
            if line.startswith("# "):
                name = line[2:].strip()
                # Description is the next non-empty line
                for j in range(i + 1, len(lines)):
                    if lines[j].strip() and not lines[j].startswith("#"):
                        description = lines[j].strip()
                        break
                break
        
        # Parse "When to Use" section
        when_to_use = self._extract_section(content, "When to Use")
        
        # Parse "Capabilities" section
        capabilities_text = self._extract_section(content, "Capabilities")
        capabilities = self._extract_list_items(capabilities_text)
        
        return Skill(
            id=skill_dir.name,
            name=name,
            description=description,
            content=content,
            path=str(skill_file),
            has_resources=(skill_dir / "resources").exists(),
            when_to_use=when_to_use,
            capabilities=capabilities,
        )
    
    def _extract_section(self, content: str, section_name: str) -> str:
        """Extract a markdown section by header name."""
        pattern = rf"##\s*{re.escape(section_name)}\s*\n(.*?)(?=\n##|\Z)"
        match = re.search(pattern, content, re.DOTALL | re.IGNORECASE)
        if match:
            return match.group(1).strip()
        return ""
    
    def _extract_list_items(self, text: str) -> list[str]:
        """Extract bullet point items from text."""
        items = []
        for line in text.split("\n"):
            line = line.strip()
            # Match numbered lists (1., 2.) or bullet points (-, *)
            if re.match(r"^[\d]+\.\s+\*\*", line) or re.match(r"^[-*]\s+", line):
                # Remove bullet/number and bold markers
                item = re.sub(r"^[\d]+\.\s*|\s*[-*]\s*", "", line)
                item = re.sub(r"\*\*([^*]+)\*\*", r"\1", item)
                # Take just the title part before " - "
                if " - " in item:
                    item = item.split(" - ")[0]
                if item:
                    items.append(item.strip())
        return items


# Pydantic models for API responses
from pydantic import BaseModel, Field


class SkillSummary(BaseModel):
    """Summary of a skill for listing."""
    
    id: str
    name: str
    description: str
    has_resources: bool = False
    capabilities: list[str] = Field(default_factory=list)


class SkillDetail(BaseModel):
    """Full skill details including content."""
    
    id: str
    name: str
    description: str
    content: str
    path: str
    has_resources: bool = False
    when_to_use: str = ""
    capabilities: list[str] = Field(default_factory=list)


def skill_to_summary(skill: Skill) -> SkillSummary:
    """Convert Skill to SkillSummary."""
    return SkillSummary(
        id=skill.id,
        name=skill.name,
        description=skill.description,
        has_resources=skill.has_resources,
        capabilities=skill.capabilities,
    )


def skill_to_detail(skill: Skill) -> SkillDetail:
    """Convert Skill to SkillDetail."""
    return SkillDetail(
        id=skill.id,
        name=skill.name,
        description=skill.description,
        content=skill.content,
        path=skill.path,
        has_resources=skill.has_resources,
        when_to_use=skill.when_to_use,
        capabilities=skill.capabilities,
    )
