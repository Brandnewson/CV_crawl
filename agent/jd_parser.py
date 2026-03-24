"""Job description parser - extracts keywords and classifies jobs."""

import json
import re
from datetime import datetime, timezone
from pathlib import Path

import anthropic

from agent.config import get_claude_model

try:
    from tools.clean_jd import clean_jd
except Exception:  # pragma: no cover - safe fallback for alternate entrypoints
    from unicodedata import normalize as _unicode_normalize

    def clean_jd(raw: str) -> str:
        text = _unicode_normalize("NFKC", raw or "")
        text = re.sub(r"([a-z])([A-Z])", r"\1 \2", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = re.sub(r"[ \t]{2,}", " ", text)
        text = re.sub(r"\xa0", " ", text)
        return text.strip()


ROLE_FAMILIES = {
    "motorsport": [
        "motorsport", "formula 1", "f1", "formula e", "race strategy",
        "lap time", "telemetry", "vehicle dynamics", "tyre model",
        "race engineer", "trackside", "racing", "automotive simulation"
    ],
    "ai-startup": [
        "machine learning", "llm", "large language model", "ai engineer",
        "ml engineer", "foundation model", "inference", "fine-tuning",
        "rag", "embeddings", "ai startup", "deep learning",
        "neural network", "transformer", "generative ai", "nlp", "computer vision"
    ],
    "forward-deployed-swe": [
        "forward deployed", "forward-deployed", "solutions engineer", "field engineer",
        "customer engineering", "implementation engineer", "technical account",
        "customer success engineer", "professional services"
    ],
    "general-swe": []  # fallback
}


KEYWORD_ALIAS_MAP = {
    "ci/cd": ["ci cd", "continuous integration", "continuous delivery", "continuous deployment"],
    "node.js": ["nodejs", "node js", "node"],
    "c#": ["csharp", "c sharp"],
    "c++": ["cpp", "c plus plus"],
    "llms": ["llm", "large language model", "large language models", "generative ai"],
    "typescript": ["ts"],
    "javascript": ["js"],
    "ai": ["artificial intelligence", "applied ai"],
    "machine learning": ["ml"],
    "deep learning": ["dl"],
    "natural language processing": ["nlp"],
    "retrieval-augmented generation": ["rag", "retrieval augmented generation"],
    "vector database": ["vector db", "vector store", "embedding store"],
    "embeddings": ["embedding"],
    "prompt engineering": ["prompt design", "prompt optimisation", "prompt optimization"],
    "model serving": ["inference serving", "model inference", "serving"],
    "fine-tuning": ["finetuning", "fine tuning"],
    "tensorflow": ["tf"],
    "pytorch": ["torch"],
    "hugging face": ["huggingface", "hf"],
    "langchain": ["lang chain"],
    "azure openai": ["azure open ai", "aoai"],
    "openai": ["gpt", "chatgpt"],
    "microsoft copilot studio": ["copilot studio", "power virtual agents"],
    "agentic ai": ["ai agents", "agent workflows", "agentic workflows"],
    "solutions architecture": ["solution architecture", "solution architect", "solutions architect"],
    "system design": ["architecture design", "technical design"],
    "enterprise architecture": ["enterprise solution architecture"],
    "technical leadership": ["tech leadership", "technical lead", "tech lead"],
    "stakeholder management": ["stakeholder communication", "executive communication"],
    "customer-facing": ["customer facing", "client-facing", "client facing"],
    "forward deployed": ["forward-deployed", "fde", "deployed engineer", "field engineer"],
    "implementation": ["implementation engineering", "solution implementation"],
    "professional services": ["ps", "delivery consulting"],
    "customer success": ["customer success engineering", "cse"],
    "discovery": ["requirements discovery", "solution discovery"],
    "api": ["apis", "rest api", "restful api", "http api"],
    "microservices": ["micro-services", "services architecture"],
    "backend": ["server-side", "server side"],
    "frontend": ["front-end", "client-side", "client side"],
    "full-stack": ["full stack", "fullstack"],
    "distributed systems": ["distributed system"],
    "event-driven architecture": ["event driven architecture", "eda"],
    "message queue": ["queue", "messaging"],
    "kafka": ["apache kafka"],
    "rabbitmq": ["rabbit mq"],
    "graphql": ["graph ql"],
    "sql": ["postgres", "postgresql", "mysql", "mssql", "sql server"],
    "nosql": ["non relational", "non-relational"],
    "mongodb": ["mongo", "mongo db"],
    "redis": ["redis cache"],
    "docker": ["container", "containerisation", "containerization", "dockerised", "dockerized"],
    "kubernetes": ["k8s"],
    "terraform": ["iac", "infrastructure as code"],
    "devops": ["dev sec ops", "devsecops", "platform engineering"],
    "observability": ["monitoring", "telemetry", "tracing", "logging"],
    "sre": ["site reliability", "site reliability engineering"],
    "testing": ["automated testing", "test automation", "unit testing", "integration testing"],
    "tdd": ["test-driven development", "test driven development"],
    "agile": ["scrum", "kanban"],
    "aws": ["amazon web services"],
    "azure": ["microsoft azure"],
    "gcp": ["google cloud", "google cloud platform"],
    "serverless": ["lambda", "azure functions", "cloud functions"],
    "react": ["reactjs", "react.js"],
    "vue": ["vuejs", "vue.js"],
    "angular": ["angularjs"],
    "python": ["py"],
    "golang": ["go"],
    "dotnet": [".net", "asp.net", "aspnet", "net core", "dotnet core"],
    "java": ["jvm"],
    "data engineering": ["data pipeline", "etl", "elt"],
    "data modelling": ["data modeling", "schema design"],
    "performance optimisation": ["performance optimization", "latency optimisation", "latency optimization"],
    "security": ["application security", "secure coding", "threat modelling", "threat modeling"],
    "identity and access management": ["iam", "identity access management"],
    "oauth": ["oauth2", "oidc", "openid connect"],
    "documentation": ["technical writing", "design docs", "architecture docs"],
    "mentoring": ["coaching", "developer mentoring"],
}

KEYWORD_EXTRACTION_PROMPT = """Extract keywords from this job description for a {role_family} role.

Job Description:
{description}

Return a JSON object with these exact keys:
- "required_keywords": technologies, skills, or qualifications explicitly marked as required or must-have
- "nice_to_have_keywords": technologies or skills mentioned as preferred, bonus, or nice-to-have
- "technical_skills": programming languages, frameworks, tools, platforms mentioned
- "soft_skills": communication, leadership, collaboration skills mentioned
- "domain_keywords": industry-specific terms, business domain concepts
- "seniority_signals": phrases indicating expected experience level (e.g., "3+ years", "expert in")

Rules:
- Each keyword should be 1-3 words, lowercase
- Extract only keywords actually present in the job description
- Do not invent keywords not mentioned
- Limit each category to 10 most important items
- Return valid JSON only, no markdown formatting"""


PHRASE_SECTION_PATTERNS = {
    "required_phrases": (
        "required",
        "must have",
        "minimum qualifications",
        "qualifications",
    ),
    "nice_to_have_phrases": (
        "nice to have",
        "preferred",
        "bonus",
        "good to have",
    ),
    "day_to_day_phrases": (
        "day-to-day",
        "what you'll do",
        "what you will do",
        "you will",
    ),
    "responsibility_phrases": (
        "responsibilities",
        "responsibility",
        "role will",
        "in this role",
    ),
}


def _extract_phrase_inventory(description: str) -> dict[str, list[str]]:
    lines = [re.sub(r"\s+", " ", line.strip()) for line in (description or "").splitlines()]
    lines = [line for line in lines if line]
    inventory: dict[str, list[str]] = {
        "required_phrases": [],
        "nice_to_have_phrases": [],
        "day_to_day_phrases": [],
        "responsibility_phrases": [],
    }

    def _add(bucket: str, phrase: str) -> None:
        cleaned = re.sub(r"\s+", " ", phrase.strip().lower())
        cleaned = cleaned.strip(" -:;,.")
        if not cleaned:
            return
        if len(cleaned.split()) < 2 or len(cleaned.split()) > 6:
            return
        if cleaned not in inventory[bucket]:
            inventory[bucket].append(cleaned)

    current_bucket = ""
    for line in lines:
        low = line.lower()
        line_text = re.sub(r"^\s*[-*•]+\s*", "", low).strip()
        matched_bucket = ""
        for bucket, markers in PHRASE_SECTION_PATTERNS.items():
            if any(marker in low for marker in markers):
                matched_bucket = bucket
                break
        if matched_bucket:
            current_bucket = matched_bucket
            continue

        if not current_bucket:
            continue

        if len(line_text) > 140:
            continue
        # Keep explicit hyphenated/slash phrases and concise action phrases.
        phrase_candidates: list[str] = []
        phrase_candidates.extend(
            re.findall(r"\b[a-z0-9]+(?:[-/][a-z0-9]+)+(?:\s+[a-z0-9]{2,}){0,2}\b", line_text)
        )
        phrase_candidates.extend(
            [
                " ".join(match)
                for match in re.findall(
                    r"\b([a-z0-9]{2,})\s+([a-z0-9]{2,})\s+([a-z0-9]{2,})(?:\s+([a-z0-9]{2,}))?",
                    line_text,
                )
            ]
        )
        if 2 <= len(line_text.split()) <= 6:
            phrase_candidates.append(line_text)

        for candidate in phrase_candidates[:6]:
            _add(current_bucket, candidate)

    return inventory


def classify_role_family(job_title: str, description: str) -> str:
    """
    Pure Python keyword match. Returns one of the four family strings.
    If multiple families match, pick the one with the most hits.
    Default to 'general-swe' if no match.
    """
    combined = f"{job_title} {description}".lower()

    scores = {}
    for family, keywords in ROLE_FAMILIES.items():
        if not keywords:  # Skip general-swe (fallback)
            continue
        score = sum(1 for kw in keywords if kw in combined)
        if score > 0:
            scores[family] = score

    if not scores:
        return "general-swe"

    # Return family with highest score
    return max(scores, key=scores.get)


def _log_api_usage(
    operation: str,
    input_tokens: int,
    output_tokens: int,
    user_id: int = 1
) -> None:
    """Log API usage to logs/api_usage.jsonl."""
    log_path = Path(__file__).parent.parent / "logs" / "api_usage.jsonl"
    log_path.parent.mkdir(exist_ok=True)

    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "user_id": user_id,
        "operation": operation,
        "model": "claude-haiku-4-5",
        "input_tokens": input_tokens,
        "output_tokens": output_tokens
    }

    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


