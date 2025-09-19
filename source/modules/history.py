import os
import json
import shutil
from datetime import datetime
from pathlib import Path
from source.modules.fakeroot import FakeRoot
from source.modules.cache import CacheManager

class History:
    """
    Histórico avançado de operações de pacotes, com persistência, rollback e auditoria.
    """

    def __init__(self, history_file="/var/log/source_history.json", fake_root: FakeRoot = None, cache_manager: CacheManager = None, verbose=False):
        self.history_file = Path(history_file).resolve()
        self.history_file.parent.mkdir(parents=True, exist_ok=True)
        if not self.history_file.exists():
            self.history_file.write_text("[]")
        self.fake_root = fake_root
        self.cache_manager = cache_manager
        self.verbose = verbose
        self.audit_history = []

    def _load_history(self):
        with self.history_file.open("r") as f:
            return json.load(f)

    def _save_history(self, history):
        with self.history_file.open("w") as f:
            json.dump(history, f, indent=4)

    # -----------------------------
    # Registro de ação
    # -----------------------------
    def record(self, action, package, details=None, status="success"):
        """
        Registra uma ação no histórico.
        """
        history = self._load_history()
        action_id = len(history) + 1
        timestamp = datetime.now().isoformat()
        entry = {
            "id": action_id,
            "timestamp": timestamp,
            "action": action,
            "package": package,
            "details": details or {},
            "status": status
        }
        history.append(entry)
        self._save_history(history)
        self.audit_history.append(entry)
        if self.verbose:
            print(f"[HISTORY] {action} | {package} | {status}")

    # -----------------------------
    # Listagem e filtragem
    # -----------------------------
    def list_history(self, limit=50, package=None, action_type=None, status=None):
        history = self._load_history()
        filtered = history
        if package:
            filtered = [h for h in filtered if h["package"] == package]
        if action_type:
            filtered = [h for h in filtered if h["action"] == action_type]
        if status:
            filtered = [h for h in filtered if h["status"] == status]
        return filtered[-limit:]

    # -----------------------------
    # Rollback seguro
    # -----------------------------
    def rollback(self, action_id):
        history = self._load_history()
        action = next((item for item in history if item["id"] == action_id), None)
        if not action:
            raise ValueError(f"Ação com ID {action_id} não encontrada.")

        # Exemplo de rollback: se ação afetou arquivos, restaurar do cache
        details = action.get("details", {})
        files = details.get("files", [])
        for f in files:
            fpath = Path(f)
            if self.cache_manager:
                cached = self.cache_manager.get_file(fpath.name)
                if cached:
                    shutil.copy(cached, fpath)
                    if self.verbose:
                        print(f"[ROLLBACK] Restaurado {fpath} do cache.")
            elif self.fake_root:
                # rollback no sandbox
                sandbox_file = self.fake_root.dest_path / fpath.relative_to(fpath.anchor)
                if sandbox_file.exists():
                    sandbox_file.unlink()
                    if self.verbose:
                        print(f"[ROLLBACK] Removido {sandbox_file} do sandbox.")
        self.record("rollback", action["package"], details={"rolled_back_id": action_id}, status="rolled_back")

    # -----------------------------
    # Exportação de histórico
    # -----------------------------
    def export_history(self, export_file):
        export_file = Path(export_file).resolve()
        history = self._load_history()
        with export_file.open("w") as f:
            json.dump(history, f, indent=4)
        if self.verbose:
            print(f"[HISTORY] Exportado para {export_file}")

    # -----------------------------
    # Auditoria
    # -----------------------------
    def get_audit_history(self):
        return self.audit_history
