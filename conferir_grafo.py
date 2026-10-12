"""
Conferência do grafo contra o desenho (§6.4).

Importa o MESMO objeto que o sistema executa (src/grafo.py: GRAFO — o que
src/sistema.py invoca) e imprime os nós e as arestas. Não monta grafo
nenhum aqui dentro. A saída vai colada em docs/arquitetura.md §6.4.

    python conferir_grafo.py
"""
from src.grafo import GRAFO
from src.sistema import GRAFO as GRAFO_DO_SISTEMA

assert GRAFO is GRAFO_DO_SISTEMA, "o script tem de conferir o grafo que o sistema executa"

g = GRAFO.get_graph()

print(f"NÓS ({len(g.nodes)}):")
for nome in g.nodes:
    print(f"  {nome}")

arestas = sorted(g.edges, key=lambda e: (e.source, e.target))
print(f"\nARESTAS ({len(arestas)}) — [cond] = condicional:")
for e in arestas:
    print(f"  {e.source} -> {e.target}{'   [cond]' if e.conditional else ''}")
