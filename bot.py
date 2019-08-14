#!/usr/bin/env python3.7

import discord
from discord.ext import commands

import json
import os, sys
import shutil
import random
from functools import reduce
import re
from enum import Enum
import argparse

import logging
from logging.handlers import RotatingFileHandler

from typing import Union

logger = logging.getLogger('root')
logger.setLevel(logging.INFO)

log_handler = RotatingFileHandler('bot.log', maxBytes=1024*1024*5, backupCount=2)
log_handler.setLevel(logging.INFO)
logger.addHandler(log_handler)

ILEE_REGEX = re.compile(r'^[i1lI\|]{2}ee(10+)?$')

GOODBOY_RESPONSES = [
    'わんわん！',
    '<:laelul:575783619503849513>'
]

class DifferentServerCheckFail(commands.CommandError):
    pass

class Db(Enum):
    MESSAGE_MAP = 'message_map'
    SETTINGS = 'settings'
    OPINIONS = 'opinions'
    QUICK_IMAGES = 'quickimages'
    NAME_LOCKS = 'name_locks'

class Starbot(commands.Bot):
    def __init__(self, *args, **kwargs):
        super().__init__(command_prefix='&', *args, **kwargs)

        self.last_message = None

        self.guild = None
        self.guild_id = None
    
    def run(self, guild_id, *args, **kwargs):
        self.guild_id = guild_id
        self.db = {}
        for d in Db:
            self.db_load(d)
        return super().run(*args, **kwargs)

    async def update_starboard_message(self, message: discord.Message):
        """ Updates or creates a post on the starboard corresponding to a message. """
        # Find the react object corresponding to the starboard emote.
        try:
            react: discord.Reaction = next(filter(lambda r: str(r.emoji) == self.db[Db.SETTINGS]['starboard']['emoji'], message.reactions))
        except StopIteration:
            react = None

        # Locate the channel to post to.
        try:
            starboard_channel = next(filter(lambda c: c.name == self.db[Db.SETTINGS]['starboard']['channel'], self.guild.channels))
        except StopIteration:
            logging.error(f'Starboard channel "{self.db[Db.SETTINGS]["starboard"]["channel"]}" not found.')
            return
     
        message_key = str(message.id)

        logging.debug(f'Processing starboard react for message {message.id}.')
        if react is not None and react.count >= self.db[Db.SETTINGS]['starboard']['threshold']:
            # Put a new message on the starboard or edit an old one.
            logging.debug(f'React above thereshold ({react.count} >= {self.db[Db.SETTINGS]["starboard"]["threshold"]}).')

            # Set up the embed.
            embed = discord.Embed()
            embed.description = f'**[Jump]({message.jump_url})**\n{message.content}'
            embed.set_footer(text=f'{self.db[Db.SETTINGS]["starboard"]["emoji"]}{react.count}  | #{message.channel.name}')
            embed.set_author(name=message.author.display_name,
                                icon_url=message.author.avatar_url)
            embed.timestamp = message.created_at
            
            # Add image to embed if the message was one.
            for attachment in message.attachments:
                if attachment.height is not None:
                    embed.set_image(url=attachment.url)
            
            if message_key not in self.db[Db.MESSAGE_MAP]:
                logging.debug('Message has not yet been posted to starboard; sending it!')

                sent = await starboard_channel.send(embed=embed)
                self.db[Db.MESSAGE_MAP][message_key] = sent.id

                logging.debug(f'Message has been posted to the starboard with ID {sent.id}.')
            else:
                logging.debug(f'Message already exists on starboard with ID {self.db[Db.MESSAGE_MAP][message_key]}; editing it.')

                starboard_message = await starboard_channel.fetch_message(self.db[Db.MESSAGE_MAP][message_key])
                await starboard_message.edit(embed=embed)
        elif message_key in self.db[Db.MESSAGE_MAP]:
            logging.debug('Reacts fell below threshold. Removing message from starboard.')
            # Message fell below the thereshold.
            starboard_message = await starboard_channel.fetch_message(self.db[Db.MESSAGE_MAP][message_key])
            await starboard_message.delete()

            del self.db[Db.MESSAGE_MAP][message_key]

        self.db_write(Db.MESSAGE_MAP)

        logging.debug(f'Done processing react for message {message.id}.')
    
    async def on_ready(self):
        self.guild: discord.Guild = self.get_guild(self.guild_id)
        logging.info(f'Logged in as "{self.user}".')

    async def on_reaction(self, payload):
        if payload.guild_id != self.guild_id:
            return
        message = await self.guild.get_channel(payload.channel_id).fetch_message(payload.message_id)
        await self.update_starboard_message(message)

    async def on_raw_reaction_add(self, payload):
        await self.on_reaction(payload)
    async def on_raw_reaction_remove(self, payload):
        await self.on_reaction(payload)
    async def on_raw_reaction_clear(self, payload):
        await self.on_reaction(payload)

    async def on_command_error(self, ctx, error):
        if type(error) is DifferentServerCheckFail:
            return
        return await super().on_command_error(ctx, error)
    
    def db_load(self, db_file):
        path = f'local/{self.guild_id}/{db_file.value}.json'
        if not os.path.exists(path):
            self.db[db_file] = {}
        else:
            with open(path, 'r', encoding='utf-8') as file:
                self.db[db_file] = json.load(file)
    
    def db_write(self, db_file):
        path = f'local/{self.guild_id}/{db_file.value}.json'
        with open(path, 'w+', encoding='utf-8') as file:
            logging.info(f'Writing to "{path}".')
            json.dump(self.db[db_file], file)
    
