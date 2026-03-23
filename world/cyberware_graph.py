"""
Cyberware dependency graph using networkx.

Builds a directed acyclic graph from all CyberwareBase subclasses at import time.
Nodes are class names; edges represent dependency relationships.

Public API:
    get_cyberware_graph()  -> nx.DiGraph
    get_conflict_graph()   -> nx.Graph
    validate_install_order(class_names)  -> (bool, str | list)
    get_install_prerequisites(class_name)  -> list[str]
    get_conflicts_for(class_name)  -> list[str]
    invalidate_graph()  -> None   (call after adding new cyberware subclasses at runtime)
"""

import importlib
import logging
import pkgutil

import networkx as nx

logger = logging.getLogger("evennia")

_dep_graph: nx.DiGraph | None = None
_conflict_graph: nx.Graph | None = None


def _all_cyberware_classes() -> list:
    """
    Collect all non-abstract CyberwareBase subclasses by importing the
    cyberware catalog and the base module.
    """
    classes = []
    try:
        from typeclasses.cyberware import CyberwareBase
        # Import the catalog so all subclasses are registered.
        import typeclasses.cyberware_catalog  # noqa: F401
        # Walk all subclasses recursively.
        stack = list(CyberwareBase.__subclasses__())
        seen = set()
        while stack:
            cls = stack.pop()
            if cls.__name__ in seen:
                continue
            seen.add(cls.__name__)
            classes.append(cls)
            stack.extend(cls.__subclasses__())
    except Exception as exc:
        logger.warning(f"[cyberware_graph] Could not enumerate cyberware classes: {exc}")
    return classes


def _build_graphs() -> tuple[nx.DiGraph, nx.Graph]:
    """Build the dependency DiGraph and conflict Graph from all cyberware classes."""
    dep_g = nx.DiGraph()
    conflict_g = nx.Graph()
    classes = _all_cyberware_classes()
    for cls in classes:
        name = cls.__name__
        dep_g.add_node(name)
        conflict_g.add_node(name)
        # required_implants: ALL of these must be installed first.
        for req in (getattr(cls, "required_implants", None) or []):
            dep_g.add_node(req)
            dep_g.add_edge(req, name, type="requires_all")
        # required_implants_any: at least one of these must be installed.
        for req in (getattr(cls, "required_implants_any", None) or []):
            dep_g.add_node(req)
            dep_g.add_edge(req, name, type="requires_any")
        # conflicts_with: cannot be installed simultaneously.
        for conf in (getattr(cls, "conflicts_with", None) or []):
            conflict_g.add_node(conf)
            conflict_g.add_edge(name, conf)
    return dep_g, conflict_g


def get_cyberware_graph() -> nx.DiGraph:
    """Return the cached cyberware dependency DiGraph, building it on first call."""
    global _dep_graph, _conflict_graph
    if _dep_graph is None:
        _dep_graph, _conflict_graph = _build_graphs()
    return _dep_graph


def get_conflict_graph() -> nx.Graph:
    """Return the cached cyberware conflict Graph, building it on first call."""
    global _dep_graph, _conflict_graph
    if _conflict_graph is None:
        _dep_graph, _conflict_graph = _build_graphs()
    return _conflict_graph


def invalidate_graph():
    """Discard cached graphs so they are rebuilt on next access."""
    global _dep_graph, _conflict_graph
    _dep_graph = None
    _conflict_graph = None


def validate_install_order(cyberware_class_names: list[str]) -> tuple[bool, object]:
    """
    Check that a proposed install list is topologically valid (no circular deps).

    Returns:
        (True, sorted_install_order: list[str]) on success.
        (False, error_message: str) on failure.
    """
    if not cyberware_class_names:
        return True, []
    G = get_cyberware_graph()
    # Use only the subgraph of the proposed set.
    subgraph = G.subgraph(cyberware_class_names)
    if not nx.is_directed_acyclic_graph(subgraph):
        try:
            cycle = nx.find_cycle(subgraph)
            return False, f"Circular dependency detected: {cycle}"
        except nx.NetworkXNoCycle:
            return False, "Circular dependency detected."
    try:
        order = list(nx.topological_sort(subgraph))
        return True, order
    except nx.NetworkXUnfeasible as exc:
        return False, str(exc)


def get_install_prerequisites(class_name: str) -> list[str]:
    """
    Return all transitive prerequisites for a cyberware class (all ancestors in the dep graph).
    """
    G = get_cyberware_graph()
    if class_name not in G:
        return []
    try:
        return sorted(nx.ancestors(G, class_name))
    except Exception:
        return []


def get_conflicts_for(class_name: str) -> list[str]:
    """Return list of cyberware class names that conflict with class_name."""
    C = get_conflict_graph()
    if class_name not in C:
        return []
    return [n for n in C.neighbors(class_name)]
