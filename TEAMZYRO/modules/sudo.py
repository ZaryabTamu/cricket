from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from functools import wraps

from TEAMZYRO import OWNER_ID, app, db

# Database collection
sudo_users = db['sudo_users']

# Powers with emojis
ALL_POWERS = {
    "add_character": "🌟 Add Character",
    "delete_character": "🗑 Delete Character",
    "update_character": "✏️ Update Character",
    "approve_request": "✅ Approve Request",
    "approve_inventory_request": "📦 Approve Inventory",
    "VIP": "👑 VIP"
}

# ================= REQUIRE POWER ================= #
def require_power(required_power):
    def decorator(func):
        @wraps(func)
        async def wrapper(client, message, *args, **kwargs):
            if isinstance(message, CallbackQuery):
                user_id = message.from_user.id
                if user_id == OWNER_ID:
                    return await func(client, message, *args, **kwargs)
                user_data = await sudo_users.find_one({"_id": user_id})
                if not user_data or not user_data.get("powers", {}).get(required_power, False):
                    return await message.answer(f"🚫 You lack `{required_power}` power!", show_alert=True)
                return await func(client, message, *args, **kwargs)

            user_id = message.from_user.id
            if user_id == OWNER_ID:
                return await func(client, message, *args, **kwargs)
            user_data = await sudo_users.find_one({"_id": user_id})
            if not user_data or not user_data.get("powers", {}).get(required_power, False):
                return await message.reply_text(f"🚫 You lack `{required_power}` power!")
            return await func(client, message, *args, **kwargs)
        return wrapper
    return decorator

# ================= ADD SUDO ================= #
@app.on_message(filters.command(["saddsudo", "assign"]) & filters.reply)
@require_power("VIP")
async def add_sudo(client, message):
    replied_user = message.reply_to_message.from_user
    replied_user_id = replied_user.id
    replied_user_name = replied_user.first_name

    existing_user = await sudo_users.find_one({"_id": replied_user_id})
    if existing_user:
        return await message.reply_text(f"⚠️ {replied_user_name} is already a sudo.")

    await sudo_users.update_one(
        {"_id": replied_user_id},
        {"$set": {"powers": {"add_character": True}}},
        upsert=True
    )
    await message.reply_text(f"✅ {replied_user_name} added as **Sudo** with `Add Character` power.")

# ================= REMOVE SUDO ================= #
@app.on_message(filters.command(["sremovesudo", "unassign"]))
@require_power("VIP")
async def remove_sudo(client, message):
    if message.reply_to_message:
        user = message.reply_to_message.from_user
        user_id, user_name = user.id, user.first_name
    elif len(message.command) > 1 and message.command[1].isdigit():
        user_id = int(message.command[1])
        try:
            user_info = await client.get_users(user_id)
            user_name = user_info.first_name
        except:
            user_name = str(user_id)
    else:
        return await message.reply_text("❌ Reply to a user or provide a valid user ID.")

    existing_user = await sudo_users.find_one({"_id": user_id})
    if not existing_user:
        return await message.reply_text(f"⚠️ {user_name} is not a sudo.")

    await sudo_users.delete_one({"_id": user_id})
    await message.reply_text(f"🗑 Removed **Sudo** {user_name}")

# ================= EDIT SUDO (INLINE BUTTONS) ================= #
@app.on_message(filters.command("editassign") & filters.reply)
@require_power("VIP")
async def edit_sudo(client, message):
    replied_user = message.reply_to_message.from_user
    replied_user_id = replied_user.id
    replied_user_name = replied_user.first_name

    user_data = await sudo_users.find_one({"_id": replied_user_id})
    if not user_data:
        return await message.reply_text("❌ This user is not a sudo.")

    powers = user_data.get("powers", {})
    buttons = []

    for power, label in ALL_POWERS.items():
        status = "🟢 ON" if powers.get(power, False) else "🔴 OFF"
        buttons.append([
            InlineKeyboardButton(f"{label}", callback_data="noop"),
            InlineKeyboardButton(status, callback_data=f"toggle_{replied_user_id}_{power}")
        ])

    buttons.append([InlineKeyboardButton("❌ Close", callback_data="close_keyboard")])
    keyboard = InlineKeyboardMarkup(buttons)

    await message.reply_text(f"⚙️ Edit powers for **{replied_user_name}**:", reply_markup=keyboard)

# ================= TOGGLE POWER ================= #
@app.on_callback_query(filters.regex(r"^toggle_(\d+)_(\w+)$"))
@require_power("VIP")
async def toggle_power(client, callback_query):
    user_id = int(callback_query.matches[0].group(1))
    power = callback_query.matches[0].group(2)

    user_data = await sudo_users.find_one({"_id": user_id})
    if not user_data:
        return await callback_query.answer("❌ User not found.", show_alert=True)

    current_status = user_data.get("powers", {}).get(power, False)
    new_status = not current_status
    await sudo_users.update_one(
        {"_id": user_id},
        {"$set": {f"powers.{power}": new_status}}
    )

    await callback_query.answer(
        f"{ALL_POWERS.get(power, power)} ➝ {'🟢 ON' if new_status else '🔴 OFF'}",
        show_alert=True
    )

    try:
        user_info = await client.get_users(user_id)
        user_name = user_info.first_name
    except:
        user_name = str(user_id)

    user_data = await sudo_users.find_one({"_id": user_id})
    powers = user_data.get("powers", {})
    buttons = []
    for p, label in ALL_POWERS.items():
        status = "🟢 ON" if powers.get(p, False) else "🔴 OFF"
        buttons.append([
            InlineKeyboardButton(f"{label}", callback_data="noop"),
            InlineKeyboardButton(status, callback_data=f"toggle_{user_id}_{p}")
        ])
    buttons.append([InlineKeyboardButton("❌ Close", callback_data="close_keyboard")])

    keyboard = InlineKeyboardMarkup(buttons)
    await callback_query.message.edit_text(
        f"⚙️ Edit powers for **{user_name}**:",
        reply_markup=keyboard
    )

# ================= CLOSE KEYBOARD ================= #
@app.on_callback_query(filters.regex(r"^close_keyboard$"))
@require_power("VIP")
async def close_keyboard(client, callback_query):
    await callback_query.message.edit_reply_markup(reply_markup=None)
    await callback_query.answer("✅ Closed.")

# ================= SUDO LIST ================= #
@app.on_message(filters.command("assigned"))
async def sudo_list(client, message):
    if message.from_user.id != OWNER_ID:
        return await message.reply_text("🚫 You don’t have permission.")

    users = await sudo_users.find().to_list(length=None)
    if not users:
        return await message.reply_text("📂 No sudo users.")

    text = "👑 **Sudo Users List:**\n\n"
    for user in users:
        user_id = user.get("_id")
        try:
            user_info = await client.get_users(user_id)
            user_name = user_info.first_name
        except:
            user_name = "Unknown"

        text += f"• {user_name} (`{user_id}`)\n"

    await message.reply_text(text, disable_web_page_preview=True)