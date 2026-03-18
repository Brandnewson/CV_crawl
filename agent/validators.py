"""Pydantic models and validators for CV generation."""

import re
from pydantic import BaseModel, field_validator, model_validator
from pathlib import Path
from typing import Optional, List


BANNED_PHRASES = [
    "fast-paced environment", "passion for", "i am excited", "team player",
    "results-driven", "leveraged synergies",
    "passionate about", "dynamic team"
]

# Common action verbs for CV bullets (past and present tense)
ACTION_VERBS = {
    # Past tense
    "achieved", "administered", "advised", "analysed", "analyzed", "applied",
    "architected", "automated", "built", "collaborated", "completed", "configured",
    "contributed", "coordinated", "created", "debugged", "delivered", "deployed",
    "designed", "developed", "diagnosed", "directed", "documented", "drove",
    "enabled", "engineered", "enhanced", "established", "evaluated", "executed",
    "expanded", "facilitated", "fixed", "formulated", "generated", "grew",
    "guided", "identified", "implemented", "improved", "increased", "initiated",
    "innovated", "integrated", "introduced", "investigated", "launched", "led",
    "maintained", "managed", "mentored", "migrated", "modelled", "modeled",
    "monitored", "negotiated", "operated", "optimised", "optimized", "orchestrated",
    "organised", "organized", "owned", "performed", "pioneered", "planned",
    "presented", "processed", "produced", "programmed", "prototyped", "provided",
    "published", "raised", "ran", "realised", "realized", "rebuilt", "received",
    "recommended", "reduced", "refactored", "refined", "replaced", "reported",
    "researched", "resolved", "restructured", "retrieved", "reviewed", "revised",
    "rewrote", "scaled", "secured", "shipped", "simplified", "solved", "sparked",
    "standardised", "standardized", "streamlined", "strengthened", "supervised",
    "supported", "surpassed", "taught", "tested", "trained", "transformed",
    "translated", "triaged", "troubleshot", "unified", "updated", "upgraded",
    "validated", "verified", "visualised", "visualized", "won", "wrote",
    # Present tense (for current roles)
    "achieve", "administer", "advise", "analyse", "analyze", "apply",
    "architect", "automate", "build", "collaborate", "complete", "configure",
    "contribute", "coordinate", "create", "debug", "deliver", "deploy",
    "design", "develop", "diagnose", "direct", "document", "drive",
    "enable", "engineer", "enhance", "establish", "evaluate", "execute",
    "expand", "facilitate", "fix", "formulate", "generate", "grow",
    "guide", "identify", "implement", "improve", "increase", "initiate",
    "innovate", "integrate", "introduce", "investigate", "launch", "lead",
    "maintain", "manage", "mentor", "migrate", "model", "monitor",
    "negotiate", "operate", "optimise", "optimize", "orchestrate", "organise",
    "organize", "own", "perform", "pioneer", "plan", "present", "process",
    "produce", "program", "prototype", "provide", "publish", "raise", "run",
    "realise", "realize", "rebuild", "receive", "recommend", "reduce",
    "refactor", "refine", "replace", "report", "research", "resolve",
    "restructure", "retrieve", "review", "revise", "rewrite", "scale",
    "secure", "ship", "simplify", "solve", "spark", "standardise", "standardize",
    "streamline", "strengthen", "supervise", "support", "surpass", "teach",
    "test", "train", "transform", "translate", "triage", "troubleshoot",
    "unify", "update", "upgrade", "validate", "verify", "visualise", "visualize",
    "win", "write"
}

HARD_CHAR_LIMIT = 110
SOFT_CHAR_LIMIT = 108


class BulletValidationError(ValueError):
    """Raised when bullet validation fails with a hard error."""
    pass


class BulletValidationWarning:
    """Container for validation warnings (non-fatal)."""
    def __init__(self, message: str):
        self.message = message


class BulletCandidate(BaseModel):
    """A candidate bullet point for a CV slot."""
    text: str
    source: str                  # 'master_bullets' | 'story_draft' | 'rephrasing'
    section: str                 # 'work_experience' | 'technical_projects'
    subsection: str              # employer or project name
    tags: List[str] = []
    role_families: List[str] = []
    relevance_score: float = 0.0  # 0.0–1.0
    char_count: int = 0          # computed on init
    over_soft_limit: bool = False  # char_count > 90
    keyword_hits: List[str] = []
    rephrase_generation: int = 0 # 0 = original, increments per rephrase
    warnings: List[str] = []     # non-fatal validation warnings

    @field_validator('text')
    @classmethod
    def validate_text_not_empty(cls, v: str) -> str:
        """Text must not be empty."""
        if not v or not v.strip():
            raise BulletValidationError("Bullet text cannot be empty")
        return v.strip()

    @field_validator('source')
    @classmethod
    def validate_source(cls, v: str) -> str:
        """Source must be one of the allowed values."""
        allowed = {'master_bullets', 'story_draft', 'rephrasing'}
        if v not in allowed:
            raise BulletValidationError(f"Source must be one of {allowed}, got '{v}'")
        return v

    @field_validator('section')
    @classmethod
    def validate_section(cls, v: str) -> str:
        """Section must be one of the allowed values."""
        allowed = {'work_experience', 'technical_projects'}
        if v not in allowed:
            raise BulletValidationError(f"Section must be one of {allowed}, got '{v}'")
        return v

    @field_validator('relevance_score')
    @classmethod
    def validate_relevance_score(cls, v: float) -> float:
        """Relevance score must be between 0 and 1."""
        if not 0.0 <= v <= 1.0:
            raise BulletValidationError(f"Relevance score must be 0.0-1.0, got {v}")
        return v

    @model_validator(mode='after')
    def compute_and_validate(self) -> 'BulletCandidate':
        """Compute char_count, over_soft_limit, and run validation rules."""
        warnings = []

        # Compute char_count
        self.char_count = len(self.text)

        # Compute over_soft_limit
        self.over_soft_limit = self.char_count > SOFT_CHAR_LIMIT

        # HARD ERROR: char_count > 120
        if self.char_count > HARD_CHAR_LIMIT:
            raise BulletValidationError(
                f"Bullet exceeds {HARD_CHAR_LIMIT} characters ({self.char_count}): '{self.text[:50]}...'"
            )

        # HARD ERROR: starts with "I "
        if self.text.lower().startswith("i "):
            raise BulletValidationError(
                f"Bullet cannot start with 'I': '{self.text[:50]}...'"
            )

        # HARD ERROR: contains banned punctuation
        if ':' in self.text or ';' in self.text:
            raise BulletValidationError(
                f"Bullet contains banned punctuation (':' or ';'): '{self.text[:50]}...'"
            )

        # HARD ERROR: contains banned phrase
        text_lower = self.text.lower()
        for phrase in BANNED_PHRASES:
            if phrase in text_lower:
                raise BulletValidationError(
                    f"Bullet contains banned phrase '{phrase}': '{self.text[:50]}...'"
                )

        # WARNING: doesn't start with action verb
        first_word = self.text.split()[0].lower().rstrip('.,;:') if self.text.split() else ""
        if first_word not in ACTION_VERBS:
            warnings.append(f"Bullet may not start with action verb: '{first_word}'")

        # WARNING: over soft limit
        if self.over_soft_limit:
            warnings.append(f"Bullet over {SOFT_CHAR_LIMIT} chars ({self.char_count})")

        self.warnings = warnings
        return self


