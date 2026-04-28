import argparse
import random
import re
import sys
from pathlib import *

import pygame

# Map symbols:
# # = wall, ' ' = floor, . = target, $ = box, * = box on target, @ = player, + = player on target
DEFAULT_LEVEL = [
    "##########",
    "#        #",
    "#  .$$   #",
    "#  .@    #",
    "#        #",
    "##########",
]

ALLOWED_TILES = {"#", " ", ".", "$", "*", "@", "+"}
MOVE_TO_VEC = {"U": (0, -1), "D": (0, 1), "L": (-1, 0), "R": (1, 0)}
KEY_TO_MOVE = {
    pygame.K_UP: "U",
    pygame.K_w: "U",
    pygame.K_DOWN: "D",
    pygame.K_s: "D",
    pygame.K_LEFT: "L",
    pygame.K_a: "L",
    pygame.K_RIGHT: "R",
    pygame.K_d: "R",
}

TILE_SIZE = 32
FPS = 60

COLORS = {
    "bg": (24, 24, 32),
    "wall": (70, 80, 110),
    "floor": (45, 45, 60),
    "target": (220, 190, 80),
    "box": (170, 110, 60),
    "box_edge": (115, 70, 35),
    "box_on_target": (100, 170, 90),
    "player": (80, 165, 230),
    "text": (235, 235, 240),
}


def build_textures(tile_size):
    textures = {}

    floor = pygame.Surface((tile_size, tile_size))
    floor.fill((52, 52, 70))
    for y in range(0, tile_size, 8):
        pygame.draw.line(floor, (58, 58, 78), (0, y), (tile_size, y), 1)
    for x in range(0, tile_size, 8):
        pygame.draw.line(floor, (48, 48, 66), (x, 0), (x, tile_size), 1)
    textures["floor"] = floor

    wall_variants = []
    for base in ((92, 97, 118), (84, 90, 112), (73, 95, 92), (104, 86, 92)):
        s = pygame.Surface((tile_size, tile_size))
        s.fill(base)
        rng = random.Random(sum(base))
        for _ in range(35):
            x = rng.randrange(0, tile_size)
            y = rng.randrange(0, tile_size)
            w = rng.randrange(2, 6)
            h = rng.randrange(2, 6)
            tint = base[0] + rng.randrange(-15, 15), base[1] + rng.randrange(-15, 15), base[2] + rng.randrange(-15, 15)
            pygame.draw.rect(s, tint, (x, y, w, h))
        for y in range(0, tile_size, 10):
            pygame.draw.line(s, (60, 65, 78), (0, y), (tile_size, y), 1)
        wall_variants.append(s)
    textures["walls"] = wall_variants

    box_materials = []

    wood = pygame.Surface((tile_size - 8, tile_size - 8))
    wood.fill((170, 112, 66))
    for i in range(4, tile_size - 8, 6):
        pygame.draw.line(wood, (130, 82, 46), (2, i), (tile_size - 10, i), 1)
    pygame.draw.rect(wood, (110, 70, 38), wood.get_rect(), 2)
    box_materials.append(wood)

    metal = pygame.Surface((tile_size - 8, tile_size - 8))
    metal.fill((145, 152, 164))
    for i in range(3, tile_size - 8, 7):
        pygame.draw.line(metal, (175, 182, 194), (i, 2), (i, tile_size - 10), 1)
    pygame.draw.rect(metal, (96, 102, 116), metal.get_rect(), 2)
    box_materials.append(metal)

    stone = pygame.Surface((tile_size - 8, tile_size - 8))
    stone.fill((120, 112, 102))
    for i in range(24):
        x = (i * 7) % (tile_size - 10)
        y = (i * 11) % (tile_size - 10)
        pygame.draw.circle(stone, (102, 96, 88), (x + 3, y + 3), 2)
    pygame.draw.rect(stone, (84, 78, 72), stone.get_rect(), 2)
    box_materials.append(stone)

    textures["boxes"] = box_materials
    return textures


