# Module for periodically awarding points to users in the voice chat.
#
# On a specified interval, the cog will gather a list of all the users in a 
#  voice channel. The cog will then add a point to the user's `score` and update
#  their `last_gained` field to the current datetime. After increasing the points,
#  the bot will output a message containing a table with all users who have gained
#  points. Users with a `last_gained` past a certain deadline will not be shown; this
#  is to keep the list clean.

import asyncio

import discord
from discord.ext import commands

from datetime import datetime, timedelta
from dataclasses import dataclass

import discord.abc

import bot_cog

BURY_RESEND_THRESHOLD = 3

LEAVE_SCOREBOARD_TIME = timedelta(minutes=2)

logging = None

async def run_on_interval(interval, func):
    import time
    while True:
        await func()
        await asyncio.sleep(interval)

@dataclass
class UserPointsInfo:
    last_gained: datetime
    score: int

    def json_vars(self):
        return {
            'last_gained': str(self.last_gained),
            'score': self.score
        }
        
class PointsTracker(bot_cog.StarbotCog):
    bury_count: int = 0
    is_hibernating: bool = True

    def __init__(self, bot, parent_logging):
        global logging
        logging = parent_logging

        super().__init__(bot, { 'members': dict(), 'scoreboard_message_id': None })
        self.launch_loop()

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.channel.name == self.bot.settings['points_tracker']['channel'] and message.author != self.bot.user:
            self.bury_count += 1

    @property
    def output_channel(self):
        try:
            output_channel = next(filter(lambda c: c.name == self.bot.settings['points_tracker']['channel'], self.bot.guild.channels))
            return output_channel
        except StopIteration:
            logging.warning('Unable to find output channel for points message.')
            return None

    def scoreboard_message(self, present_users):
        """ Generate the contents of the scoreboard message. """
        message = 'Points have been awarded to those in the voice chat!\n'
        message += '```\n'
        message += f'{"User":>40} | Score\n'
        message += f"{''.join(['-' for i in range(len('User'))]):>40}---{''.join(['-' for i in range(len('Score'))])}\n"

        for member_id, score_info in self.cog_db_ro['members'].items():
            last_gained = datetime.fromisoformat(score_info['last_gained'])
            print(datetime.utcnow() - last_gained)
            if datetime.utcnow() - last_gained > LEAVE_SCOREBOARD_TIME:
                continue

            member = self.bot.get_user(int(member_id))
            if member is None:
                logging.warn(f'user {member_id} not found')
                continue
            message += f'{member.display_name:>40} | {score_info["score"]}'
            
            if int(member_id) in map(lambda m: m.id, present_users):
                message += ' (+)'

            message += '\n'

        message += '```'
        return message

    async def handle_points(self):
        logging.info('Checking for VC users to give points to')
        members = []
        for vc in self.bot.guild.voice_channels:
            for member in vc.members:
                members.append(member)

        if len(members) == 0:
            if self.is_hibernating is False:
                await self.output_channel.send("Everyone left voice chat. I'll stop updating the scoreboard.")
                self.is_hibernating = True
            return

        # Emerge from hibernation if we were in it.
        self.is_hibernating = False

        with self.cog_db() as db:
            for member in members:
                if str(member.id) not in db['members']:
                    logging.info(f'Adding user {member.id} to scoreboard')
                    db['members'][str(member.id)] = UserPointsInfo(datetime.utcnow(), 0).json_vars()
                db['members'][str(member.id)]['score'] += 1
                db['members'][str(member.id)]['last_gained'] = str(datetime.utcnow())

        if self.output_channel is not None:
            with self.cog_db() as db:
                if db['scoreboard_message_id'] is None or (db['scoreboard_message_id'] is not None and self.bury_count >= BURY_RESEND_THRESHOLD):
                    if db['scoreboard_message_id'] is not None:
                        old_message = await self.output_channel.fetch_message(db['scoreboard_message_id'])
                        await old_message.delete()
                    message = await self.output_channel.send(self.scoreboard_message(members))
                    db['scoreboard_message_id'] = message.id
                    self.bury_count = 0
                else:
                    message = await self.output_channel.fetch_message(db['scoreboard_message_id'])
                    await message.edit(content=self.scoreboard_message(members))

    def launch_loop(self):
        asyncio.create_task(run_on_interval(180, self.handle_points))
