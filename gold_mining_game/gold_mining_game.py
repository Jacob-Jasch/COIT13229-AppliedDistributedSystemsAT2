import random
import os
import time

WIDTH = 20
HEIGHT = 20
NUM_BOTS = 3
NUM_GOLD = 5

# ANSI colors
RESET = "\033[0m"
GOLD = "\033[33m"
PLAYER = "\033[32m"
BOT = "\033[31m"

def clear():
    os.system("cls" if os.name == "nt" else "clear")

class Entity:
    def __init__(self, x, y, icon, color):
        self.x = x
        self.y = y
        self.icon = icon
        self.color = color
        self.score = 0

    def move(self, dx, dy):
        self.x = max(0, min(WIDTH - 1, self.x + dx))
        self.y = max(0, min(HEIGHT - 1, self.y + dy))


def spawn_positions(count):
    positions = set()
    while len(positions) < count:
        positions.add((random.randint(0, WIDTH-1), random.randint(0, HEIGHT-1)))
    return list(positions)


def draw(player, bots, golds):
    grid = [["." for _ in range(WIDTH)] for _ in range(HEIGHT)]

    for gx, gy in golds:
        grid[gy][gx] = GOLD + "$" + RESET

    for bot in bots:
        grid[bot.y][bot.x] = BOT + "B" + RESET

    grid[player.y][player.x] = PLAYER + "P" + RESET

    for row in grid:
        print(" ".join(row))

    print(f"\nPlayer Score: {player.score}")
    for i, b in enumerate(bots):
        print(f"Bot {i+1} Score: {b.score}")


def nearest_gold(entity, golds):
    if not golds:
        return None
    return min(golds, key=lambda g: abs(g[0] - entity.x) + abs(g[1] - entity.y))


def bot_move(bot, golds):
    target = nearest_gold(bot, golds)
    if not target:
        return

    dx = target[0] - bot.x
    dy = target[1] - bot.y

    if abs(dx) > abs(dy):
        bot.move(1 if dx > 0 else -1, 0)
    elif abs(dy) > abs(dx):
        bot.move(0, 1 if dy > 0 else -1)
    else:
        if random.random() < 0.5:
            bot.move(1 if dx > 0 else -1, 0)
        else:
            bot.move(0, 1 if dy > 0 else -1)


def check_gold(entity, golds):
    if (entity.x, entity.y) in golds:
        golds.remove((entity.x, entity.y))
        entity.score += 1
        golds.append((random.randint(0, WIDTH-1), random.randint(0, HEIGHT-1)))


def main():
    player_pos = spawn_positions(1)[0]
    player = Entity(player_pos[0], player_pos[1], "P", PLAYER)

    bot_positions = spawn_positions(NUM_BOTS)
    bots = [Entity(x, y, "B", BOT) for x, y in bot_positions]

    golds = spawn_positions(NUM_GOLD)

    while True:
        clear()
        draw(player, bots, golds)

        move = input("\nMove (WASD, Q to quit): ").lower()

        if move == "q":
            break

        valid_moves = {"w", "a", "s", "d"}
        if move not in valid_moves:
            continue 

        dx, dy = 0, 0
        if move == "w":
            dy = -1
        elif move == "s":
            dy = 1
        elif move == "a":
            dx = -1
        elif move == "d":
            dx = 1

        player.move(dx, dy)
        check_gold(player, golds)

        for bot in bots:
            bot_move(bot, golds)
            check_gold(bot, golds)

        time.sleep(0.05)


if __name__ == "__main__":
    main()