def normalize_level(lines):
    clean = [line.rstrip("\n") for line in lines if line.rstrip("\n")]
    if not clean:
        raise ValueError("Map is empty.")

    width = max(len(row) for row in clean)
    normalized = []
    for row in clean:
        padded = row.ljust(width, "#")
        bad = [c for c in padded if c not in ALLOWED_TILES]
        if bad:
            raise ValueError(f"Map contains unsupported tiles: {sorted(set(bad))}")
        normalized.append(padded)
    return normalized


def parse_level(raw_level):
    walls = set()
    floors = set()
    targets = set()
    boxes = set()
    player = None

    for y, row in enumerate(raw_level):
        for x, cell in enumerate(row):
            pos = (x, y)
            if cell == "#":
                walls.add(pos)
                continue

            floors.add(pos)
            if cell in ".+*":
                targets.add(pos)
            if cell in "$*":
                boxes.add(pos)
            if cell in "@+":
                if player is not None:
                    raise ValueError("Map can only contain one player start (@ or +).")
                player = pos

    if player is None:
        raise ValueError("Map must contain a player (@ or +).")
    if not boxes:
        raise ValueError("Map must contain at least one box ($ or *).")
    if len(boxes) != len(targets):
        raise ValueError("Number of boxes must match number of targets.")

    return walls, floors, targets, boxes, player


def try_move(player, boxes, walls, floors, move):
    dx, dy = MOVE_TO_VEC[move]
    next_pos = (player[0] + dx, player[1] + dy)

    if next_pos in walls or next_pos not in floors:
        return player, boxes

    if next_pos in boxes:
        beyond = (next_pos[0] + dx, next_pos[1] + dy)
        if beyond in walls or beyond in boxes or beyond not in floors:
            return player, boxes
        new_boxes = set(boxes)
        new_boxes.remove(next_pos)
        new_boxes.add(beyond)
        return next_pos, new_boxes

    return next_pos, boxes


def try_move_with_materials(player, boxes, box_materials, walls, floors, move):
    dx, dy = MOVE_TO_VEC[move]
    next_pos = (player[0] + dx, player[1] + dy)

    if next_pos in walls or next_pos not in floors:
        return player, boxes, box_materials, False

    if next_pos in boxes:
        beyond = (next_pos[0] + dx, next_pos[1] + dy)
        if beyond in walls or beyond in boxes or beyond not in floors:
            return player, boxes, box_materials, False
        new_boxes = set(boxes)
        new_boxes.remove(next_pos)
        new_boxes.add(beyond)
        new_materials = dict(box_materials)
        new_materials[beyond] = new_materials.pop(next_pos)
        return next_pos, new_boxes, new_materials, True

    return next_pos, boxes, box_materials, next_pos != player


def map_from_file(path):
    return normalize_level(Path(path).read_text(encoding="utf-8").splitlines())


def create_map_file(path):
    print("Create your map line-by-line. Use # . $ @ + * and spaces. Submit empty line to finish.")
    lines = []
    while True:
        line = input()
        if line == "":
            break
        lines.append(line)

    level = normalize_level(lines)
    parse_level(level)
    Path(path).write_text("\n".join(level) + "\n", encoding="utf-8")
    print(f"Saved map to {path}")


def load_level_pack(path):
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    levels = {}
    current_num = None
    current_lines = []

    def flush():
        nonlocal current_num, current_lines
        if current_num is not None and current_lines:
            levels[current_num] = normalize_level(current_lines)
        current_num, current_lines = None, []

    for line in lines:
        if line.strip() == "---":
            flush()
            continue
        m = re.match(r"^;\s*(\d+)\s*$", line.strip())
        if m:
            flush()
            current_num = int(m.group(1))
            continue
        if current_num is not None and not line.strip().startswith(";"):
            current_lines.append(line.rstrip("\n"))

    flush()
    if not levels:
        raise ValueError(f"No levels found in {path}")
    return [levels[i] for i in sorted(levels.keys())]


def draw_tile(screen, x, y, color):
    rect = pygame.Rect(x * TILE_SIZE, y * TILE_SIZE, TILE_SIZE, TILE_SIZE)
    pygame.draw.rect(screen, color, rect)
    return rect