def extract_keywords(job_description: str, role_family: str, client, user_id: int = 1) -> dict:
    """
    Call claude-haiku-4-5 to extract keywords from job description.

    Returns:
    {
        "required_keywords": [...],
        "nice_to_have_keywords": [...],
        "technical_skills": [...],
        "soft_skills": [...],
        "domain_keywords": [...],
        "seniority_signals": [...]
    }
    """
    prompt = KEYWORD_EXTRACTION_PROMPT.format(
        role_family=role_family,
        description=job_description[:8000]  # Truncate very long descriptions
    )

    response = client.messages.create(
        model=get_claude_model(),
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}]
    )

    # Log usage
    _log_api_usage(
        operation="extract_keywords",
        input_tokens=response.usage.input_tokens,
        output_tokens=response.usage.output_tokens,
        user_id=user_id
    )

    # Parse response
    content = response.content[0].text.strip()

    # Handle potential markdown code blocks
    if content.startswith("```"):
        content = re.sub(r"^```(?:json)?\n?", "", content)
        content = re.sub(r"\n?```$", "", content)

    try:
        keywords = json.loads(content)
    except json.JSONDecodeError:
        # Return empty structure if parsing fails
        keywords = {
            "required_keywords": [],
            "nice_to_have_keywords": [],
            "technical_skills": [],
            "soft_skills": [],
            "domain_keywords": [],
            "seniority_signals": []
        }

    # Ensure all expected keys exist
    default_keys = [
        "required_keywords", "nice_to_have_keywords", "technical_skills",
        "soft_skills", "domain_keywords", "seniority_signals"
    ]
    for key in default_keys:
        if key not in keywords:
            keywords[key] = []

    return keywords


