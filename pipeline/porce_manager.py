#!/usr/bin/env python3
"""
PORCE MANAGER (Path Planning Core)
-------------------------------
A* planner for short-range local replanning.
"""

import heapq
import math
from typing import Callable, Iterable, Optional

from constants import (
    EARTH_RADIUS_M,
    GRID_CELL_SIZE_M,
    PLANNER_SAFETY_DISTANCE_M,
    GEOMETRY_COS_LAT_EPS,
    PLANNER_BOUNDARY_SEARCH_RANGE_CELLS,
    PLANNER_GRID_RADIUS_CELLS,
    PLANNER_MAX_ITERATIONS,
    PLANNER_GOAL_REACHED_TOLERANCE_CELLS,
    PLANNER_MOVE_COST_CARDINAL,
    PLANNER_MOVE_COST_DIAGONAL,
)


class Node:
    def __init__(self, x: int, y: int, parent: Optional["Node"] = None):
        self.x = x
        self.y = y
        self.parent = parent
        self.g = 0
        self.h = 0
        self.f = 0

    def __eq__(self, other):
        return isinstance(other, Node) and self.x == other.x and self.y == other.y

    def __lt__(self, other):
        return self.f < other.f

    def __hash__(self):
        return hash((self.x, self.y))

    def __repr__(self):
        return f"Node({self.x}, {self.y})"


