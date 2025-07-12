from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message
from TEAMZYRO import app, user_collection, collection
import random
import uuid
from asyncio import sleep

# Rarity map
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

# Initialize game state
def create_game():
    grid = [[0 for _ in range(GRID_SIZE)] for _ in range(GRID_SIZE)]  # 0 = empty, -1 = mine, 1 = opened
    mines = random.sample([(i, j) for i in range(GRID_SIZE) for j in range(GRID_SIZE)], NUM_MINES)
    for mine_x, mine_y in mines:
        grid[mine_x][mine_y] = -1
    return grid, mines

# Generate inline keyboard for the game
def generate_keyboard(grid, game_id, player_id, safe_opened, mine_hits):
    keyboard = []
    # Grid buttons
    for i in range(GRID_SIZE):
        row = []
        for j in range(GRID_SIZE):
            if grid[i][j] == 1:  # Opened cell
                row.append(InlineKeyboardButton("⬜", callback_data=f"mine_{game_id}_{player_id}_{i}_{j}_opened"))
            else:  # Unopened cell (mines are hidden)
                row.append(InlineKeyboardButton("🔳", callback_data=f"mine_{game_id}_{player_id}_{i}_{j}"))
        keyboard.append(row)
    # Claim button (appears after at least one safe box is opened)
    if safe_opened > 0:
        keyboard.append([InlineKeyboardButton("Claim Reward", callback_data=f"claim_{game_id}_{player_id}_{safe_opened}")])
    return InlineKeyboardMarkup(keyboard)

# Get random character based on rarity
async def get_random_character(rarities):
    try:
        pipeline = [
            {'$match': {'rarity': {'$in': rarities}}},
            {'$sample': {'size': 1}}  # Randomly sample one character
        ]
        cursor = collection.aggregate(pipeline)
        characters = await cursor.to_list(length=None)
        if characters:
            character = characters[0]
            # Ensure all required fields are present
            required_fields = ['id', 'name', 'anime', 'rarity']
            if all(field in character for field in required_fields):
                return {
                    'id': character['id'],
                    'name': character['name'],
                    'anime': character['anime'],
                    'rarity': character['rarity'],
                    'img_url': character.get('img_url', ''),
                    'vid_url': character.get('vid_url', '')
                }
        return None
    except Exception as e:
        print(f"Error retrieving character: {e}")
        return None

# Calculate rewards
async def award_rewards(user_id, safe_opened):
    user_data = await user_collection.find_one({'id': user_id})
    if not user_data:
        user_data = {
            'id': user_id,
            'username': '',
            'first_name': '',
            'balance': 0,
            'tokens': 0,
            'characters': []
        }

    character = None
    if safe_opened == 1:
        user_data['balance'] += 100
    elif safe_opened == 2:
        user_data['balance'] += 200
    elif safe_opened == 3:
        user_data['balance'] += 400
    elif safe_opened == 4:
        character = await get_random_character(['🟣 Rare', '💮 Special Edition'])
        if character:
            user_data['characters'].append(character)
    elif safe_opened == 5:
        character = await get_random_character(['🔮 Limited Edition', '🎐 Celestial'])
        if character:
            user_data['characters'].append(character)
    elif safe_opened == 6:
        user_data['balance'] += 2000
        character = await get_random_character(['💸 Expensive', '✨ Neon'])
        if character:
            user_data['characters'].append(character)

    try:
        await user_collection.update_one(
            {'id': user_id},
            {'$set': {'balance': user_data['balance'], 'characters': user_data['characters']}},
            upsert=True
        )
    except Exception as e:
        print(f"Error updating user_collection: {e}")
        return user_data, None

    return user_data, character

# In-memory game state (consider MongoDB for persistence)
game_state = {}

@app.on_message(filters.command("mines"))
async def start_mines(client: Client, message: Message):
    user_id = message.from_user.id
    # Check tokens
    user_data = await user_collection.find_one({'id': user_id}, {'tokens': 1})
    if not user_data or user_data.get('tokens', 0) < TOKEN_COST:
        await message.reply_text("You need 1 token to play Minesweeper! Use /redeemtoken to get tokens.")
        return

    # Deduct token
    try:
        await user_collection.update_one({'id': user_id}, {'$inc': {'tokens': -TOKEN_COST}})
    except Exception as e:
        print(f"Error deducting token: {e}")
        await message.reply_text("❌ Error starting game. Try again later.")
        return
    
    game_id = str(uuid.uuid4())  # Unique game ID
    player_id = str(user_id)  # Player ID for button restriction
    grid, mines = create_game()
    
    # Store game state with mine_hits
    game_state[user_id] = {
        'grid': grid,
        'mines': mines,
        'game_id': game_id,
        'player_id': player_id,
        'safe_opened': 0,
        'mine_hits': 0
    }
    
    await message.reply_text(
        "Welcome to Minesweeper! Open safe cells to win rewards. 3 mines are hidden. Survive one mine hit, but two will end the game! Click to reveal, then claim your reward!",
        reply_markup=generate_keyboard(grid, game_id, player_id, 0, 0)
    )