class BulletSlot(BaseModel):
    """A slot in the CV that needs a bullet."""
    slot_index: int
    section: str
    subsection: str
    current_candidate: Optional[BulletCandidate] = None
    rephrase_history: List[BulletCandidate] = []
    is_approved: bool = False

    @field_validator('section')
    @classmethod
    def validate_section(cls, v: str) -> str:
        """Section must be one of the allowed values."""
        allowed = {'work_experience', 'technical_projects'}
        if v not in allowed:
            raise ValueError(f"Section must be one of {allowed}, got '{v}'")
        return v


class CVSelectionPlan(BaseModel):
    """Complete plan for CV generation."""
    job_id: int
    user_id: int = 1
    job_title: str
    company: str
    role_family: str
    seniority_level: str
    required_keywords: List[str]
    nice_to_have_keywords: List[str]
    technical_keywords: List[str]
    work_experience_slots: List[BulletSlot]
    technical_project_slots: List[BulletSlot]
    projects_to_hide: List[str]
    keyword_coverage: dict          # {keyword: slot_indices_that_cover_it}
    uncovered_keywords: List[str]
    keyword_bucket_coverage: dict = {}  # {bucket: [{keyword, status, covering_slots}]}

    @field_validator('role_family')
    @classmethod
    def validate_role_family(cls, v: str) -> str:
        """Role family must be one of the allowed values."""
        allowed = {'motorsport', 'ai-startup', 'forward-deployed-swe', 'general-swe'}
        if v not in allowed:
            raise ValueError(f"Role family must be one of {allowed}, got '{v}'")
        return v

    @field_validator('seniority_level')
    @classmethod
    def validate_seniority_level(cls, v: str) -> str:
        """Seniority level must be one of the allowed values."""
        allowed = {'junior', 'junior-mid', 'mid', 'senior'}
        if v not in allowed:
            raise ValueError(f"Seniority level must be one of {allowed}, got '{v}'")
        return v


class UserSelections(BaseModel):
    """User's final selections for CV generation."""
    job_id: int
    user_id: int = 1
    approved_bullets: List[dict]    # [{slot_index, section, subsection, text, source, rephrase_generation}]
    hidden_projects: List[str]
    header_swaps: List[dict] = []   # [{section, subsection, header_xpath_index, text}]
    session_timestamp: str


def validate_bullet_text(text: str) -> tuple[bool, str, List[str]]:
    """
    Validate bullet text without creating a full BulletCandidate.

    Returns: (is_valid, error_message, warnings)
    - is_valid: True if no hard errors
    - error_message: Empty string if valid, error description otherwise
    - warnings: List of warning messages
    """
    warnings = []

    # Check empty
    if not text or not text.strip():
        return False, "Bullet text cannot be empty", []

    text = text.strip()
    char_count = len(text)

    # Hard error: too long
    if char_count > HARD_CHAR_LIMIT:
        return False, f"Exceeds {HARD_CHAR_LIMIT} characters ({char_count})", []

    # Hard error: starts with I
    if text.lower().startswith("i "):
        return False, "Cannot start with 'I'", []

    # Hard error: banned punctuation
    if ':' in text or ';' in text:
        return False, "Bullet contains banned punctuation (':' or ';')", []

    # Hard error: banned phrase
    text_lower = text.lower()
    for phrase in BANNED_PHRASES:
        if phrase in text_lower:
            return False, f"Contains banned phrase: '{phrase}'", []

    # Warning: over soft limit
    if char_count > SOFT_CHAR_LIMIT:
        warnings.append(f"Over {SOFT_CHAR_LIMIT} characters ({char_count})")

    # Warning: no action verb
    first_word = text.split()[0].lower().rstrip('.,;:') if text.split() else ""
    if first_word not in ACTION_VERBS:
        warnings.append(f"May not start with action verb: '{first_word}'")

    return True, "", warnings