bot = Starbot()

@bot.check
def check_guild(ctx):
    if ctx.message.guild.id != bot.guild_id:
        raise DifferentServerCheckFail()
    return True

@bot.command()
async def delete_starred(ctx, message_id):
    try:
        starboard_channel = next(filter(lambda c: c.name == bot.db[Db.SETTINGS]['starboard']['channel'], bot.guild.channels))
    except StopIteration:
        logging.error(f'Starboard channel "{bot.db[Db.SETTINGS]["starboard"]["channel"]}" not found.')
        return

    starboard_message = await starboard_channel.fetch_message(int(message_id))
    await starboard_message.delete()

    new_map = {}
    for k in bot.message_map:
        if bot.message_map[k] != int(message_id):
            new_map[k] = bot.message_map[k] 
    bot.message_map = new_map

    bot.db_write(Db.MESSAGE_MAP)

@bot.command()
async def hi(ctx):
    await ctx.send('hi lol')

@bot.command(aliases=['gb', 'pet'])
async def goodboy(ctx):
    await ctx.send(random.choice(GOODBOY_RESPONSES))

@bot.command(aliases=['o'])
async def opinion(ctx, name, *args):
    """
    Get or set my opinion about a name. Prefixing the opinion with `!`
    will cause me to set my opinion of the name to whatever comes after
    the name.
    """
    name = name.lower()

    if ILEE_REGEX.match(name):
        name = 'ilee'
    
    if name[0] == '!':
        # We are setting an opinion.
        name = name[1:]

        logging.debug(f'Setting opinion for "{name}".')

        if len(args) == 0:
            await ctx.send('You did not provide an opinion.')
            return
        
        acc = ''
        for arg in args:
            acc += arg + ' '
        bot.db[Db.OPINIONS][name] = acc.strip()

        await ctx.send(f'Gotcha, my new opinion of {name} is "{acc}".')

        logging.debug(f'Opinion for "{name}" set to "{acc}"')

        bot.db_write(Db.OPINIONS)

        return

    # Otherwise we are getting.
    logging.debug(f'Getting opinion for "{name}".')

    if name == 'ilee':
        await ctx.send('bad boy') 
        return

    if name not in bot.db[Db.OPINIONS]:
        logging.debug(f'Opinion for "{name}" not found.')
        await ctx.send(f'I have no thoughts on {name}')
        return

    await ctx.send(bot.db[Db.OPINIONS][name])

@bot.command(aliases=['ilock'])
async def image_name_lock(ctx, name):
    """
    Lock a name to your Discord account. Images can only be added to a locked
    name by the user that locked it. You can only have one locked name at a
    time.
    """
    name = name.lower()

    if name in bot.db[Db.NAME_LOCKS]:
        if bot.db[Db.NAME_LOCKS][name] == ctx.author.id:
            await ctx.send('You already own that name!')
        else:
            await ctx.send(f'"{name}" is already owned by someone else.')
        return

    for k, v in bot.db[Db.NAME_LOCKS].items():
        if v == ctx.author.id:
            await ctx.send(f'Relinquished ownership of the name "{k}".')
            del bot.db[Db.NAME_LOCKS][k]
            break
    
    bot.db[Db.NAME_LOCKS][name] = ctx.author.id
    bot.db_write(Db.NAME_LOCKS)
    await ctx.send(f'You now have ownership of "{name}". Enjoy!')

@bot.command(aliases=['ia'])
async def image_add(ctx, name):
    """
    Add an image for a name. Calling `image_get` with the same name will
    retrieve a random image that has been added through here.
    """
    name = name.lower()

    if len(ctx.message.attachments) > 0:
        url = ctx.message.attachments[0].url
    else:
        await ctx.send('Attach an image for me to save it.')
        return

    if name in bot.db[Db.NAME_LOCKS] and bot.db[Db.NAME_LOCKS][name] != ctx.author.id:
        await ctx.send('You are not the owner of that name, so you cannot add images to it.')
        return

    logging.debug(f'Adding image "{url}" to quickimages of {name}.')

    if name not in bot.db[Db.QUICK_IMAGES]:
        bot.db[Db.QUICK_IMAGES][name] = []
    
    bot.db[Db.QUICK_IMAGES][name].append(url)

    await ctx.send(f'Added. {name} now has {len(bot.db[Db.QUICK_IMAGES][name])} images.')

    bot.db_write(bot.db[Db.QUICK_IMAGES])

