from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message
from pyrogram import enums
from TEAMZYRO import app, user_collection, collection
import random
import uuid
from asyncio import sleep
import re

# Rarity map (aligned with harem (2).py's rarity_map2)
rarity_map = {
    1: "⚪️ Common",
    2: "🟣 Rare",
    3: "🟡 Legendary",
    4: "🟢 Medium",
    5: "💮 Special Edition",
    6: "🔮 Limited Edition",
    7: "🎐 Celestial",
    8: "💖 Valentine",
    9: "🎃 Halloween",
    10: "❄️ Winter",
    11: "💸 Expensive",
    12: "💌 AMV",
    13: "🏖 Summer",
    14: "🧬 X-Verse",
    15: "✨ Neon",
    16: "⚜ Royal",
    17: "🎨 Holi Addition",
    18: "🥵 Erotic"
}

# Game settings
GRID_SIZE = 3  # 3x3 grid
NUM_MINES = 3  # 3 mines
TOKEN_COST = 1  # 1 token to start
MAX_MINE_HITS = 2  # Game over after 2 mine hits

# Game State Key:
#  0: Unopened cell
#  1: Opened safe cell
# -1: Hidden mine
# -2: Revealed mine (after being clicked)

# Validate URL (HTTP/HTTPS check)
def is_valid_url(url):
    if not url or not isinstance(url, str):
        return False
    return re.match(r'^https?://[^\s/$.?#].[^\s]*$', url) is not None

# Initialize game state
def create_game():
    grid = [[0 for _ in range(GRID_SIZE)] for _ in range(GRID_SIZE)]
    mines = random.sample([(i, j) for i in range(GRID_SIZE) for j in range(GRID_SIZE)], NUM_MINES)
    for mine_x, mine_y in mines:
        grid[mine_x][mine_y] = -1
    return grid, mines

# Generate inline keyboard for the game - MODIFIED
def generate_keyboard(grid, game_id, player_id, safe_opened, mine_hits, game_over=False):
    keyboard = []
    # Grid buttons
    for i in range(GRID_SIZE):
        row = []
        for j in range(GRID_SIZE):
            cell_state = grid[i][j]
            if game_over:
                # On game over, reveal all mines and disable all buttons
                if cell_state == -1 or cell_state == -2:  # If it was a hidden or revealed mine
                    row.append(InlineKeyboardButton("💣", callback_data="game_over"))
                elif cell_state == 1:  # If it was an opened safe cell
                    row.append(InlineKeyboardButton("⬜", callback_data="game_over"))
                else:  # Unopened safe cells
                    row.append(InlineKeyboardButton("🔳", callback_data="game_over"))
            else:
                # Active game logic
                if cell_state == 1:  # Opened safe cell
                    row.append(InlineKeyboardButton("⬜", callback_data=f"mine_{game_id}_{player_id}_{i}_{j}_opened"))
                elif cell_state == -2:  # Revealed mine
                    row.append(InlineKeyboardButton("💣", callback_data=f"mine_{game_id}_{player_id}_{i}_{j}_revealed"))
                else:  # Unopened cell (mines are hidden as 🔳)
                    row.append(InlineKeyboardButton("🔳", callback_data=f"mine_{game_id}_{player_id}_{i}_{j}"))
        keyboard.append(row)

    # Claim button (appears after at least one safe box is opened and game is not over)
    if not game_over and safe_opened > 0:
        keyboard.append([InlineKeyboardButton("Claim Reward", callback_data=f"claim_{game_id}_{player_id}_{safe_opened}")])

    return InlineKeyboardMarkup(keyboard)

