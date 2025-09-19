import json
import yaml
from pathlib import Path
from source.modules.verify import Verifier
from source.modules.cache import CacheManager
from source.modules.history import History
from source.modules.fakeroot import FakeRoot
from source.modules.hooks import HookManager
from tabulate import tabulate

class HashGenerator:
    """
    Gera hashes de arquivos de pacotes, integrado com:
    - Sandbox (FakeRoot)
    - Auditoria (History)
    - Cache (CacheManager)
    - Hooks pré e pós-geração
    - Multi-hash (SHA256, SHA512, MD5, BLAKE2b)
    - Exportação de resultados em múltiplos formatos
    """

    def __init__(self, repo_path="/usr/source", cache_manager=None, history=None, hook_manager=None, fake_root=None, verbose=False):
        self.repo_path = Path(repo_path).resolve()
        self.cache_manager = cache_manager
        self.history = history
        self.hook_manager = hook_manager
        self.fake_root = fake_root
        self.verifier = Verifier()
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
    # Geração de hashes
    # -----------------------------
    def generate_hashes(self, package_name, files, algorithms=None):
        if algorithms is None:
            algorithms = ["sha256"]
        hashes = {}

        self._run_hooks(self.pre_hooks, package_name, {"files": files})

        for f in files:
            file_path = Path(f)
            if self.fake_root:
                file_path = self.fake_root.dest_path / file_path.relative_to(file_path.anchor)

            file_hashes = {}
            for algo in algorithms:
                if self.cache_manager:
                    cached_file = self.cache_manager.get_file(file_path.name)
                    if cached_file:
                        file_hashes[algo] = self.verifier.compute_hash(cached_file, algo)
                        continue
                file_hashes[algo] = self.verifier.compute_hash(file_path, algo)
            hashes[str(file_path)] = file_hashes

        self._run_hooks(self.post_hooks, package_name, hashes)

        if self.history:
            self.history.record("generate_hashes", package_name, {"files": files, "hashes": hashes})

        return hashes

    # -----------------------------
    # Escrita em receitas
    # -----------------------------
    def write_to_recipe(self, package_name, hashes):
        recipe_path = self.repo_path / package_name / "recipe.json"
        recipe_path.parent.mkdir(parents=True, exist_ok=True)
        recipe_data = {"hashes": hashes}

        if recipe_path.exists():
            existing = json.load(recipe_path.open())
            existing.update(recipe_data)
            recipe_data = existing

        with recipe_path.open("w") as f:
            json.dump(recipe_data, f, indent=4)

        if self.history:
            self.history.record("write_to_recipe", package_name, {"hashes": hashes})

    # -----------------------------
    # Exportação de resultados
    # -----------------------------
    def export(self, hashes, format="json"):
        if format == "json":
            return json.dumps(hashes, indent=4)
        elif format == "yaml":
            return yaml.dump(hashes, default_flow_style=False)
        elif format == "markdown":
            return tabulate([(k, v) for k, v in hashes.items()], headers=["File", "Hashes"], tablefmt="github")
        elif format == "csv":
            output = []
            for k, v in hashes.items():
                output.append(",".join([k] + [f"{alg}:{h}" for alg, h in v.items()]))
            return "\n".join(output)
        else:
            raise ValueError(f"Formato de exportação '{format}' não suportado.")

    # -----------------------------
    # Rollback
    # -----------------------------
    def rollback(self, package_name):
        recipe_path = self.repo_path / package_name / "recipe.json"
        if recipe_path.exists():
            recipe_path.unlink()
            if self.history:
                self.history.record("rollback", package_name, {"removed": True}, status="rolled_back")
            return {"removed": True}
        return {"removed": False}
