from source.modules.graph import DependencyGraph

class DependencyResolver:
    """
    Resolve dependências de pacotes.
    Integra com banco de dados de pacotes instalados e USE flags.
    """

    def __init__(self, installed_db, verbose=False):
        self.installed_db = installed_db
        self.verbose = verbose

    def parse_dependencies(self, recipe, use_flags=None):
        """
        Retorna lista de dependências de um pacote (build/runtime/optional)
        considerando USE flags.
        """
        deps = set()

        # build/runtime/optional deps
        for dep_type in ["build", "runtime", "optional"]:
            for dep, flag in recipe.get(f"{dep_type}_deps", {}).items():
                if not flag or (use_flags and flag in use_flags):
                    deps.add(dep)
        return deps

    def resolve(self, recipe, use_flags=None):
        """
        Retorna lista ordenada de dependências (topo sort) para instalação/upgrade.
        """
        graph = DependencyGraph()
        visited = set()

        def visit(r):
            if r["name"] in visited:
                return
            visited.add(r["name"])
            deps = self.parse_dependencies(r, use_flags)
            graph.add_package(r["name"], deps)
            for dep_name in deps:
                dep_recipe = self.installed_db.get_recipe(dep_name)
                if dep_recipe:
                    visit(dep_recipe)

        visit(recipe)

        if graph.detect_cycles():
            raise RuntimeError("Ciclo de dependências detectado!")

        return graph.topo_sort()

    def find_missing(self, recipe, use_flags=None):
        """Retorna dependências que não estão instaladas."""
        resolved = self.resolve(recipe, use_flags)
        missing = [pkg for pkg in resolved if not self.installed_db.is_installed(pkg)]
        return missing

    def find_reverse_dependencies(self, package_name):
        """
        Retorna lista de pacotes que dependem do pacote informado.
        """
        reverse_deps = []
        for pkg in self.installed_db.get_installed_packages():
            recipe = self.installed_db.get_recipe(pkg)
            deps = self.parse_dependencies(recipe)
            if package_name in deps:
                reverse_deps.append(pkg)
        return reverse_deps
