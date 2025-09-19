import os
import yaml
import logging
from pathlib import Path
from datetime import datetime
from source.modules.hooks import HookManager
from source.modules.fakeroot import FakeRoot
import subprocess
import requests

class RecipeCreator:
    """
    Cria e gerencia pacotes completos.
    Suporta múltiplos sistemas de build, sandbox FakeRoot, hooks avançados e auditoria.
    """

    SUPPORTED_BUILD_SYSTEMS = ["autotools", "meson", "cmake", "python", "rust"]

    def __init__(self, base_dir="/usr/source", verbose=False):
        self.base_dir = Path(base_dir).resolve()
        self.verbose = verbose
        self.logger = self._setup_logger()
        self.hook_manager = HookManager(verbose=verbose)
        self.audit_history = []

    def _setup_logger(self):
        logger = logging.getLogger("RecipeCreator")
        logger.setLevel(logging.DEBUG if self.verbose else logging.INFO)
        if not logger.handlers:
            ch = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')
            ch.setFormatter(formatter)
            logger.addHandler(ch)
        return logger

    # -----------------------------
    # Criação do pacote
    # -----------------------------
    def create_package_dir(self, package_name: str):
        package_dir = self.base_dir / package_name
        package_dir.mkdir(parents=True, exist_ok=True)
        self.logger.info(f"Diretório do pacote criado: {package_dir}")
        return package_dir

    def create_base_recipe(self, package_name: str, version="1.0.0", build_system="autotools"):
        if build_system not in self.SUPPORTED_BUILD_SYSTEMS:
            raise ValueError(f"Sistema de build '{build_system}' não suportado.")

        package_dir = self.create_package_dir(package_name)
        recipe_file = package_dir / "recipe.yaml"

        recipe = {
            "name": package_name,
            "version": version,
            "source": {"url": "", "sha256": ""},
            "build_system": build_system,
            "dependencies": [],
            "use_flags": [],
            "hooks": {stage: [] for stage in [
                "pre_fetch", "post_fetch",
                "pre_configure", "post_configure",
                "pre_build", "post_build",
                "pre_install", "post_install",
                "pre_remove", "post_remove"
            ]}
        }

        with recipe_file.open("w") as f:
            yaml.dump(recipe, f)
        self.logger.info(f"Receita base criada: {recipe_file}")

        self._create_hook_templates(package_dir)
        self._create_readme(package_dir, package_name)
        self._init_git_repo(package_dir)

        self.audit_history.append({
            "timestamp": datetime.now().isoformat(),
            "package": package_name,
            "action": "create_recipe",
            "status": "success"
        })

        return recipe_file

    # -----------------------------
    # Templates de hooks
    # -----------------------------
    def _create_hook_templates(self, package_dir: Path):
        hooks_dir = package_dir / "hooks"
        hooks_dir.mkdir(exist_ok=True)
        for stage in ["pre_fetch", "post_fetch", "pre_configure", "post_configure",
                      "pre_build", "post_build", "pre_install", "post_install",
                      "pre_remove", "post_remove"]:
            hook_file = hooks_dir / f"{stage}.sh"
            if not hook_file.exists():
                hook_file.write_text(f"#!/bin/bash\n# Hook {stage} para {package_dir.name}\n")
                os.chmod(hook_file, 0o755)
        self.logger.info(f"Templates de hooks criados em {hooks_dir}")

    # -----------------------------
    # README automático
    # -----------------------------
    def _create_readme(self, package_dir: Path, package_name: str):
        readme = package_dir / "README.md"
        readme.write_text(f"# Pacote {package_name}\n\n"
                          "Este pacote foi criado com RecipeCreator.\n"
                          "Hooks disponíveis em 'hooks/' podem ser usados para customizar o build.\n")
        self.logger.info(f"README criado: {readme}")

    # -----------------------------
    # Git inicial
    # -----------------------------
    def _init_git_repo(self, package_dir: Path):
        if not (package_dir / ".git").exists():
            subprocess.run(["git", "init"], cwd=package_dir, stdout=subprocess.DEVNULL)
            subprocess.run(["git", "add", "."], cwd=package_dir, stdout=subprocess.DEVNULL)
            subprocess.run(["git", "commit", "-m", "Commit inicial do pacote"], cwd=package_dir, stdout=subprocess.DEVNULL)
            self.logger.info(f"Repositório Git inicializado em {package_dir}")

    # -----------------------------
    # Validação da receita
    # -----------------------------
    def validate_recipe(self, recipe_file: Path):
        with recipe_file.open() as f:
            recipe = yaml.safe_load(f)

        required_fields = ["name", "version", "source", "build_system"]
        for field in required_fields:
            if field not in recipe:
                raise ValueError(f"Campo obrigatório '{field}' ausente na receita.")

        url = recipe["source"].get("url", "")
        if url:
            try:
                resp = requests.head(url, timeout=5)
                if resp.status_code >= 400:
                    raise ValueError(f"URL do tarball inacessível: {url}")
            except Exception:
                raise ValueError(f"Falha ao verificar URL: {url}")

        sha = recipe["source"].get("sha256", "")
        if sha and len(sha) != 64:
            raise ValueError(f"SHA256 inválido: {sha}")

        if recipe["build_system"] not in self.SUPPORTED_BUILD_SYSTEMS:
            raise ValueError(f"Sistema de build '{recipe['build_system']}' não suportado.")

        self.logger.info(f"Receita {recipe_file} validada com sucesso.")
        return True

    # -----------------------------
    # Auditoria
    # -----------------------------
    def get_audit_history(self):
        return self.audit_history
