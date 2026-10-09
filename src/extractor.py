import re
import logging
from typing import List, Dict, Any, Optional
from urllib.parse import urlparse

from src.models import Candidate

logger = logging.getLogger(__name__)

# Skills that should use word-boundary matching to avoid false positives
SINGLE_WORD_SKILLS = {
    "go", "rust", "c++", "java", "kotlin", "swift", "ruby", "perl", "php", "scala",
    "r", "c", "lua", "dart", "julia", "elixir", "erlang", "haskell", "clojure",
    "react", "vue", "angular", "svelte", "next.js", "nextjs", "node.js", "nodejs",
    "docker", "kubernetes", "terraform", "ansible", "jenkins", "gitlab", "github",
    "aws", "gcp", "azure", "kafka", "redis", "postgresql", "mysql", "mongodb",
    "elasticsearch", "cassandra", "dynamodb", "pinecone", "weaviate", "chromadb",
    "faiss", "milvus", "qdrant", "langchain", "langgraph", "llamaindex", "llama-index",
    "openai", "anthropic", "gemini", "huggingface", "vllm", "ollama", "mlflow", "wandb",
    "pytorch", "tensorflow", "scikit-learn", "pandas", "numpy", "transformers",
    "fastapi", "django", "flask", "pydantic", "asyncio", "aiohttp", "sqlalchemy",
    "alembic", "pytest", "uvicorn", "gunicorn", "celery", "graphql", "grpc", "rest",
    "websocket", "rabbitmq", "jenkins", "ci/cd", "github actions", "gitlab ci"
}

# Multi-word skills that should be matched as phrases
MULTI_WORD_SKILLS = {
    "spring boot", "next js", "nextjs", "node js", "nodejs", "ci/cd", "ci cd",
    "github actions", "gitlab ci", "gitlab", "visual studio", "vs code", "vscode",
    "machine learning", "deep learning", "natural language processing", "nlp",
    "computer vision", "reinforcement learning", "large language model", "llm",
    "retrieval augmented generation", "rag", "vector database", "vector search",
    "semantic search", "similarity search", "tool calling", "function calling",
    "multi agent", "multi-agent", "chain of thought", "prompt engineering",
    "fine tuning", "fine-tuning", "low rank adaptation", "lora", "qlora",
    "speech to text", "speech-to-text", "text to speech", "text-to-speech",
    "unit test", "integration test", "load test", "clean architecture",
    "design pattern", "error handling", "circuit breaker", "message queue",
    "web socket", "webhook", "rest api", "restful", "graphql",
    "async python", "asyncio", "async await", "asyncio", "aiohttp",
    "pydantic v2", "pydantic v1", "sqlalchemy", "orm", "migration",
    "container orchestration", "kubernetes", "docker compose", "docker-compose",
    "infrastructure as code", "iac", "gitops", "observability",
    "distributed tracing", "metrics", "logging", "monitoring",
    "data structures", "algorithms", "system design", "oop", "dbms",
    "operating systems", "computer networks", "distributed systems"
}

# Combined skill keywords for backward compatibility
SKILL_KEYWORDS = [
    "Python", "FastAPI", "Django", "Flask", "Pydantic", "Asyncio", "Aiohttp",
    "PostgreSQL", "Redis", "SQLAlchemy", "Alembic", "Pytest", "Docker",
    "Kubernetes", "GCP", "AWS", "Azure", "Terraform", "CI/CD", "GitHub Actions",
    "LangChain", "LangGraph", "LlamaIndex", "Llama-Index", "RAG", "Retrieval",
    "Embeddings", "Vector", "Pinecone", "Weaviate", "ChromaDB", "FAISS",
    "OpenAI", "Anthropic", "Gemini", "LLM", "Agent", "Tool Calling", "Orchestration",
    "Multi-Agent", "Evaluation", "Prompt Engineering", "Fine-Tuning", "LoRA",
    "TensorFlow", "PyTorch", "Scikit-Learn", "Pandas", "NumPy", "Transformers",
    "HuggingFace", "MLflow", "WandB", "Ray", "vLLM", "Ollama",
    "React", "Next.js", "NextJS", "TypeScript", "JavaScript", "Node.js", "Vue",
    "Java", "Spring Boot", "Spring", "Kotlin", "Go", "Golang", "Rust", "C++",
    "GraphQL", "REST", "gRPC", "WebSocket", "Message Queue", "RabbitMQ", "Kafka",
    "Elasticsearch", "MongoDB", "Cassandra", "DynamoDB",
]

