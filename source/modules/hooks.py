import asyncio
import logging
import subprocess
from typing import Callable, List, Dict, Any
from datetime import datetime
from source.modules.fakeroot import FakeRoot  # integração com o sandbox

class Hook:
    """
    Representa um hook:
    - func: função Python (opcional)
    - commands: lista de comandos shell da receita
    - stage: etapa do hook
    - package: pacote alvo
    - priority: ordem de execução
    - rollback: função opcional para desfazer alterações
    - condition: função opcional para habilitar/desabilitar hook
    """
    def __init__(self, stage: str, package: str = None, func: Callable = None,
                 commands: List[str] = None, priority: int = 10,
                 rollback: Callable = None, condition: Callable = None):
        self.stage = stage
        self.package = package
        self.func = func
        self.commands = commands or []
        self.priority = priority
        self.rollback = rollback
        self.condition = condition

class HookManager:
    """
    Gerenciador de hooks capaz de executar:
    - funções Python
    - comandos da receita
    Tudo dentro do sandbox FakeRoot.
    """

    def __init__(self, verbose: bool = False):
        self.hooks: List[Hook] = []
        self.verbose = verbose
        self.history: List[Dict] = []
        self.logger = self._setup_logger()

    def _setup_logger(self):
        logger = logging.getLogger("HookManager")
        logger.setLevel(logging.DEBUG if self.verbose else logging.INFO)
        if not logger.handlers:
            ch = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')
            ch.setFormatter(formatter)
            logger.addHandler(ch)
        return logger

    def register_hook(self, stage: str, package: str = None, func: Callable = None,
                      commands: List[str] = None, priority: int = 10,
                      rollback: Callable = None, condition: Callable = None):
        """
        Registra um hook com comandos e/ou função Python.
        """
        self.hooks.append(Hook(stage, package, func, commands, priority, rollback, condition))
        self.logger.info(f"Hook registrado: stage={stage}, package={package}, priority={priority}")

    async def run_hooks(self, stage: str, package: str = None, fake_root: FakeRoot = None, *args, **kwargs):
        """
        Executa hooks para o estágio e pacote, dentro do sandbox FakeRoot.
        """
        applicable_hooks = sorted(
            [h for h in self.hooks if h.stage == stage and (h.package is None or h.package == package)],
            key=lambda h: h.priority
        )

        for hook in applicable_hooks:
            if hook.condition and not hook.condition(package):
                continue

            start_time = datetime.now().isoformat()
            status = "success"
            output = ""
            try:
                # Executa função Python, se houver
                if hook.func:
                    if asyncio.iscoroutinefunction(hook.func):
                        await hook.func(*args, **kwargs)
                    else:
                        hook.func(*args, **kwargs)

                # Executa comandos da receita dentro do sandbox
                for cmd in hook.commands:
                    if fake_root:
                        # prefixa comandos com DESTDIR para usar sandbox
                        cmd = f"DESTDIR={fake_root.dest_path} {cmd}"
                    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
                    output += f"$ {cmd}\n{result.stdout}{result.stderr}\n"
                    if result.returncode != 0:
                        raise RuntimeError(f"Comando falhou: {cmd}\n{result.stderr}")

                self.logger.info(f"Hook executado com sucesso: stage={stage}, package={package}")

            except Exception as e:
                status = f"error: {e}"
                self.logger.error(f"Erro no hook stage={stage}, package={package}: {e}")
                # aplica rollback se definido
                if hook.rollback:
                    try:
                        hook.rollback(*args, **kwargs)
                        self.logger.info(f"Rollback aplicado para hook stage={stage}, package={package}")
                    except Exception as re:
                        self.logger.error(f"Erro no rollback: {re}")

            # registra histórico
            self.history.append({
                "timestamp": start_time,
                "stage": stage,
                "package": package,
                "status": status,
                "commands_output": output
            })

    def get_history(self, package: str = None, stage: str = None):
        """
        Retorna histórico filtrado por pacote ou estágio.
        """
        h = self.history
        if package:
            h = [x for x in h if x["package"] == package]
        if stage:
            h = [x for x in h if x["stage"] == stage]
        return h
