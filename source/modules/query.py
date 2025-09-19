import os
import json
import logging
from pathlib import Path
from datetime import datetime
from source.modules.fakeroot import FakeRoot

class UseQuery:
    """
    Gerencia consultas e alterações de USE flags.
    Suporte a sandbox, múltiplos repositórios, auditoria e rollback.
    """

    def __init__(self, repo_paths, use_flags, fake_root: FakeRoot = None, cache_dir="/var/cache/source/query", verbose=False):
        self.repo_paths = [Path(path).resolve() for path in repo_paths]
        self.use_flags = use_flags
        self.fake_root = fake_root
        self.cache_dir = Path(cache_dir).resolve()
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.verbose = verbose
        self.logger = self._setup_logger()
        self.audit_history = []

    def _setup_logger(self):
        logger = logging.getLogger("UseQuery")
        logger.setLevel(logging.DEBUG if self.verbose else logging.INFO)
        if not logger.handlers:
            ch = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')
            ch.setFormatter(formatter)
            logger.addHandler(ch)
        return logger

    # -----------------------------
    # Cache
    # -----------------------------
    def _get_cache_file(self, key):
        return self.cache_dir / f"{key}.json"

    def _load_cache(self, key):
        cache_file = self._get_cache_file(key)
        if cache_file.exists():
            with cache_file.open("r") as f:
                return json.load(f)
        return None

    def _save_cache(self, key, data):
        cache_file = self._get_cache_file(key)
        with cache_file.open("w") as f:
            json.dump(data, f, indent=4)

    # -----------------------------
    # Listagem global de USE flags
    # -----------------------------
    def list_all_flags(self):
        cache_key = "all_flags"
        cached = self._load_cache(cache_key)
        if cached:
            self.logger.debug("Usando cache para todas as flags")
            return cached

        all_flags = set()
        for repo_path in self.repo_paths:
            use_desc = repo_path / "profiles" / "use.desc"
            if use_desc.exists():
                with use_desc.open() as f:
                    for line in f:
                        if line.strip() and not line.startswith("#"):
                            all_flags.add(line.strip().split()[0])

        all_flags = sorted(all_flags)
        self._save_cache(cache_key, all_flags)
        return all_flags

    # -----------------------------
    # Listagem de flags de um pacote
    # -----------------------------
    def list_package_flags(self, package):
        package_flags = {}
        for repo_path in self.repo_paths:
            package_path = repo_path / "profiles" / "package.use" / package
            if package_path.exists():
                with package_path.open() as f:
                    for line in f:
                        if line.strip() and "=" in line:
                            flag, status = line.strip().split("=")
                            package_flags[flag] = status

        self.audit_history.append({
            "timestamp": datetime.now().isoformat(),
            "action": "list_package_flags",
            "package": package,
            "result": package_flags
        })

        return package_flags

    # -----------------------------
    # Checagem de flag
    # -----------------------------
    def check_flag_status(self, flag):
        for repo_path in self.repo_paths:
            use_desc = repo_path / "profiles" / "use.desc"
            if use_desc.exists():
                with use_desc.open() as f:
                    for line in f:
                        if line.startswith(flag):
                            status = line.strip().split()[1] if len(line.strip().split())>1 else "unknown"
                            self.audit_history.append({
                                "timestamp": datetime.now().isoformat(),
                                "action": "check_flag_status",
                                "flag": flag,
                                "status": status
                            })
                            return status
        return None

    # -----------------------------
    # Alterar flag de um pacote (sandbox)
    # -----------------------------
    def set_package_flag(self, package, flag, value="enabled"):
        if not self.fake_root:
            raise RuntimeError("Sandbox FakeRoot não configurado.")

        package_path = self.fake_root.dest_path / "package.use" / package
        package_path.parent.mkdir(parents=True, exist_ok=True)

        flags = {}
        if package_path.exists():
            with package_path.open() as f:
                for line in f:
                    if "=" in line:
                        k, v = line.strip().split("=")
                        flags[k] = v

        flags[flag] = value

        with package_path.open("w") as f:
            for k, v in flags.items():
                f.write(f"{k}={v}\n")

        self.audit_history.append({
            "timestamp": datetime.now().isoformat(),
            "action": "set_package_flag",
            "package": package,
            "flag": flag,
            "value": value
        })
        self.logger.info(f"Flag '{flag}' de {package} definida como {value} no sandbox")

    # -----------------------------
    # Histórico de auditoria
    # -----------------------------
    def get_audit_history(self):
        return self.audit_history

    # -----------------------------
    # Sugestão automática de flags
    # -----------------------------
    def suggest_flags(self, package):
        """
        Sugere flags com base nas dependências do pacote e USE flags globais.
        """
        suggested = []
        package_flags = self.list_package_flags(package)
        all_flags = self.list_all_flags()

        for flag in all_flags:
            if flag not in package_flags:
                suggested.append(flag)

        self.audit_history.append({
            "timestamp": datetime.now().isoformat(),
            "action": "suggest_flags",
            "package": package,
            "suggested": suggested
        })

        return suggested
