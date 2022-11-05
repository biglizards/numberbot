#!/usr/bin/env python3
import asyncio
import operator
import os
import sqlite3
import time

import discord
from discord.ext import commands

intents = discord.Intents.default()
intents.members = True

##############################
# you need to set these things, set your own id here
counting_id = 254639193479708680
counting_log_id = 254908823926603776
binary_id = 254723002267074565
fibonacci_id = 254723032659132417
letters_id = 545727211349606410
milestone_id = 254654570276323330
error_log_id = 254962029402652672
##############################

async def binary(message):
    b = bin(int(open("numb_bin", "r").read(), 2) + 1)[2:]
    if message.content != b:
        await message.delete()
        return
    open("numb_bin", "w").write(message.content)
    await get_stats_if_required(1)


async def fib(message):
    l = open("numb_fib", "r").read().split(" ")
    c = int(l[0]) + int(l[1])  # a+b
    if message.content != str(c):
        await message.delete()
        return
    open("numb_fib", "w").write("{} {}".format(l[1], c))


letter_values = {
    'a': 1, 'b': 2, 'c': 3, 'd': 4, 'e': 5, 'f': 6, 'g': 7, 'h': 8, 'i': 9, 'j': 10, 'k': 11, 'l': 12,
    'm': 13, 'n': 14, 'o': 15, 'p': 16, 'q': 17, 'r': 18, 's': 19, 't': 20, 'u': 21, 'v': 22, 'w': 23,
    'x': 24, 'y': 25, 'z': 26,
}


def letters_to_int(word):
    try:
        t = 0
        for i, char in enumerate(reversed(word)):
            t += letter_values[char.lower()] * 26 ** i
        return t
    except AttributeError:
        return 0


async def letters(message):
    last_num = int(open("numb_letters", "r").read())
    if letters_to_int(message.content) != last_num + 1:
        await message.delete()
        return
    open("numb_letters", "w").write(str(last_num + 1))
    await get_stats_if_required(2)


class RetryLock(asyncio.Lock):
    """Lock that tells you if anyone else is waiting on it. Useful for preventing overlapping fetches"""
    def __init__(self):
        super().__init__()
        self.has_waiting = False

    async def acquire(self):
        if self.locked():
            self.has_waiting = True
        return await super().acquire()

    def release(self) -> None:
        self.has_waiting = False
        super().release()

    def should_acquire(self):
        return not self.has_waiting


real_path = os.path.dirname(os.path.realpath(__file__)) + "/"
os.chdir(real_path)

database = sqlite3.connect("stats.db")
c = database.cursor()
channel_locks = {name: RetryLock() for name in ['fib', 'letters', 'bin']}

c.execute('''CREATE TABLE IF NOT EXISTS edits
             (id int, num int)''')
c.execute('''CREATE TABLE IF NOT EXISTS milestones
             (id int, num int)''')

c.execute('''CREATE TABLE IF NOT EXISTS numbers
             (num int unique primary key on conflict ignore, user int, time datetime)''')
c.execute('''CREATE TABLE IF NOT EXISTS letters
             (num int unique primary key on conflict ignore, user int, time datetime)''')
c.execute('''CREATE TABLE IF NOT EXISTS fib
             (num int unique primary key on conflict ignore, user int, time datetime)''')
c.execute('''CREATE TABLE IF NOT EXISTS bin
             (num int unique primary key on conflict ignore, user int, time datetime)''')

bot = commands.Bot(command_prefix=';', description='no', intents=intents)


@bot.command(hidden=True)
async def get_stats():
    messages = []
    limit = c.execute('SELECT num FROM numbers ORDER BY num DESC LIMIT 1').fetchone()
    if not limit:
        limit = (0,)
    async for message in bot.get_channel(counting_id).history(limit=999999999999999):
        try:
            int_message = int(message.content)
            if int_message <= limit[0]:
                break
            messages.append((int_message, str(message.author.id), message.created_at))
        except ValueError:
            pass
    if not messages: return
    c.executemany('INSERT INTO numbers VALUES (?,?,?)', messages)
    database.commit()


@bot.command(hidden=True)
async def get_stats_again(ctx, option):
    await get_stats_if_required(option)


async def get_stats_if_required(option):
    # getting stats takes a few seconds, even for single messages
    # allowing every call would be wasteful (and spam the log)
    # but using a simple lock means if someone sends two messages quickly, we miss the second one
    # thus, we limit at most one task to be waiting on the lock
    table, channel_id, convert_to_int = \
        [('fib', fibonacci_id, int), ('bin', binary_id, lambda x: int(x, 2)), ('letters', letters_id, letters_to_int)][
            int(option)]
    lock = channel_locks[table]
    if lock.should_acquire():
        async with lock:
            await get_stats_inner(table, channel_id, convert_to_int)


