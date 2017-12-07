import os
from heapq import heappush, heappop

import numpy as np

def astar_path(weights, start, goal):
    assert weights.min(axis=None) >= 1., (
        'weights.min() = %.2f != 1' % weights.min(axis=None))
    height, width = weights.shape
    start_idx = np.ravel_multi_index(start, (height, width))
    goal_idx = np.ravel_multi_index(goal, (height, width))


    success, paths = astar(weights.flatten(), height, width, start_idx, goal_idx)

    if not success:
        return np.array([])

    coordinates = []
    path_idx = goal_idx
    while path_idx != start_idx:
        pi, pj = np.unravel_index(path_idx, (height, width))
        coordinates.append((pi, pj))

        path_idx = paths[path_idx]

    if coordinates:
        return np.vstack(coordinates[::-1])
    else:
        return np.array([])


def heuristic(i0, j0, i1, j1):
    """
    Squared eucledian distance. At the moment it's much faster without sqrt. (4000x4000 grid ~8s vs ~60s)
    If the script is not accurate use with math.sqrt.
    """
    return ((i0 - i1) ** 2) + ((j0 - j1) ** 2)


def astar(weights, height, width, start, goal):
    # The array for return.
    path = np.full(height * width, -1, dtype=np.int32)

    node_start = (0, start)
    node_goal = (0, goal)

    costs = np.full((width * height,), np.inf, dtype=float)

    costs[start] = 0

    nodes_to_visit = []
    heappush(nodes_to_visit, node_start)

    found = False
    while len(nodes_to_visit):
        current = heappop(nodes_to_visit)

        if (current[1] == goal):
            found = True
            break

        nbrs = [0] * 8

        # top
        nbrs[0] = (current[1] - width) if (current[1] // width > 0) else -1
        # left
        nbrs[1] = (current[1] - 1) if (current[1] % width > 0) else -1
        # bottom
        nbrs[2] = (current[1] + width) if (current[1] // width + 1 < height) else -1
        # right
        nbrs[3] = (current[1] + 1) if (current[1] % width + 1 < width) else -1
        # top-left
        nbrs[4] = (current[1] - width - 1) if (current[1] // width > 0 and current[1] % width > 0) else -1
        # top-right
        nbrs[5] = (current[1] - width + 1) if (current[1] // width > 0 and current[1] % width + 1 > 0) else -1
        # bottom-left
        nbrs[6] = (current[1] + width - 1) if (current[1] // width + 1 < height and current[1] % width > 0) else -1
        # bottom-right
        nbrs[7] = (current[1] + width + 1) if (current[1] // width + 1 < height and current[1] % width + 1 < width) else -1

        for nbr in nbrs:
            if nbr > 0:
                new_cost = costs[current[1]] + weights[nbr]

                if new_cost < costs[nbr]:
                    costs[nbr] = new_cost
                    priority = new_cost + heuristic(nbr // width, nbr % width, goal // width, goal % width)

                    heappush(nodes_to_visit, (priority, nbr))

                    path[nbr] = current[1]

    return (found, path)
