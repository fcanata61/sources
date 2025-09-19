import os
import shutil
import stat
import logging
from pathlib import Path
from datetime import datetime
from typing import Callable

class FakeRoot:
    """
    Sandbox completo para builds e instalações simuladas.
    - Suporte multi-versão
    - Rollback automático
    - Auditoria avançada
    - Hooks pre/post install
    """

    def __init__(self, dest_path, verbose=False):
        self.dest_path = Path(dest_path).resolve()
        self.verbose = verbose
        self._ensure_dest_path()
        self.installed_files = {}  # path -> checksum/metadata
        self.snapshots = []
        self.logger = self._setup_logger()
        self.pre_install_hooks = []
        self.post_install_hooks = []

    # -----------------------------
    # Logger
    # -----------------------------

    def _setup_logger(self):
        logger = logging.getLogger(f"FakeRoot:{self.dest_path}")
        logger.setLevel(logging.DEBUG if self.verbose else logging.INFO)
        if not logger.handlers:
            ch = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')
            ch.setFormatter(formatter)
            logger.addHandler(ch)
        return logger

    # -----------------------------
    # Setup
    # -----------------------------

    def _ensure_dest_path(self):
        self.dest_path.mkdir(parents=True, exist_ok=True)
        if self.verbose:
            self.logger.debug(f"FakeRoot initialized at {self.dest_path}")

    # -----------------------------
    # Hooks
    # -----------------------------

    def add_pre_install_hook(self, hook: Callable[[str], None]):
        self.pre_install_hooks.append(hook)

    def add_post_install_hook(self, hook: Callable[[str], None]):
        self.post_install_hooks.append(hook)

    def _run_hooks(self, hooks, path):
        for hook in hooks:
            try:
                hook(path)
            except Exception as e:
                self.logger.error(f"Hook error for {path}: {e}")

    # -----------------------------
    # Arquivos e instalação
    # -----------------------------

    def install_files(self, source_files, overwrite=True):
        """
        Instala arquivos no FakeRoot:
        - preserva permissões
        - evita reinstalação se arquivo já presente e idêntico
        """
        for src_path in source_files:
            src = Path(src_path).resolve()
            if not src.exists():
                self.logger.warning(f"Arquivo não encontrado: {src}")
                continue
            rel_path = src.relative_to(src.anchor)
            dst = self.dest_path / rel_path
            dst.parent.mkdir(parents=True, exist_ok=True)

            # Verifica se precisa sobrescrever
            if not overwrite and dst.exists():
                self.logger.info(f"Ignorado (já existe): {dst}")
                continue

            self._run_hooks(self.pre_install_hooks, str(src))
            shutil.copy2(src, dst)
            self._preserve_permissions(src, dst)
            self.installed_files[dst] = self._get_file_metadata(dst)
            self._run_hooks(self.post_install_hooks, str(dst))
            self.logger.info(f"Instalado: {dst}")

    def _preserve_permissions(self, src, dst):
        st = src.stat()
        dst.chmod(st.st_mode)
        try:
            os.chown(dst, st.st_uid, st.st_gid)
        except PermissionError:
            self.logger.debug(f"Não foi possível alterar proprietário de {dst}")

    def _get_file_metadata(self, path):
        st = path.stat()
        return {"size": st.st_size, "mtime": st.st_mtime, "mode": st.st_mode}

    # -----------------------------
    # Symlinks
    # -----------------------------

    def create_symlink(self, target, link_name):
        link_path = self.dest_path / link_name
        link_path.parent.mkdir(parents=True, exist_ok=True)
        if link_path.exists() or link_path.is_symlink():
            link_path.unlink()
        os.symlink(target, link_path)
        self.installed_files[link_path] = {"symlink": target}
        self.logger.info(f"Symlink criado: {link_path} -> {target}")

    # -----------------------------
    # Auditoria
    # -----------------------------

    def list_installed_files(self):
        return [f.relative_to(self.dest_path) for f in self.installed_files.keys()]

    def audit(self):
        """
        Auditoria completa:
        - arquivos existentes
        - symlinks
        - arquivos órfãos
        """
        audit_report = {
            "installed_files": [],
            "missing_files": [],
            "symlinks": [],
        }
        for f, meta in self.installed_files.items():
            if f.exists():
                audit_report["installed_files"].append(f.relative_to(self.dest_path))
            else:
                audit_report["missing_files"].append(f.relative_to(self.dest_path))
            if isinstance(meta, dict) and "symlink" in meta:
                audit_report["symlinks"].append((f.relative_to(self.dest_path), meta["symlink"]))
        return audit_report

    # -----------------------------
    # Snapshots e rollback
    # -----------------------------

    def snapshot(self):
        snap = {
            "timestamp": datetime.now().isoformat(),
            "files": self.installed_files.copy()
        }
        self.snapshots.append(snap)
        return snap

    def rollback(self):
        if not self.snapshots:
            self.logger.warning("Nenhum snapshot disponível para rollback")
            return
        last_snap = self.snapshots.pop()
        # Remove arquivos adicionados desde o snapshot
        current_files = set(self.installed_files.keys())
        snapshot_files = set(last_snap["files"].keys())
        to_remove = current_files - snapshot_files
        for f in to_remove:
            if f.exists():
                if f.is_symlink() or f.is_file():
                    f.unlink()
                elif f.is_dir():
                    shutil.rmtree(f)
            self.installed_files.pop(f, None)
        self.logger.info("Rollback aplicado com sucesso")

    # -----------------------------
    # Limpeza
    # -----------------------------

    def cleanup(self):
        if self.dest_path.exists():
            shutil.rmtree(self.dest_path)
            self.installed_files.clear()
            self.snapshots.clear()
            self.logger.info(f"FakeRoot limpo: {self.dest_path}")
