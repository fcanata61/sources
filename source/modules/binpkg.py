import os
import tarfile
import json
import hashlib
import logging
from pathlib import Path
from datetime import datetime
from source.modules.fakeroot import FakeRoot
from source.modules.hooks import HookManager

class BinPackageManager:
    """
    Gerencia pacotes binários (binpkg) dentro de um sandbox.
    Suporta criação, instalação, validação e auditoria avançada.
    """

    def __init__(self, binpkg_dir="/var/cache/source/binpkgs", fake_root: FakeRoot = None, hook_manager: HookManager = None, verbose=False):
        self.binpkg_dir = Path(binpkg_dir).resolve()
        self.verbose = verbose
        self.fake_root = fake_root
        self.hooks = hook_manager
        self.logger = self._setup_logger()
        self.audit_history = []
        os.makedirs(self.binpkg_dir, exist_ok=True)

    def _setup_logger(self):
        logger = logging.getLogger("BinPackageManager")
        logger.setLevel(logging.DEBUG if self.verbose else logging.INFO)
        if not logger.handlers:
            ch = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')
            ch.setFormatter(formatter)
            logger.addHandler(ch)
        return logger

    # -----------------------------
    # Utilitários de hash
    # -----------------------------
    def _compute_sha256(self, filepath: Path):
        sha256_hash = hashlib.sha256()
        with open(filepath, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()

    # -----------------------------
    # Criação de pacotes binários
    # -----------------------------
    def create_binpkg(self, package_name, version, install_path, arch="x86_64", compress="gz"):
        ext = "tar.gz" if compress=="gz" else "tar.xz"
        filename = f"{package_name}-{version}-{arch}.{ext}"
        filepath = self.binpkg_dir / filename

        mode = "w:gz" if compress=="gz" else "w:xz"
        with tarfile.open(filepath, mode) as tar:
            tar.add(install_path, arcname=os.path.basename(install_path))

        sha256 = self._compute_sha256(filepath)

        pkginfo = {
            "name": package_name,
            "version": version,
            "arch": arch,
            "created_at": datetime.now().isoformat(),
            "install_path": str(install_path),
            "sha256": sha256,
            "compress": compress
        }

        pkginfo_file = self.binpkg_dir / f"{package_name}-{version}-{arch}.pkginfo"
        with pkginfo_file.open("w") as f:
            json.dump(pkginfo, f, indent=4)

        self.logger.info(f"Pacote binário criado: {filepath}")
        self.audit_history.append({
            "timestamp": datetime.now().isoformat(),
            "action": "create_binpkg",
            "package": package_name,
            "version": version,
            "arch": arch,
            "status": "success"
        })
        return filepath

    # -----------------------------
    # Instalação de pacotes binários
    # -----------------------------
    def install_binpkg(self, package_name, version, dest_path=None, arch="x86_64", force=False):
        if dest_path is None:
            dest_path = self.fake_root.dest_path if self.fake_root else "/"

        filename = f"{package_name}-{version}-{arch}.tar.gz"
        filepath = self.binpkg_dir / filename
        pkginfo_file = self.binpkg_dir / f"{package_name}-{version}-{arch}.pkginfo"

        if not filepath.exists():
            raise FileNotFoundError(f"Pacote binário {filename} não encontrado.")

        # Validar integridade
        expected_sha = ""
        if pkginfo_file.exists():
            with pkginfo_file.open() as f:
                pkginfo = json.load(f)
                expected_sha = pkginfo.get("sha256", "")
        actual_sha = self._compute_sha256(filepath)
        if expected_sha and actual_sha != expected_sha:
            raise ValueError(f"Falha na integridade do pacote {filename}: SHA256 não confere")

        # Hooks pré-instalação
        import asyncio
        if self.hooks:
            asyncio.run(self.hooks.run_hooks("pre_install", package_name, fake_root=self.fake_root))

        # Instalação no sandbox ou sistema real
        with tarfile.open(filepath, "r:gz") as tar:
            tar.extractall(path=dest_path)

        # Hooks pós-instalação
        if self.hooks:
            asyncio.run(self.hooks.run_hooks("post_install", package_name, fake_root=self.fake_root))

        self.logger.info(f"Pacote binário {package_name}-{version} instalado em: {dest_path}")
        self.audit_history.append({
            "timestamp": datetime.now().isoformat(),
            "action": "install_binpkg",
            "package": package_name,
            "version": version,
            "arch": arch,
            "dest": dest_path,
            "status": "success"
        })
        return dest_path

    # -----------------------------
    # Validação de pacotes binários
    # -----------------------------
    def validate_binpkg(self, package_name, version, arch="x86_64"):
        filename = f"{package_name}-{version}-{arch}.tar.gz"
        filepath = self.binpkg_dir / filename
        pkginfo_file = self.binpkg_dir / f"{package_name}-{version}-{arch}.pkginfo"

        if not filepath.exists() or not pkginfo_file.exists():
            self.logger.error(f"Pacote ou metadados ausentes: {filename}")
            return False

        with tarfile.open(filepath, "r:gz") as tar:
            try:
                tar.testzip()
            except Exception as e:
                self.logger.error(f"Falha na integridade do pacote {filename}: {e}")
                return False

        with pkginfo_file.open() as f:
            pkginfo = json.load(f)

        actual_sha = self._compute_sha256(filepath)
        if actual_sha != pkginfo.get("sha256", ""):
            self.logger.error(f"SHA256 do pacote {filename} não confere")
            return False

        self.logger.info(f"Pacote binário {package_name}-{version} validado com sucesso")
        return True

    # -----------------------------
    # Listagem avançada de pacotes
    # -----------------------------
    def list_binpkgs(self):
        binpkgs = []
        for filepath in self.binpkg_dir.glob("*.tar.gz"):
            pkginfo_file = filepath.with_suffix(".pkginfo")
            if pkginfo_file.exists():
                with pkginfo_file.open() as f:
                    pkginfo = json.load(f)
                binpkgs.append(pkginfo)
        return binpkgs

    # -----------------------------
    # Histórico de auditoria
    # -----------------------------
    def get_audit_history(self):
        return self.audit_history
