from discord.ext import commands

from bot import Starbot
from bot import logging

class CogDb:
    def __init__(self, bot, name):
        self.bot = bot
        self.name = name 

    def __enter__(self):
        return self.bot.db_load_name(self.name)

    def __exit__(self, *args):
        self.bot.db_write_name(self.name)
    

class StarbotCog(commands.Cog):
    def __init__(self, bot: Starbot, default_config):
        self.bot = bot
        with self.cog_db() as db:
            for key in default_config:
                if key not in db or type(db[key]) is not type(default_config[key]):
                    logging.info(f'Updating "{key}" in DB to default value ("{default_config[key]}")')
                    db[key] = default_config[key]

    def cog_db(self):
        return self.bot.cog_db('cog__' + type(self).__name__)

    @property
    def cog_db_ro(self):
        return self.bot.db['cog__' + type(self).__name__]