async def get_stats_inner(table, channel_id, convert_to_int):
    messages = []
    last_num = int(open("numb_bin", "r").read(), 2) if table == 'bin' else int(open("numb_letters", "r").read())
    limit = c.execute('SELECT num FROM {} ORDER BY num DESC LIMIT 1'.format(table)).fetchone()
    if not limit:
        limit = (0,)
    async for message in bot.get_channel(channel_id).history(limit=999999999999999):
        try:
            int_message = convert_to_int(message.content)
            if int_message <= limit[0]:
                break
            if limit[0] < int_message <= last_num:
                messages.append((int_message, str(message.author.id), message.created_at))
        except ValueError:
            pass
    if not messages:
        return
    print(len(messages), messages[:10])
    c.executemany('INSERT INTO {} VALUES (?,?,?)'.format(table), messages)
    database.commit()


@bot.command(pass_context=True)
async def stats(context, user=None):
    if not user:
        user = str(context.message.author.id)
    else:
        user = ''.join([char for char in user if char in '1234567890'])

    stats = c.execute("SELECT num FROM numbers WHERE user=? ORDER BY num ASC", (user,)).fetchall()
    max_run = last_num = cur_run = max_num = 0
    for num in stats:
        if num[0] == last_num + 1:
            cur_run += 1
            if cur_run > max_run:
                max_run = cur_run
                max_num = num[0]
        else:
            cur_run = 0
        last_num = num[0]
    mile = c.execute("SELECT num FROM milestones WHERE id=?", (user,)).fetchone()
    if not mile:
        mile = (0,)
    last_num = c.execute('SELECT num FROM numbers ORDER BY num DESC LIMIT 1').fetchone()[0]
    perc = '%.2f' % round(len(stats) / last_num * 100, 2)
    await context.send(
        "```\nHighest streak: {} ({}-{})\nTotal counted: {}\nTotal milestones: {}\nPercentage: {}%```".format(
            max_run + 1, max_num - max_run, max_num, len(stats), mile[0], perc))

    user_ob = discord.utils.get(context.message.author.guild.members, id=int(user))
    if len(stats) > 4999:
        await user_ob.add_roles(discord.utils.get(context.message.author.guild.roles, name="Team Counters"))
    if len(stats) > 24999:
        await user_ob.add_roles(discord.utils.get(context.message.author.guild.roles, name="Team Counters+"))
    if mile[0] > 4:
        await user_ob.add_roles(discord.utils.get(context.message.author.guild.roles, name="Team Milestones"))
    if mile[0] > 24:
        await user_ob.add_roles(discord.utils.get(context.message.author.guild.roles, name="Team Milestones+"))
    if mile[0] > 99:
        await user_ob.add_roles(
            discord.utils.get(context.message.author.guild.roles, name="100 milestones are you insane"))
    if mile[0] > 499:
        await user_ob.add_roles(
            discord.utils.get(context.message.author.guild.roles, name="that is entirely too many milestones"))
    if mile[0] > 2499:
        await user_ob.add_roles(discord.utils.get(context.message.author.guild.roles, name="go home"))
    if max_run > 2000:
        await user_ob.add_roles(discord.utils.get(context.message.author.guild.roles, name="Team Streakers"))
    if max_run > 10000:
        await user_ob.add_roles(discord.utils.get(context.message.author.guild.roles, name="Team Streakers+"))


@bot.command(pass_context=True)
async def streaks(context, end=10, start=0, channel='counting'):
    t = time.time()
    """valid channels are counting, bin/binary, and letters. counting by default"""
    channel = {'counting': 'numbers', 'bin': 'bin', 'binary': 'bin', 'letters': 'letters'}[channel]

    stats = c.execute("SELECT num, user FROM {} ORDER BY num ASC".format(channel)).fetchall()
    streaks = {}
    cur_usr = cur_streak = 0

    for stat in stats:
        if stat[1] == cur_usr:
            cur_streak += 1
            if streaks.get(cur_usr, 4) < cur_streak:
                streaks[cur_usr] = cur_streak
        else:
            cur_usr = stat[1]
            cur_streak = 1

    sorted_streaks = sorted(streaks.items(), key=operator.itemgetter(1), reverse=True)
    reply = ['```']

    user_streaks = []

    for i, (uid, streak) in enumerate(sorted_streaks[start:end]):
        user = discord.utils.get(context.message.guild.members, id=int(uid))
        try:
            if not user:
                user = await bot.get_user(int(uid))
        except:
            pass

        if not user:
            reply.append(f"{i+start+1:<2}: {streak} - unknown user")
        else:
            reply.append(f"{i+start+1:<2}: {streak} - {user.name}")
            user_streaks.append((streak, user))

    reply.append('```')
    await context.send('\n'.join(reply))

    for streak, user in user_streaks:
        try:
            if streak > 2000:
                await user.add_roles(discord.utils.get(context.message.author.guild.roles, name="Team Streakers"))
            if streak > 10000:
                await user.add_roles(discord.utils.get(context.message.author.guild.roles, name="Team Streakers+"))
        except:
            pass