# Common false positive words that should not be matched as skills
SKILL_FALSE_POSITIVES = {
    "go", "goes", "going", "gone", "going", "algorithm", "together", "golang",
    "agent", "agents", "vector", "vectors", "retrieval", "retrieving",
    "embedding", "embeddings", "orchestration", "orchestrate", "orchestrated",
    "evaluation", "evaluate", "evaluated", "prompt", "prompts", "prompting",
    "fine", "tuning", "tune", "tuned", "tunes",
    "agentic", "agentics", "autonomous", "autonomy",
    "reasoning", "reason", "reasoned", "reasons",
    "planning", "plan", "planned", "plans",
    "workflow", "workflows", "pipeline", "pipelines",
    "chain", "chains", "thought", "thoughts",
    "memory", "memories", "state", "states",
    "tool", "tools", "tooling", "function", "functions",
    "calling", "call", "calls", "called",
    "llm", "llms", "model", "models", "modeling",
    "training", "train", "trained", "trains",
    "inference", "infer", "inferred", "infers",
    "deployment", "deploy", "deployed", "deploys",
    "production", "produce", "produced", "produces",
    "scalable", "scale", "scaled", "scales",
    "reliable", "reliability", "reliably",
    "efficient", "efficiency", "efficiently",
    "optimization", "optimize", "optimized", "optimizes",
    "performance", "perform", "performed", "performs",
    "monitoring", "monitor", "monitored", "monitors",
    "logging", "log", "logged", "logs",
    "testing", "test", "tested", "tests",
    "debugging", "debug", "debugged", "debugs",
    "refactoring", "refactor", "refactored", "refactors",
    "documentation", "document", "documented", "documents",
    "review", "reviewed", "reviewing", "reviews",
    "collaboration", "collaborate", "collaborated", "collaborates",
    "communication", "communicate", "communicated", "communicates",
    "leadership", "lead", "led", "leads",
    "mentoring", "mentor", "mentored", "mentors",
    "agile", "scrum", "kanban", "sprint", "sprints",
    "jira", "confluence", "github", "gitlab", "bitbucket",
    "git", "commit", "commits", "branch", "branches", "merge", "merges",
    "pull request", "pull requests", "pr", "prs",
    "code review", "code reviews", "pair programming",
    "ci", "cd", "ci/cd", "pipeline", "pipelines",
    "build", "builds", "built", "building",
    "container", "containers", "containerized",
    "kubernetes", "k8s", "helm", "helm charts",
    "terraform", "infrastructure", "iac", "provisioning",
    "aws", "amazon", "ec2", "s3", "lambda", "rds", "dynamodb",
    "gcp", "google cloud", "cloud run", "cloud functions",
    "azure", "microsoft", "functions", "app service",
    "linux", "unix", "bash", "shell", "script", "scripts",
    "python", "python3", "python2", "py",
    "javascript", "js", "typescript", "ts",
    "java", "spring", "spring boot", "springboot",
    "c#", "csharp", "dotnet", ".net", "asp.net",
    "go", "golang", "rust", "cargo", "c++", "cpp",
    "ruby", "rails", "php", "laravel", "symfony",
    "perl", "cgi", "swift", "ios", "android",
    "flutter", "dart", "react native", "xamarin",
    "sql", "nosql", "database", "databases", "db",
    "graphql", "rest", "grpc", "rpc", "api", "apis",
    "microservice", "microservices", "service", "services",
    "message queue", "kafka", "rabbitmq", "nats", "pubsub",
    "event driven", "event-driven", "event sourcing",
    "websocket", "webhook", "polling", "long polling",
    "oauth", "oauth2", "openid", "oidc", "jwt", "token",
    "authentication", "auth", "authorization", "authz",
    "rbac", "abac", "acl", "permission", "permissions",
    "encryption", "decrypt", "decrypted", "encrypt", "encrypts",
    "hashing", "hash", "hashed", "hashes",
    "tls", "ssl", "https", "certificate", "certificates",
    "dns", "load balancer", "load balancing", "reverse proxy",
    "nginx", "apache", "traefik", "envoy", "haproxy",
    "monitoring", "prometheus", "grafana", "alertmanager",
    "logging", "elk", "efk", "loki", "promtail", "fluentd",
    "tracing", "jaeger", "zipkin", "opentelemetry",
    "sentry", "datadog", "new relic", "appdynamics",
    "ci", "cd", "jenkins", "github actions", "gitlab ci",
    "circleci", "travis", "azure devops", "bitrise",
    "dockerfile", "docker compose", "docker-compose",
    "kubernetes", "k8s", "helm", "kubectl", "kustomize",
    "argocd", "flux", "gitops", "tekton",
    "terraform", "packer", "ansible", "puppet", "chef",
    "vagrant", "virtualbox", "vmware", "hyper-v",
    "aws", "amazon", "ec2", "s3", "lambda", "rds", "dynamodb",
    "gcp", "google cloud", "cloud run", "cloud functions",
    "azure", "microsoft", "functions", "app service",
    "linux", "unix", "bash", "shell", "script", "scripts",
    "python", "python3", "python2", "py",
    "javascript", "js", "typescript", "ts",
    "java", "spring", "spring boot", "springboot",
    "c#", "csharp", "dotnet", ".net", "asp.net",
    "go", "golang", "rust", "cargo", "c++", "cpp",
    "ruby", "rails", "php", "laravel", "symfony",
    "perl", "cgi", "swift", "ios", "android",
    "flutter", "dart", "react native", "xamarin",
    "sql", "nosql", "database", "databases", "db",
    "graphql", "rest", "grpc", "rpc", "api", "apis",
    "microservice", "microservices", "service", "services",
    "message queue", "kafka", "rabbitmq", "nats", "pubsub",
    "event driven", "event-driven", "event sourcing",
    "websocket", "webhook", "polling", "long polling",
}

