import json
import os
import datetime
from collections import defaultdict

class UseFlags:
    """
    Gerencia USE flags globais e específicas por pacote, com histórico e grupos.
    """

    def __init__(self, config_path="/etc/source/use.conf", verbose=False):
        self.config_path = config_path
        self.global_flags = {}
        self.package_flags = {}
        self.history = []
        self.groups = defaultdict(set)  # grupo -> set de flags
        self.verbose = verbose
        self.load()

    # -----------------------------
    # Load / Save
    # -----------------------------

    def load(self):
        """Carrega flags e histórico do arquivo JSON."""
        if os.path.exists(self.config_path):
            with open(self.config_path, "r") as f:
                config = json.load(f)
                self.global_flags = config.get("global_flags", {})
                self.package_flags = config.get("package_flags", {})
                self.history = config.get("history", [])
                self.groups = defaultdict(set, {k: set(v) for k, v in config.get("groups", {}).items()})
            if self.verbose:
                print(f"[DEBUG] Flags carregadas de {self.config_path}")
        else:
            if self.verbose:
                print(f"[DEBUG] Arquivo de configuração não encontrado: {self.config_path}")

    def save(self):
        """Salva flags, histórico e grupos no arquivo JSON."""
        config = {
            "global_flags": self.global_flags,
            "package_flags": self.package_flags,
            "history": self.history,
            "groups": {k: list(v) for k, v in self.groups.items()}
        }
        with open(self.config_path, "w") as f:
            json.dump(config, f, indent=4)
        if self.verbose:
            print(f"[DEBUG] Flags salvas em {self.config_path}")

    # -----------------------------
    # Manipulação de flags
    # -----------------------------

    def enable_global(self, flag, user="system"):
        self.global_flags[flag] = True
        self._log_action("enable_global", flag, user)
        self.save()

    def disable_global(self, flag, user="system"):
        self.global_flags[flag] = False
        self._log_action("disable_global", flag, user)
        self.save()

    def set_package_flags(self, package, flags_dict, user="system"):
        """Define flags específicas para um pacote."""
        self.package_flags[package] = flags_dict
        for flag, enabled in flags_dict.items():
            action = "enable_package" if enabled else "disable_package"
            self._log_action(action, flag, user, package)
        self.save()

    # -----------------------------
    # Consultas
    # -----------------------------

    def is_flag_enabled(self, flag):
        """Verifica se uma flag global está ativada."""
        return self.global_flags.get(flag, False)

    def is_package_flag_enabled(self, package, flag):
        """Verifica se uma flag está ativada para um pacote."""
        pkg_flags = self.package_flags.get(package, {})
        return pkg_flags.get(flag, self.is_flag_enabled(flag))

    def list_enabled_flags(self):
        """Lista todas flags ativas globais e por pacote."""
        enabled_global = [f for f, v in self.global_flags.items() if v]
        enabled_packages = {
            pkg: [f for f, v in flags.items() if v]
            for pkg, flags in self.package_flags.items()
            if any(flags.values())
        }
        return {"global": enabled_global, "packages": enabled_packages}

    def list_all_flags(self):
        """Lista todas as flags (ativadas ou não)."""
        all_pkg_flags = {pkg: list(flags.keys()) for pkg, flags in self.package_flags.items()}
        return {"global": list(self.global_flags.keys()), "packages": all_pkg_flags}

    # -----------------------------
    # Grupos de flags
    # -----------------------------

    def register_group(self, group_name, flags):
        """Cria um grupo de flags."""
        self.groups[group_name].update(flags)
        self.save()

    def enable_group(self, group_name, user="system"):
        for flag in self.groups.get(group_name, []):
            self.enable_global(flag, user=user)

    def disable_group(self, group_name, user="system"):
        for flag in self.groups.get(group_name, []):
            self.disable_global(flag, user=user)

    # -----------------------------
    # Histórico de alterações
    # -----------------------------

    def _log_action(self, action, flag, user, package=None):
        entry = {
            "timestamp": datetime.datetime.now().isoformat(),
            "action": action,
            "flag": flag,
            "user": user,
            "package": package
        }
        self.history.append(entry)
        if self.verbose:
            print(f"[DEBUG] {entry}")

    def get_history(self, package=None):
        """Retorna histórico de alterações. Filtra por pacote se fornecido."""
        if package:
            return [h for h in self.history if h.get("package") == package]
        return self.history

    # -----------------------------
    # Export / Import
    # -----------------------------

    def export_json(self):
        return json.dumps({
            "global_flags": self.global_flags,
            "package_flags": self.package_flags,
            "history": self.history,
            "groups": {k: list(v) for k, v in self.groups.items()}
        }, indent=4)

    def import_json(self, json_str):
        data = json.loads(json_str)
        self.global_flags = data.get("global_flags", {})
        self.package_flags = data.get("package_flags", {})
        self.history = data.get("history", [])
        self.groups = defaultdict(set, {k: set(v) for k, v in data.get("groups", {}).items()})
        self.save()