@app.on_callback_query(filters.regex(r'mine_(\S+)_(\d+)_(\d+)_(\d+)(?:_opened)?'))
async def handle_mine_click(client: Client, callback_query):
    user_id = callback_query.from_user.id
    data = callback_query.data.split('_')
    game_id, player_id, x, y = data[1], data[2], int(data[3]), int(data[4])
    
    # Restrict to player who started the game
    if str(user_id) != player_id:
        await callback_query.answer("This is not your game!", show_alert=True)
        return
    
    # Verify game state
    if user_id not in game_state or game_state[user_id]['game_id'] != game_id:
        await callback_query.answer("Game expired or invalid!", show_alert=True)
        return
    
    state = game_state[user_id]
    grid, mines, safe_opened, mine_hits = state['grid'], state['mines'], state['safe_opened'], state['mine_hits']
    
    # Check if cell is already opened
    if grid[x][y] == 1:
        await callback_query.answer("This cell is already opened!", show_alert=True)
        return
    
    # Check if it's a mine
    if (x, y) in mines:
        state['mine_hits'] += 1
        if state['mine_hits'] >= MAX_MINE_HITS:
            # End game, remove buttons, no rewards
            await callback_query.message.edit_text("💥 Game Over! You hit two mines. No rewards earned. Try /mines to play again.")
            del game_state[user_id]
            return
        # Survive first mine hit
        await callback_query.message.edit_text(
            f"💥 You hit a mine but survived! One more hit will end the game. Safe cells opened: {safe_opened}. Keep going or claim your reward!",
            reply_markup=generate_keyboard(grid, game_id, player_id, safe_opened, mine_hits)
        )
        return
    
    # Safe cell
    grid[x][y] = 1
    state['safe_opened'] += 1
    
    await callback_query.message.edit_text(
        f"Opened a safe cell! Safe cells opened: {state['safe_opened']}. Survive one mine hit, but two will end the game! Keep going or claim your reward!",
        reply_markup=generate_keyboard(grid, game_id, player_id, state['safe_opened'], mine_hits)
    )

@app.on_callback_query(filters.regex(r'claim_(\S+)_(\d+)_(\d+)'))
async def handle_claim(client: Client, callback_query):
    user_id = callback_query.from_user.id
    data = callback_query.data.split('_')
    game_id, player_id, safe_opened = data[1], data[2], int(data[3])
    
    # Restrict to player
    if str(user_id) != player_id:
        await callback_query.answer("This is not your game!", show_alert=True)
        return
    
    # Verify game state
    if user_id not in game_state or game_state[user_id]['game_id'] != game_id:
        await callback_query.answer("Game expired or invalid!", show_alert=True)
        return
    
    # Award rewards
    user_data, character = await award_rewards(user_id, safe_opened)
    if safe_opened == 0:
        await callback_query.message.edit_text("No safe cells opened, no rewards to claim.")
    elif safe_opened in [1, 2, 3]:
        coins = {1: 100, 2: 200, 3: 400}[safe_opened]
        await callback_query.message.edit_text(f"You claimed {coins} coins for opening {safe_opened} safe cell(s)!")
    elif safe_opened in [4, 5]:
        if character:
            await callback_query.message.edit_text(
                f"You claimed a character: {character['name']} ({character['anime']}, {character['rarity']}) for opening {safe_opened} safe cells!"
            )
        else:
            await callback_query.message.edit_text(
                f"No characters available for {safe_opened} safe cells. Try again later!"
            )
    elif safe_opened == 6:
        if character:
            await callback_query.message.edit_text(
                f"You claimed 2000 coins and a character: {character['name']} ({character['anime']}, {character['rarity']}) for opening {safe_opened} safe cells!"
            )
        else:
            await callback_query.message.edit_text(
                f"You claimed 2000 coins for opening {safe_opened} safe cells! No characters available."
            )
    
    # End game, remove buttons
    del game_state[user_id]
