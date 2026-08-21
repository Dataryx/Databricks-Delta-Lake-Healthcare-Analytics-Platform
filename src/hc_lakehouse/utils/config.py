"""Platform configuration loader.

All table names, paths, thresholds, and environment knobs come from environment
variables and YAML under ``conf/``. No secrets are stored in this module.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

from hc_lakehouse.utils.logging import get_logger

logger = get_logger(__name__)

# Repository root: src/hc_lakehouse/utils/config.py → parents[3]
REPO_ROOT = Path(__file__).resolve().parents[3]
CONF_ROOT = REPO_ROOT / "conf"


@dataclass(frozen=True)
class LayerPaths:
    """Logical container / schema paths for medallion layers."""

    landing: str
    bronze: str
    silver: str
    gold: str
    quarantine: str
    checkpoints: str
    artifacts: str
    restricted: str
    ops: str
    ml: str
    sandbox: str


@dataclass(frozen=True)
class PlatformConfig:
    """Immutable runtime configuration for local or Databricks execution."""

    runtime_mode: str
    env: str
    catalog: str
    org: str
    azure_region: str
    uc_metastore: str
    storage_account: str
    local_delta_root: Path
    small_cell_k: int
    retention_years: int
    deid_salt_env_key: str
    log_level: str
    log_format: str
    schemas: LayerPaths
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def is_local(self) -> bool:
        return self.runtime_mode.lower() in {"local", "demo"}

    def table_fqn(self, schema: str, table: str) -> str:
        """Return catalog.schema.table (Unity Catalog style)."""
        return f"{self.catalog}.{schema}.{table}"

    def local_path(self, *parts: str) -> Path:
        """Resolve a path under the local Delta root."""
        return self.local_delta_root.joinpath(*parts)

    def deid_salt(self) -> str:
        """Load HMAC pepper from environment (local) or raise if missing.

        Production must inject this via Databricks secret scope / Key Vault.
        """
        value = os.environ.get(self.deid_salt_env_key, "")
        if not value:
            msg = (
                f"Missing de-identification salt env var {self.deid_salt_env_key}. "
                "Local: set HC_DEID_SALT. Cloud: map Key Vault secret to this env."
            )
            raise RuntimeError(msg)
        if value == "local-demo-pepper-not-for-production" and not self.is_local:
            raise RuntimeError("Demo de-identification salt must not be used outside local mode.")
        return value


def _default_schemas() -> LayerPaths:
    return LayerPaths(
        landing="landing",
        bronze="bronze",
        silver="silver",
        gold="gold",
        quarantine="quarantine",
        checkpoints="checkpoints",
        artifacts="artifacts",
        restricted="restricted",
        ops="ops",
        ml="ml",
        sandbox="sandbox",
    )


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Expected mapping in {path}, got {type(data).__name__}")
    return data


def load_yaml_config(relative: str) -> dict[str, Any]:
    """Load a YAML file from ``conf/`` by relative path."""
    path = CONF_ROOT / relative
    logger.debug("loading_config_file", extra={"path": str(path)})
    return _load_yaml(path)


@lru_cache(maxsize=1)
def load_config(*, dotenv_path: str | None = None) -> PlatformConfig:
    """Load platform config from ``.env`` + optional ``conf/platform.yml``.

    Parameters
    ----------
    dotenv_path:
        Optional explicit path to a dotenv file. Defaults to repo ``.env``.
    """
    env_file = Path(dotenv_path) if dotenv_path else REPO_ROOT / ".env"
    if env_file.exists():
        load_dotenv(env_file, override=False)
    else:
        example = REPO_ROOT / ".env.example"
        if example.exists():
            load_dotenv(example, override=False)

    platform_yml = _load_yaml(CONF_ROOT / "platform.yml")

    local_root = Path(
        os.environ.get("HC_LOCAL_DELTA_ROOT", platform_yml.get("local_delta_root", ".local_delta"))
    )
    if not local_root.is_absolute():
        local_root = REPO_ROOT / local_root

    config = PlatformConfig(
        runtime_mode=os.environ.get("HC_RUNTIME_MODE", platform_yml.get("runtime_mode", "local")),
        env=os.environ.get("HC_ENV", platform_yml.get("env", "dev")),
        catalog=os.environ.get("HC_CATALOG", platform_yml.get("catalog", "hc_dev")),
        org=os.environ.get("HC_ORG", platform_yml.get("org", "INDHC")),
        azure_region=os.environ.get("HC_AZURE_REGION", platform_yml.get("azure_region", "eastus2")),
        uc_metastore=os.environ.get(
            "HC_UC_METASTORE", platform_yml.get("uc_metastore", "uc_metastore_eastus2")
        ),
        storage_account=os.environ.get(
            "HC_STORAGE_ACCOUNT", platform_yml.get("storage_account", "stindominushclake")
        ),
        local_delta_root=local_root,
        small_cell_k=int(os.environ.get("HC_SMALL_CELL_K", platform_yml.get("small_cell_k", 11))),
        retention_years=int(
            os.environ.get("HC_RETENTION_YEARS", platform_yml.get("retention_years", 7))
        ),
        deid_salt_env_key=platform_yml.get("deid_salt_env_key", "HC_DEID_SALT"),
        log_level=os.environ.get("HC_LOG_LEVEL", platform_yml.get("log_level", "INFO")),
        log_format=os.environ.get("HC_LOG_FORMAT", platform_yml.get("log_format", "json")),
        schemas=_default_schemas(),
        extra=platform_yml.get("extra", {}),
    )
    logger.info(
        "config_loaded",
        extra={
            "runtime_mode": config.runtime_mode,
            "env": config.env,
            "catalog": config.catalog,
            "local_delta_root": str(config.local_delta_root),
        },
    )
    return config


def clear_config_cache() -> None:
    """Clear the cached config (for tests)."""
    load_config.cache_clear()