def extract_keywords_safe(
    job_description: str,
    job_title: str = "",
    user_id: int = 1,
) -> dict:
    """Safe one-call keyword extraction wrapper for orchestrators/scripts."""
    cleaned = clean_jd(job_description or "")
    role_family = classify_role_family(job_title or "", cleaned)
    try:
        client = anthropic.Anthropic()
        keywords = extract_keywords(
            job_description=cleaned,
            role_family=role_family,
            client=client,
            user_id=user_id,
        )
    except Exception:
        text = cleaned.lower()
        required_seed: list[str] = []
        nice_seed: list[str] = []
        for canonical, aliases in KEYWORD_ALIAS_MAP.items():
            variants = [canonical] + aliases
            if any(str(variant).lower() in text for variant in variants):
                required_seed.append(canonical)
        for phrase in ("end-to-end", "customer-facing", "real-time", "forward deployed", "machine learning"):
            if phrase in text and phrase not in required_seed:
                required_seed.append(phrase)
        keywords = {
            "required_keywords": required_seed[:25],
            "nice_to_have_keywords": nice_seed[:15],
            "technical_skills": [],
            "soft_skills": [],
            "domain_keywords": [],
            "seniority_signals": [],
        }

    def _normalise(values: list[str]) -> list[str]:
        out: list[str] = []
        for value in values:
            text = re.sub(r"\s+", " ", str(value or "").strip())
            if text and text not in out:
                out.append(text)
        return out

    required = _normalise(
        keywords.get("required_keywords", [])
        + keywords.get("technical_skills", [])
        + keywords.get("domain_keywords", [])
    )
    nice_to_have = _normalise(
        keywords.get("nice_to_have_keywords", [])
        + keywords.get("soft_skills", [])
        + keywords.get("seniority_signals", [])
    )
    phrase_inventory = _extract_phrase_inventory(cleaned)
    return {
        "keywords": {
            "required": required,
            "nice_to_have": nice_to_have,
            "phrase_inventory": phrase_inventory,
        },
        "role_family": role_family,
    }


