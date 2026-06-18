"""DAG (Directed Acyclic Graph) validator for card dependencies."""

from __future__ import annotations

from collections import defaultdict, deque
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import selectinload

import app.db
from app.domain.backlog import Card, Phase
from app.domain.projects import Project
from app.enums import CardDepRelation
from app.schemas.common import ValidationIssue
from app.validators.base import BaseValidator


class DagValidator(BaseValidator):
    """Validates card dependency DAG structure."""

    def validate(self, project_slug: str) -> list[ValidationIssue]:
        """Validate DAG structure for a project."""
        issues = []

        with app.db.session_scope() as session:
            # Load project with full dependency structure
            project_query = select(Project).where(
                Project.slug == project_slug
            ).options(
                selectinload(Project.phases).selectinload(Phase.cards).selectinload(Card.deps_out)
            )
            project = session.execute(project_query).scalar_one_or_none()

            if not project:
                issues.append(self.create_issue(
                    "error",
                    "dag.project_not_found",
                    f"Project '{project_slug}' not found",
                    {"project_slug": project_slug}
                ))
                return issues

            # Build dependency graph
            cards_by_code = {}
            dependency_graph = defaultdict(list)  # card_code -> [dependent_card_codes]
            reverse_graph = defaultdict(list)     # card_code -> [dependency_card_codes]

            # Collect all cards
            for phase in project.phases:
                for card in phase.cards:
                    cards_by_code[card.code] = card

            # Build dependency relationships
            for phase in project.phases:
                for card in phase.cards:
                    for dep in card.deps_out:
                        if dep.relation == CardDepRelation.DEPENDS_ON:
                            # card depends on dep.depends_on_card_id
                            dep_card = session.get(Card, dep.depends_on_card_id)
                            if dep_card:
                                dependency_graph[dep_card.code].append(card.code)
                                reverse_graph[card.code].append(dep_card.code)

            # Run validations
            issues.extend(self._validate_cycles(dependency_graph, project_slug))
            issues.extend(self._validate_cross_phase_dependencies(cards_by_code, reverse_graph, project_slug))
            issues.extend(self._validate_orphaned_cards(cards_by_code, dependency_graph, reverse_graph, project_slug))
            issues.extend(self._validate_critical_path(project, cards_by_code, project_slug))

        return issues

    def _validate_cycles(self, graph: dict[str, list[str]], project_slug: str) -> list[ValidationIssue]:
        """Detect cycles in the dependency graph using DFS."""
        issues = []
        visited = set()
        rec_stack = set()

        def dfs(node: str, path: list[str]) -> bool:
            """Returns True if cycle found."""
            if node in rec_stack:
                # Found cycle - extract the cycle portion
                cycle_start = path.index(node)
                cycle = [*path[cycle_start:], node]
                cycle_str = " -> ".join(cycle)

                issues.append(self.create_issue(
                    "error",
                    "dag.cycle",
                    f"Circular dependency detected: {cycle_str}",
                    {
                        "project_slug": project_slug,
                        "cycle_cards": ",".join(cycle[:-1]),  # Exclude duplicate end node
                        "cycle_length": str(len(cycle) - 1)
                    }
                ))
                return True

            if node in visited:
                return False

            visited.add(node)
            rec_stack.add(node)

            for neighbor in graph.get(node, []):
                if dfs(neighbor, [*path, neighbor]):
                    return True

            rec_stack.remove(node)
            return False

        # Check all nodes for cycles
        for node in graph:
            if node not in visited:
                dfs(node, [node])

        return issues

    def _validate_cross_phase_dependencies(
        self,
        cards_by_code: dict[str, Card],
        reverse_graph: dict[str, list[str]],
        project_slug: str
    ) -> list[ValidationIssue]:
        """Validate dependencies between phases follow logical order."""
        issues = []

        # Build phase ordering map
        phases = set()
        for card in cards_by_code.values():
            phases.add(card.phase)

        phase_order = {phase.code: phase.order_no for phase in phases}

        # Check each dependency
        for card_code, dependencies in reverse_graph.items():
            card = cards_by_code[card_code]
            card_phase_order = phase_order[card.phase.code]

            for dep_code in dependencies:
                dep_card = cards_by_code.get(dep_code)
                if not dep_card:
                    continue

                dep_phase_order = phase_order[dep_card.phase.code]

                # Dependencies should come from earlier or same phase
                if dep_phase_order > card_phase_order:
                    issues.append(self.create_issue(
                        "error",
                        "dag.reverse_phase_dependency",
                        f"Card {card_code} depends on {dep_code} from a later phase",
                        {
                            "project_slug": project_slug,
                            "card_code": card_code,
                            "card_phase": card.phase.code,
                            "dependency_code": dep_code,
                            "dependency_phase": dep_card.phase.code
                        }
                    ))

        return issues

    def _validate_orphaned_cards(
        self,
        cards_by_code: dict[str, Card],
        dependency_graph: dict[str, list[str]],
        reverse_graph: dict[str, list[str]],
        project_slug: str
    ) -> list[ValidationIssue]:
        """Detect cards that are isolated from the dependency graph."""
        issues = []

        # Find cards with no incoming or outgoing dependencies
        for card_code, card in cards_by_code.items():
            has_dependencies = bool(reverse_graph.get(card_code, []))
            has_dependents = bool(dependency_graph.get(card_code, []))

            if not has_dependencies and not has_dependents and len(cards_by_code) > 1:
                # Only flag as warning if there are other cards (single-card projects are OK)
                issues.append(self.create_issue(
                    "warning",
                    "dag.orphaned_card",
                    f"Card {card_code} has no dependencies or dependents (isolated)",
                    {
                        "project_slug": project_slug,
                        "card_code": card_code,
                        "phase_code": card.phase.code
                    }
                ))

        return issues

    def _validate_critical_path(
        self,
        project: Any,
        cards_by_code: dict[str, Card],
        project_slug: str
    ) -> list[ValidationIssue]:
        """Validate critical path codes reference valid cards."""
        issues = []

        # Note: Critical path is typically stored in project metadata or calculated
        # For now, this is a placeholder for when critical path functionality is added

        # If project had a critical_path_codes field, we would validate:
        # for code in getattr(project, 'critical_path_codes', []):
        #     if code not in cards_by_code:
        #         issues.append(self.create_issue(
        #             "error",
        #             "dag.invalid_critical_path",
        #             f"Critical path references non-existent card: {code}",
        #             {"project_slug": project_slug, "card_code": code}
        #         ))

        return issues

    def calculate_topological_order(self, project_slug: str) -> list[str] | None:
        """Calculate topological ordering of cards (useful for execution planning).

        Returns:
            List of card codes in topological order, or None if cycles exist
        """
        with app.db.session_scope() as session:
            # Load project dependencies
            project_query = select(Project).where(
                Project.slug == project_slug
            ).options(
                selectinload(Project.phases).selectinload(Phase.cards).selectinload(Card.deps_out)
            )
            project = session.execute(project_query).scalar_one_or_none()

            if not project:
                return None

            # Build graph and in-degree count
            graph = defaultdict(list)
            in_degree = defaultdict(int)
            all_cards = set()

            for phase in project.phases:
                for card in phase.cards:
                    all_cards.add(card.code)
                    in_degree[card.code] = 0

            for phase in project.phases:
                for card in phase.cards:
                    for dep in card.deps_out:
                        if dep.relation == CardDepRelation.DEPENDS_ON:
                            dep_card = session.get(Card, dep.depends_on_card_id)
                            if dep_card:
                                graph[dep_card.code].append(card.code)
                                in_degree[card.code] += 1

            # Kahn's algorithm for topological sort
            queue = deque([card for card in all_cards if in_degree[card] == 0])
            topo_order = []

            while queue:
                node = queue.popleft()
                topo_order.append(node)

                for neighbor in graph[node]:
                    in_degree[neighbor] -= 1
                    if in_degree[neighbor] == 0:
                        queue.append(neighbor)

            # Check if all nodes were processed (no cycles)
            if len(topo_order) != len(all_cards):
                return None  # Cycle detected

            return topo_order
