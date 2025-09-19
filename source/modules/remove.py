import os
import shutil
import logging
from datetime import datetime
from typing import List
from source.modules.fakeroot import FakeRoot
from source.modules.hooks import HookManager
from source.modules.resolver import DependencyResolver

class Remover:
    """
    Gerencia a remoção de pacotes dentro do sandbox FakeRoot
    com auditoria, rollback e hooks avançados.
    """

    def __init__(self, installed_db, fake_root: FakeRoot, hook_manager: HookManager,
                 resolver: DependencyResolver, verbose=False):
        self.installed_db = installed_db
        self.fake_root = fake_root
        self.hooks = hook_manager
        self.resolver = resolver
        self.verbose = verbose
        self.logger = self._setup_logger()
        self.history = []

    def _setup_logger(self):
        logger = logging.getLogger("Remover")
        logger.setLevel(logging.DEBUG if self.verbose else logging.INFO)
        if not logger.handlers:
            ch = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')
            ch.setFormatter(formatter)
            logger.addHandler(ch)
        return logger

    # -----------------------------
    # Dependências
    # -----------------------------
    def _check_dependencies(self, package, force=False):
        deps = self.resolver.get_reverse_dependencies(package)
        if deps and not force:
            raise Exception(f"Pacotes dependentes encontrados: {deps}")
        return deps

    # -----------------------------
    # Hooks
    # -----------------------------
    async def _run_hooks(self, stage, package):
        import asyncio
        await self.hooks.run_hooks(stage, package, fake_root=self.fake_root)

    # -----------------------------
    # Remoção de arquivos
    # -----------------------------
    def _remove_files(self, package):
        files = self.installed_db.get_files(package)
        removed_files = []
        for f in files:
            path = os.path.join(self.fake_root.dest_path, f)
            try:
                if os.path.exists(path):
                    if os.path.isfile(path) or os.path.islink(path):
                        os.remove(path)
                    elif os.path.isdir(path):
                        shutil.rmtree(path)
                    removed_files.append(f)
                    self.logger.debug(f"Removido: {path}")
            except Exception as e:
                self.logger.error(f"Falha ao remover {path}: {e}")
        return removed_files

    # -----------------------------
    # Snapshots para rollback
    # -----------------------------
    def _snapshot(self):
        """Cria snapshot do estado atual do FakeRoot para rollback."""
        return self.fake_root.snapshot()

    def _rollback(self, snapshot):
        """Restaura o estado anterior do FakeRoot em caso de falha."""
        self.fake_root.rollback()
        self.logger.info("Rollback do sandbox aplicado com sucesso.")

    # -----------------------------
    # Remoção de pacote
    # -----------------------------
    def remove_package(self, package, force=False):
        import asyncio
        snapshot = self._snapshot()
        try:
            self._check_dependencies(package, force=force)
            asyncio.run(self._run_hooks("pre_remove", package))
            removed_files = self._remove_files(package)
            asyncio.run(self._run_hooks("post_remove", package))

            # Atualiza banco de dados
            self.installed_db.remove_package(package)

            # Histórico detalhado
            self.history.append({
                "timestamp": datetime.now().isoformat(),
                "package": package,
                "removed_files": removed_files,
                "status": "success"
            })
            self.logger.info(f"Pacote '{package}' removido com sucesso.")
            return True

        except Exception as e:
            self._rollback(snapshot)
            self.history.append({
                "timestamp": datetime.now().isoformat(),
                "package": package,
                "removed_files": [],
                "status": f"error: {e}"
            })
            self.logger.error(f"Erro ao remover pacote '{package}': {e}")
            return False

    # -----------------------------
    # Remoção de múltiplos pacotes
    # -----------------------------
    def remove_packages(self, packages: List[str], force=False):
        results = {}
        for pkg in packages:
            results[pkg] = self.remove_package(pkg, force=force)
        return results

    # -----------------------------
    # Histórico
    # -----------------------------
    def get_history(self):
        return self.history
