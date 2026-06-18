import os
import discord
from discord.ext import commands
from discord import app_commands
import random
import psycopg2

class MyBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=discord.Intents.default())

    async def setup_hook(self):
        await self.tree.sync() 
        print("Слеш-команды успешно синхронизированы!")

bot = MyBot()

# --- БАЗА ДАННЫХ POSTGRESQL (NEON) ---
# Получаем ссылку на базу данных из настроек хостинга
DATABASE_URL = os.getenv('DATABASE_URL')

# Подключаемся к облачной БД
conn = psycopg2.connect(DATABASE_URL)
conn.autocommit = True # Автоматическое сохранение изменений
cursor = conn.cursor()

# Создаем таблицу users (BIGINT нужен, так как ID в дискорде очень длинные)
cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        user_id BIGINT,
        guild_id BIGINT,
        liters REAL,
        UNIQUE(user_id, guild_id)
    )
''')

DRINKS = [
    "🍺 Светлое нефильтрованное", "🍻 Темный ирландский стаут",
    "🍷 Бокал красного сухого", "🥃 Шот текилы с лимоном",
    "🍸 Водка со льдом", "🍹 Коктейль 'Куба Либре'",
    "🍾 Бутылку шампанского"
]

# --- КОМАНДА /DRINK ---
@bot.tree.command(name="drink", description="Выпить алкоголь в баре")
# Кулдаун временно отключен для тестов. Чтобы включить, убери решетку ниже:
@app_commands.checks.cooldown(1, 3600.0, key=lambda i: (i.guild_id, i.user.id))
async def drink(interaction: discord.Interaction):
    user_id = interaction.user.id
    guild_id = interaction.guild_id
    
    drink_choice = random.choice(DRINKS)
    
    # Ищем пользователя в PostgreSQL (используем %s вместо ?)
    cursor.execute("SELECT liters FROM users WHERE user_id = %s AND guild_id = %s", (user_id, guild_id))
    result = cursor.fetchone()
    current_liters = result[0] if result else 0.0
    
    if current_liters < 5.0: added_liters = random.uniform(0.3, 0.5)
    elif current_liters < 15.0: added_liters = random.uniform(0.5, 1.0)
    elif current_liters < 30.0: added_liters = random.uniform(1.0, 2.0)
    else: added_liters = random.uniform(2.0, 4.0)
        
    added_liters = round(added_liters, 2)
    new_total = round(current_liters + added_liters, 2)
    
    # Обновляем или добавляем данные
    if result is None:
        cursor.execute("INSERT INTO users (user_id, guild_id, liters) VALUES (%s, %s, %s)", (user_id, guild_id, new_total))
    else:
        cursor.execute("UPDATE users SET liters = %s WHERE user_id = %s AND guild_id = %s", (new_total, user_id, guild_id))
    
    await interaction.response.send_message(f"**{interaction.user.name}** {drink_choice} выпивает залпом **{added_liters} л.**! 🥂\n*(Всего выпито: {new_total} л.)*")

@drink.error
async def drink_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.CommandOnCooldown):
        minutes = int(error.retry_after / 60)
        await interaction.response.send_message(f"🛑 Приходи через {minutes} минут.", ephemeral=True)

# --- КОМАНДА /LEADERBOARD ---
@bot.tree.command(name="leaderboard", description="Показать список лидеров сервера")
async def leaderboard(interaction: discord.Interaction):
    cursor.execute("SELECT user_id, liters FROM users WHERE guild_id = %s ORDER BY liters DESC LIMIT 10", (interaction.guild_id,))
    top_users_list = cursor.fetchall()
    
    if not top_users_list:
        await interaction.response.send_message("🍺Будь первым, используй /drink")
        return

    embed = discord.Embed(title="🏆 Топ", description="Самые стойкие участники нашего сервера:", color=discord.Color.gold())

    for index, (uid, liters_count) in enumerate(top_users_list, 1):
        if index == 1: medal = "🥇"
        elif index == 2: medal = "🥈"
        elif index == 3: medal = "🥉"
        else: medal = "🍺"
            
        embed.add_field(name=f"{medal} {index} место", value=f"<@{uid}> — **{liters_count} л.**", inline=False)
        
    await interaction.response.send_message(embed=embed)

# --- КОМАНДА /STATS ---
@bot.tree.command(name="stats", description="Посмотреть свою личную статистику")
async def stats(interaction: discord.Interaction):
    user_id = interaction.user.id
    guild_id = interaction.guild_id
    
    cursor.execute("SELECT liters FROM users WHERE user_id = %s AND guild_id = %s", (user_id, guild_id))
    result = cursor.fetchone()
    liters_count = result[0] if result else 0.0
    
    embed = discord.Embed(title=f"📊 Барная карта: {interaction.user.name}", color=discord.Color.blue())
    if interaction.user.avatar: embed.set_thumbnail(url=interaction.user.avatar.url)
        
    if liters_count == 0: status = "Трезвенник 🥱"
    elif liters_count < 5.0: status = "Школота 🥂"
    elif liters_count < 15.0: status = "Любитель тусовок 🍺"
    elif liters_count < 30.0: status = "Алкашня 🥃"
    else: status = "Легенда 👑"
        
    embed.add_field(name="Выпито алкоголя:", value=f"**{liters_count} л.**", inline=True)
    embed.add_field(name="Твой статус:", value=f"*{status}*", inline=True)
    
    if liters_count == 0: embed.set_footer(text="Бармен ждет твоего заказа! Используй /drink")
    else: embed.set_footer(text="Чем выше статус, тем больше литров ты пьешь за раз!")

    await interaction.response.send_message(embed=embed)

# ЗАПУСК БОТА С ТОКЕНОМ ИЗ НАСТРОЕК
bot.run(os.getenv('TOKEN'))