from __future__ import annotations

import re

SKILL_ALIASES: dict[str, tuple[str, ...]] = {
    "java": ("java", "j2ee", "java/j2ee", "full stack java", "core java", "java se", "java ee"),
    "spring": ("spring", "spring boot", "spring framework", "java spring", "spring mvc", "spring data", "spring security"),
    "hibernate": ("hibernate", "jpa", "jakarta persistence"),
    "rest api": ("rest api", "rest apis", "restful api", "restful apis", "rest", "representational state transfer"),
    "microservices": ("microservice", "microservices"),
    "distributed systems": ("distributed system", "distributed systems"),
    "sql": ("sql", "pl/sql", "tsql"),
    "nosql": ("nosql", "no sql"),
    "postgresql": ("postgresql", "postgres"),
    "mongodb": ("mongodb", "mongo"),
    "git": ("git", "github", "gitlab", "bitbucket"),
    "docker": ("docker",),
    "ci/cd": ("ci/cd", "cicd", "continuous integration", "continuous deployment"),
    "design patterns": ("design pattern", "design patterns", "go4 patterns"),
    "clean architecture": ("clean architecture", "hexagonal architecture", "onion architecture"),
    "debugging": ("debugging", "troubleshooting"),
    "python": ("python",),
    "django": ("django",),
    "fastapi": ("fastapi", "fast api"),
    "javascript": ("javascript", "java script", "js", "ecmascript"),
    "typescript": ("typescript", "type script", "ts"),
    "react": ("react", "react.js", "reactjs"),
    "node.js": ("node.js", "nodejs", "node js"),
    "angular": ("angular", "angular.js", "angularjs"),
    "vue": ("vue", "vue.js", "vuejs"),
    "aws": ("aws", "amazon web services"),
    "azure": ("azure",),
    "kubernetes": ("kubernetes", "k8s"),
    "maven": ("maven", "apache maven"),
    "gradle": ("gradle",),
    "tomcat": ("tomcat", "apache tomcat"),
    "servlets": ("servlet", "servlets", "java servlet"),
    "jsp": ("jsp", "java server pages", "javaserver pages"),
    "jenkins": ("jenkins",),
    "junit": ("junit", "junit5", "testng"),
    "mockito": ("mockito",),
    "kafka": ("kafka", "apache kafka"),
    "redis": ("redis",),
    "rabbitmq": ("rabbitmq",),
    "soap": ("soap", "soap web services", "soap api"),
    "jdbc": ("jdbc",),
    "jms": ("jms", "java message service"),
    "activemq": ("activemq",),
    "agile": ("agile", "agile methodologies", "scrum", "kanban"),
    "ansible": ("ansible",),
    "ant": ("ant", "apache ant"),
    "api": ("api", "api development", "api design", "restful api development"),
    "cassandra": ("cassandra",),
    "confluence": ("confluence",),
    "datadog": ("datadog",),
    "dynamodb": ("dynamodb",),
    "ejb": ("ejb", "enterprise java beans"),
    "elasticsearch": ("elasticsearch", "es", "elastic search"),
    "elk": ("elk", "elastic stack", "elasticsearch logstash kibana"),
    "gcp": ("gcp", "google cloud", "google cloud platform"),
    "grafana": ("grafana",),
    "graphql": ("graphql",),
    "html": ("html", "html5"),
    "css": ("css", "css3"),
    "jboss": ("jboss", "wildfly", "jboss eap"),
    "jira": ("jira",),
    "jsf": ("jsf", "java server faces", "javaserver faces"),
    "json": ("json",),
    "linux": ("linux", "unix", "bash", "shell scripting"),
    "mariadb": ("mariadb",),
    "mysql": ("mysql",),
    "new relic": ("new relic",),
    "oauth": ("oauth", "oauth2", "jwt", "json web token"),
    "oop": ("oop", "object oriented", "object oriented programming"),
    "oracle": ("oracle", "oracle db", "oracle database"),
    "oracle cloud": ("oracle cloud", "oci"),
    "prometheus": ("prometheus",),
    "pulsar": ("pulsar",),
    "sdlc": ("sdlc", "software development life cycle"),
    "slack": ("slack",),
    "solid": ("solid", "solid principles"),
    "splunk": ("splunk",),
    "struts": ("struts", "apache struts"),
    "svn": ("svn", "subversion"),
    "swing": ("swing", "javafx", "awt"),
    "teams": ("microsoft teams", "teams"),
    "terraform": ("terraform", "iac", "infrastructure as code"),
    "testing": ("testing", "unit test", "integration test", "e2e", "tdd", "bdd"),
    "weblogic": ("weblogic", "oracle weblogic"),
    "websphere": ("websphere", "ibm websphere"),
    "xml": ("xml",),
    "yaml": ("yaml", "yml"),
}

GENERIC_SKILL_ANCHORS: set[str] = {
    "entry",
    "entry level",
    "fresher",
    "intern",
    "internship",
    "junior",
    "mid",
    "mid level",
    "senior",
    "lead",
    "principal",
}


def normalize_keyword(value: object) -> str:
    return " ".join(str(value).strip().lower().split())


def normalize_skill_text(value: object) -> str:
    text = str(value or "").lower()
    replacements = {
        "java/j2ee": " java j2ee ",
        "node.js": " nodejs ",
        "react.js": " reactjs ",
        "vue.js": " vuejs ",
        "ci/cd": " cicd ",
    }
    for source, target in replacements.items():
        text = text.replace(source, target)
    return " ".join(re.sub(r"[^a-z0-9+#.]+", " ", text).split())


def normalize_search_text(value: object) -> str:
    text = str(value or "").lower()
    replacements = {
        "c#": " csharp ",
        "c++": " cpp ",
        "node.js": " nodejs ",
        "react.js": " reactjs ",
        "vue.js": " vuejs ",
        "ci/cd": " cicd ",
        "java/j2ee": " java j2ee ",
    }
    for source, target in replacements.items():
        text = text.replace(source, target)
    return " ".join("".join(char if char.isalnum() else " " for char in text).split())


def contains_skill_phrase(text: str, phrase: str) -> bool:
    normalized_phrase = normalize_search_text(phrase)
    if not normalized_phrase:
        return False
    return f" {normalized_phrase} " in f" {text} "


def is_generic_skill_anchor(value: str) -> bool:
    return normalize_keyword(value) in GENERIC_SKILL_ANCHORS


def matches_any_keyword(value: str, keywords: list[str]) -> bool:
    if not value:
        return False
    return any(keyword and (keyword in value or value in keyword) for keyword in keywords)


def resolve_skill_anchor(
    skill_name: str,
    skill_evidence: str,
    skill_normalized: str | None,
    skill_weights: dict[str, int],
) -> str | None:
    normalized = normalize_keyword(skill_normalized or "")
    if normalized in skill_weights:
        return normalized

    haystack = normalize_skill_text(
        " ".join(item for item in [skill_name, skill_evidence, skill_normalized or ""] if item)
    )
    if not haystack:
        return None

    for anchor in skill_weights:
        phrases = [anchor, *SKILL_ALIASES.get(anchor, ())]
        for phrase in phrases:
            normalized_phrase = normalize_skill_text(phrase)
            if normalized_phrase and f" {normalized_phrase} " in f" {haystack} ":
                return anchor
    return None
