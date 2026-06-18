import discord
from discord.ext import commands
from discord import app_commands
import sqlite3
import random
import os

class MyBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=discord.Intents.default())

    async def setup_hook(self):
        await self.tree.sync() 
        print("Слеш-команды успешно синхронизированы!")

bot = MyBot()

# --- БАЗА ДАННЫХ ---
conn = sqlite3.connect('bar.db')
cursor = conn.cursor()
# Теперь сохраняем литры в формате REAL (числа с плавающей точкой)
cursor.execute('''CREATE TABLE IF NOT EXISTS users 
                  (user_id INTEGER, guild_id INTEGER, liters REAL)''')
conn.commit()

DRINKS = [
    "🍺 Светлое нефильтрованное", "🍻 Темный ирландский стаут",
    "🍷 Бокал красного сухого", "🥃 Шот текилы с лимоном",
    "🍸 Водка со льдом", "🍹 Коктейль 'Куба Либре'",
    "🍾 Бутылку шампанского"
]

# --- КОМАНДА /DRINK ---
@bot.tree.command(name="drink", description="Выпить алкоголь")
@app_commands.checks.cooldown(1, 3600.0, key=lambda i: (i.guild_id, i.user.id))
async def drink(interaction: discord.Interaction):
    user_id = interaction.user.id
    guild_id = interaction.guild_id
    
    drink_choice = random.choice(DRINKS)
    
    # Узнаем, сколько пользователь УЖЕ выпил
    cursor.execute("SELECT liters FROM users WHERE user_id=? AND guild_id=?", (user_id, guild_id))
    result = cursor.fetchone()
    current_liters = result[0] if result is not None else 0.0
    
    # Определяем, сколько литров он выпьет СЕЙЧАС, в зависимости от его текущего статуса
    if current_liters < 5.0:
        added_liters = random.uniform(0.3, 0.5) # Новичок пьет мало
    elif current_liters < 15.0:
        added_liters = random.uniform(0.5, 1.0) # Любитель пьет больше
    elif current_liters < 30.0:
        added_liters = random.uniform(1.0, 2.0) # Завсегдатай
    else:
        added_liters = random.uniform(2.0, 4.0) # Легенда пьет литрами
        
    # Округляем до двух знаков после запятой (например, 0.45)
    added_liters = round(added_liters, 2)
    new_total = round(current_liters + added_liters, 2)
    
    # Сохраняем в базу данных
    if result is None:
        cursor.execute("INSERT INTO users VALUES (?, ?, ?)", (user_id, guild_id, new_total))
    else:
        cursor.execute("UPDATE users SET liters=? WHERE user_id=? AND guild_id=?", (new_total, user_id, guild_id))
    conn.commit()
    
    await interaction.response.send_message(f"**{interaction.user.name}** {drink_choice} выпивает залпом **{added_liters} л.**! 🥂\n*(Всего выпито: {new_total} л.)*")

@drink.error
async def drink_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.CommandOnCooldown):
        minutes = int(error.retry_after / 60)
        await interaction.response.send_message(f"🛑 Приходи через {minutes} минут.", ephemeral=True)


# --- КОМАНДА /LEADERBOARD ---
@bot.tree.command(name="leaderboard", description="Показать топ сервера")
async def leaderboard(interaction: discord.Interaction):
    # Достаем топ-10 пользователей
    cursor.execute("SELECT user_id, liters FROM users WHERE guild_id=? ORDER BY liters DESC LIMIT 10", (interaction.guild_id,))
    top_users = cursor.fetchall()
    
    if not top_users:
        await interaction.response.send_message("🍺 Будь первым, используй /drink")
        return

    embed = discord.Embed(
        title="🏆 Топ",
        description="Топ участников сервера:",
        color=discord.Color.gold()
    )

    for index, row in enumerate(top_users, 1):
        user_id = row[0]
        liters_count = row[1]
        
        if index == 1: medal = "🥇"
        elif index == 2: medal = "🥈"
        elif index == 3: medal = "🥉"
        else: medal = "🍺"
            
        # ИСПОЛЬЗУЕМ ПИНГ ПО ID <@user_id> ВМЕСТО ИМЕНИ, ЧТОБЫ ИЗБЕЖАТЬ "НЕИЗВЕСТНОГО"
        embed.add_field(
            name=f"{medal} {index} место", 
            value=f"<@{user_id}> — **{liters_count} л.**", 
            inline=False
        )
        
    await interaction.response.send_message(embed=embed)


# --- КОМАНДА /STATS ---
@bot.tree.command(name="stats", description="Посмотреть свою личную статистику")
async def stats(interaction: discord.Interaction):
    user_id = interaction.user.id
    guild_id = interaction.guild_id
    
    cursor.execute("SELECT liters FROM users WHERE user_id=? AND guild_id=?", (user_id, guild_id))
    result = cursor.fetchone()
    
    liters_count = result[0] if result is not None else 0.0
    
    embed = discord.Embed(
        title=f"📊 Барная карта: {interaction.user.name}",
        color=discord.Color.blue()
    )
    
    if interaction.user.avatar:
        embed.set_thumbnail(url=interaction.user.avatar.url)
        
    # Считаем статусы отталкиваясь от литров
    if liters_count == 0:
        status = "Трезвенник 🥱"
    elif liters_count < 5.0:
        status = "Школота 🥂"
    elif liters_count < 15.0:
        status = "Любитель тусовок 🍺"
    elif liters_count < 30.0:
        status = "Алкашня 🥃"
    else:
        status = "Легенда 👑"
        
    embed.add_field(name="Выпито алкоголя:", value=f"**{liters_count} л.**", inline=True)
    embed.add_field(name="Твой статус:", value=f"*{status}*", inline=True)
    
    if liters_count == 0:
        embed.set_footer(text="Используй /drink")
    else:
        embed.set_footer(text="Чем выше статус, тем больше литров ты пьешь за раз!")

    await interaction.response.send_message(embed=embed)


# ЗАПУСК БОТА
bot.run(os.getenv('TOKEN'))