# Get random character based on rarity - FIXED VERSION
async def get_random_character(user_id, safe_opened):
    try:
        user_data = await user_collection.find_one({'id': user_id}, {'filter_rarity': 1})
        filter_rarity = user_data.get('filter_rarity') if user_data else None

        if filter_rarity:
            if isinstance(filter_rarity, int):
                rarities = [rarity_map.get(filter_rarity)]
            else:
                rarities = [filter_rarity]
            rarities = [r for r in rarities if r is not None]
        else:
            if safe_opened == 4:
                rarities = ['🟣 Rare', '💮 Special Edition']
            elif safe_opened == 5:
                rarities = ['🔮 Limited Edition', '💸 Expensive']
            elif safe_opened == 6:
                rarities = ['🎐 Celestial', '✨ Neon']
            else:
                return None

        if not rarities:
            return None

        pipeline = [
            {'$match': {'rarity': {'$in': rarities}, 'img_url': {'$exists': True, '$ne': ''}, 'id': {'$exists': True}, 'name': {'$exists': True}, 'anime': {'$exists': True}}},
            {'$sample': {'size': 1}}
        ]
        cursor = collection.aggregate(pipeline)
        characters = await cursor.to_list(length=None)

        if characters:
            character = characters[0]
            if is_valid_url(character.get('img_url')):
                return character
        return None
    except Exception as e:
        print(f"Error retrieving character: {e}")
        return None

# Calculate rewards
async def award_rewards(user_id, safe_opened):
    user_data = await user_collection.find_one({'id': user_id})
    if not user_data:
        user_data = {'id': user_id, 'username': '', 'first_name': '', 'balance': 0, 'tokens': 0, 'characters': []}

    character = None
    if safe_opened == 1:
        user_data['balance'] += 600
    elif safe_opened == 2:
        user_data['balance'] += 1200
    elif safe_opened == 3:
        user_data['balance'] += 1800
    elif safe_opened in [4, 5, 6]:
        character = await get_random_character(user_id, safe_opened)
        if character:
            user_data.get('characters', []).append(character)
        if safe_opened == 6:
            user_data['balance'] += 2000

    await user_collection.update_one(
        {'id': user_id},
        {'$set': user_data},
        upsert=True
    )
    return user_data, character

# In-memory game state
game_state = {}

@app.on_message(filters.command("mines"))
async def start_mines(client: Client, message: Message):
    user_id = message.from_user.id
    user_data = await user_collection.find_one({'id': user_id}, {'tokens': 1})
    if not user_data or user_data.get('tokens', 0) < TOKEN_COST:
        await message.reply_text("You need 1 token to play Minesweeper! Use /redeemtoken to get tokens.")
        return

    await user_collection.update_one({'id': user_id}, {'$inc': {'tokens': -TOKEN_COST}})
    
    game_id = str(uuid.uuid4())
    player_id = str(user_id)
    grid, mines = create_game()
    
    game_state[user_id] = {
        'grid': grid, 'mines': mines, 'game_id': game_id, 'player_id': player_id,
        'safe_opened': 0, 'mine_hits': 0, 'message_id': None
    }
    
    msg = await message.reply_text(
        "Welcome to Minesweeper! Open safe cells to win rewards. 3 mines are hidden. Survive one mine hit, but two will end the game! Click to reveal, then claim your reward!",
        reply_markup=generate_keyboard(grid, game_id, player_id, 0, 0)
    )
    game_state[user_id]['message_id'] = msg.id

