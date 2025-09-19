from collections import defaultdict, deque
import json

class DependencyGraph:
    """Grafo de dependências avançado para pacotes."""

    def __init__(self, verbose=False):
        self.graph = defaultdict(dict)  # pacote -> {dep: weight}
        self.nodes = set()
        self.verbose = verbose

    # -----------------------------
    # Manipulação do grafo
    # -----------------------------

    def add_package(self, package, dependencies=None, weight=1):
        """
        Adiciona pacote e dependências ao grafo.
        dependencies: dict ou lista de pacotes
        weight: peso default das arestas
        """
        self.nodes.add(package)
        if dependencies:
            if isinstance(dependencies, dict):
                for dep, w in dependencies.items():
                    self.graph[package][dep] = w
                    self.nodes.add(dep)
            else:  # lista
                for dep in dependencies:
                    self.graph[package][dep] = weight
                    self.nodes.add(dep)
        if self.verbose:
            print(f"[DEBUG] Pacote '{package}' adicionado com deps: {self.graph.get(package, {})}")

    def remove_package(self, package):
        """Remove um pacote do grafo e todas as referências a ele."""
        self.graph.pop(package, None)
        for deps in self.graph.values():
            deps.pop(package, None)
        self.nodes.discard(package)
        if self.verbose:
            print(f"[DEBUG] Pacote '{package}' removido do grafo")

    # -----------------------------
    # Consultas
    # -----------------------------

    def get_direct_dependencies(self, package):
        """Retorna dependências diretas do pacote."""
        return list(self.graph.get(package, {}).keys())

    def get_all_dependencies(self, package):
        """Retorna todas dependências diretas e indiretas."""
        all_deps = set()
        stack = [package]
        while stack:
            pkg = stack.pop()
            for dep in self.graph.get(pkg, {}):
                if dep not in all_deps:
                    all_deps.add(dep)
                    stack.append(dep)
        return list(all_deps)

    def get_dependents(self, package):
        """Retorna pacotes que dependem diretamente de 'package'."""
        dependents = [pkg for pkg, deps in self.graph.items() if package in deps]
        return dependents

    # -----------------------------
    # Ciclos e topologia
    # -----------------------------

    def detect_cycles(self):
        """Detecta ciclos no grafo. Retorna True/False."""
        visited = set()
        rec_stack = set()

        def dfs(node):
            visited.add(node)
            rec_stack.add(node)
            for neighbor in self.graph.get(node, {}):
                if neighbor not in visited:
                    if dfs(neighbor):
                        return True
                elif neighbor in rec_stack:
                    return True
            rec_stack.remove(node)
            return False

        for node in self.nodes:
            if node not in visited and dfs(node):
                return True
        return False

    def topo_sort(self):
        """
        Ordenação topológica (Kahn).
        Levanta exceção se houver ciclos.
        """
        in_degree = {node: 0 for node in self.nodes}
        for deps in self.graph.values():
            for dep in deps:
                in_degree[dep] += 1

        queue = deque([node for node, deg in in_degree.items() if deg == 0])
        order = []

        while queue:
            node = queue.popleft()
            order.append(node)
            for neighbor in self.graph.get(node, {}):
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        if len(order) != len(self.nodes):
            raise RuntimeError("Ciclo de dependências detectado no grafo!")

        return order

    # -----------------------------
    # Subgrafo e métricas
    # -----------------------------

    def subgraph(self, packages):
        """Retorna um subgrafo contendo apenas os pacotes especificados."""
        sg = DependencyGraph(verbose=self.verbose)
        for pkg in packages:
            if pkg in self.nodes:
                deps = {dep: w for dep, w in self.graph.get(pkg, {}).items() if dep in packages}
                sg.add_package(pkg, deps)
        return sg

    def metrics(self):
        """Retorna métricas básicas do grafo."""
        leaves = [node for node in self.nodes if not self.graph.get(node)]
        roots = [node for node in self.nodes if not self.get_dependents(node)]
        return {
            "total_nodes": len(self.nodes),
            "total_edges": sum(len(deps) for deps in self.graph.values()),
            "leaves": leaves,
            "roots": roots
        }

    # -----------------------------
    # Export / Import
    # -----------------------------

    def to_dict(self):
        """Retorna grafo como dicionário."""
        return {node: deps.copy() for node, deps in self.graph.items()}

    def from_dict(self, d):
        """Carrega grafo de um dicionário."""
        self.graph = {k: v.copy() for k, v in d.items()}
        self.nodes = set(self.graph.keys())
        for deps in self.graph.values():
            self.nodes.update(deps.keys())

    def to_json(self):
        """Exporta grafo para JSON."""
        return json.dumps(self.to_dict(), indent=2)

    def from_json(self, json_str):
        """Importa grafo de JSON."""
        self.from_dict(json.loads(json_str))
