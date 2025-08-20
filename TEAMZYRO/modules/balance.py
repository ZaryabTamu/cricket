from TEAMZYRO import *
from pyrogram import Client, filters
from pyrogram.types import Message
import html

async def get_balance(user_id):
    user_data = await user_collection.find_one({'id': user_id}, {'balance': 1, 'tokens': 1})
    if user_data:
        return user_data.get('balance', 0), user_data.get('tokens', 0)
    return 0, 0

@app.on_message(filters.command("balance"))
async def balance(client: Client, message: Message):
    user_id = message.from_user.id
    user_balance, user_tokens = await get_balance(user_id)

    response = (
        f"👤 **{html.escape(message.from_user.first_name)}'s Profile**\n\n"
        f"💲 **Money:** {user_balance}\n"
        f"🎫 **Tokens:** {user_tokens}"
    )

    await message.reply_text(response, quote=True)

@app.on_message(filters.command("pay"))
async def pay(client: Client, message: Message):
    sender_id = message.from_user.id
    args = message.command

    # If no amount provided
    if len(args) < 2:
        await message.reply_text(
            "⚠️ **Usage:** `/pay <amount> [@username/user_id]` or reply to a user.\n\n"
            "💡 Example: `/pay 100 @username`"
        )
        return

    # Validate amount
    try:
        amount = int(args[1])
        if amount <= 0:
            raise ValueError
    except ValueError:
        await message.reply_text("❌ Invalid amount. Please enter a positive number.")
        return

    recipient_id = None
    recipient_name = None

    # If replying to a user
    if message.reply_to_message:
        recipient_id = message.reply_to_message.from_user.id
        recipient_name = message.reply_to_message.from_user.first_name

    # If username/user_id provided
    elif len(args) > 2:
        try:
            recipient_id = int(args[2])
        except ValueError:
            recipient_username = args[2].lstrip('@')  # remove '@'
            user_data = await user_collection.find_one(
                {'username': recipient_username}, {'id': 1, 'first_name': 1}
            )
            if user_data:
                recipient_id = user_data['id']
                recipient_name = user_data.get('first_name', recipient_username)
            else:
                await message.reply_text("🙅 Recipient not found. Please reply to a user or provide a valid username/ID.")
                return

    if not recipient_id:
        await message.reply_text("⚠️ Recipient not found. Reply to a user or provide a valid user ID/username.")
        return

    # Check sender balance
    sender_balance, _ = await get_balance(sender_id)
    if sender_balance < amount:
        await message.reply_text("💸 Insufficient balance! You don’t have enough coins.")
        return

    # Update balances
    await user_collection.update_one({'id': sender_id}, {'$inc': {'balance': -amount}})
    await user_collection.update_one({'id': recipient_id}, {'$inc': {'balance': amount}})

    updated_sender_balance, _ = await get_balance(sender_id)
    updated_recipient_balance, _ = await get_balance(recipient_id)

    # Display names
    recipient_display = html.escape(recipient_name or str(recipient_id))
    sender_display = html.escape(message.from_user.first_name or str(sender_id))

    # Notify sender
    await message.reply_text(
        f"✅ **Payment Successful!**\n\n"
        f"👤 You sent **{amount} 💰 coins** to **{recipient_display}**.\n"
        f"💳 **Your New Balance:** {updated_sender_balance} coins"
    )

    # Notify recipient
    await client.send_message(
        chat_id=recipient_id,
        text=(
            f"🎉 **You Received a Payment!**\n\n"
            f"💸 **Amount:** {amount} coins\n"
            f"👤 **From:** {sender_display}\n"
            f"💳 **Your New Balance:** {updated_recipient_balance} coins"
        )
    )

@app.on_message(filters.command("kill"))
@require_power("VIP")
async def kill_handler(client, message):
    # Get the user_id from the reply message
    if message.reply_to_message:
        user_id = message.reply_to_message.from_user.id
    else:
        await message.reply_text("Please reply to a user's message to use the /kill command.")
        return

    command_args = message.text.split()

    if len(command_args) < 2:
        await message.reply_text("Please specify an option: `c` to delete character, `f` to delete full data, or `b` to delete balance.")
        return

    option = command_args[1]

    try:
        if option == 'f':
            # Delete full user data
            await user_collection.delete_one({"id": user_id})
            await message.reply_text("The full data of the user has been deleted.")

        elif option == 'c':
            # Delete specific character from the user's collection
            if len(command_args) < 3:
                await message.reply_text("Please specify a character ID to remove.")
                return

            char_id = command_args[2]
            user = await user_collection.find_one({"id": user_id})

            if user and 'characters' in user:
                characters = user['characters']
                updated_characters = [c for c in characters if c.get('id') != char_id]

                if len(updated_characters) == len(characters):
                    await message.reply_text(f"No character with ID {char_id} found in the user's collection.")
                    return

                # Update user collection
                await user_collection.update_one({"id": user_id}, {"$set": {"characters": updated_characters}})
                await message.reply_text(f"Character with ID {char_id} has been removed from the user's collection.")
            else:
                await message.reply_text(f"No characters found in the user's collection.")

        elif option == 'b':
            # Check if amount is provided
            if len(command_args) < 3:
                await message.reply_text("Please specify an amount to deduct from balance.")
                return

            try:
                amount = int(command_args[2])
            except ValueError:
                await message.reply_text("Invalid amount. Please enter a valid number.")
                return

            # Fetch user balance
            user_data = await user_collection.find_one({"id": user_id}, {"balance": 1})
            if user_data and "balance" in user_data:
                current_balance = user_data["balance"]
                new_balance = max(0, current_balance - amount)  # Ensure balance doesn't go negative
                
                await user_collection.update_one({"id": user_id}, {"$set": {"balance": new_balance}})
                await message.reply_text(f"{amount} has been deducted from the user's balance. New balance: {new_balance}")
            else:
                await message.reply_text("The user has no balance to deduct from.")

        else:
            await message.reply_text("Invalid option. Use `c` for character, `f` for full data, or `b {amount}` to deduct balance.")

    except Exception as e:
        print(f"Error in /kill command: {e}")
        await message.reply_text("An error occurred while processing the request. Please try again later.")



@app.on_message(filters.command("give"))
@require_power("VIP")  # Only VIPs can use this
async def give_handler(client: Client, message: Message):
    if not message.reply_to_message:
        await message.reply_text("Reply to a user to give them coins or tokens.")
        return

    args = message.command
    if len(args) < 3:
        await message.reply_text("Usage: /give [c|t] [amount]\n\n`c` = coins\n`t` = tokens")
        return

    option = args[1].lower()
    try:
        amount = int(args[2])
        if amount <= 0:
            raise ValueError
    except ValueError:
        await message.reply_text("Amount must be a positive number.")
        return

    recipient_id = message.reply_to_message.from_user.id
    recipient_name = html.escape(message.reply_to_message.from_user.first_name or str(recipient_id))

    if option == 'c':
        await user_collection.update_one({'id': recipient_id}, {'$inc': {'balance': amount}})
        await message.reply_text(f"✅ {amount} coins have been added to {recipient_name}'s balance.")
    elif option == 't':
        await user_collection.update_one({'id': recipient_id}, {'$inc': {'tokens': amount}})
        await message.reply_text(f"✅ {amount} tokens have been added to {recipient_name}'s account.")
    else:
        await message.reply_text("Invalid option. Use `c` for coins or `t` for tokens.")
