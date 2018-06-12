#!/bin/python3

"""

Copyright (C) 2018 MonaIzquierda (mona.izquierda@gmail.com)

This file is part of PraxisBot.

PraxisBot is free software: you can redistribute it and/or  modify
it under the terms of the GNU Affero General Public License, version 3,
as published by the Free Software Foundation.

PraxisBot is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License
along with TeeUniverse.  If not, see <http://www.gnu.org/licenses/>.

"""

import discord
import sys
import traceback

from context import Context
from plugin import UserPermission
from plugins.core import CorePlugin
from plugins.trigger import TriggerPlugin

########################################################################
# Init

if len(sys.argv) < 2:
	print("Usage: "+sys.argv[0]+" <DISCORD_TOKEN>")
	exit(0)

botToken = sys.argv[1]

########################################################################
# Bot

class PraxisBot(discord.Client):
	"""
	The main class of PraxisBot
	"""
	
	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		
		self.ctx = None
		self.plugins = []
	
	def load_plugin(self, plugin):
		"""
		Create an instance of a plugin and register it
		"""
		try:
			instance = plugin(self.ctx)
			self.plugins.append(instance)
			self.ctx.log("Plugin {0} loaded".format(plugin.name))
		except:
			self.ctx.log("Plugin {0} can't be loaded".format(plugin.name))
	
	def load_all_plugins(self):
		self.load_plugin(CorePlugin)
		self.load_plugin(TriggerPlugin)
	
	async def execute_command(self, command, options, server, channel, author, perm, level):
		if level > 8:
			return
		
		try:
			for p in self.plugins:
				res = await p.execute_command(self, command, options, server, channel, author, perm, level)
				if res == True:
					break
		
		except:
			print(traceback.format_exc())
			pass
	
	async def on_ready(self):
		self.ctx = Context(self, "testing")
		
		self.ctx.log("Logged on as {0}".format(self.user))
		
		self.load_all_plugins()
	
	async def on_message(self, message):
		if not self.ctx:
			return
		
		if message.channel.is_private:
			return
		if message.author.__class__ != discord.Member:
			return
		
		prefix = self.ctx.get_command_prefix(message.server)
		
		if message.content.find(self.user.mention+" ") == 0:
			command = message.content[len(self.user.mention+" "):]
		elif prefix and message.content.find(prefix) == 0:
			command = message.content[len(prefix):]
		else:
			return
		
		args = command.split(" ");
		
		perm = UserPermission.Member
		if message.author.server_permissions.administrator:
			perm = UserPermission.Admin
		
		await self.execute_command(args[0], " ".join(args[1:]), message.server, message.channel, message.author, perm, 0)
	
	async def on_member_join(self, member):
		try:
			for p in self.plugins:
				await p.on_member_join(self, member)
		
		except:
			print(traceback.format_exc())
			pass
	
	async def on_member_remove(self, member):
		try:
			for p in self.plugins:
				await p.on_member_leave(self, member)
		
		except:
			print(traceback.format_exc())
			pass
	
	async def on_ban(self, member):
		try:
			for p in self.plugins:
				await p.on_ban(self, member)
		
		except:
			print(traceback.format_exc())
			pass
	
	async def on_unban(self, server, user):
		try:
			for p in self.plugins:
				await p.on_unban(self, server, user)
		
		except:
			print(traceback.format_exc())
			pass
		
	
########################################################################
# Execute

bot = PraxisBot()
bot.run(botToken)
