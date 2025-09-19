import hashlib
from pathlib import Path
from datetime import datetime
from source.modules.fakeroot import FakeRoot
from source.modules.cache import CacheManager
import json

class RecipeHash:
    """
    Gera, verifica e injeta hashes (SHA256, SHA512, MD5, BLAKE2b) em receitas.
    Suporte a sandbox, cache e auditoria.
    """

    def __init__(self, repo_path="/usr/source", fake_root: FakeRoot = None, cache_manager: CacheManager = None, verbose=False):
        self.repo_path = Path(repo_path).resolve()
        self.fake_root = fake_root
        self.cache_manager = cache_manager
        self.verbose = verbose
        self.audit_history = []

    # -----------------------------
    # Geração de hash
    # -----------------------------
    def generate_hash(self, file_path, algorithm="sha256"):
        file_path = Path(file_path)
        if self.fake_root:
            file_path = self.fake_root.dest_path / file_path.relative_to(file_path.anchor)

        if self.cache_manager:
            cached_file = self.cache_manager.get_file(file_path.name)
            if cached_file:
                return self._compute_hash(cached_file, algorithm)

        return self._compute_hash(file_path, algorithm)

    def _compute_hash(self, file_path: Path, algorithm="sha256"):
        if algorithm not in hashlib.algorithms_available:
            raise ValueError(f"Algoritmo {algorithm} não suportado.")

        hash_func = hashlib.new(algorithm)
        with file_path.open("rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                hash_func.update(chunk)
        digest = hash_func.hexdigest()

        self.audit_history.append({
            "timestamp": datetime.now().isoformat(),
            "action": "generate_hash",
            "file": str(file_path),
            "algorithm": algorithm,
            "hash": digest
        })

        if self.verbose:
            print(f"[HASH] {algorithm} {file_path}: {digest}")
        return digest

    # -----------------------------
    # Injeção de hash em receita
    # -----------------------------
    def inject_into_recipe(self, recipe_file, file_hashes: dict):
        recipe_file = Path(recipe_file).resolve()
        if not recipe_file.exists():
            raise FileNotFoundError(f"Arquivo de receita {recipe_file} não encontrado.")

        try:
            data = json.loads(recipe_file.read_text())
        except json.JSONDecodeError:
            raise ValueError("A receita deve estar em formato JSON válido.")

        data["hashes"] = file_hashes
        recipe_file.write_text(json.dumps(data, indent=4))

        self.audit_history.append({
            "timestamp": datetime.now().isoformat(),
            "action": "inject_into_recipe",
            "file": str(recipe_file),
            "hashes": file_hashes
        })

    # -----------------------------
    # Verificação de integridade
    # -----------------------------
    def verify_integrity(self, file_path, expected_hash, algorithm="sha256"):
        actual_hash = self.generate_hash(file_path, algorithm)
        result = actual_hash == expected_hash

        self.audit_history.append({
            "timestamp": datetime.now().isoformat(),
            "action": "verify_integrity",
            "file": str(file_path),
            "algorithm": algorithm,
            "expected": expected_hash,
            "actual": actual_hash,
            "result": result
        })
        return result

    # -----------------------------
    # Gerar hashes para múltiplos arquivos
    # -----------------------------
    def generate_for_files(self, files: list, algorithms=None):
        if algorithms is None:
            algorithms = ["sha256"]

        all_hashes = {}
        for f in files:
            file_hashes = {}
            for algo in algorithms:
                file_hashes[algo] = self.generate_hash(f, algo)
            all_hashes[str(f)] = file_hashes
        return all_hashes

    # -----------------------------
    # Auditoria
    # -----------------------------
    def get_audit_history(self):
        return self.audit_history
