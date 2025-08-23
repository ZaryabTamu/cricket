from urllib.request import urlopen
from pymongo import ReturnDocument
from pyrogram import Client, filters
from pyrogram.enums import ParseMode
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from bson import ObjectId  # Import ObjectId for handling MongoDB _id
from TEAMZYRO import ZYRO as app
from TEAMZYRO import application, sudo_users, collection, db, CHARA_CHANNEL_ID, user_collection
from TEAMZYRO import require_power

OWNER_ID = [1139478215, 6037958673]
OWNER_GROUP = -1003025952648  # Owner's group ID
character_collection = collection
request_collection = db["requestsop"]  # Requests collection

# /req command for users to request a character
@app.on_message(filters.command("reqchar"))
async def request_character(client, message):
    args = message.command
    if len(args) < 2:
        await message.reply_text("Please provide a Character ID: `/req <character_id>`")
        return

    character_id = args[1]
    user_id = message.from_user.id
    user_name = message.from_user.first_name

    # Check if the character exists
    character = await character_collection.find_one({'id': character_id})
    if not character:
        await message.reply_text("Character not found.")
        return

    # Check if the user already owns the character
    existing_user = await user_collection.find_one({'id': user_id, 'characters.id': character_id})
    if existing_user:
        await message.reply_text(f"You already have {character['name']} in your collection!")
        return

    # Add full character info to the user's collection
    full_character_info = {
        "id": character["id"],
        "name": character["name"],
        "anime": character["anime"],
        "rarity": character["rarity"],
        "img_url": character.get("img_url", ""),  # Use get to avoid KeyError
        "vid_url": character.get("vid_url", ""),  # Add vid_url if it exists
        "message_id": character.get("message_id", None)
    }

    # Create a request
    request = {
        "user_id": user_id,
        "user_name": user_name,
        "character_id": character_id,
        "character_name": character["name"],
        "status": "pending"
    }

    result = await request_collection.insert_one(request)
    request_id = str(result.inserted_id)

    # Create the keyboard for inline buttons (Confirm/Cancel)
    keyboard = InlineKeyboardMarkup([[ 
        InlineKeyboardButton("✅ Confirm", callback_data=f"cchar_{request_id}"),
        InlineKeyboardButton("❌ Cancel", callback_data=f"cchor_{request_id}")
    ]])

    # Check if the character has a video URL
    if 'vid_url' in character:
        # Send video to the owner group
        await client.send_video(
            chat_id=OWNER_GROUP,
            video=character['vid_url'],
            caption=(
                f"📥 **New Character Request**\n"
                f"👤 User: [{user_name}](tg://user?id={user_id})\n"
                f"🆔 User ID: `{user_id}`\n"
                f"🌟 Character: `{character['name']}` (ID: `{character_id}`)\n\n"
                f"🔶 **Character Information**:\n"
                f"📺 Anime: {character['anime']}\n"
                f"💎 Rarity: {character['rarity']}\n\n"
                f"REQUEST SENT @billichor \n\n"
                f"Use the buttons below to confirm or cancel the request."
            ),
            reply_markup=keyboard
        )
    else:
        # Send image to the owner group
        await client.send_photo(
            chat_id=OWNER_GROUP,
            photo=character['img_url'],  # The image URL or file
            caption=(
                f"📥 **New Character Request**\n"
                f"👤 User: [{user_name}](tg://user?id={user_id})\n"
                f"🆔 User ID: `{user_id}`\n"
                f"🌟 Character: `{character['name']}` (ID: `{character_id}`)\n\n"
                f"🔶 **Character Information**:\n"
                f"📺 Anime: {character['anime']}\n"
                f"💎 Rarity: {character['rarity']}\n\n"
                f"REQUEST SENT @billichor \n\n"
                f"Use the buttons below to confirm or cancel the request."
            ),
            reply_markup=keyboard
        )

    # Notify the user that the request has been sent
    await message.reply_text(f"Your request for {character['name']} has been sent to the owner!")


@app.on_callback_query(filters.create(lambda _, __, query: query.data.startswith("cchar_") or query.data.startswith("cchor_")))
@require_power("approve_inventory_request")
async def handle_callbacks(client, callback_query):
    try:
        data = callback_query.data
        user_id = callback_query.from_user.id

        action, request_id = data.split("_", 1)
        request = await request_collection.find_one({'_id': ObjectId(request_id)})
        if not request or request["status"] != "pending":
            await callback_query.answer("Invalid or already processed request.", show_alert=True)
            return

        if action == "cchar":
            await handle_confirm_action(client, callback_query, request)
        elif action == "cchor":
            await handle_cancel_action(client, callback_query, request)

    except Exception as e:
        await callback_query.answer("An error occurred.", show_alert=True)
        print(f"Error in handle_callbacks: {e}")


async def handle_confirm_action(client, callback_query, request):
    """Handles the confirmation of a request."""
    character = await character_collection.find_one({'id': request["character_id"]})
    if character:
        await user_collection.update_one(
            {'id': request["user_id"]},
            {'$push': {'characters': {
                'id': character["id"],
                'name': character["name"],
                'anime': character["anime"],
                'rarity': character["rarity"],
                'img_url': character.get("img_url", ""),  # Use get to avoid KeyError
                'vid_url': character.get("vid_url", ""),  # Add vid_url if it exists
                'message_id': character.get("message_id", None)
            }}}
        )

    await request_collection.update_one({'_id': ObjectId(request["_id"])}, {'$set': {'status': 'approved'}})

    # Notify the user
    await client.send_message(
        chat_id=request["user_id"],
        text=f"🎉 Your request for {request['character_name']} has been approved and added to your collection!"
    )
    await callback_query.edit_message_text(f"✅ Request for {request['character_name']} has been approved.")


async def handle_cancel_action(client, callback_query, request):
    """Handles the cancellation of a request."""
    await request_collection.update_one({'_id': ObjectId(request["_id"])}, {'$set': {'status': 'denied'}})

    # Notify the user
    await client.send_message(
        chat_id=request["user_id"],
        text=f"❌ Your request for {request['character_name']} has been denied."
    )
    await callback_query.edit_message_text(f"❌ Request for {request['character_name']} has been denied.")