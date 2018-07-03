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
import re
import traceback
import time
import asyncio
import inspect
import datetime
from pytz import timezone
import sqlite3
import praxisbot
from plugins.core import CorePlugin
from plugins.trigger import TriggerPlugin
from plugins.moderation import ModerationPlugin
from plugins.board import BoardPlugin
from plugins.archive import ArchivePlugin
from plugins.poll import PollPlugin
from plugins.emoji import EmojiPlugin
from plugins.http import HTTPPlugin

########################################################################
# Init

if len(sys.argv) < 4:
	print("Usage: "+sys.argv[0]+" <BOT_TOKEN> <HUMAN_EMAIL> <HUMAN_PASSWORD>")
	exit(0)

botToken = sys.argv[1]
humanEmail = sys.argv[2]
humanPassword = sys.argv[3]

########################################################################
# Human

class PraxisHuman(discord.Client):
	"""
	The main class of PraxisHuman
	"""

	async def on_ready(self):
		print("Human logged on as {0}".format(self.user))


########################################################################
# Bot

class PraxisBot(discord.Client):
	"""
	The main class of PraxisBot
	"""

	def __init__(self, client_human):
		super().__init__()

		self.mode = "testing"
		self.dbprefix = "pb_"
		self.dbcon = sqlite3.connect("databases/praxisbot-"+self.mode+".db", detect_types=sqlite3.PARSE_DECLTYPES|sqlite3.PARSE_COLNAMES)
		self.banned_members = {}

		with self.dbcon:
			#Server list
			self.dbcon.execute("CREATE TABLE IF NOT EXISTS "+self.dbprefix+"servers(discord_sid INTEGER PRIMARY KEY, command_prefix TEXT)");

		self.shell = praxisbot.Shell(self, client_human, self.dbprefix, self.dbcon)

		self.loopstarted = False

	def load_all_plugins(self):
		self.shell.load_plugin(CorePlugin)
		self.shell.load_plugin(TriggerPlugin)
		self.shell.load_plugin(ModerationPlugin)
		self.shell.load_plugin(BoardPlugin)
		self.shell.load_plugin(ArchivePlugin)
		self.shell.load_plugin(PollPlugin)
		self.shell.load_plugin(EmojiPlugin)
		self.shell.load_plugin(HTTPPlugin)

	async def on_ready(self):
		print("Bot logged on as {0}".format(self.user))

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

				for p in self.shell.plugins:
					for s in self.servers:
						scope = self.shell.create_scope(s, [""])
						scope.channel = self.shell.get_default_channel(s)
						scope.user = s.me
						scope.permission = praxisbot.UserPermission.Script

						await p.on_loop(scope)

	async def on_message(self, message):
		if message.channel.is_private:
			return
		if message.author.__class__ != discord.Member:
			return
		if message.author.bot:
			return

		prefixes = [self.user.mention+" "]

		customCommandPrefix = self.shell.get_sql_data("servers", ["command_prefix"], {"discord_sid": int(message.server.id)})
		if customCommandPrefix:
			prefixes.append(customCommandPrefix[0])

		scope = self.shell.create_scope(message.server, prefixes)
		scope.channel = message.channel
		scope.user = message.author
		if message.author.id == message.server.owner.id:
			scope.permission = praxisbot.UserPermission.Owner
		elif message.author.server_permissions.administrator:
			scope.permission = praxisbot.UserPermission.Admin

		if await self.shell.execute_command(scope, message.content):
			if scope.deletecmd:
				try:
					await self.shell.client.delete_message(message)
				except:
					pass


	async def on_member_join(self, member):
		try:
			scope = self.shell.create_scope(member.server, [""])
			scope.channel = self.shell.get_default_channel(member.server)
			scope.user = member.server.me
			scope.permission = praxisbot.UserPermission.Script
			scope.vars["target"] = member.name+"#"+member.discriminator

			for p in self.shell.plugins:
				await p.on_member_join(scope)

		except:
			print(traceback.format_exc())
			pass

	async def on_member_remove(self, member):
		reason = "leave"

		if member.id in self.banned_members:
			accepted_time = datetime.datetime.now() - datetime.timedelta(minutes=1)
			if self.banned_members[member.id] > accepted_time:
				reason = "ban"

		try:
			scope = self.shell.create_scope(member.server, [""])
			scope.channel = self.shell.get_default_channel(member.server)
			scope.user = member.server.me
			scope.permission = praxisbot.UserPermission.Script
			scope.vars["target"] = member.name+"#"+member.discriminator
			scope.vars["reason"] = reason

			for p in self.shell.plugins:
				await p.on_member_leave(scope)

		except:
			print(traceback.format_exc())
			pass

	async def on_member_ban(self, member):

		self.banned_members[member.id] = datetime.datetime.now()

		ban_author = ""
		ban_target = ""
		ban_reason = ""
		
		bans = await self.shell.client.get_ban_logs(member.server, limit=5)
		for b in bans:
			if b.target.id == member.id:
				author = b.author
				reason = b.reason

				if b.author.id == self.shell.client.user.id:
					#Try to find the true author in the reason
					res = re.search("(.+#[0-9][0-9][0-9][0-9]) using ban command", b.reason)
					if res:
						u = self.shell.find_member(res.group(1), member.server)
						if u:
							author = u

					res = re.search("using ban command:(.+)", b.reason)
					if res:
						reason = res.group(1).strip()

				ban_author = author.name+"#"+author.discriminator
				ban_reason = reason
				ban_target = b.target.name+"#"+b.target.discriminator
				break

		try:
			scope = self.shell.create_scope(member.server, [""])
			scope.channel = self.shell.get_default_channel(member.server)
			scope.user = member.server.me
			scope.permission = praxisbot.UserPermission.Script
			scope.vars["reason"] = ban_reason
			scope.vars["author"] = ban_author
			scope.vars["target"] = member.name+"#"+member.discriminator

			for p in self.shell.plugins:
				await p.on_ban(scope)

		except:
			print(traceback.format_exc())
			pass

	async def on_member_unban(self, server, user):
		try:
			scope = self.shell.create_scope(server, [""])
			scope.channel = self.shell.get_default_channel(server)
			scope.user = server.me
			scope.permission = praxisbot.UserPermission.Script
			scope.vars["target"] = user.name+"#"+user.discriminator

			for p in self.shell.plugins:
				await p.on_unban(scope)

		except:
			print(traceback.format_exc())
			pass

########################################################################
# Execute

try:
	human = PraxisHuman()
	human.loop.create_task(human.start(humanEmail, humanPassword))

	bot = PraxisBot(human)
	bot.run(botToken)

except KeyboardInterrupt:
	human.loop.run_until_complete(human.logout())
	bot.loop.run_until_complete(bot.logout())
