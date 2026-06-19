import os
import discord
from discord.ext import commands, tasks
from discord import app_commands
import random
import psycopg2

# --- ФУНКЦИЯ ПОДКЛЮЧЕНИЯ К БД ---
DATABASE_URL = os.getenv('DATABASE_URL')

def connect_to_db():
    c = psycopg2.connect(DATABASE_URL)
    c.autocommit = True
    return c, c.cursor()

# Создаем первичное подключение
conn, cursor = connect_to_db()

# Создаем таблицу
cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        user_id BIGINT,
        guild_id BIGINT,
        liters REAL,
        UNIQUE(user_id, guild_id)
    )
''')

class MyBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=discord.Intents.default())

    async def setup_hook(self):
        await self.tree.sync() 
        self.keep_db_alive.start() # Запускаем наш "Пульс" при старте бота
        print("Слеш-команды успешно синхронизированы и БД под контролем!")

    # --- ТОТ САМЫЙ "ПУЛЬС" ---
    # Каждые 3 минуты бот будет пинговать базу, чтобы она не уснула
    @tasks.loop(minutes=3.0)
    async def keep_db_alive(self):
        global conn, cursor
        try:
            cursor.execute("SELECT 1") # Пустой запрос чисто для активности
        except Exception as e:
            print("Соединение с БД потеряно. Переподключаюсь...")
            try:
                conn, cursor = connect_to_db()
                print("Успешное переподключение!")
            except Exception as reconnect_error:
                print(f"Ошибка переподключения: {reconnect_error}")

bot = MyBot()

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
    
    # Перед каждым запросом проверяем, живо ли соединение (на всякий случай)
    global conn, cursor
    if conn.closed != 0:
        conn, cursor = connect_to_db()

    cursor.execute("SELECT liters FROM users WHERE user_id = %s AND guild_id = %s", (user_id, guild_id))
    result = cursor.fetchone()
    current_liters = result[0] if result else 0.0
    
    if current_liters < 5.0: added_liters = random.uniform(0.3, 0.5)
    elif current_liters < 15.0: added_liters = random.uniform(0.5, 1.0)
    elif current_liters < 30.0: added_liters = random.uniform(1.0, 2.0)
    else: added_liters = random.uniform(2.0, 4.0)
        
    added_liters = round(added_liters, 2)
    new_total = round(current_liters + added_liters, 2)
    
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
@bot.tree.command(name="leaderboard", description="Показать список лидеров")
async def leaderboard(interaction: discord.Interaction):
    global conn, cursor
    if conn.closed != 0:
        conn, cursor = connect_to_db()

    cursor.execute("SELECT user_id, liters FROM users WHERE guild_id = %s ORDER BY liters DESC LIMIT 10", (interaction.guild_id,))
    top_users_list = cursor.fetchall()
    
    if not top_users_list:
        await interaction.response.send_message("🍺 Будь первым, используй /drink")
        return

    embed = discord.Embed(title="🏆 Топ посетителей бара", description="Самые стойкие участники нашего сервера:", color=discord.Color.gold())

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
    global conn, cursor
    if conn.closed != 0:
        conn, cursor = connect_to_db()

    cursor.execute("SELECT liters FROM users WHERE user_id = %s AND guild_id = %s", (user_id, guild_id))
    result = cursor.fetchone()
    liters_count = result[0] if result else 0.0
    
    embed = discord.Embed(title=f"📊 Барная карта: {interaction.user.name}", color=discord.Color.blue())
    if interaction.user.avatar: embed.set_thumbnail(url=interaction.user.avatar.url)
        
    if liters_count == 0: status = "Трезвенник 🥱"
    elif liters_count < 50.0: status = "Школота 🥂"
    elif liters_count < 100.0: status = "Любитель тусовок 🍺"
    elif liters_count < 200.0: status = "Алкашня 🥃"
    else: status = "Легенда 👑"
        
    embed.add_field(name="Выпито алкоголя:", value=f"**{liters_count} л.**", inline=True)
    embed.add_field(name="Твой статус:", value=f"*{status}*", inline=True)
    
    if liters_count == 0: embed.set_footer(text="Используй /drink")
    else: embed.set_footer(text="Чем выше статус, тем больше литров ты пьешь за раз!")

    await interaction.response.send_message(embed=embed)

bot.run(os.getenv('TOKEN'))