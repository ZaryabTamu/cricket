import random
import asyncio
import html
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pymongo import MongoClient
from TEAMZYRO import app, user_collection, collection, rarity_map2

# MongoDB collection for game state
db = MongoClient().get_database("TEAMZYRO")  # Assumes db is configured in TEAMZYRO
mines_games = db["mines_games"]

# Decorator for VIP access (from balance.py)
def require_power(power):
    def decorator(func):
        async def wrapper(client, update, *args, **kwargs):
            user_id = update.from_user.id
            sudo_users = db["sudo_users"]
            user = sudo_users.find_one({"_id": user_id})
            if user_id == OWNER_ID or (user and user.get("powers", {}).get(power, False)):
                return await func(client, update, *args, **kwargs)
            else:
                await update.message.reply_text("This command is restricted to VIP users.")
        return wrapper
    return decorator

# Generate 4x4 grid with 4 mines
def create_mines_grid():
    grid = [0] * 16  # 0 = safe, 1 = mine
    mine_indices = random.sample(range(16), 4)  # Randomly select 4 mine positions
    for idx in mine_indices:
        grid[idx] = 1
    return grid

# Convert grid to button display
def grid_to_buttons(game_id, grid, revealed, game_over=False):
    buttons = []
    for i in range(4):
        row = []
        for j in range(4):
            idx = i * 4 + j
            if idx in revealed:
                if grid[idx] == 1:
                    emoji = "💥"  # Mine
                else:
                    emoji = "✅"  # Safe
            else:
                emoji = "❓" if not game_over else ("💥" if grid[idx] == 1 else "✅")
            callback_data = f"mines_{game_id}_{idx}" if not game_over else "noop"
            row.append(InlineKeyboardButton(emoji, callback_data=callback_data))
        buttons.append(row)
    return InlineKeyboardMarkup(buttons)

# Get a random character from collection
def get_random_character():
    characters = list(collection.find())
    if not characters:
        return None
    return random.choice(characters)

# Mines game command
@app.on_message(filters.command("mines"))
@require_power("VIP")
async def mines_command(client, message):
    user_id = message.from_user.id
    user = user_collection.find_one({"id": user_id})
    if not user:
        user_collection.insert_one({
            "id": user_id,
            "username": message.from_user.username or "",
            "first_name": message.from_user.first_name or "",
            "characters": [],
            "balance": 0,
            "tokens": 0,
            "filter_rarity": None,
            "favorites": []
        })

    # Create new game
    game_id = str(int(time.time() * 1000))  # Unique game ID
    grid = create_mines_grid()
    game_state = {
        "game_id": game_id,
        "user_id": user_id,
        "grid": grid,
        "revealed": [],
        "safe_count": 0,
        "active": True
    }
    mines_games.insert_one(game_state)

    # Send initial grid
    await message.reply_text(
        f"{html.escape(message.from_user.first_name)}, select 3 safe buttons to win!\nAvoid the 💥 mines!",
        reply_markup=grid_to_buttons(game_id, grid, [])
    )

# Handle button clicks
@app.on_callback_query(filters.regex(r"^mines_(\d+)_(\d+)$"))
async def mines_callback(client, callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    game_id, idx = callback_query.data.split("_")[1:]
    idx = int(idx)
    game = mines_games.find_one({"game_id": game_id, "user_id": user_id, "active": True})

    if not game:
        await callback_query.answer("This game is no longer active.")
        return

    revealed = game["revealed"]
    grid = game["grid"]
    safe_count = game["safe_count"]

    if idx in revealed:
        await callback_query.answer("This button was already clicked.")
        return

    revealed.append(idx)
    if grid[idx] == 1:  # Hit a mine
        mines_games.update_one({"game_id": game_id}, {"$set": {"active": False}})
        await callback_query.message.edit_text(
            f"{html.escape(callback_query.from_user.first_name)}, you hit a mine! 💥 Game over.",
            reply_markup=grid_to_buttons(game_id, grid, revealed, game_over=True)
        )
        await asyncio.sleep(5)
        await callback_query.message.delete()
    else:  # Safe button
        safe_count += 1
        mines_games.update_one({"game_id": game_id}, {"$set": {"revealed": revealed, "safe_count": safe_count}})
        if safe_count >= 3:  # Win condition
            character = get_random_character()
            if character:
                user_collection.update_one(
                    {"id": user_id},
                    {"$push": {"characters": character}, "$inc": {"balance": 100}}
                )
                rarity_emoji = rarity_map2.get(character["rarity"], "")
                await callback_query.message.edit_text(
                    f"🎉 {html.escape(callback_query.from_user.first_name)}, you won!\n"
                    f"Reward: {html.escape(character['name'])} ({html.escape(character['anime'])}) {rarity_emoji} + 100 coins!",
                    reply_markup=grid_to_buttons(game_id, grid, revealed, game_over=True)
                )
            else:
                await callback_query.message.edit_text(
                    f"🎉 {html.escape(callback_query.from_user.first_name)}, you won! +100 coins (no characters available).",
                    reply_markup=grid_to_buttons(game_id, grid, revealed, game_over=True)
                )
                user_collection.update_one({"id": user_id}, {"$inc": {"balance": 100}})
            mines_games.update_one({"game_id": game_id}, {"$set": {"active": False}})
            await asyncio.sleep(5)
            await callback_query.message.delete()
        else:
            await callback_query.message.edit_text(
                f"{html.escape(callback_query.from_user.first_name)}, {3 - safe_count} safe buttons left!",
                reply_markup=grid_to_buttons(game_id, grid, revealed)
            )

# Handle no-op callbacks (for game over state)
@app.on_callback_query(filters.regex(r"^noop$"))
async def noop_callback(client, callback_query):
    await callback_query.answer("Game is over.")
