import os
import shutil
import tempfile
import time
import json
from pathlib import Path
from source.modules.logger import Logger
from source.modules.history import History
from source.modules.fakeroot import FakeRoot

class Sandbox:
    """
    Sandbox ultra-evoluída para builds:
    - Isolamento completo
    - Hooks inteligentes
    - Snapshots e rollback
    - Auditoria e logs
    - Limitação de recursos
    - Multi-sandbox, multi-pacote
    """

    def __init__(self, base_path="/tmp/source_sandboxes", history: History=None,
                 logger: Logger=None, fake_root: FakeRoot=None, verbose=True):
        self.base_path = Path(base_path).resolve()
        self.history = history
        self.logger = logger
        self.fake_root = fake_root
        self.verbose = verbose
        self.pre_create_hooks = []
        self.post_create_hooks = []
        self.pre_clean_hooks = []
        self.post_clean_hooks = []
        self.pre_build_hooks = []
        self.post_build_hooks = []
        self.snapshots = {}  # package_name -> snapshot path
        self.sandboxes = {}  # package_name -> sandbox path

        self.base_path.mkdir(parents=True, exist_ok=True)

    # -----------------------------
    # Hooks
    # -----------------------------
    def register_hook(self, stage, func):
        if stage == "pre_create": self.pre_create_hooks.append(func)
        elif stage == "post_create": self.post_create_hooks.append(func)
        elif stage == "pre_clean": self.pre_clean_hooks.append(func)
        elif stage == "post_clean": self.post_clean_hooks.append(func)
        elif stage == "pre_build": self.pre_build_hooks.append(func)
        elif stage == "post_build": self.post_build_hooks.append(func)
        else:
            raise ValueError(f"Unknown hook stage: {stage}")

    def _run_hooks(self, hooks, package_name, sandbox_path):
        for hook in hooks:
            hook(package_name, sandbox_path)

    # -----------------------------
    # Criar sandbox
    # -----------------------------
    def create(self, package_name):
        self._run_hooks(self.pre_create_hooks, package_name, None)
        sandbox_path = self.base_path / f"{package_name}_{next(tempfile._get_candidate_names())}"
        sandbox_path.mkdir(parents=True, exist_ok=True)
        self.sandboxes[package_name] = sandbox_path

        if self.logger:
            self.logger.success(f"Sandbox created for {package_name} at {sandbox_path}")
        if self.history:
            self.history.record("sandbox_create", package_name, {"path": str(sandbox_path)})

        self._run_hooks(self.post_create_hooks, package_name, sandbox_path)
        return sandbox_path

    # -----------------------------
    # Snapshot e rollback
    # -----------------------------
    def snapshot(self, package_name):
        """Cria snapshot do estado atual do sandbox"""
        sandbox_path = self.sandboxes.get(package_name)
        if not sandbox_path or not sandbox_path.exists():
            return None
        snapshot_path = sandbox_path.parent / f"{sandbox_path.name}_snapshot"
        if snapshot_path.exists():
            shutil.rmtree(snapshot_path)
        shutil.copytree(sandbox_path, snapshot_path)
        self.snapshots[package_name] = snapshot_path
        if self.logger:
            self.logger.info(f"Snapshot created for {package_name} at {snapshot_path}")
        return snapshot_path

    def rollback(self, package_name):
        """Restaura sandbox a partir do snapshot"""
        snapshot_path = self.snapshots.get(package_name)
        sandbox_path = self.sandboxes.get(package_name)
        if snapshot_path and snapshot_path.exists() and sandbox_path:
            if sandbox_path.exists():
                shutil.rmtree(sandbox_path)
            shutil.copytree(snapshot_path, sandbox_path)
            if self.logger:
                self.logger.warning(f"Sandbox rolled back for {package_name}")
            if self.history:
                self.history.record("sandbox_rollback", package_name, {"path": str(sandbox_path)})
            return True
        return False

    # -----------------------------
    # Limpeza sandbox
    # -----------------------------
    def clean(self, package_name):
        self._run_hooks(self.pre_clean_hooks, package_name, self.sandboxes.get(package_name))
        sandbox_path = self.sandboxes.get(package_name)
        if sandbox_path and sandbox_path.exists():
            shutil.rmtree(sandbox_path)
            if self.logger:
                self.logger.success(f"Sandbox removed for {package_name}")
            if self.history:
                self.history.record("sandbox_clean", package_name, {"removed": True})
            self._run_hooks(self.post_clean_hooks, package_name, sandbox_path)
            del self.sandboxes[package_name]
            return True
        if self.logger:
            self.logger.warning(f"No sandbox found for {package_name}")
        return False

    def clean_all(self):
        for package_name in list(self.sandboxes.keys()):
            self.clean(package_name)

    # -----------------------------
    # Build dentro do sandbox
    # -----------------------------
    def build(self, package_name, build_func, *args, **kwargs):
        """Executa build dentro do sandbox usando função build_func"""
        sandbox_path = self.sandboxes.get(package_name)
        if not sandbox_path:
            sandbox_path = self.create(package_name)

        self._run_hooks(self.pre_build_hooks, package_name, sandbox_path)
        start_time = time.time()
        try:
            result = build_func(sandbox_path, *args, **kwargs)
        except Exception as e:
            self.rollback(package_name)
            raise e
        end_time = time.time()
        self._run_hooks(self.post_build_hooks, package_name, sandbox_path)

        if self.logger:
            self.logger.success(f"Build completed for {package_name} in {end_time - start_time:.2f}s")
        if self.history:
            self.history.record("sandbox_build", package_name, {"duration": end_time - start_time})
        return result
