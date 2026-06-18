import os
import discord
from discord.ext import commands
from discord import app_commands
import random
from pymongo import MongoClient

class MyBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=discord.Intents.default())

    async def setup_hook(self):
        await self.tree.sync() 
        print("Слеш-команды успешно синхронизированы!")

bot = MyBot()

# --- БАЗА ДАННЫХ MONGODB ---
# Получаем секретную ссылку из настроек хостинга
MONGO_URL = os.getenv('MONGO_URL')
cluster = MongoClient(MONGO_URL)
db = cluster["barbot_database"] # Создаем базу данных
users_collection = db["users"] # Создаем "таблицу" (коллекцию) пользователей

DRINKS = [
    "🍺 Светлое нефильтрованное", "🍻 Темный ирландский стаут",
    "🍷 Бокал красного сухого", "🥃 Шот текилы с лимоном",
    "🍸 Водка со льдом", "🍹 Коктейль 'Куба Либре'",
    "🍾 Бутылку шампанского"
]

# --- КОМАНДА /DRINK ---
@bot.tree.command(name="drink", description="Выпить алкоголь в баре")
#@app_commands.checks.cooldown(1, 3600.0, key=lambda i: (i.guild_id, i.user.id))
async def drink(interaction: discord.Interaction):
    user_id = interaction.user.id
    guild_id = interaction.guild_id
    
    drink_choice = random.choice(DRINKS)
    
    # Ищем пользователя в MongoDB
    user_data = users_collection.find_one({"user_id": user_id, "guild_id": guild_id})
    current_liters = user_data["liters"] if user_data else 0.0
    
    if current_liters < 5.0: added_liters = random.uniform(0.3, 0.5)
    elif current_liters < 15.0: added_liters = random.uniform(0.5, 1.0)
    elif current_liters < 30.0: added_liters = random.uniform(1.0, 2.0)
    else: added_liters = random.uniform(2.0, 4.0)
        
    added_liters = round(added_liters, 2)
    new_total = round(current_liters + added_liters, 2)
    
    # Обновляем или добавляем данные
    if user_data is None:
        users_collection.insert_one({"user_id": user_id, "guild_id": guild_id, "liters": new_total})
    else:
        users_collection.update_one({"user_id": user_id, "guild_id": guild_id}, {"$set": {"liters": new_total}})
    
    await interaction.response.send_message(f"**{interaction.user.name}** заказывает у бармена {drink_choice} и выпивает залпом **{added_liters} л.**! 🥂\n*(Всего выпито: {new_total} л.)*")

@drink.error
async def drink_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.CommandOnCooldown):
        minutes = int(error.retry_after / 60)
        await interaction.response.send_message(f"🛑 Твоя печень просит пощады! Приходи к барной стойке через {minutes} минут.", ephemeral=True)


# --- КОМАНДА /LEADERBOARD ---
@bot.tree.command(name="leaderboard", description="Показать список главных алко-баронов сервера")
async def leaderboard(interaction: discord.Interaction):
    # Достаем топ-10 пользователей из MongoDB и сортируем по убыванию
    top_users = users_collection.find({"guild_id": interaction.guild_id}).sort("liters", -1).limit(10)
    top_users_list = list(top_users)
    
    if not top_users_list:
        await interaction.response.send_message("🍺 В этом баре еще никто не пил! Будь первым, используй /drink")
        return

    embed = discord.Embed(title="🏆 Топ посетителей бара", description="Самые стойкие участники нашего сервера:", color=discord.Color.gold())

    for index, user_data in enumerate(top_users_list, 1):
        uid = user_data["user_id"]
        liters_count = user_data["liters"]
        
        if index == 1: medal = "🥇"
        elif index == 2: medal = "🥈"
        elif index == 3: medal = "🥉"
        else: medal = "🍺"
            
        embed.add_field(name=f"{medal} {index} место", value=f"<@{uid}> — **{liters_count} л.**", inline=False)
        
    await interaction.response.send_message(embed=embed)


# --- КОМАНДА /STATS ---
@bot.tree.command(name="stats", description="Посмотреть свою личную статистику в баре")
async def stats(interaction: discord.Interaction):
    user_id = interaction.user.id
    guild_id = interaction.guild_id
    
    user_data = users_collection.find_one({"user_id": user_id, "guild_id": guild_id})
    liters_count = user_data["liters"] if user_data else 0.0
    
    embed = discord.Embed(title=f"📊 Барная карта: {interaction.user.name}", color=discord.Color.blue())
    if interaction.user.avatar: embed.set_thumbnail(url=interaction.user.avatar.url)
        
    if liters_count == 0: status = "Трезвенник 🥱"
    elif liters_count < 5.0: status = "Новичок в баре 🥂"
    elif liters_count < 15.0: status = "Любитель тусовок 🍺"
    elif liters_count < 30.0: status = "Завсегдатай клуба 🥃"
    else: status = "Легенда этого заведения 👑"
        
    embed.add_field(name="Выпито алкоголя:", value=f"**{liters_count} л.**", inline=True)
    embed.add_field(name="Твой статус:", value=f"*{status}*", inline=True)
    
    if liters_count == 0: embed.set_footer(text="Бармен ждет твоего заказа! Используй /drink")
    else: embed.set_footer(text="Чем выше статус, тем больше литров ты пьешь за раз!")

    await interaction.response.send_message(embed=embed)

# ЗАПУСК БОТА С ТОКЕНОМ ИЗ НАСТРОЕК
bot.run(os.getenv('TOKEN'))