import os
import json
import yaml
from pathlib import Path
from tabulate import tabulate
from source.modules.history import History
from source.modules.logger import Logger
from source.modules.fakeroot import FakeRoot

class PackageSearch:
    """
    Ferramentas avançadas para buscar pacotes, dependências e arquivos nos repositórios.
    - Multi-repositório
    - Sandbox (FakeRoot)
    - Auditoria (History)
    - Logger integrado
    - Hooks pré e pós-busca
    """

    def __init__(self, repo_paths=None, history: History=None, logger: Logger=None, fake_root: FakeRoot=None, verbose=True):
        self.repo_paths = [Path(p).resolve() for p in (repo_paths or ["/usr/source"])]
        self.history = history
        self.logger = logger
        self.fake_root = fake_root
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

    def _run_hooks(self, hooks, package_name, result):
        for hook in hooks:
            hook(package_name, result)

    # -----------------------------
    # Listar todos pacotes
    # -----------------------------
    def list_all_packages(self):
        packages = set()
        for repo in self.repo_paths:
            if repo.exists():
                packages.update([d.name for d in repo.iterdir() if d.is_dir()])
        result = sorted(packages)
        if self.logger:
            self.logger.info(f"List all packages: {len(result)} found")
        if self.history:
            self.history.record("list_all_packages", "system", {"count": len(result)})
        return result

    # -----------------------------
    # Buscar pacote específico
    # -----------------------------
    def find_package(self, package_name):
        self._run_hooks(self.pre_hooks, package_name, None)
        for repo in self.repo_paths:
            pkg_path = repo / package_name
            if self.fake_root:
                pkg_path = self.fake_root.dest_path / pkg_path.relative_to(pkg_path.anchor)
            if pkg_path.exists():
                self._run_hooks(self.post_hooks, package_name, {"found": True, "path": str(pkg_path)})
                if self.logger:
                    self.logger.success(f"Package found: {package_name} at {pkg_path}")
                if self.history:
                    self.history.record("find_package", package_name, {"found": True, "path": str(pkg_path)})
                return pkg_path
        self._run_hooks(self.post_hooks, package_name, {"found": False})
        if self.logger:
            self.logger.warning(f"Package not found: {package_name}")
        if self.history:
            self.history.record("find_package", package_name, {"found": False})
        return None

    # -----------------------------
    # Listar arquivos do pacote
    # -----------------------------
    def list_files(self, package_name):
        pkg_path = self.find_package(package_name)
        if not pkg_path:
            return []
        files = [f.name for f in pkg_path.rglob("*") if f.is_file()]
        if self.logger:
            self.logger.info(f"Files for package {package_name}: {len(files)} found")
        if self.history:
            self.history.record("list_files", package_name, {"files_count": len(files)})
        return files

    # -----------------------------
    # Listar dependências
    # -----------------------------
    def list_dependencies(self, package_name):
        pkg_path = self.find_package(package_name)
        if not pkg_path:
            return {"build": [], "runtime": []}
        recipe_file = pkg_path / "recipe.json"
        if not recipe_file.exists():
            return {"build": [], "runtime": []}
        with recipe_file.open() as f:
            recipe = json.load(f)
        deps = {
            "build": recipe.get("build_dependencies", []),
            "runtime": recipe.get("runtime_dependencies", [])
        }
        if self.logger:
            self.logger.info(f"Dependencies for package {package_name}: build={len(deps['build'])}, runtime={len(deps['runtime'])}")
        if self.history:
            self.history.record("list_dependencies", package_name, deps)
        return deps

    # -----------------------------
    # Exportar resultados
    # -----------------------------
    def export(self, data, output_file, format="json"):
        output_file = Path(output_file).resolve()
        if format == "json":
            output_file.write_text(json.dumps(data, indent=4))
        elif format == "yaml":
            output_file.write_text(yaml.dump(data, default_flow_style=False))
        elif format == "markdown":
            table = tabulate(data.items() if isinstance(data, dict) else [(k, v) for k, v in enumerate(data)],
                             headers=["Key", "Value"], tablefmt="github")
            output_file.write_text(table)
        else:
            raise ValueError(f"Formato de exportação '{format}' não suportado")
        if self.logger:
            self.logger.success(f"Exported search results to {output_file}")
