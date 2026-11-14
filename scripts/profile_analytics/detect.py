"""Identify technologies evidenced by a repository's manifests and tooling files."""

from collections.abc import Mapping
import json
from pathlib import PurePosixPath
import re
import tomllib


TECHNOLOGY_ORDER = (
    "Vue", "Nuxt", "React", "Next.js", "Storybook", "Vite",
    "Express", "Fastify", "NestJS", "Laravel", "Symfony",
    "Django", "FastAPI", "Flask", "Gin", "Echo", "Fiber", "Chi", "gRPC",
    "PostgreSQL", "Redis", "ClickHouse", "MySQL", "MongoDB",
    "Kafka", "RabbitMQ", "Prometheus", "Grafana",
    "Docker", "Kubernetes", "Helm", "Terraform", "GitHub Actions", "GitLab CI",
)

NPM = {
    "vue": "Vue", "@vue/compat": "Vue",
    "nuxt": "Nuxt", "nuxt3": "Nuxt", "nuxt-edge": "Nuxt",
    "react": "React", "next": "Next.js", "storybook": "Storybook",
    "vite": "Vite",
    "express": "Express", "fastify": "Fastify", "@nestjs/core": "NestJS",
    "@grpc/grpc-js": "gRPC",
    "pg": "PostgreSQL", "postgres": "PostgreSQL",
    "redis": "Redis", "ioredis": "Redis", "@redis/client": "Redis",
    "@clickhouse/client": "ClickHouse",
    "mysql": "MySQL", "mysql2": "MySQL",
    "mongodb": "MongoDB", "mongoose": "MongoDB",
    "kafkajs": "Kafka", "@confluentinc/kafka-javascript": "Kafka",
    "amqplib": "RabbitMQ", "prom-client": "Prometheus",
}

COMPOSER = {
    "laravel/framework": "Laravel",
    "symfony/framework-bundle": "Symfony", "symfony/symfony": "Symfony",
    "grpc/grpc": "gRPC",
    "ext-pgsql": "PostgreSQL", "ext-pdo_pgsql": "PostgreSQL",
    "predis/predis": "Redis", "ext-redis": "Redis",
    "smi2/phpclickhouse": "ClickHouse",
    "ext-mysqli": "MySQL", "ext-pdo_mysql": "MySQL",
    "mongodb/mongodb": "MongoDB", "ext-mongodb": "MongoDB",
    "ext-rdkafka": "Kafka", "php-amqplib/php-amqplib": "RabbitMQ",
    "promphp/prometheus_client_php": "Prometheus",
}

GO = {
    "github.com/gin-gonic/gin": "Gin",
    "github.com/labstack/echo": "Echo",
    "github.com/gofiber/fiber": "Fiber",
    "github.com/go-chi/chi": "Chi",
    "google.golang.org/grpc": "gRPC",
    "github.com/jackc/pgx": "PostgreSQL", "github.com/lib/pq": "PostgreSQL",
    "github.com/redis/go-redis": "Redis", "github.com/go-redis/redis": "Redis",
    "github.com/clickhouse/clickhouse-go": "ClickHouse",
    "github.com/go-sql-driver/mysql": "MySQL",
    "go.mongodb.org/mongo-driver": "MongoDB",
    "github.com/segmentio/kafka-go": "Kafka", "github.com/confluentinc/confluent-kafka-go": "Kafka",
    "github.com/ibm/sarama": "Kafka", "github.com/shopify/sarama": "Kafka",
    "github.com/rabbitmq/amqp091-go": "RabbitMQ", "github.com/streadway/amqp": "RabbitMQ",
    "github.com/prometheus/client_golang": "Prometheus",
}

