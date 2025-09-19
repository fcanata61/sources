import sys
import argparse
from source.modules.build import Builder
from source.modules.remove import Remover
from source.modules.upgrade import Upgrader
from source.modules.flags import UseFlags
from source.modules.query import UseQuery
from source.modules.sync import SyncManager
from source.modules.logger import Logger

class SourceCLI:
    """ Interface de linha de comando (CLI) para o gerenciador de pacotes source. """

    def __init__(self):
        self.logger = Logger()
        self.parser = argparse.ArgumentParser(
            prog="source",
            description="Gerenciador de pacotes - Source"
        )
        self.subparsers = self.parser.add_subparsers(dest="command")

        # Global flags
        self.parser.add_argument(
            "-v", "--verbose", action="store_true",
            help="Modo verbose"
        )
        self.parser.add_argument(
            "--dry-run", action="store_true",
            help="Simular operações sem realmente executar"
        )
        self.parser.add_argument(
            "--jobs", "-j", type=int, default=1,
            help="Número de jobs/paralelismo para construções"
        )

        # Comandos principais
        self._add_install()
        self._add_remove()
        self._add_upgrade()
        self._add_flags()
        self._add_sync()
        self._add_create()
        self._add_history()

    def _add_install(self):
        sp = self.subparsers.add_parser("install", aliases=["i"], help="Instalar pacotes")
        sp.add_argument("package", help="Nome do pacote a instalar")
        sp.add_argument("--prefix", help="Prefixo de instalação customizado")
        sp.add_argument("--force", action="store_true", help="Forçar reinstalação mesmo que já instalado")

    def _add_remove(self):
        sp = self.subparsers.add_parser("remove", aliases=["rm"], help="Remover pacotes")
        sp.add_argument("package", help="Nome do pacote a remover")
        sp.add_argument("--force", action="store_true", help="Forçar remoção ignorando dependências")

    def _add_upgrade(self):
        sp = self.subparsers.add_parser("upgrade", aliases=["up"], help="Atualizar pacotes")
        sp.add_argument("package", nargs="?", help="Nome do pacote (vazio = todo o sistema)")
        sp.add_argument("--all", action="store_true", help="Atualizar todos os pacotes instalados")

    def _add_flags(self):
        sp = self.subparsers.add_parser("flags", aliases=["fl"], help="Consultar ou ajustar USE flags")
        sp.add_argument("package", nargs="?", help="Nome do pacote para exibir flags")
        sp.add_argument("--list", action="store_true", help="Listar todas as flags globais")
        sp.add_argument("--enable", help="Ativar flag global")
        sp.add_argument("--disable", help="Desativar flag global")

    def _add_sync(self):
        sp = self.subparsers.add_parser("sync", aliases=["s"], help="Sincronizar repositório")
        sp.add_argument("--repo-url", help="URL do repositório remoto", default=None)

    def _add_create(self):
        sp = self.subparsers.add_parser("create", aliases=["c"], help="Criar nova receita")
        sp.add_argument("package", help="Nome do pacote a criar")
        sp.add_argument("--template", help="Usar um template para a receita", default=None)

    def _add_history(self):
        sp = self.subparsers.add_parser("history", aliases=["h"], help="Exibir histórico de operações")
        sp.add_argument("--limit", type=int, default=50, help="Número de registros a exibir")

    def run(self, args=None):
        args = self.parser.parse_args(args)

        # Ajustar logger / configurações globais
        if getattr(args, "verbose", False):
            self.logger.set_level("DEBUG")
        if getattr(args, "dry_run", False):
            self.logger.info("Modo dry-run ativado — nenhuma ação será de fato realizada")

        try:
            if args.command in ("install", "i"):
                self.logger.info(f"Instalando {args.package}...")
                # Instanciar Builder ou outro módulo que gerencia install
                builder = Builder(
                    recipe=None,  # aqui você deveria transformar args.package numa recipe
                    sandbox_path="...",  # configuração ou padrão
                    dest_path="...",
                    verbose=args.verbose,
                    dry_run=args.dry_run,
                    jobs=args.jobs
                )
                # Possivelmente verificar se já está instalado, tratar force
                builder.build()
                builder.install()

            elif args.command in ("remove", "rm"):
                self.logger.info(f"Removendo {args.package} (force={args.force})...")
                remover = Remover(package=args.package, force=args.force, dry_run=args.dry_run)
                remover.remove()

            elif args.command in ("upgrade", "up"):
                if args.all:
                    self.logger.info("Atualizando todos os pacotes instalados...")
                    upgrader = Upgrader(all_packages=True, dry_run=args.dry_run)
                elif args.package:
                    self.logger.info(f"Atualizando pacote {args.package}...")
                    upgrader = Upgrader(package=args.package, dry_run=args.dry_run)
                else:
                    self.logger.error("Para upgrade: especifique --all ou um nome de pacote")
                    return 1
                upgrader.upgrade()

            elif args.command in ("flags", "fl"):
                uf = UseFlags(logger=self.logger)  # supondo que esse módulo exista
                if args.list:
                    uf.list_global()
                elif args.enable:
                    uf.enable_global(args.enable)
                elif args.disable:
                    uf.disable_global(args.disable)
                elif args.package:
                    q = UseQuery(package=args.package, logger=self.logger)
                    q.show_flags()

            elif args.command in ("sync", "s"):
                repo_url = args.repo_url
                sm = SyncManager(repo_url=repo_url, logger=self.logger)
                sm.sync()

            elif args.command in ("create", "c"):
                self.logger.info(f"Criando nova receita para {args.package}...")
                # chamar módulo que gera um template de receita
                from source.modules.create import RecipeCreator
                creator = RecipeCreator(package=args.package, template=args.template, logger=self.logger)
                creator.create()

            elif args.command in ("history", "h"):
                self.logger.info(f"Exibindo histórico (limite={args.limit})...")
                from source.modules.history import HistoryManager
                hm = HistoryManager(limit=args.limit, logger=self.logger)
                hm.show()

            else:
                self.parser.print_help()

            return 0

        except Exception as e:
            self.logger.error(f"Erro: {e}")
            if getattr(args, "verbose", False):
                import traceback
                traceback.print_exc()
            return 1


def main():
    cli = SourceCLI()
    sys.exit(cli.run())

if __name__ == "__main__":
    main()
