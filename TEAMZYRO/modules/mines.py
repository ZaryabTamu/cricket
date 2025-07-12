from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message
from TEAMZYRO import app, user_collection, collection
import random
from asyncio import sleep

# Game settings
GRID_SIZE = 4  # 4x4 grid
NUM_MINES = 3  # 3 mines
MAX_ATTEMPTS = 3  # 3 attempts to win
REWARD_COINS = 100  # Reward for winning

# Initialize game state
def create_game():
    grid = [[0 for _ in range(GRID_SIZE)] for _ in range(GRID_SIZE)]  # 0 = empty, -1 = mine, 1 = opened
    mines = random.sample([(i, j) for i in range(GRID_SIZE) for j in range(GRID_SIZE)], NUM_MINES)
    for mine_x, mine_y in mines:
        grid[mine_x][mine_y] = -1
    return grid, mines, MAX_ATTEMPTS

# Generate inline keyboard for the game
def generate_keyboard(grid, game_id):
    keyboard = []
    for i in range(GRID_SIZE):
        row = []
        for j in range(GRID_SIZE):
            if grid[i][j] == 1:  # Opened cell
                row.append(InlineKeyboardButton("⬜", callback_data=f"mine_{game_id}_{i}_{j}_opened"))
            else:  # Unopened cell
                row.append(InlineKeyboardButton("🔳", callback_data=f"mine_{game_id}_{i}_{j}"))
        keyboard.append(row)
    return InlineKeyboardMarkup(keyboard)

# Check if the game is won
def check_win(grid):
    return sum(row.count(1) for row in grid) == (GRID_SIZE * GRID_SIZE - NUM_MINES)

# Get random character from collection
async def get_random_character():
    characters = await collection.find({}).to_list(length=None)
    if characters:
        return random.choice(characters)
    return None

@app.on_message(filters.command("mines"))
async def start_mines(client: Client, message: Message):
    user_id = message.from_user.id
    game_id = str(random.randint(100000, 999999))  # Unique game ID
    grid, mines, attempts = create_game()
    
    # Store game state (in-memory for simplicity; consider MongoDB for persistence)
    game_state[user_id] = {"grid": grid, "mines": mines, "attempts": attempts, "game_id": game_id}
    
    await message.reply_text(
        f"Welcome to Minesweeper! Open all non-mine cells ({GRID_SIZE * GRID_SIZE - NUM_MINES}) in {MAX_ATTEMPTS} attempts. Click a button to reveal a cell.",
        reply_markup=generate_keyboard(grid, game_id)
    )

# Store game state (in-memory; could be moved to MongoDB)
game_state = {}

@app.on_callback_query(filters.regex(r"mine_(\d+)_(\d+)_(\d+)(?:_opened)?"))
async def handle_mine_click(client: Client, callback_query):
    user_id = callback_query.from_user.id
    data = callback_query.data.split("_")
    game_id, x, y = data[1], int(data[2]), int(data[3])
    
    # Verify game state
    if user_id not in game_state or game_state[user_id]["game_id"] != game_id:
        await callback_query.answer("Game expired or invalid!", show_alert=True)
        return
    
    state = game_state[user_id]
    grid, mines, attempts = state["grid"], state["mines"], state["attempts"]
    
    # Check if cell is already opened
    if grid[x][y] == 1:
        await callback_query.answer("This cell is already opened!", show_alert=True)
        return
    
    # Check if it's a mine
    if (x, y) in mines:
        grid[x][y] = 1  # Mark as opened
        state["attempts"] -= 1
        await callback_query.message.edit_text(
            f"💥 You hit a mine! Attempts left: {state['attempts']}.",
            reply_markup=generate_keyboard(grid, game_id)
        )
        if state["attempts"] == 0:
            await callback_query.message.edit_text("Game Over! You ran out of attempts. Try /mines to play again.")
            del game_state[user_id]
        return
    
    # Safe cell
    grid[x][y] = 1
    state["attempts"] -= 1
    
    if check_win(grid):
        # Reward: Add coins and a random character
        user_data = await user_collection.find_one({"id": user_id})
        if not user_data:
            user_data = {
                "id": user_id,
                "username": callback_query.from_user.username or "",
                "first_name": callback_query.from_user.first_name or "",
                "balance": 0,
                "tokens": 0,
                "characters": []
            }
        
        user_data["balance"] = user_data.get("balance", 0) + REWARD_COINS
        character = await get_random_character()
        if character:
            user_data["characters"].append({
                "id": character["id"],
                "name": character["name"],
                "anime": character["anime"],
                "rarity": character["rarity"],
                "img_url": character.get("img_url", ""),
                "vid_url": character.get("vid_url", "")
            })
            await user_collection.update_one(
                {"id": user_id},
                {"$set": {"balance": user_data["balance"], "characters": user_data["characters"]}},
                upsert=True
            )
            await callback_query.message.edit_text(
                f"🎉 You won! You opened all safe cells! Gained {REWARD_COINS} coins and a new character: {character['name']} ({character['anime']})."
            )
        else:
            await user_collection.update_one(
                {"id": user_id},
                {"$set": {"balance": user_data["balance"]}},
                upsert=True
            )
            await callback_query.message.edit_text(
                f"🎉 You won! Gained {REWARD_COINS} coins. (No characters available in collection.)"
            )
        del game_state[user_id]
        return
    
    # Update game state
    await callback_query.message.edit_text(
        f"Opened a safe cell! Attempts left: {state['attempts']}.",
        reply_markup=generate_keyboard(grid, game_id)
    )
    if state["attempts"] == 0 and not check_win(grid):
        await callback_query.message.edit_text("Game Over! You ran out of attempts. Try /mines to play again.")
        del game_state[user_id]