PYTHON = {
    "django": "Django", "fastapi": "FastAPI", "flask": "Flask",
    "grpcio": "gRPC",
    "psycopg": "PostgreSQL", "psycopg-binary": "PostgreSQL", "psycopg2": "PostgreSQL",
    "psycopg2-binary": "PostgreSQL", "asyncpg": "PostgreSQL",
    "redis": "Redis", "aioredis": "Redis",
    "clickhouse-connect": "ClickHouse", "clickhouse-driver": "ClickHouse",
    "mysqlclient": "MySQL", "pymysql": "MySQL", "mysql-connector-python": "MySQL",
    "pymongo": "MongoDB", "motor": "MongoDB",
    "confluent-kafka": "Kafka", "kafka-python": "Kafka", "aiokafka": "Kafka",
    "pika": "RabbitMQ", "aio-pika": "RabbitMQ",
    "prometheus-client": "Prometheus",
}

CONTAINER_IMAGES = {
    "postgres": "PostgreSQL", "postgis/postgis": "PostgreSQL",
    "redis": "Redis", "redis/redis-stack": "Redis", "redis/redis-stack-server": "Redis",
    "clickhouse/clickhouse-server": "ClickHouse", "yandex/clickhouse-server": "ClickHouse",
    "mysql": "MySQL", "mongo": "MongoDB", "mongodb/mongodb-community-server": "MongoDB",
    "apache/kafka": "Kafka", "bitnami/kafka": "Kafka", "confluentinc/cp-kafka": "Kafka",
    "rabbitmq": "RabbitMQ", "prom/prometheus": "Prometheus", "grafana/grafana": "Grafana",
}

MANIFEST_NAMES = {
    "package.json", "composer.json", "go.mod", "pyproject.toml", "pipfile",
    "chart.yaml", "chart.yml", "kustomization.yaml", "kustomization.yml",
    ".gitlab-ci.yml", ".gitlab-ci.yaml", "dockerfile", "containerfile",
}

IGNORED_PARTS = {
    ".git", ".venv", "venv", "node_modules", "vendor", "third_party",
    "dist", "build", "coverage", ".next", ".nuxt",
}

REQUIREMENTS_NAME = re.compile(r"(?:.*[-_.])?requirements(?:[-_.].*)?\.(?:txt|in)$")
CONTAINER_FILE = re.compile(r"(?:dockerfile|containerfile)[.-].+|.+\.(?:dockerfile|containerfile)$")
COMPOSE_FILE = re.compile(r"(?:docker-)?compose(?:[.-][^.]+)*\.ya?ml$")
GO_REQUIREMENT_BLOCK = re.compile(r"^require[ \t]+\(([^)]*)\)", re.MULTILINE)
GO_REQUIREMENT_SINGLE = re.compile(r"^require[ \t]+([^\n]+)", re.MULTILINE)
GO_REQUIREMENT = re.compile(r"\s*([^\s]+)\s+v\d+\.\d+\.\d+")
PYTHON_NAME = re.compile(r"\s*([a-zA-Z0-9][a-zA-Z0-9._-]*)")
COMPOSE_IMAGE = re.compile(r"""^\s*image\s*:\s*['"]?([^'"\s#]+)""", re.MULTILINE)
KUBE_MANIFEST = re.compile(r"^apiVersion\s*:\s*\S+", re.MULTILINE)
KUBE_KIND = re.compile(r"^kind\s*:\s*\S+", re.MULTILINE)


def is_manifest(path: str) -> bool:
    parts = PurePosixPath(path.lower()).parts
    if not parts or IGNORED_PARTS.intersection(parts):
        return False
    name = parts[-1]
    if name in MANIFEST_NAMES or name.endswith(".tf"):
        return True
    if REQUIREMENTS_NAME.fullmatch(name) or ("requirements" in parts[:-1] and name.endswith((".txt", ".in"))):
        return True
    if CONTAINER_FILE.fullmatch(name) or COMPOSE_FILE.fullmatch(name):
        return True
    manifest_directory = {"k8s", "kube", "kubernetes"}.intersection(parts[:-1])
    return name.endswith((".yml", ".yaml")) and bool(manifest_directory or parts[:2] == (".github", "workflows"))


def json_dependencies(contents, groups):
    data = json.loads(contents)
    if not isinstance(data, dict):
        return set()
    return {
        name.lower()
        for group in groups
        if isinstance(data.get(group), dict)
        for name in data[group]
    }


