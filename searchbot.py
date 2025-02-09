from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import asyncpg
from datetime import datetime
import tempfile

# Database connection pool
DATABASE_URL = "postgresql://bot_user:976431@localhost/credential_db"
BOT_TOKEN = "2031734372:AAHik4D-ASQecvdQGz7PXxJk9hFePAjIkHs";

# Start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    async with asyncpg.create_pool(DATABASE_URL) as pool:
        async with pool.acquire() as conn:
            # Check if user exists, if not, create a new entry
            user = await conn.fetchrow("SELECT * FROM users WHERE user_id = $1", user_id)
            if not user:
                await conn.execute("INSERT INTO users (user_id, credits, role) VALUES ($1, $2, $3)", user_id, 2, 'user')  # Default role is 'user'
                await update.message.reply_text("Welcome {user)!\n\n"
   					 "You have been given 2 free credits.\n"
   					 "Use /search <query> to search the database.\n"
					 "Use /credits to check balance.")
            else:
                await update.message.reply_text(f"Welcome back! You have {user['credits']} credits remaining.\n\n""Use /search <query> to search the database.\n"
					 "Use /credits to check balance.")

# Search command
async def search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    query = " ".join(context.args)
    
    if not query:
        await update.message.reply_text("Please provide a search term. Example: /search example.com")
        return

    async with asyncpg.create_pool(DATABASE_URL) as pool:
        async with pool.acquire() as conn:
            user = await conn.fetchrow("SELECT * FROM users WHERE user_id = $1", user_id)
            if not user:
                await update.message.reply_text("You are not registered. Use /start to register.")
                return

            if user['credits'] < 1 and user['role'] != 'owner':
                await update.message.reply_text("Insufficient credits! Please purchase more credits.")
                return

            # Deduct credit for regular users
            if user['role'] != 'owner':
                await conn.execute("UPDATE users SET credits = credits - 1 WHERE user_id = $1", user_id)

            # Log the search query
            await conn.execute("INSERT INTO search_logs (user_id, query) VALUES ($1, $2)", user_id, query)

            # Get 50 results
            results = await conn.fetch(
                "SELECT url, username, password FROM credentials WHERE url ILIKE $1 OR username ILIKE $1 LIMIT 50",
                f"%{query}%"
            )

            if not results:
                await update.message.reply_text("No results found.")
                return

            # Create temporary file
            with tempfile.NamedTemporaryFile(mode='w+', suffix='.txt', delete=True) as temp_file:
                # Write results to file
                for row in results:
                    temp_file.write(f"{row['url']}:{row['username']}:{row['password']}\n")
                
                # Reset file pointer to beginning
                temp_file.seek(0)
                
                # Send as document
                await update.message.reply_document(
                    document=temp_file,
                    filename=f"search_results_{query[:20]}.txt",
                    caption=f"Found {len(results)} results for '{query}'"
                )
# Credits command
async def credits(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    async with asyncpg.create_pool(DATABASE_URL) as pool:
        async with pool.acquire() as conn:
            # Check user credits
            user = await conn.fetchrow("SELECT * FROM users WHERE user_id = $1", user_id)
            if not user:
                await update.message.reply_text("You are not registered. Use /start to register.")
                return

            await update.message.reply_text(f"You have {user['credits']} credits remaining.")

# Admin command to add credits
async def add_credits(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    async with asyncpg.create_pool(DATABASE_URL) as pool:
        async with pool.acquire() as conn:
            # Check if the user is the owner
            user = await conn.fetchrow("SELECT * FROM users WHERE user_id = $1", user_id)
            if user['role'] != 'owner':
                await update.message.reply_text("You do not have permission to use this command.")
                return

            # Get the target user and credits to add
            try:
                target_user_id = int(context.args[0])
                credits_to_add = int(context.args[1])
            except (IndexError, ValueError):
                await update.message.reply_text("Usage: /addcredits <user_id> <credits>")
                return

            # Add credits to the target user
            await conn.execute("UPDATE users SET credits = credits + $1 WHERE user_id = $2", credits_to_add, target_user_id)
            await update.message.reply_text(f"Added {credits_to_add} credits to user {target_user_id}.")

# Main function
def main():
    # Create the Application
    application = Application.builder().token(BOT_TOKEN).build()

    # Add command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("search", search))
    application.add_handler(CommandHandler("credits", credits))
    application.add_handler(CommandHandler("addcredits", add_credits))

    # Run the bot
    application.run_polling()

if __name__ == "__main__":
    main()