class PorcePlanner:
    def __init__(
        self,
        *,
        cell_size: float | None = None,
        safety_radius_m: float | None = None,
        grid_radius_cells: int | None = None,
        max_iterations: int | None = None,
        boundary_search_range_cells: int | None = None,
        allow_diagonal: bool = True,
        log_fn: Optional[Callable[[str], None]] = None,
    ):
        self.cell_size = float(cell_size if cell_size is not None else GRID_CELL_SIZE_M)
        self.safety_radius_m = float(safety_radius_m if safety_radius_m is not None else PLANNER_SAFETY_DISTANCE_M)
        self.grid_radius_cells = max(1, int(grid_radius_cells if grid_radius_cells is not None else PLANNER_GRID_RADIUS_CELLS))
        self.max_iterations = max(1, int(max_iterations if max_iterations is not None else PLANNER_MAX_ITERATIONS))
        self.boundary_search_range_cells = max(
            0,
            int(
                boundary_search_range_cells
                if boundary_search_range_cells is not None
                else PLANNER_BOUNDARY_SEARCH_RANGE_CELLS
            ),
        )
        self.allow_diagonal = bool(allow_diagonal)
        self._log_fn = log_fn

    def _log(self, msg: str) -> None:
        if self._log_fn is None:
            return
        try:
            self._log_fn(msg)
        except Exception:
            pass

    @staticmethod
    def _normalize_obstacles(obstacles: Iterable[dict]) -> list[dict]:
        clean = []
        for obs in obstacles:
            if not isinstance(obs, dict):
                continue
            lat = obs.get("lat")
            lon = obs.get("lon")
            try:
                if lat is None or lon is None:
                    continue
                lat_f = float(lat)
                lon_f = float(lon)
            except Exception:
                continue
            if not math.isfinite(lat_f) or not math.isfinite(lon_f):
                continue
            clean.append({"lat": lat_f, "lon": lon_f})
        return clean

    @staticmethod
    def latlon_to_meters(lat_ref, lon_ref, lat, lon):
        dlat = math.radians(lat - lat_ref)
        dlon = math.radians(lon - lon_ref)
        north_m = dlat * EARTH_RADIUS_M
        east_m = dlon * EARTH_RADIUS_M * (math.cos(math.radians(lat_ref)) or float(GEOMETRY_COS_LAT_EPS))
        return north_m, east_m

    @staticmethod
    def meters_to_latlon(lat_ref, lon_ref, north_m, east_m):
        dlat = north_m / EARTH_RADIUS_M
        cos_lat = math.cos(math.radians(lat_ref)) or float(GEOMETRY_COS_LAT_EPS)
        dlon = east_m / (EARTH_RADIUS_M * cos_lat)
        return lat_ref + math.degrees(dlat), lon_ref + math.degrees(dlon)

    def _get_neighbors(self, node, grid_obstacles):
        children = []
        moves = [
            (0, -1), (0, 1), (-1, 0), (1, 0),
        ]
        if self.allow_diagonal:
            moves += [(-1, -1), (-1, 1), (1, -1), (1, 1)]

        for dx, dy in moves:
            nx, ny = node.x + dx, node.y + dy
            if abs(nx) > self.grid_radius_cells or abs(ny) > self.grid_radius_cells:
                continue
            if (nx, ny) in grid_obstacles:
                continue
            children.append(Node(nx, ny, node))
        return children

    def plan_route(self, start_lat, start_lon, end_lat, end_lon, obstacles):
        ref_lat, ref_lon = start_lat, start_lon

        goal_n, goal_e = self.latlon_to_meters(ref_lat, ref_lon, end_lat, end_lon)
        grid_obstacles = set()
        safety_cells = max(0, int(math.ceil(self.safety_radius_m / self.cell_size)))

        for obs in self._normalize_obstacles(obstacles):
            obs_n, obs_e = self.latlon_to_meters(ref_lat, ref_lon, obs["lat"], obs["lon"])
            ox = int(obs_e / self.cell_size)
            oy = int(obs_n / self.cell_size)
            for dx in range(-safety_cells, safety_cells + 1):
                for dy in range(-safety_cells, safety_cells + 1):
                    grid_obstacles.add((ox + dx, oy + dy))

        # Start may be inside an inflated obstacle by projection tolerance; allow escape.
        if (0, 0) in grid_obstacles:
            grid_obstacles.remove((0, 0))

        grid_radius_m = self.grid_radius_cells * self.cell_size
        dist_to_goal = math.hypot(goal_n, goal_e)
        if dist_to_goal > grid_radius_m and dist_to_goal > 0:
            scale = grid_radius_m / dist_to_goal
            goal_n *= scale
            goal_e *= scale

        goal_x = int(goal_e / self.cell_size)
        goal_y = int(goal_n / self.cell_size)
        goal_x = max(-self.grid_radius_cells, min(self.grid_radius_cells, goal_x))
        goal_y = max(-self.grid_radius_cells, min(self.grid_radius_cells, goal_y))

        if (goal_x, goal_y) in grid_obstacles:
            self._log(f"Meta ideal bloqueada en ({goal_x}, {goal_y}), buscando alternativa local.")
            found_alt = False
            best_dist = float("inf")
            alt_x, alt_y = goal_x, goal_y

            for dx in range(-self.boundary_search_range_cells, self.boundary_search_range_cells + 1):
                for dy in range(-self.boundary_search_range_cells, self.boundary_search_range_cells + 1):
                    cand_x, cand_y = goal_x + dx, goal_y + dy
                    if abs(cand_x) > self.grid_radius_cells or abs(cand_y) > self.grid_radius_cells:
                        continue
                    if (cand_x, cand_y) in grid_obstacles:
                        continue
                    dist = math.hypot(dx, dy)
                    if dist < best_dist:
                        best_dist = dist
                        alt_x, alt_y = cand_x, cand_y
                        found_alt = True

            if found_alt:
                goal_x, goal_y = alt_x, alt_y
                self._log(f"Salida alternativa para meta en ({goal_x}, {goal_y}).")
            else:
                self._log("Sin salida local para meta bloqueada; se cancela plan.")
                return None

        start_pos = (0, 0)
        goal_pos = (int(goal_x), int(goal_y))

        if goal_pos in grid_obstacles:
            return None

        goal_tol = max(0, int(PLANNER_GOAL_REACHED_TOLERANCE_CELLS))
        open_heap: list[tuple[float, int, tuple[int, int]]] = []
        closed_set: set[tuple[int, int]] = set()
        came_from: dict[tuple[int, int], tuple[int, int]] = {}
        g_score: dict[tuple[int, int], float] = {start_pos: 0.0}

        push_seq = 0
        start_h = math.hypot(start_pos[0] - goal_pos[0], start_pos[1] - goal_pos[1])
        heapq.heappush(open_heap, (float(start_h), int(push_seq), start_pos))

        iterations = 0
        reached_pos: Optional[tuple[int, int]] = None
        while open_heap:
            iterations += 1
            if iterations > self.max_iterations:
                self._log("A* timeout: no se encontro ruta.")
                return None

            _, _, current_pos = heapq.heappop(open_heap)
            if current_pos in closed_set:
                continue

            if (
                abs(int(current_pos[0]) - int(goal_pos[0])) <= goal_tol
                and abs(int(current_pos[1]) - int(goal_pos[1])) <= goal_tol
            ):
                reached_pos = current_pos
                break

            closed_set.add(current_pos)
            current_node = Node(int(current_pos[0]), int(current_pos[1]))
            current_g = float(g_score.get(current_pos, float("inf")))
            if not math.isfinite(current_g):
                continue

            for child in self._get_neighbors(current_node, grid_obstacles):
                child_pos = (int(child.x), int(child.y))
                if child_pos in closed_set:
                    continue

                is_diagonal = (child_pos[0] != current_pos[0]) and (child_pos[1] != current_pos[1])
                move_cost = float(PLANNER_MOVE_COST_DIAGONAL if is_diagonal else PLANNER_MOVE_COST_CARDINAL)
                tentative_g = float(current_g) + float(move_cost)
                if tentative_g >= float(g_score.get(child_pos, float("inf"))):
                    continue

                came_from[child_pos] = current_pos
                g_score[child_pos] = tentative_g
                child_h = math.hypot(child_pos[0] - goal_pos[0], child_pos[1] - goal_pos[1])
                child_f = tentative_g + float(child_h)
                push_seq += 1
                heapq.heappush(open_heap, (float(child_f), int(push_seq), child_pos))

        if reached_pos is None:
            self._log("A* sin ruta: no se alcanzo la meta local.")
            return None

        path_cells = [reached_pos]
        while path_cells[-1] != start_pos:
            parent = came_from.get(path_cells[-1])
            if parent is None:
                self._log("A* ruta incompleta: falta parent en reconstruccion.")
                return None
            path_cells.append(parent)
        path_cells.reverse()

        path = []
        for cell_x, cell_y in path_cells:
            east_m = float(cell_x) * self.cell_size
            north_m = float(cell_y) * self.cell_size
            lat, lon = self.meters_to_latlon(ref_lat, ref_lon, north_m, east_m)
            path.append({"lat": lat, "lon": lon})
        return path


if __name__ == "__main__":
    planner = PorcePlanner()
    print("Testing PorcePlanner...")
    obstacles = [{"lat": 0.00018, "lon": 0.0}]
    path = planner.plan_route(0, 0, 0.00036, 0, obstacles)
    if path:
        print(f"Ruta encontrada: {len(path)} pasos.")
    else:
        print("Ruta no encontrada.")
