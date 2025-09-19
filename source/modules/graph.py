from collections import defaultdict, deque

class DependencyGraph:
    """Grafo de dependências para pacotes."""

    def __init__(self):
        self.graph = defaultdict(set)  # pacote -> set de dependências
        self.packages = set()

    def add_package(self, package, dependencies=None):
        """Adiciona pacote e suas dependências ao grafo."""
        self.packages.add(package)
        if dependencies:
            for dep in dependencies:
                self.graph[package].add(dep)
                self.packages.add(dep)

    def detect_cycles(self):
        """Detecta ciclos no grafo. Retorna True se existir ciclo."""
        visited = set()
        rec_stack = set()

        def dfs(node):
            visited.add(node)
            rec_stack.add(node)
            for neighbor in self.graph.get(node, []):
                if neighbor not in visited:
                    if dfs(neighbor):
                        return True
                elif neighbor in rec_stack:
                    return True
            rec_stack.remove(node)
            return False

        for pkg in self.packages:
            if pkg not in visited:
                if dfs(pkg):
                    return True
        return False

    def topo_sort(self):
        """
        Retorna lista de pacotes ordenada topologicamente
        (ordem correta para instalação/upgrades).
        """
        in_degree = {pkg: 0 for pkg in self.packages}
        for deps in self.graph.values():
            for dep in deps:
                in_degree[dep] += 1

        queue = deque([pkg for pkg, deg in in_degree.items() if deg == 0])
        order = []

        while queue:
            pkg = queue.popleft()
            order.append(pkg)
            for neighbor in self.graph.get(pkg, []):
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        if len(order) != len(self.packages):
            raise RuntimeError("Ciclo de dependências detectado no grafo!")
        return order