def python_dependencies(name, contents):
    if name == "pipfile":
        data = tomllib.loads(contents)
        specs = [*data.get("packages", {}), *data.get("dev-packages", {})]
    elif name == "pyproject.toml":
        data = tomllib.loads(contents)
        project = data.get("project", {})
        poetry = data.get("tool", {}).get("poetry", {})
        specs = [
            *project.get("dependencies", []),
            *poetry.get("dependencies", {}),
            *poetry.get("dev-dependencies", {}),
        ]
        for group in project.get("optional-dependencies", {}).values():
            specs.extend(group)
        for group in data.get("dependency-groups", {}).values():
            specs.extend(group)
        for group in poetry.get("group", {}).values():
            specs.extend(group.get("dependencies", {}))
    else:
        specs = contents.splitlines()
    names = set()
    for spec in specs:
        if isinstance(spec, str) and (match := PYTHON_NAME.match(spec)):
            names.add(re.sub(r"[-_.]+", "-", match[1].lower()))
    return names


def go_dependencies(contents):
    single = GO_REQUIREMENT_SINGLE.findall(contents)
    grouped = GO_REQUIREMENT_BLOCK.findall(contents)
    for line in (*single, *(line for group in grouped for line in group.splitlines())):
        if re.search(r"//\s*indirect\b", line):
            continue
        if match := GO_REQUIREMENT.match(line):
            yield re.sub(r"/v\d+$", "", match[1].lower())


def compose_image_names(contents):
    for image in COMPOSE_IMAGE.findall(contents):
        image = image.split("@", 1)[0]
        registry, separator, name = image.partition("/")
        if separator and ("." in registry or ":" in registry):
            image = name
        image = image.split(":", 1)[0]
        yield image.removeprefix("library/")


def detect_technologies(files: Mapping[str, str]) -> set[str]:
    found = set()
    for path, contents in sorted(files.items()):
        if not is_manifest(path):
            continue
        parts = PurePosixPath(path.lower()).parts
        name = parts[-1]
        try:
            if name == "package.json":
                packages = json_dependencies(contents, ("dependencies", "devDependencies", "peerDependencies", "optionalDependencies"))
                found.update(NPM[package] for package in packages if package in NPM)
                if any(package.startswith("@storybook/") for package in packages):
                    found.add("Storybook")
            elif name == "composer.json":
                packages = json_dependencies(contents, ("require", "require-dev"))
                found.update(COMPOSER[package] for package in packages if package in COMPOSER)
            elif name == "go.mod":
                found.update(GO[package] for package in go_dependencies(contents) if package in GO)
            elif name in {"pyproject.toml", "pipfile"} or name.endswith((".txt", ".in")):
                packages = python_dependencies(name, contents)
                found.update(PYTHON[package] for package in packages if package in PYTHON)
            elif parts[:2] == (".github", "workflows"):
                found.add("GitHub Actions")
            elif name in {".gitlab-ci.yml", ".gitlab-ci.yaml"}:
                found.add("GitLab CI")
            elif name.endswith(".tf"):
                found.add("Terraform")
            elif name in {"dockerfile", "containerfile"} or CONTAINER_FILE.fullmatch(name):
                found.add("Docker")
            elif COMPOSE_FILE.fullmatch(name):
                found.add("Docker")
                found.update(CONTAINER_IMAGES[image] for image in compose_image_names(contents) if image in CONTAINER_IMAGES)
            elif name in {"chart.yaml", "chart.yml"} and re.search(r"^apiVersion\s*:", contents, re.MULTILINE):
                found.update(("Helm", "Kubernetes"))
            elif KUBE_MANIFEST.search(contents) and KUBE_KIND.search(contents):
                found.add("Kubernetes")
        except (json.JSONDecodeError, tomllib.TOMLDecodeError, AttributeError, TypeError):
            # Keep evidence from other manifests when a repository has an invalid file.
            continue
    return found