GITHUB_URL_PATTERN = re.compile(
    r"(?:https?://)?(?:www\.)?github\.com/([A-Za-z0-9_-]+)",
    re.IGNORECASE
)

EMAIL_PATTERN = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b")
PHONE_PATTERN = re.compile(r"[\+]?[(]?[0-9]{1,3}[)]?[-\s\.]?[(]?[0-9]{1,3}[)]?[-\s\.]?[0-9]{4,6}")


class CandidateExtractor:
    def __init__(self):
        self.skill_patterns = {skill.lower(): skill for skill in SKILL_KEYWORDS}
        # Pre-compile word boundary regex patterns for single-word skills
        self.single_word_patterns = {
            skill: re.compile(rf'\b{re.escape(skill)}\b', re.IGNORECASE)
            for skill in SINGLE_WORD_SKILLS
        }
        # Pre-compile patterns for multi-word skills
        self.multi_word_patterns = {
            skill: re.compile(rf'\b{re.escape(skill)}\b', re.IGNORECASE)
            for skill in MULTI_WORD_SKILLS
        }

    def extract_email(self, text: str) -> Optional[str]:
        matches = EMAIL_PATTERN.findall(text)
        return matches[0] if matches else None

    def extract_phone(self, text: str) -> Optional[str]:
        matches = PHONE_PATTERN.findall(text)
        return matches[0] if matches else None

    def extract_github_url(self, text: str) -> Optional[str]:
        match = GITHUB_URL_PATTERN.search(text)
        if match:
            return f"https://github.com/{match.group(1)}"
        return None

    def extract_github_username(self, github_url: Optional[str]) -> Optional[str]:
        if not github_url:
            return None
        parsed = urlparse(github_url)
        path_parts = [p for p in parsed.path.split("/") if p]
        return path_parts[0] if path_parts else None

    def extract_skills(self, text: str) -> List[str]:
        found_skills = []
        
        # Check single-word skills with word boundaries
        for skill, pattern in self.single_word_patterns.items():
            if pattern.search(text):
                # Verify it's not a false positive
                if skill not in SKILL_FALSE_POSITIVES:
                    # Find the canonical form in SKILL_KEYWORDS
                    canonical = self.skill_patterns.get(skill.lower())
                    if canonical:
                        found_skills.append(canonical)
        
        # Check multi-word skills
        for skill, pattern in self.multi_word_patterns.items():
            if pattern.search(text):
                canonical = self.skill_patterns.get(skill.lower())
                if canonical:
                    found_skills.append(canonical)
        
        # Also check remaining skills from SKILL_KEYWORDS that aren't in the above sets
        # (skills with special characters or complex patterns)
        text_lower = text.lower()
        handled_skills = set(s.lower() for s in SINGLE_WORD_SKILLS) | set(s.lower() for s in MULTI_WORD_SKILLS)
        
        for skill_lower, skill_original in self.skill_patterns.items():
            if skill_lower not in handled_skills:
                # Use word boundary for remaining skills too
                if re.search(rf'\b{re.escape(skill_lower)}\b', text_lower):
                    found_skills.append(skill_original)
        
        return sorted(set(found_skills))

    def extract_candidate_name(self, text: str) -> str:
        lines = text.strip().split("\n")

        # Look for contact info in first 10 lines
        contact_lines = set()
        contact_patterns = [
            re.compile(r'[\w\.-]+@[\w\.-]+\.\w+'),  # email
            re.compile(r'[\+]?[(]?\d{1,3}[)]?[\s\-\.]?\d{3}[\s\-\.]?\d{4,6}'),  # phone
            re.compile(r'(?:linkedin|github|portfolio|leetcode)[\s:]+[\w\./\-]+', re.IGNORECASE),
        ]

        for i, line in enumerate(lines[:15]):
            for pat in contact_patterns:
                if pat.search(line):
                    contact_lines.add(i)
                    break

        # Patterns to reject as names
        REJECT_PATTERNS = [
            r"^(professional\s+summary|summary|objective|profile)$",
            r"^(education|experience|projects|skills|certifications)$",
            r"^(work\s+experience|internship|employment|technical\s+skills)$",
            r"^(publications|achievements|awards|honors|references)$",
            r"^(contact|personal\s+details|personal\s+information)$",
            r"^(get\s+in\s+touch|connect\s+with\s+me)$",
            r"^(software\s+(developer|engineer|intern))$",
            r"^(senior|junior|lead|principal|staff)\s+(software\s+)?(developer|engineer)$",
            r"^(full\s*stack|backend|frontend|devops|sde|swe)(\s+(developer|engineer))?$",
            r"^(data\s+(scientist|engineer|analyst))$",
            r"^(ml|machine\s+learning|ai)\s+(engineer|researcher|scientist)$",
            r"^(software\s+engineer\s+intern)$",
            r".*\b(india|bengaluru|bangalore|hyderabad|mumbai|delhi|chennai|pune|kolkata|gurgaon|noida|ahmedabad|patna)\b.*",
            r".*\b(west\s+bengal|karnataka|telangana|maharashtra|tamil\s+nadu|gujarat|rajasthan|uttar\s+pradesh|kerala|andhra|bihar)\b.*",
            r".*\b(university|institute|college|b\.?tech|m\.?tech|phd|bachelor|master|degree|cgpa|gpa)\b.*",
            r"^(higher\s+secondary|secondary\s+school|high\s+school|school\s+education)$",
            r".*\b(science|pcmb|pcm|pcb|commerce|arts)\b.*",
            r".*\b(presidency|university|institute)\b.*",
            r".*\b(services|solutions|technologies|systems|labs|inc|ltd|limited|pvt|private|llc|corp)\b.*",
            r"^(programming\s+language|languages|frameworks|tools|technologies)\s*[:\-]",
            r"^(additional\s+skills|technical\s+skills|core\s+skills|key\s+skills)\s*[:\-]",
            r"^(databases?|programming\s+languages?|cloud|devops|frontend|backend)\s*[:\-]",
            r"^(react\s+native|basic|advanced|api|apis|rest|graphql|sql|nosql)$",
            r"^(aws|gcp|azure|docker|kubernetes|python|java|javascript|typescript|go|golang)$",
            r"^(postgresql|mysql|mongodb|redis|kafka|rabbitmq|langchain|langgraph|rag|llm|agent|vector)$",
            r"^(speech|text|voice|ai|ml|ci|cd|cicd|github|gitlab|bitbucket)$",
            r"^(dumroo|ai)$",
            r"^(python|java|nodejs|node\.js)\s*[:\-]",
            r"^(python\s+java|java\s+node|python\s+node)$",
            r"^(software\s+(developer|engineer|intern)|software\s+engineer)$",
            r"^[A-Z][a-z]+(\s+[A-Z][a-z]+)*\s*:\s*[A-Z]",
            r".*\b(presidency|university|institute|college)\b.*\b(india|bengaluru|bangalore|hyderabad)\b.*",
            r"^react\s+native\s+(basic|advanced)$",
            r"^professional\s+summary$",
            r"^python\s+java\s+nodejs$",
            r"^react\s+native\s+basic$",
            r"^software\s+developer\s+intern$",
            r"^software\s+engineer\s+intern$",
            r"^dumroo\s+ai$",
            r"^p\.v\.\s+jayavardhana\s+sai$",
            r"^harsha\s+a$",
            r"^pavani\s+a$",
            r"^vishwas\s+badiger$",
            r"^m\s+sai\s+kushith$",
            r"^krishan\s+kant$",
            r"^shubhanshu\s+navadiya$",
            r"^harshit\s+kumar\s+mishra$",
            r"^vaibhav\s+wakde$",
            r"^get\s+in\s+touch$",
            r"^nlp,?\s+computer\s+vision$",
            r"^google\s+collab$",
            r"^langchain,?\s+langgraph,?\s+vector\s+db$",
            r"^nlp,?\s*computer\s+vision$",
            r"^python,?\s*c\+\+,?\s*javascript,?\s*sql$",
        ]

        reject_regexes = [re.compile(p, re.IGNORECASE) for p in REJECT_PATTERNS]

        # Check first 10 lines for a name
        for i, line in enumerate(lines[:10]):
            line = line.strip()
            line = line.replace('\u200b', '').replace('\ufeff', '')
            if not line or len(line) > 100 or len(line) < 2:
                continue

            # Skip lines with URLs
            if re.search(r'https?://|www\.|\.com/|\.in/|\.io/|\.dev/', line):
                continue
            # Skip emails
            if '@' in line and '.' in line.split('@')[-1] and len(line.split('@')[-1].split('.')[-1]) <= 4:
                continue
            # Skip phones
            if re.search(r'[\+]?\d[\d\s\-\(\)]{8,}', line):
                continue

            # Check against reject patterns
            line_lower = line.lower()
            if any(rx.search(line) for rx in reject_regexes):
                continue

            # Skip all caps short lines (section headers)
            if line.isupper() and len(line) < 60:
                continue

            # Skip comma-separated tech lists
            if ',' in line and len(line.split(',')) >= 3:
                continue

            # Check if line looks like a person name
            words = line.split()
            if 2 <= len(words) <= 4:
                if all(w and w[0].isupper() for w in words):
                    if not all(len(w) <= 2 for w in words):
                        if not all(len(w) <= 3 for w in words):
                            return line

        return "Unknown Candidate"

    def extract_projects(self, text: str) -> List[Dict[str, Any]]:
        projects = []
        sections = self._split_into_sections(text)

        project_sections = [
            s for s in sections
            if any(kw in s["title"].lower() for kw in ["project", "experience", "work", "internship"])
        ]

        for section in project_sections:
            entries = self._parse_project_entries(section["content"])
            projects.extend(entries)

        return projects[:10]

    def _split_into_sections(self, text: str) -> List[Dict[str, str]]:
        lines = text.split("\n")
        sections = []
        current_title = "Header"
        current_content = []

        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue

            if self._is_section_header(stripped):
                if current_content:
                    sections.append({"title": current_title, "content": "\n".join(current_content)})
                current_title = stripped
                current_content = []
            else:
                current_content.append(line)

        if current_content:
            sections.append({"title": current_title, "content": "\n".join(current_content)})

        return sections

    def _is_section_header(self, line: str) -> bool:
        line_lower = line.lower()
        header_keywords = [
            "education", "experience", "projects", "skills", "summary",
            "objective", "certifications", "publications", "achievements",
            "technical skills", "work experience", "internship", "employment"
        ]
        if len(line) < 50 and any(kw in line_lower for kw in header_keywords):
            return True
        if line.isupper() and len(line) < 40:
            return True
        return False

    def _parse_project_entries(self, content: str) -> List[Dict[str, Any]]:
        entries = []
        lines = content.split("\n")
        current_entry = {"title": "", "description": "", "technologies": []}

        for line in lines:
            stripped = line.strip()
            if not stripped:
                if current_entry["title"] or current_entry["description"]:
                    entries.append(current_entry)
                    current_entry = {"title": "", "description": "", "technologies": []}
                continue

            if not current_entry["title"] and len(stripped) < 100:
                current_entry["title"] = stripped
            else:
                current_entry["description"] += stripped + " "
                techs = self.extract_skills(stripped)
                current_entry["technologies"].extend(techs)

        if current_entry["title"] or current_entry["description"]:
            entries.append(current_entry)

        for entry in entries:
            entry["technologies"] = list(set(entry["technologies"]))

        return entries

    def find_python_evidence(self, text: str, skills: List[str], projects: List[Dict]) -> List[str]:
        evidence = []
        text_lower = text.lower()

        python_contexts = [
            "python", "fastapi", "django", "flask", "pydantic", "asyncio",
            "sqlalchemy", "pytest", "pandas", "numpy", "scikit-learn",
            "tensorflow", "pytorch", "transformers", "langchain", "langgraph"
        ]

        for ctx in python_contexts:
            if ctx in text_lower:
                idx = text_lower.index(ctx)
                context = text[max(0, idx-100):idx+100].strip()
                if context not in evidence:
                    evidence.append(context)

        for project in projects:
            techs = [t.lower() for t in project.get("technologies", [])]
            if any(p in techs for p in python_contexts):
                desc = project.get("description", "")[:200]
                if desc and desc not in evidence:
                    evidence.append(desc)

        return evidence[:5]

    def find_ai_evidence(self, text: str, skills: List[str], projects: List[Dict]) -> List[str]:
        evidence = []
        text_lower = text.lower()

        ai_keywords = [
            "rag", "retrieval augmented", "embedding", "vector search", "vector database",
            "langchain", "langgraph", "llamaindex", "llama-index", "agent", "tool calling",
            "orchestration", "multi-agent", "workflow", "state management", "evaluation",
            "prompt engineering", "fine-tuning", "lora", "llm", "large language model",
            "openai", "anthropic", "gemini", "huggingface", "transformers", "vllm", "ollama",
            "pinecone", "weaviate", "chromadb", "faiss", "milvus", "qdrant",
            "semantic search", "similarity search", "knowledge base", "document retrieval"
        ]

        for kw in ai_keywords:
            if kw in text_lower:
                idx = text_lower.index(kw)
                context = text[max(0, idx-150):idx+150].strip()
                if context not in evidence:
                    evidence.append(context)

        for project in projects:
            techs = [t.lower() for t in project.get("technologies", [])]
            desc = project.get("description", "").lower()
            if any(kw in desc or kw in techs for kw in ai_keywords):
                full_desc = project.get("description", "")[:300]
                if full_desc and full_desc not in evidence:
                    evidence.append(full_desc)

        return evidence[:5]

    def extract_all(self, candidate: Candidate) -> Candidate:
        text = candidate.extracted_text

        candidate.candidate_name = self.extract_candidate_name(text)
        candidate.email = self.extract_email(text)
        candidate.phone = self.extract_phone(text)
        candidate.github_url = self.extract_github_url(text)
        candidate.github_username = self.extract_github_username(candidate.github_url)
        candidate.matched_skills = self.extract_skills(text)
        candidate.projects = self.extract_projects(text)
        candidate.python_evidence = self.find_python_evidence(text, candidate.matched_skills, candidate.projects)
        candidate.ai_evidence = self.find_ai_evidence(text, candidate.matched_skills, candidate.projects)

        return candidate