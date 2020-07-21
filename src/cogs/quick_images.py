import bot_cog

import discord
from discord.ext import commands

from cogs.react_prompt import ReactPromptPreset, react_prompt_response

logging = None

class QuickImages(bot_cog.StarbotCog):
    def __init__(self, bot, parent_logging):
        global logging
        logging = parent_logging

        super().__init__(bot, { 'collections': dict(), 'name_locks': dict() })

    def register_name(self, user, name):
        """ Maps a user's ID to a name, replacing the old mapping if it exists. """
        with self.cog_db() as db:
            if name in db['name_locks'].values():
                raise ValueError(f'name "{name}" is already locked')
            if str(user.id) in db['name_locks']:
                del db['name_locks'][str(user.id)]
            db['name_locks'][str(user.id)] = name

    def user_locked_name(self, user):
        locks = self.cog_db_ro['name_locks']
        return locks[str(user.id)] if str(user.id) in locks else None

    @commands.command()
    async def image_add_cog(self, ctx, link):
        # They wish to add an image to their locked name. 
        if self.user_locked_name(ctx.author) is None:
            await ctx.send('Please provide a name as the first argument, or lock a name first.')
            return
        
        with self.cog_db() as db:
            name = self.user_locked_name(ctx.author)
            if name not in db['collections']:
                db['collections'][name] = []
            db['collections'][name].append(link)

            await ctx.send('Added image successfully.')
    
    @commands.command()
    async def image_register_name_cog(self, ctx, name):
        logging.info(self.cog_db_ro['name_locks'])
        if str(ctx.author.id) in self.cog_db_ro['name_locks']:
            logging.info(ctx.author.id)
            # They already have locked a name, so process the change.
            if self.cog_db_ro['name_locks'][str(ctx.author.id)] == name:
                # They're trying to lock the same name that they already have.
                await ctx.send(f'You have already locked "{name}".')
                return

            # Ask if they want to overwrite.
            message = await ctx.send(f'You have already locked the name "{self.cog_db_ro["name_locks"][str(ctx.author.id)]}". Would you like to change your locked name?')
            choice = await react_prompt_response(self.bot, ctx.author, message, ReactPromptPreset.YES_NO)

            logging.info(f'User responded with: {choice}')
            if choice != 'yes':
                return
        
        try:
            self.register_name(ctx.author, name)
        except ValueError as e:
            await ctx.send('That name is already registered, so you cannot lock it.')
            return
        await ctx.send(f'You have locked the name "{name}".')
