import json
import yaml
import csv
from datetime import datetime
from pathlib import Path
from tabulate import tabulate
from source.modules.cache import CacheManager
from source.modules.fakeroot import FakeRoot
from source.modules.history import History
from source.modules.flags import UseQuery
from source.modules.hash import RecipeHash

class PackageInfo:
    """
    Exibe informações detalhadas de um pacote com suporte a:
    - Sandbox (FakeRoot)
    - Auditoria (History)
    - Cache (CacheManager)
    - USE flags (UseQuery)
    - Hashes (RecipeHash)
    - Hooks pré e pós-consulta
    """

    def __init__(self, installed_db, repo_paths=None, cache_manager=None, fake_root=None,
                 history=None, flags=None, recipe_hash=None, verbose=False):
        self.installed_db = installed_db
        self.repo_paths = [Path(p).resolve() for p in (repo_paths or ["/usr/source"])]
        self.cache_manager = cache_manager
        self.fake_root = fake_root
        self.history = history
        self.flags = flags
        self.recipe_hash = recipe_hash
        self.verbose = verbose
        self.pre_hooks = []
        self.post_hooks = []

    # -----------------------------
    # Hooks
    # -----------------------------
    def register_pre_hook(self, func):
        self.pre_hooks.append(func)

    def register_post_hook(self, func):
        self.post_hooks.append(func)

    def _run_hooks(self, hooks, package_name, info):
        for hook in hooks:
            hook(package_name, info)

    # -----------------------------
    # Consulta de status
    # -----------------------------
    def status(self, package_name):
        installed = self.installed_db.get(package_name)
        status_info = {"installed": bool(installed)}
        if installed:
            status_info["version"] = installed.get("version")
        if self.history:
            self.history.record("status", package_name, status_info)
        return status_info

    # -----------------------------
    # Informações detalhadas
    # -----------------------------
    def details(self, package_name, output_format="json"):
        info = self._get_package_info(package_name)
        if not info:
            return None

        # Consultas adicionais
        if self.flags:
            info["use_flags"] = self.flags.list_package_flags(package_name)
        if self.recipe_hash:
            files = info.get("source_files", [])
            info["hashes"] = self.recipe_hash.generate_for_files(files)

        self._run_hooks(self.pre_hooks, package_name, info)
        if self.history:
            self.history.record("details", package_name, info)
        self._run_hooks(self.post_hooks, package_name, info)

        return self._format_output(info, output_format)

    # -----------------------------
    # Obtenção de informações do pacote
    # -----------------------------
    def _get_package_info(self, package_name):
        for repo_path in self.repo_paths:
            pkg_file = repo_path / f"{package_name}.json"
            if pkg_file.exists():
                if self.cache_manager:
                    cached = self.cache_manager.get_file(pkg_file.name)
                    if cached:
                        return json.load(cached.open())
                return json.load(pkg_file.open())
        return None

    # -----------------------------
    # Formatação de saída
    # -----------------------------
    def _format_output(self, info, output_format):
        if output_format == "json":
            return json.dumps(info, indent=4)
        elif output_format == "yaml":
            return yaml.dump(info, default_flow_style=False)
        elif output_format == "csv":
            return self._to_csv(info)
        elif output_format == "markdown":
            return tabulate(info.items(), tablefmt="github")
        elif output_format == "table":
            return tabulate(info.items(), headers=["Key", "Value"], tablefmt="grid")
        else:
            raise ValueError(f"Formato de saída '{output_format}' não suportado.")

    def _to_csv(self, info):
        output = []
        for k, v in info.items():
            if isinstance(v, list):
                v = ",".join(map(str, v))
            elif isinstance(v, dict):
                v = json.dumps(v)
            output.append([k, v])
        return "\n".join([",".join(row) for row in output])

    # -----------------------------
    # Rollback
    # -----------------------------
    def rollback(self, package_name):
        installed = self.installed_db.get(package_name)
        if installed:
            del self.installed_db[package_name]
            if self.history:
                self.history.record("rollback", package_name, {"removed": True}, status="rolled_back")
            return {"removed": True}
        return {"removed": False}
