import os
from bson.objectid import ObjectId
from pyrogram import filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from TEAMZYRO import app as ZYRO, CHARA_CHANNEL_ID, db, collection, require_power, rarity_map
from TEAMZYRO.modules.upload import upload_to_catbox

# Define wrong format message
WRONG_FORMAT_TEXT = """Wrong ❌ format...  
eg. /addchar muzan-kibutsuji Demon-slayer

format:- /addchar character-name anime-name"""

# Rarity map

upload_collection = db.uploads

# Find next available ID
async def find_available_id():
    cursor = collection.find().sort('id', 1)
    ids = []
    async for doc in cursor:
        if 'id' in doc:
            try:
                ids.append(int(doc['id']))
            except:
                continue
    if ids:
        return str(max(ids) + 1).zfill(2)
    return '01'


# Command: /addchar
@ZYRO.on_message(filters.command(["addchar"]))
async def request_upload(client, message):
    reply = message.reply_to_message
    if not reply or not (reply.photo or reply.document):
        return await message.reply_text("Please reply to a photo or document.")

    args = message.text.split()
    if len(args) != 3:
        return await message.reply_text(WRONG_FORMAT_TEXT)

    processing_message = await message.reply("⏳ Processing...")

    character_name = args[1].replace('-', ' ').title()
    anime = args[2].replace('-', ' ').title()
    path = await reply.download()

    try:
        catbox_url = await upload_to_catbox(path)  # FIXED: Added await

        upload_data = {
            'name': character_name,
            'anime': anime,
            'img_url': catbox_url,
            'requested_by': {
                'id': message.from_user.id,
                'name': message.from_user.first_name
            }
        }

        result = await upload_collection.insert_one(upload_data)

        # Build rarity buttons (4 per row)
        rarity_buttons = []
        rarity_items = list(rarity_map.items())
        for i in range(0, len(rarity_items), 4):
            row = [
                InlineKeyboardButton(text=value, callback_data=f"rarity_{result.inserted_id}_{key}")
                for key, value in rarity_items[i:i+4]
            ]
            rarity_buttons.append(row)

        # Cancel button
        rarity_buttons.append([InlineKeyboardButton("❌ Cancel", callback_data=f"cancel_{result.inserted_id}")])

        keyboard = InlineKeyboardMarkup(rarity_buttons)

        await client.send_photo(
            chat_id=CHARA_CHANNEL_ID,
            photo=catbox_url,
            caption=(
                f"#pending\n\n"
                f"**New Character Upload Request**\n"
                f"Character Name: {character_name}\n"
                f"Anime Name: {anime}\n"
                f"Requested by [{message.from_user.first_name}](tg://user?id={message.from_user.id})\n\n"
                f"Select a rarity to upload the character or cancel the request:"
            ),
            reply_markup=keyboard
        )

        await processing_message.edit("✅ Your request has been submitted successfully!")
    except Exception as e:
        await processing_message.edit(f"❌ Request upload failed.\nError: {str(e)}")
    finally:
        try:
            os.remove(path)
        except:
            pass


# Cancel request handler
@ZYRO.on_callback_query(filters.create(lambda _, __, q: q.data.startswith("cancel_")))
@require_power("add_character")
async def handle_cancel(client, callback_query):
    try:
        _, request_id = callback_query.data.split("_")
        result = await upload_collection.delete_one({"_id": ObjectId(request_id)})

        if result.deleted_count > 0:
            await callback_query.edit_message_caption(
                caption="❌ The upload request has been canceled.",
                reply_markup=None
            )
            await callback_query.answer("Request canceled successfully.")
        else:
            await callback_query.answer("Request not found or already processed.", show_alert=True)
    except Exception as e:
        print(f"Error in handle_cancel: {str(e)}")
        await callback_query.answer("An error occurred while canceling the request.", show_alert=True)


# Approve request with rarity
@ZYRO.on_callback_query(filters.create(lambda _, __, q: q.data.startswith("rarity_")))
@require_power("approve_request")
async def handle_callback(client, callback_query):
    try:
        _, request_id, new_rarity = callback_query.data.split("_")
        new_rarity = int(new_rarity)
        new_rarity_text = rarity_map[new_rarity]

        request = await upload_collection.find_one({"_id": ObjectId(request_id)})
        if not request:
            return await callback_query.answer("Request not found or already processed.", show_alert=True)

        available_id = await find_available_id()
        request['id'] = available_id
        request['rarity'] = new_rarity_text

        await collection.insert_one(request)
        await upload_collection.delete_one({"_id": ObjectId(request_id)})

        await callback_query.edit_message_caption(
            caption=(
                f"**✅ Character Uploaded**\n"
                f"Character Name: {request['name']}\n"
                f"Anime Name: {request['anime']}\n"
                f"Rarity: {new_rarity_text}\n"
                f"ID: {available_id}\n"
                f"Uploaded by [{callback_query.from_user.first_name}](tg://user?id={callback_query.from_user.id})"
            ),
            reply_markup=None
        )

        await callback_query.answer(f"Character uploaded with rarity: {new_rarity_text}")
    except Exception as e:
        print(f"Error in handle_callback: {str(e)}")
        await callback_query.answer("An error occurred while processing the request.", show_alert=True)