def draw_scene(screen, font, level_size, walls, floors, targets, boxes, box_materials, player, status_lines, textures, won):
    screen.fill(COLORS["bg"])

    for x, y in floors:
        screen.blit(textures["floor"], (x * TILE_SIZE, y * TILE_SIZE))

    for x, y in walls:
        variant = textures["walls"][(x * 73 + y * 37) % len(textures["walls"])]
        rect = pygame.Rect(x * TILE_SIZE, y * TILE_SIZE, TILE_SIZE, TILE_SIZE)
        screen.blit(variant, rect.topleft)

    for x, y in targets:
        center = (x * TILE_SIZE + TILE_SIZE // 2, y * TILE_SIZE + TILE_SIZE // 2)
        pygame.draw.circle(screen, COLORS["target"], center, TILE_SIZE // 6)

    for x, y in boxes:
        rect = pygame.Rect(x * TILE_SIZE + 4, y * TILE_SIZE + 4, TILE_SIZE - 8, TILE_SIZE - 8)
        material = textures["boxes"][box_materials[(x, y)]]
        screen.blit(material, rect.topleft)
        if (x, y) in targets:
            pygame.draw.rect(screen, COLORS["box_on_target"], rect, width=3, border_radius=5)
        else:
            pygame.draw.rect(screen, COLORS["box_edge"], rect, width=2, border_radius=5)

    px, py = player
    pcenter = (px * TILE_SIZE + TILE_SIZE // 2, py * TILE_SIZE + TILE_SIZE // 2)
    pygame.draw.circle(screen, (36, 88, 132), (pcenter[0], pcenter[1] + 3), TILE_SIZE // 3)
    pygame.draw.circle(screen, (92, 184, 245), pcenter, TILE_SIZE // 3)
    pygame.draw.circle(screen, (120, 215, 255), (pcenter[0] - 5, pcenter[1] - 7), TILE_SIZE // 7)
    eye_y = pcenter[1] - 2
    pygame.draw.circle(screen, (20, 24, 30), (pcenter[0] - 6, eye_y), 2)
    pygame.draw.circle(screen, (20, 24, 30), (pcenter[0] + 6, eye_y), 2)
    pygame.draw.arc(
        screen,
        (20, 24, 30),
        pygame.Rect(pcenter[0] - 7, pcenter[1] - 1, 14, 10),
        0.25,
        2.9,
        2,
    )

    board_h = level_size[1] * TILE_SIZE
    for i, line in enumerate(status_lines):
        surf = font.render(line, True, COLORS["text"])
        screen.blit(surf, (10, board_h + 6 + i * 22))

    replay_rect = None
    if won:
        replay_rect = pygame.Rect(level_size[0] * TILE_SIZE - 140, board_h + 10, 120, 28)
        pygame.draw.rect(screen, (74, 156, 92), replay_rect, border_radius=6)
        pygame.draw.rect(screen, (50, 120, 68), replay_rect, width=2, border_radius=6)
        label = font.render("Replay", True, (242, 248, 244))
        screen.blit(label, (replay_rect.x + 28, replay_rect.y + 5))
    return replay_rect


def main():
    parser = argparse.ArgumentParser(description="Sokoban in pygame with custom maps and level pack support.")
    parser.add_argument("--map", dest="map_path", help="Load one map from a text file.")
    parser.add_argument("--create-map", dest="create_path", help="Create and save a map from terminal input.")
    parser.add_argument("--level-pack", default="maps/rooms_50_levels.txt", help="Path to built-in level pack.")
    parser.add_argument("--level", type=int, default=1, help="Starting level index (1-based) in level pack.")
    args = parser.parse_args()

    if args.create_path:
        create_map_file(args.create_path)
        return

    packed_levels = load_level_pack(args.level_pack) if not args.map_path else []
    current_level_index = max(0, min(args.level - 1, max(len(packed_levels) - 1, 0)))

    def get_level_map():
        if args.map_path:
            return map_from_file(args.map_path)
        return packed_levels[current_level_index]

    pygame.init()
    pygame.display.set_caption("Sokoban")
    font = pygame.font.SysFont("arial", 18)
    clock = pygame.time.Clock()
    textures = build_textures(TILE_SIZE)

    def reset_level(level_override=None):
        nonlocal walls, floors, targets, initial_boxes, initial_player, boxes, box_materials
        nonlocal initial_box_materials, player, moves, level_map, screen, move_history
        nonlocal replay_moves, replay_accumulator, replaying
        level_map = level_override if level_override is not None else get_level_map()
        walls, floors, targets, initial_boxes, initial_player = parse_level(level_map)
        boxes = set(initial_boxes)
        ordered_boxes = sorted(initial_boxes)
        box_materials = {pos: i % len(textures["boxes"]) for i, pos in enumerate(ordered_boxes)}
        initial_box_materials = dict(box_materials)
        player = initial_player
        moves = 0
        move_history = []
        replay_moves = []
        replay_accumulator = 0.0
        replaying = False
        board_w, board_h = len(level_map[0]), len(level_map)
        screen = pygame.display.set_mode((board_w * TILE_SIZE, board_h * TILE_SIZE + 74))

    walls = floors = targets = initial_boxes = boxes = set()
    box_materials = {}
    initial_box_materials = {}
    initial_player = player = (0, 0)
    moves = 0
    move_history = []
    replay_moves = []
    replay_accumulator = 0.0
    replaying = False
    level_map = []
    screen = None
    reset_level()

    while True:
        board_w, board_h = len(level_map[0]), len(level_map)
        dt = clock.tick(FPS) / 1000.0
        won = boxes == targets
        replay_button = pygame.Rect(board_w * TILE_SIZE - 140, board_h * TILE_SIZE + 10, 120, 28) if won else None

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    pygame.quit()
                    sys.exit()
                if event.key == pygame.K_r:
                    reset_level()
                    continue
                if not args.map_path and event.key == pygame.K_LEFTBRACKET:
                    current_level_index = (current_level_index - 1) % len(packed_levels)
                    reset_level()
                    continue
                if not args.map_path and event.key == pygame.K_RIGHTBRACKET:
                    current_level_index = (current_level_index + 1) % len(packed_levels)
                    reset_level()
                    continue

                if won or replaying:
                    continue

                if event.key in KEY_TO_MOVE:
                    new_player, new_boxes, new_materials, moved = try_move_with_materials(
                        player,
                        boxes,
                        box_materials,
                        walls,
                        floors,
                        KEY_TO_MOVE[event.key],
                    )
                    if moved:
                        moves += 1
                        move_history.append(KEY_TO_MOVE[event.key])
                    player, boxes, box_materials = new_player, new_boxes, new_materials

            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and won and replay_button:
                if replay_button.collidepoint(event.pos) and move_history:
                    boxes = set(initial_boxes)
                    box_materials = dict(initial_box_materials)
                    player = initial_player
                    moves = 0
                    replay_moves = list(move_history)
                    replay_accumulator = 0.0
                    replaying = True

        if replaying and replay_moves:
            replay_accumulator += dt
            while replay_accumulator >= 0.5 and replay_moves:
                replay_accumulator -= 0.5
                step = replay_moves.pop(0)
                new_player, new_boxes, new_materials, moved = try_move_with_materials(
                    player,
                    boxes,
                    box_materials,
                    walls,
                    floors,
                    step,
                )
                if moved:
                    moves += 1
                player, boxes, box_materials = new_player, new_boxes, new_materials
            if not replay_moves:
                replaying = False

        level_text = "Custom map" if args.map_path else f"Level {current_level_index + 1}/{len(packed_levels)}"
        status_lines = [
            "Move: Arrowkeys/WASD | R to reset | [ or ] to switch levels | ESC to quit",
            f"{level_text} | Moves: {moves}",
        ]
        if won:
            status_lines[0] = "Damn u solved it! Click Replay to rewatch your run at 2 moves/sec"
        elif replaying:
            status_lines[0] = "Replaying your solution in progress"

        draw_scene(
            screen,
            font,
            (board_w, board_h),
            walls,
            floors,
            targets,
            boxes,
            box_materials,
            player,
            status_lines,
            textures,
            won,
        )
        pygame.display.flip()


if __name__ == "__main__":
    main()