@bot.command(pass_context=True)
async def totals(context, end=10, start=0, channel='counting'):
    """valid channels are counting, bin/binary, and letters. counting by default"""
    channel = {'counting': 'numbers', 'bin': 'bin', 'binary': 'bin', 'letters': 'letters'}[channel]
    stats = c.execute("SELECT num, user FROM {} ORDER BY num ASC".format(channel)).fetchall()
    totals = {}
    for stat in stats:
        totals[stat[1]] = totals.get(stat[1], 0) + 1
    sorted_streaks = sorted(totals.items(), key=operator.itemgetter(1), reverse=True)
    reply = '```\n'
    for x in range(start, end):
        user = discord.utils.get(context.message.guild.members, id=int(sorted_streaks[x][0]))
        try:
            if not user:
                user = await bot.get_user(int(sorted_streaks[x][0]))
        except:
            pass
        if not user:
            reply += "\n{} - {}".format(sorted_streaks[x][1], "unknown user")
            continue
        reply += "\n{} - {}".format(sorted_streaks[x][1], user.name)
    await context.send(reply + "```")


@bot.command(pass_context=True)
async def milestones(ctx, end=10, start=0):
    mile = c.execute("SELECT id, num FROM milestones").fetchall()
    sorted_milestones = sorted(mile, key=lambda y: y[1], reverse=True)[start:end]
    reply = '```'
    for uid, num in sorted_milestones:
        user = discord.utils.get(ctx.message.guild.members, id=int(uid))
        if not user:
            user = "deleted user " + hex(uid).strip('0')
        else:
            user = user.name
        reply += '\n{} - {}'.format(num, user)
    await ctx.send(reply + "```")


@bot.command(pass_context=True)
async def current_num(ctx):
    await ctx.send("the last number i saw someone count was " + open("numb", "r").read())


@bot.event
async def on_ready():
    print('Logged in as')
    print(bot.user.name)
    print(bot.user.id)
    print('------')
    await bot.change_presence(activity=discord.Game(name="prefix is ;"))


@bot.event
async def on_message(message):
    t = time.time()
    try:
        if message.channel.id != counting_id:
            await bot.process_commands(message)
            if message.channel.id == binary_id:
                await binary(message)
            elif message.channel.id == fibonacci_id:
                await fib(message)
            elif message.channel.id == letters_id:
                await letters(message)
            return
        if message.content != str(int(open("numb", "r").read()) + 1):
            await message.delete()
            return

        c.execute("INSERT INTO numbers VALUES (?,?,?)", (message.content, message.author.id, message.created_at))
        database.commit()
        open("numb", "w").write(message.content)
        # print("partially processed message: took", time.time()-t)
        await bot.get_channel(counting_log_id).send("{} - **{}**".format(message.content, message.author.name))

        if int(message.content) % 500 == 0:
            x = c.execute("SELECT num FROM milestones WHERE id=?", (message.author.id,)).fetchone()
            if not x:
                c.execute("INSERT INTO milestones VALUES (?, ?)", (message.author.id, 0))
            c.execute("UPDATE milestones SET num = num + 1 WHERE id = ?", (message.author.id,))
            database.commit()
            await bot.get_channel(milestone_id).send(
                "We've hit {} boys! Thanks to {}!".format(message.content, message.author.mention))
        await bot.process_commands(message)
    except Exception as e:
        await message.delete()
        await bot.get_channel(error_log_id).send(e)
        raise
    # print("processed message: took", time.time()-t)


# wow i was _really_ aggressive about this 5 years ago huh
@bot.event
async def on_message_edit(before, after):
    if after.channel.id != counting_id or before.content == after.content:
        return
    await after.delete()
    x = c.execute("SELECT num FROM edits WHERE id=?", (before.author.id,)).fetchone()
    if not x:
        c.execute("INSERT INTO edits VALUES (?, ?)", (before.author.id, 1))
        database.commit()
        await before.author.send("Do ***NOT*** edit your messages in counting\nYou will be muted next time\n\n<3 Number"
                                 " bot")
    else:
        role = [x for x in before.guild.roles if x.id == 254646567359873024][
            0]  # ok idk how to do this one. feel free to delete this whole function
        await before.author.add_roles(role)
        await before.author.send("Do ***NOT*** edit your messages in counting\n**You have been muted for 24 hours, "
                                 "you will be kicked next time**\n\n<3 Number bot")


try:
    bot.run(open('token', 'r').read().strip('\n'))
except FileNotFoundError:
    print('token not found\nplease create a file called "token" and put the token in that')