@bot.command(aliases=['ig'])
async def image_get(ctx, *args):
    """
    Retrieve a random image that has been registered to a name through
    `image_add`.
    """
    if len(args) < 1:
        try:
            name = next(iter([k for k, v in bot.db[Db.NAME_LOCKS].items() if v == ctx.author.id]))
        except StopIteration:
            await ctx.send('To call `image_get` with no name, you have to register your name with `image_name_lock` first!') 
            return
    else:
        name = args[0].lower()
    
    if len(args) > 1:
        await ctx.send('Too many arguments!')

    if name not in bot.db[Db.QUICK_IMAGES]:
        await ctx.send(f'I have no images for {name}. Please register some with `&ia`')
        return
    
    index = random.randint(0, len(bot.db[Db.QUICK_IMAGES][name]) - 1)
    basename = bot.db[Db.QUICK_IMAGES][name][index].split('/')[-1]
    image_text = f'|| {bot.db[Db.QUICK_IMAGES][name][index]} ||' if basename.startswith('SPOILER_') else bot.db[Db.QUICK_IMAGES][name][index]
    await ctx.send(content=f'[{index+1}/{len(bot.db[Db.QUICK_IMAGES][name])}] {image_text}')

@bot.command(aliases=['ir'])
async def image_remove(ctx, name, index):
    """
    Remove an image from the rotation associated with a name. Use
    the index given by `image_get` as an argument.
    """
    name = name.lower()

    if name not in bot.db[Db.QUICK_IMAGES]:
        await ctx.send('There are no images to remove.')
        return

    if name in bot.db[Db.NAME_LOCKS] and bot.db[Db.NAME_LOCKS][name] != ctx.author.id:
        await ctx.send('You are not the owner of that name, so you cannot remove images from it.')
        return

    try:
        index = int(index) - 1
    except TypeError:
        await ctx.send('Please enter an integer index.')
        return

    if index >= len(bot.db[Db.QUICK_IMAGES][name]):
        await ctx.send('Invalid index.')
        return

    del bot.db[Db.QUICK_IMAGES][name][index]

    bot.db_write(Db.QUICK_IMAGES)

    await ctx.send(f'Deleted. {name} now has {len(bot.db[Db.QUICK_IMAGES][name])} images.')

@bot.command(aliases=['id'])
async def image_dump(ctx, name):
    """
    Print out a list of images for a name along with their indices.
    """
    name = name.lower()

    if name not in bot.db[Db.QUICK_IMAGES]:
        await ctx.send('There are no images to dump.')
        return

    text = f'```\nName: {name}\n=====================\n'
    
    for i, image in enumerate(bot.db[Db.QUICK_IMAGES][name]):
        line = f' {i+1:>3} {image}\n'
        if len(text) >= 2000 - len(line) - len('```'):
            await ctx.send(text + '```')
            text = '```\n'
        text += line
    
    if len(text.strip()) > 0:
        await ctx.send(text.strip() + '```')

@bot.command(aliases=['s'])
async def setting(ctx, *args):
    if len(args) == 0:
        # Just print the settings.
        await ctx.send(f'My current settings are:\n```json\n{json.dumps(bot.db[Db.SETTINGS], indent=4)}\n```')
        return
    
    # Otherwise set one.
    if len(args) != 2:
        await ctx.send(f'This takes two arguments; you gave me {len(args)}.' )
        return
    
    # Descend into the settings object by each `.` in the argument.
    splitter = args[0].split('.')
    settings_domain = bot.db[Db.SETTINGS]
    while len(splitter) > 1:
        settings_domain = settings_domain[splitter[0]]
        splitter = splitter[1:]

    if splitter[0] not in settings_domain:
        await ctx.send(f'I do not have a setting called "{args[0]}".')
        return

    try:
        cur_type = type(settings_domain[splitter[0]])
        settings_domain[splitter[0]] = (cur_type)(args[-1])
        await ctx.send(f'Done! `{args[0]}` has been set to `{args[-1]}`.')
    except TypeError:
        await ctx.send(f'I was unable to convert "{args[-1]}" to the right type.')
        return
    
    bot.db_write(Db.SETTINGS)

if not os.path.exists('servers.json'):
    print('Servers file not found. Please make a file called `severs.json` and put the server names as keys and their IDs as values.', file=sys.stderr)
    sys.exit(1)

if not os.path.exists('token.txt'):
    print('Token file not found. Place your Discord token ID in a file called `token.txt`.', file=sys.stderr)
    sys.exit(1)

with open('token.txt', 'r') as token_file, open('servers.json', 'r') as servers_file:
    servers = json.load(servers_file)
    if sys.argv[1] not in servers:
        print(f'Server "{sys.argv[1]}" not found. Aborting.', file=sys.stderr)
        sys.exit(1)

    bot.run(int(servers[sys.argv[1]]), token_file.read())