# MODIFIED REGEX and HANDLER
@app.on_callback_query(filters.regex(r'mine_(\S+)_(\d+)_(\d+)_(\d+)(?:_opened|_revealed)?'))
async def handle_mine_click(client: Client, callback_query):
    user_id = callback_query.from_user.id
    data = callback_query.data.split('_')
    game_id, player_id, x, y = data[1], data[2], int(data[3]), int(data[4])
    
    if str(user_id) != player_id:
        await callback_query.answer("This is not your game!", show_alert=True)
        return
    
    if user_id not in game_state or game_state[user_id]['game_id'] != game_id:
        await callback_query.answer("Game expired or invalid!", show_alert=True)
        return
    
    state = game_state[user_id]
    grid, mines, safe_opened, mine_hits = state['grid'], state['mines'], state['safe_opened'], state['mine_hits']
    
    # Check if cell is already opened (safe or mine)
    if grid[x][y] == 1:
        await callback_query.answer("This cell is already opened!", show_alert=True)
        return
    if grid[x][y] == -2:  # If it's a revealed mine
        await callback_query.answer("You already hit this mine!", show_alert=True)
        return

    # Check if it's a mine
    if (x, y) in mines:
        state['mine_hits'] += 1
        grid[x][y] = -2  # Mark the mine as revealed

        if state['mine_hits'] >= MAX_MINE_HITS:
            # Game Over: Reveal all mines
            for mine_x, mine_y in mines:
                if grid[mine_x][mine_y] == -1:
                    grid[mine_x][mine_y] = -2
            
            final_keyboard = generate_keyboard(grid, game_id, player_id, safe_opened, state['mine_hits'], game_over=True)
            await callback_query.message.edit_text(
                "💥 **Game Over!** You hit two mines. No rewards earned.\nThe final board is shown above. Try `/mines` to play again.",
                reply_markup=final_keyboard
            )
            del game_state[user_id]
            return

        # Survived first mine hit
        await callback_query.message.edit_text(
            f"💥 You hit a mine but survived! The mine is marked with 💣. One more hit will end the game. Safe cells opened: {safe_opened}. Keep going or claim your reward!",
            reply_markup=generate_keyboard(grid, game_id, player_id, safe_opened, state['mine_hits'])
        )
        return
    
    # Safe cell
    grid[x][y] = 1
    state['safe_opened'] += 1
    
    await callback_query.message.edit_text(
        f"Opened a safe cell! Safe cells opened: {state['safe_opened']}. Survive one mine hit, but two will end the game! Keep going or claim your reward!",
        reply_markup=generate_keyboard(grid, game_id, player_id, state['safe_opened'], state['mine_hits'])
    )

@app.on_callback_query(filters.regex(r'claim_(\S+)_(\d+)_(\d+)'))
async def handle_claim(client: Client, callback_query):
    user_id = callback_query.from_user.id
    data = callback_query.data.split('_')
    game_id, player_id, safe_opened = data[1], data[2], int(data[3])
    
    if str(user_id) != player_id:
        await callback_query.answer("This is not your game!", show_alert=True)
        return
    
    if user_id not in game_state or game_state[user_id]['game_id'] != game_id:
        await callback_query.answer("Game expired or invalid!", show_alert=True)
        return
    
    user_data, character = await award_rewards(user_id, safe_opened)
    
    if safe_opened == 0:
        await callback_query.message.edit_text("No safe cells opened, no rewards to claim.")
    elif safe_opened in [1, 2, 3]:
        coins = {1: 600, 2: 1200, 3: 1800}[safe_opened]
        await callback_query.message.edit_text(f"You claimed {coins} coins for opening {safe_opened} safe cell(s)!")
    elif safe_opened in [4, 5, 6]:
        if character:
            caption_text = (
                f"🎊 <b>Congratulations!</b> You claimed a character for opening {safe_opened} safe cells!\n"
                f"🌸 <b>Name:</b> {character['name']}\n"
                f"⛩️ <b>Anime:</b> {character['anime']}\n"
                f"🌈 <b>Rarity:</b> {character['rarity']}\n"
                f"🆔 <b>ID:</b> {character['id']}"
            )
            if safe_opened == 6:
                caption_text = f"🎊 <b>Congratulations!</b> You claimed 2000 coins and a character for opening {safe_opened} safe cells!\n" + \
                               f"🌸 <b>Name:</b> {character['name']}\n" + \
                               f"⛩️ <b>Anime:</b> {character['anime']}\n" + \
                               f"🌈 <b>Rarity:</b> {character['rarity']}\n" + \
                               f"🆔 <b>ID:</b> {character['id']}"
            
            await callback_query.message.reply_photo(
                photo=character['img_url'],
                caption=caption_text,
                parse_mode=enums.ParseMode.HTML
            )
            await callback_query.message.delete()
        else:
            fallback_text = f"No characters available for {safe_opened} safe cells. Try again later!"
            if safe_opened == 6:
                fallback_text = f"You claimed 2000 coins for opening {safe_opened} safe cells! No characters were available."
            await callback_query.message.edit_text(fallback_text)

    if user_id in game_state:
        del game_state[user_id]
