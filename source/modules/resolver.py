from source.modules.graph import DependencyGraph
import json

class DependencyResolver:
    """
    Resolver de dependências avançado.
    Integra com DependencyGraph e installed_db.
    """

    def __init__(self, installed_db, verbose=False):
        self.installed_db = installed_db
        self.verbose = verbose

    # -----------------------------
    # Parsing e Resolução
    # -----------------------------

    def parse_dependencies(self, recipe, use_flags=None):
        """
        Retorna todas dependências válidas de um pacote considerando USE flags.
        Retorna um dict {dep_name: weight}, weight default=1.
        """
        deps = {}
        for dep_type in ["build_deps", "runtime_deps", "optional_deps"]:
            for dep, flag in recipe.get(dep_type, {}).items():
                if not flag or (use_flags and flag in use_flags):
                    deps[dep] = 1
        return deps

    def build_graph(self, recipe, use_flags=None):
        """
        Constrói grafo completo de dependências de um pacote.
        Retorna DependencyGraph.
        """
        graph = DependencyGraph(verbose=self.verbose)
        visited = set()

        def visit(r):
            if r["name"] in visited:
                return
            visited.add(r["name"])
            deps = self.parse_dependencies(r, use_flags)
            graph.add_package(r["name"], deps)
            for dep_name in deps.keys():
                dep_recipe = self.installed_db.get_recipe(dep_name)
                if dep_recipe:
                    visit(dep_recipe)

        visit(recipe)

        if graph.detect_cycles():
            raise RuntimeError("Ciclo de dependências detectado!")

        return graph

    # -----------------------------
    # Consultas
    # -----------------------------

    def resolve(self, recipe, use_flags=None):
        """
        Retorna lista ordenada topologicamente de pacotes para instalação.
        """
        graph = self.build_graph(recipe, use_flags)
        return graph.topo_sort()

    def find_missing(self, recipe, use_flags=None):
        """Retorna lista de dependências não instaladas."""
        resolved = self.resolve(recipe, use_flags)
        missing = [pkg for pkg in resolved if not self.installed_db.is_installed(pkg)]
        return missing

    def find_reverse_dependencies(self, package_name):
        """Retorna pacotes que dependem diretamente do pacote informado."""
        reverse_deps = []
        for pkg in self.installed_db.get_installed_packages():
            recipe = self.installed_db.get_recipe(pkg)
            deps = self.parse_dependencies(recipe)
            if package_name in deps:
                reverse_deps.append(pkg)
        return reverse_deps

    def get_subgraph(self, recipe, use_flags=None, packages=None):
        """
        Retorna subgrafo contendo apenas pacotes específicos ou todas dependências do recipe.
        """
        graph = self.build_graph(recipe, use_flags)
        if packages:
            return graph.subgraph(packages)
        return graph

    # -----------------------------
    # Auditoria
    # -----------------------------

    def audit(self, recipe, use_flags=None):
        """
        Audita o pacote e retorna:
        - dependências ausentes
        - dependências órfãs
        """
        graph = self.build_graph(recipe, use_flags)
        missing = [pkg for pkg in graph.nodes if not self.installed_db.is_installed(pkg)]
        orphans = [pkg for pkg in self.installed_db.get_installed_packages()
                   if not self.installed_db.has_dependents(pkg)]
        return {
            "missing": missing,
            "orphans": orphans
        }

    # -----------------------------
    # Export / Import
    # -----------------------------

    def export_graph(self, recipe, use_flags=None):
        """Exporta grafo de dependências para JSON."""
        graph = self.build_graph(recipe, use_flags)
        return graph.to_json()

    def import_graph(self, json_str):
        """Importa grafo de dependências a partir de JSON."""
        graph = DependencyGraph(verbose=self.verbose)
        graph.from_json(json_str)
        return graph

    # -----------------------------
    # Debug / Verbose
    # -----------------------------

    def print_graph(self, recipe, use_flags=None):
        graph = self.build_graph(recipe, use_flags)
        for pkg in graph.nodes:
            deps = graph.get_direct_dependencies(pkg)
            print(f"{pkg} -> {deps}")
