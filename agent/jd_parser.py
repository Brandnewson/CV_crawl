"""Job description parser - extracts keywords and classifies jobs."""

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from agent.config import get_claude_model


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

# Order matters: check more specific levels first
SENIORITY_CHECK_ORDER = ["senior", "junior", "junior-mid", "mid"]

SENIORITY_RULES = {
    "junior": ["junior", "graduate", "entry level", "entry-level", "intern", "placement", "trainee"],
    "junior-mid": ["associate", "junior-mid", "early career"],
    "mid": ["mid-level", "mid level", "intermediate", "engineer ii"],
    "senior": ["senior", "sr.", "lead", "principal", "staff", "head of", "director", "vp", "manager"],
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


def classify_seniority(job_title: str, description: str) -> str:
    """
    Pure Python. Title takes priority.
    Default to 'mid' if ambiguous — most unlabelled roles are mid-level.
    Returns: 'junior' | 'junior-mid' | 'mid' | 'senior'
    """
    title_lower = job_title.lower()
    desc_lower = description.lower()

    # Check title first (takes priority), in order of specificity
    for level in SENIORITY_CHECK_ORDER:
        keywords = SENIORITY_RULES[level]
        for kw in keywords:
            if kw in title_lower:
                return level

    # Then check description
    for level in SENIORITY_CHECK_ORDER:
        keywords = SENIORITY_RULES[level]
        for kw in keywords:
            if kw in desc_lower:
                return level

    # Default to mid if ambiguous
    return "mid"


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


def score_bullet_against_keywords(bullet: str, keywords: dict) -> tuple[float, list[str]]:
    """
    Pure Python, no LLM.
    Returns (score, matched_keywords).
    Required keyword hit = 1.0 weight, nice-to-have = 0.5, domain = 0.3.
    Normalise to 0.0–1.0. Case-insensitive substring match.
    """
    bullet_lower = bullet.lower()
    matched = []
    weighted_score = 0.0

    # Weight definitions
    weights = {
        "required_keywords": 1.0,
        "nice_to_have_keywords": 0.5,
        "technical_skills": 0.8,
        "soft_skills": 0.3,
        "domain_keywords": 0.3,
        "seniority_signals": 0.1
    }

    def normalise_keyword(keyword: str) -> str:
        return re.sub(r"\s+", " ", (keyword or "").strip().lower())

    def is_word_phrase(variant: str) -> bool:
        return bool(re.fullmatch(r"[a-z0-9 ]+", variant))

    def build_variants(keyword: str) -> list[str]:
        canonical = normalise_keyword(keyword)
        aliases = KEYWORD_ALIAS_MAP.get(canonical, [])
        variants = [canonical] + [normalise_keyword(alias) for alias in aliases]
        return list(dict.fromkeys([variant for variant in variants if variant]))

    def keyword_in_bullet(keyword: str) -> bool:
        for variant in build_variants(keyword):
            if is_word_phrase(variant):
                pattern = r"\b" + r"\s+".join(re.escape(token) for token in variant.split(" ")) + r"\b"
                if re.search(pattern, bullet_lower):
                    return True
            elif variant in bullet_lower:
                return True
        return False

    for category, weight in weights.items():
        kw_list = keywords.get(category, [])
        for kw in kw_list:
            if not kw:
                continue
            if keyword_in_bullet(str(kw)):
                weighted_score += weight
                matched.append(normalise_keyword(str(kw)))

    matched = list(dict.fromkeys(matched))

    # Normalise to 0.0-1.0 using a fixed realistic max (5.0 = excellent multi-category match)
    normalised_score = min(1.0, weighted_score / 5.0)
    return round(normalised_score, 3), matched


def get_job_from_db(job_id: int, conn, user_id: int = 1) -> Optional[dict]:
    """Fetch job details from database."""
    cur = conn.cursor()
    cur.execute("""
        SELECT id, company, title, description, location, job_url
        FROM jobs
        WHERE id = %s AND user_id = %s
    """, (job_id, user_id))
    row = cur.fetchone()
    cur.close()

    if not row:
        return None

    return {
        "id": row[0],
        "company": row[1],
        "title": row[2],
        "description": row[3],
        "location": row[4],
        "job_url": row[5]
    }
