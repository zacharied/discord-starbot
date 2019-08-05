import discord
from discord.ext import commands

import json
import os
import shutil

import logging

from typing import Union

logging.basicConfig(level=logging.INFO)

STARBOARD_MAP = {}


class StarbotClient(commands.Bot):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.settings = {}

        # Maintains the mappings between messages the bot has sent to the starboard and the
        # actual message it references.
        self.starboard_map = {}

    def run(self, settings_file, *args):
        """ Runs the bot, loading from and saving to the specified settings file. """
        self.settings_file = settings_file
        self.settings = json.load(settings_file)
        self.write_settings()
        return super().run(*args)

    def write_settings(self):
        self.settings_file.seek(0)
        self.settings_file.write(json.dumps(self.settings))
        self.settings_file.truncate()

    def write_starboard_map(self):
        with open('message_map.json', 'w+') as out:
            out.write(json.dumps(self.starboard_map))

    def set_starboard_channel(self, channel_name):
        for ch in self.get_all_channels():
            if ch.name == self.settings['channel']:
                self.starboard_channel = ch

    async def on_ready(self):
        logging.info(f'Logged in as "{self.user}".')

        # Find the starboard channel.
        self.starboard_channel = None
        self.set_starboard_channel(self.settings['channel'])
        if self.starboard_channel is None:
            raise Exception(
                f'no channel called "{self.settings["channel"]}" found')

    async def on_raw_reaction_add(self, payload):
        message: discord.Message = await self.get_channel(payload.channel_id).fetch_message(payload.message_id)
        try:
            react: discord.Reaction = next(
                iter([r for r in message.reactions if str(r.emoji) == self.settings['emote']]))
            if react.count >= self.settings['count']:
                if self.starboard_channel is None:
                    await message.channel.send("I can't find the starboard channel grrrr :angery:")
                    return

                embed = discord.Embed()
                embed.title = 'View'
                embed.url = message.jump_url
                embed.description = message.content
                embed.set_footer(
                    text=f'{self.settings["emote"]}{react.count}  | #{message.channel.name}')
                embed.set_author(name=message.author.display_name,
                                 icon_url=message.author.avatar_url)
                embed.timestamp = message.created_at

                if not message.id in self.starboard_map:
                    sent = await self.starboard_channel.send(embed=embed)
                    self.starboard_map[message.id] = sent.id
                    self.write_starboard_map()
                else:
                    await (await self.starboard_channel.fetch_message(self.starboard_map[message.id])).edit(embed=embed)
        except StopIteration:
            # This message doesn't have the react.
            pass


client = StarbotClient(command_prefix='~starbot ')


@client.command()
async def hi(ctx):
    await ctx.send('hi lol')

@client.command()
async def info(ctx):
    await ctx.send('''I am a bot made by Nekoht (https://github.com/zacharied).
You can find my code at https://github.com/zacharied/discord-starbot .
If Nekoht isn't in this server then something has gone wrong!''')

@client.command()
async def setting(ctx, *args):
    if len(args) > 0:
        if len(args) != 2:
            await ctx.send(f'**ERROR** please provide 0 or 2 arguments to `setting`.')
            return

        key = args[0]
        val = args[1]

        if key not in client.settings:
            await ctx.send(f'**ERROR** `{key}` is not a valid setting.')

        try:
            client.settings[key] = type(client.settings[key])(val)
            client.write_settings()
            await ctx.send(f'`{key}` has been set to `{val}`.')
            if key == 'channel':
                client.set_starboard_channel(client.settings[key])
        except ValueError:
            await ctx.send(f'**ERROR** unable to convert `{val}` to `{type(client.settings[key])}`.')
            return

    await ctx.send(f'Current settings: ```json\n{json.dumps(client.settings, indent=4)}```')

@client.command()
async def opinion(ctx, *args):
    if len(args) == 0:
        await ctx.send('My opinion of whomst?')
        return
    
    if not os.path.exists('opinions.json'):
        await ctx.send("I can't find the opinions file. Someone let neko know.")
        return

    if args[0][0] == '!':
        if len(args) < 2:
            await ctx.send("What should my opinion be?")
            return

        with open('opinions.json', 'r+', encoding='utf-8') as file:
            opinions = json.loads(file.read())
            
            acc = ""
            for word in args[1:]:
                acc += word + ' '
            acc = acc.strip()

            opinions[args[0][1:]] = acc
            
            file.seek(0)
            file.write(json.dumps(opinions))
            file.truncate()
            await ctx.send(f'Gotcha. My new opinion of {args[0][1:]} is "{acc}"')
            return

    with open('opinions.json', 'r', encoding='utf-8') as file:
        opinions = json.loads(file.read())
        if args[0] in opinions:
            await ctx.send(opinions[args[0]])
        else:
            await ctx.send('I have no thoughts on the matter.')

if __name__ == '__main__':
    if not os.path.exists('settings.json'):
        shutil.copyfile('settings.default.json', 'settings.json')

    with open('token.txt', 'r') as file, open('settings.json', 'r+') as settings:
        client.run(settings, file.read())
