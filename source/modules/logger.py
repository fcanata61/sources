import os
import json
import yaml
import datetime
from pathlib import Path
from logging.handlers import RotatingFileHandler

class Logger:
    """
    Logger avançado para o gerenciador de pacotes.
    - Multi-level logging: DEBUG, INFO, SUCCESS, WARNING, ERROR, CRITICAL
    - Rotação de logs automática
    - Saída colorida no terminal
    - Persistência em arquivo (JSON/YAML)
    - Integração com History e Hooks
    - Suporte a sandbox (FakeRoot)
    """

    LOG_COLORS = {
        "DEBUG": "\033[96m",     # Ciano
        "INFO": "\033[94m",      # Azul
        "SUCCESS": "\033[92m",   # Verde
        "WARNING": "\033[93m",   # Amarelo
        "ERROR": "\033[91m",     # Vermelho
        "CRITICAL": "\033[95m",  # Magenta
        "RESET": "\033[0m"
    }

    def __init__(self, log_file="/var/log/source.log", max_bytes=5*1024*1024, backup_count=5,
                 history=None, hooks=None, verbose=True, fake_root=None):
        self.log_file = Path(log_file)
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        self.history = history
        self.hooks = hooks or []
        self.verbose = verbose
        self.fake_root = fake_root

        # RotatingFileHandler
        self.handler = RotatingFileHandler(str(self.log_file), maxBytes=max_bytes, backupCount=backup_count)
        self.handler.setLevel("DEBUG")

    # -----------------------------
    # Formatação das mensagens
    # -----------------------------
    def _format_message(self, level, message):
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return {"timestamp": timestamp, "level": level, "message": message}

    def _write_console(self, level, message):
        if self.verbose:
            color = self.LOG_COLORS.get(level, "")
            reset = self.LOG_COLORS["RESET"]
            print(f"{color}[{message['timestamp']}] [{level}] {message['message']}{reset}")

    def _write_file(self, message):
        # Suporte a FakeRoot
        file_path = self.fake_root.dest_path / self.log_file.name if self.fake_root else self.log_file
        with file_path.open("a") as f:
            f.write(json.dumps(message) + "\n")

    def _trigger_hooks(self, level, message):
        for hook in self.hooks:
            hook(level, message)

    # -----------------------------
    # Logging genérico
    # -----------------------------
    def log(self, level, msg):
        message = self._format_message(level, msg)
        self._write_console(level, message)
        self._write_file(message)
        self._trigger_hooks(level, message)
        # Integração com History
        if self.history:
            self.history.record("log", "system", {"level": level, "message": msg})

    # -----------------------------
    # Funções de nível
    # -----------------------------
    def debug(self, msg): self.log("DEBUG", msg)
    def info(self, msg): self.log("INFO", msg)
    def success(self, msg): self.log("SUCCESS", msg)
    def warning(self, msg): self.log("WARNING", msg)
    def error(self, msg): self.log("ERROR", msg)
    def critical(self, msg): self.log("CRITICAL", msg)

    # -----------------------------
    # Exportação de logs
    # -----------------------------
    def export_logs(self, output_file, format="json"):
        output_file = Path(output_file)
        logs = []
        with self.log_file.open("r") as f:
            for line in f:
                try:
                    logs.append(json.loads(line))
                except:
                    continue
        if format == "json":
            output_file.write_text(json.dumps(logs, indent=4))
        elif format == "yaml":
            output_file.write_text(yaml.dump(logs, default_flow_style=False))
        else:
            raise ValueError("Formato de exportação inválido. Suporte: json, yaml.")
