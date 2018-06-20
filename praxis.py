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
along with PraxisBot.  If not, see <http://www.gnu.org/licenses/>.

"""

import discord
import sys
import io
import traceback
import time
import asyncio

from context import Context
from scope import UserPermission
from scope import ExecutionScope
from plugins.core import CorePlugin
from plugins.trigger import TriggerPlugin
from plugins.board import BoardPlugin
from plugins.archive import ArchivePlugin
from plugins.moderation import ModerationPlugin
from plugins.http import HTTPPlugin
from plugins.poll import PollPlugin

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
		self.loopstarted = False

	def load_plugin(self, plugin):
		"""
		Create an instance of a plugin and register it
		"""
		try:
			instance = plugin(self.ctx, self)
			self.plugins.append(instance)
			self.ctx.log("Plugin {0} loaded".format(plugin.name))
		except:
			print(traceback.format_exc())
			self.ctx.log("Plugin {0} can't be loaded".format(plugin.name))

	def load_all_plugins(self):
		self.load_plugin(CorePlugin)
		self.load_plugin(TriggerPlugin)
		self.load_plugin(BoardPlugin)
		self.load_plugin(ArchivePlugin)
		self.load_plugin(ModerationPlugin)
		self.load_plugin(HTTPPlugin)
		self.load_plugin(PollPlugin)

	async def execute_command(self, command, options, scope):
		if scope.level > 8:
			return scope

		try:
			for p in self.plugins:
				i = scope.iter
				scope = await p.execute_command(self, command, options, scope)
				if scope.iter != i:
					return scope

			await self.ctx.send_message(scope.channel, "Command not found:\n`"+command+options+"`")

		except Exception as exception:
			print(traceback.format_exc())
			await self.ctx.send_message(scope.channel, "PraxisBot Internal Error ("+type(exception).__name__+"):\n`"+command+options+"`")
			scope.abort = True
			pass

		return scope

	async def on_ready(self):
		self.ctx = Context(self, "testing")

		self.ctx.log("Logged on as {0}".format(self.user))

		self.load_all_plugins()

		if not self.loopstarted:
			self.loopstarted = True
			prevTime = time.time()
			while True:
				currTime = time.time()
				sleepDuration = 5 - (currTime - prevTime)
				prevTime = currTime
				if sleepDuration > 0:
					await asyncio.sleep(sleepDuration)

				for p in self.plugins:
					await p.on_loop(self)


	def add_global_variables_in_scope(self, scope):
		newScope = scope

		with self.ctx.dbcon:
			c = self.ctx.dbcon.cursor()
			for row in c.execute("SELECT name, value FROM "+self.ctx.dbprefix+"variables WHERE discord_sid = ?", [int(scope.server.id)]):
				newScope.vars[row[0]] = row[1]

		return newScope

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

		lines = command.split("\n");
		args = lines[0].split(" ")

		if args[0] == "help":
			cmdlist = ["help"]
			for p in self.plugins:
				cmdlist = cmdlist + await p.list_commands(message.server)
			cmdlist = sorted(cmdlist)
			await self.ctx.send_message(message.channel, "Command list: "+", ".join(cmdlist)+".")

		elif args[0] == "dump":
			text = []
			for p in self.plugins:
				text = text + await p.dump(message.server)

			f = io.BytesIO(("\n----------------------\n".join(text)).encode('UTF-8'))
			await self.ctx.client.send_file(message.channel, f, filename="commands.txt", content=str(len(text))+" commands generated.")
			f.close()

		else:
			scope = ExecutionScope()
			scope.server = message.server
			scope.channel = message.channel
			scope.user = message.author
			if message.author.id == message.server.owner.id:
				scope.permission = UserPermission.Owner
			elif message.author.server_permissions.administrator:
				scope.permission = UserPermission.Admin

			scope = self.add_global_variables_in_scope(scope)

			scope = await self.execute_command(args[0], command[len(args[0]):], scope)
			if scope.deletecmd:
				await self.ctx.client.delete_message(message)

	async def on_member_join(self, member):
		try:
			scope = ExecutionScope()
			scope.server = member.server
			scope.channel = self.ctx.get_default_channel(member.server)
			scope.user = member
			scope.permission = UserPermission.Script
			scope = self.add_global_variables_in_scope(scope)

			for p in self.plugins:
				await p.on_member_join(self, scope)

		except:
			print(traceback.format_exc())
			pass

	async def on_member_remove(self, member):
		try:
			scope = ExecutionScope()
			scope.server = member.server
			scope.channel = self.ctx.get_default_channel(member.server)
			scope.user = member
			scope.permission = UserPermission.Script
			scope = self.add_global_variables_in_scope(scope)

			for p in self.plugins:
				await p.on_member_leave(self, scope)

		except:
			print(traceback.format_exc())
			pass

	async def on_member_ban(self, member):
		try:
			scope = ExecutionScope()
			scope.server = member.server
			scope.channel = self.ctx.get_default_channel(member.server)
			scope.user = member
			scope.permission = UserPermission.Script
			scope = self.add_global_variables_in_scope(scope)

			for p in self.plugins:
				await p.on_ban(self, scope)

		except:
			print(traceback.format_exc())
			pass

	async def on_member_unban(self, server, user):
		try:
			scope = ExecutionScope()
			scope.server = server
			scope.channel = self.ctx.get_default_channel(server)
			scope.user = user
			scope.permission = UserPermission.Script
			scope = self.add_global_variables_in_scope(scope)

			for p in self.plugins:
				await p.on_unban(self, scope)

		except:
			print(traceback.format_exc())
			pass


########################################################################
# Execute

bot = PraxisBot()
bot.run(botToken)
