import os
import shutil
import hashlib
import logging
import tarfile
from pathlib import Path
from datetime import datetime, timedelta
from source.modules.fakeroot import FakeRoot

class CacheManager:
    """
    Gerencia cache de downloads e arquivos de origem dentro de sandbox.
    Suporta auditoria, rollback, multi-repositório e compressão otimizada.
    """

    def __init__(self, cache_dirs=None, max_age_days=30, max_size_mb=2048, fake_root: FakeRoot = None, verbose=False):
        self.cache_dirs = [Path(d).resolve() for d in (cache_dirs or ["/var/cache/source/distfiles"])]
        self.max_age = timedelta(days=max_age_days)
        self.max_size = max_size_mb * 1024 * 1024
        self.fake_root = fake_root
        self.verbose = verbose
        self.logger = self._setup_logger()
        self.audit_history = []

        for d in self.cache_dirs:
            d.mkdir(parents=True, exist_ok=True)

    def _setup_logger(self):
        logger = logging.getLogger("CacheManager")
        logger.setLevel(logging.DEBUG if self.verbose else logging.INFO)
        if not logger.handlers:
            ch = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')
            ch.setFormatter(formatter)
            logger.addHandler(ch)
        return logger

    # -----------------------------
    # Hash e checksum
    # -----------------------------
    def _compute_hash(self, filepath: Path, algorithm="sha256"):
        hash_func = hashlib.sha256() if algorithm=="sha256" else hashlib.md5()
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_func.update(chunk)
        return hash_func.hexdigest()

    # -----------------------------
    # Armazenamento de arquivos
    # -----------------------------
    def store_file(self, file_path, compress=False):
        file_path = Path(file_path).resolve()
        dest_dir = self.cache_dirs[0]
        dest_file = dest_dir / file_path.name

        if compress:
            dest_file = dest_file.with_suffix(dest_file.suffix + ".gz")
            with tarfile.open(dest_file, "w:gz") as tar:
                tar.add(file_path, arcname=file_path.name)
        else:
            shutil.copy(file_path, dest_file)

        sha256 = self._compute_hash(dest_file)
        self.audit_history.append({
            "timestamp": datetime.now().isoformat(),
            "action": "store_file",
            "file": str(dest_file),
            "sha256": sha256
        })

        self.logger.info(f"Arquivo armazenado no cache: {dest_file}")
        return dest_file

    # -----------------------------
    # Recuperação de arquivos
    # -----------------------------
    def get_file(self, filename):
        for d in self.cache_dirs:
            fpath = d / filename
            if fpath.exists() and self._is_valid(fpath):
                self.logger.info(f"Arquivo {filename} encontrado no cache.")
                return fpath
        self.logger.warning(f"Arquivo {filename} não encontrado ou inválido no cache.")
        return None

    # -----------------------------
    # Validação de arquivos
    # -----------------------------
    def _is_valid(self, file_path: Path):
        age = datetime.now() - datetime.fromtimestamp(file_path.stat().st_mtime)
        if age > self.max_age:
            self.logger.debug(f"Arquivo {file_path} expirou.")
            return False
        try:
            with open(file_path, "rb") as f:
                f.read(1)
        except Exception:
            self.logger.debug(f"Arquivo {file_path} está corrompido.")
            return False
        return True

    # -----------------------------
    # Limpeza inteligente
    # -----------------------------
    def clean_cache(self, force=False):
        for d in self.cache_dirs:
            for f in d.iterdir():
                if not f.is_file():
                    continue
                if force or not self._is_valid(f):
                    try:
                        f.unlink()
                        self.audit_history.append({
                            "timestamp": datetime.now().isoformat(),
                            "action": "clean_cache",
                            "file": str(f)
                        })
                        self.logger.info(f"Arquivo removido do cache: {f}")
                    except Exception as e:
                        self.logger.error(f"Erro ao remover arquivo {f}: {e}")

    # -----------------------------
    # Inspeção avançada do cache
    # -----------------------------
    def list_cache(self):
        cache_list = []
        for d in self.cache_dirs:
            for f in d.iterdir():
                if f.is_file():
                    cache_list.append({
                        "file": str(f),
                        "size": f.stat().st_size,
                        "mtime": datetime.fromtimestamp(f.stat().st_mtime).isoformat(),
                        "sha256": self._compute_hash(f),
                        "valid": self._is_valid(f)
                    })
        return cache_list

    # -----------------------------
    # Auditoria
    # -----------------------------
    def get_audit_history(self):
        return self.audit_history
