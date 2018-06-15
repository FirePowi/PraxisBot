"""

Copyright (C) 2017 ManoIzquierda (manoizquierda.dev@gmail.com)

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

import re
import sqlite3
import random
import discord

from scope import UserPermission
from scope import ExecutionScope

class Context:
	def __init__(self, client, mode):
		self.mode = mode
		self.client = client
		self.dbprefix = "pb_"
		self.dbcon = sqlite3.connect("databases/praxisbot-"+mode+".db")

		with self.dbcon:
			#Server list
			self.dbcon.execute("CREATE TABLE IF NOT EXISTS "+self.dbprefix+"servers(discord_sid INTEGER PRIMARY KEY, command_prefix TEXT)");

	def log(self, msg):
		print(msg)

	def format_text(self, text, scope):
		if not text:
			return ""

		user = scope.user
		channel = scope.channel
		server = scope.server

		p = re.compile("\{\{([^\}]+)\}\}")

		formatedText = ""
		textIter = 0
		mi = p.finditer(text)
		for m in mi:
			formatedText = formatedText + text[textIter:m.start()]
			textIter = m.end()

			#Process tag
			tag = m.group(1).strip()
			tagOutput = m.group()

			if tag.find('|') >= 0:
				tag = random.choice(tag.split("|"))
				tagOutput = tag

			u = user
			user_chk = re.fullmatch('([*@#]?user(?:_time|_avatar)?)=(.*)', tag)
			if user_chk:
				subUser = user_chk.group(2).strip()
				if subUser in scope.vars:
					subUser = scope.vars[subUser]
				u = self.find_member(subUser, server)
				tag = user_chk.group(1)

			c = channel
			channel_chk = re.fullmatch('([#]?channel)=(.*)', tag)
			if channel_chk:
				subChan = channel_chk.group(2).strip()
				if subChan in scope.vars:
					subChan = scope.vars[subUser]
				c = self.find_channel(subChan, server)
				tag = channel_chk.group(1)

			if tag.lower() == "server" and server:
				tagOutput = server.name
			elif tag.lower() == "n":
				tagOutput = "\n"
			elif tag.lower() == "channel" and c:
				tagOutput = c.name
			elif tag.lower() == "#channel" and c:
				tagOutput = c.mention
			elif tag.lower() == "#user" and u:
				tagOutput = u.name+"#"+u.discriminator
			elif tag.lower() == "@user" and u:
				tagOutput = u.mention
			elif tag.lower() == "*user" and u:
				tagOutput = u.name+"#"+u.discriminator+" ("+u.id+")"
			elif tag.lower() == "user" and u:
				tagOutput = u.display_name
			elif tag.lower() == "user_time" and u:
				tagOutput = str(u.created_at)
			elif tag.lower() == "user_avatar" and u:
				tagOutput = str(u.avatar_url.replace(".webp", ".png"))
			elif tag in scope.vars:
				tagOutput = scope.vars[tag]
			formatedText = formatedText + tagOutput

		formatedText = formatedText + text[textIter:]

		return formatedText

	def find_channel(self, chan_name, server):
		if not chan_name:
			return None

		chan_name = chan_name.strip()

		for c in server.channels:
			if c.name == chan_name:
				return c
			elif c.id == chan_name:
				return c
			elif "<#"+c.id+">" == chan_name:
				return c
			elif "#"+c.id == chan_name:
				return c
		return None

	def find_member(self, member_name, server):
		if not member_name:
			return None

		member_name = member_name.strip()

		for m in server.members:
			if "<@"+m.id+">" == member_name:
				return m
			if "<@!"+m.id+">" == member_name:
				return m
			elif m.name+"#"+m.discriminator == member_name:
				return m
			elif m.id == member_name:
				return m

		return None

	def find_role(self, role_name, server):
		if not role_name:
			return None

		for r in server.roles:
			if "<@"+r.id+">" == role_name:
				return r
			elif r.name == role_name:
				return r

		return None

	def get_default_channel(self, server):
		for c in server.channels:
			if c.type == discord.ChannelType.text:
				return c
		return None

	def get_command_prefix(self, server):
		with self.dbcon:
			c = self.dbcon.cursor()
			c.execute("SELECT command_prefix FROM "+self.dbprefix+"servers WHERE discord_sid = ?", [int(server.id)])
			r = c.fetchone()
			if r:
				return r[0]
		return None

	def set_command_prefix(self, server, prefix):
		if not re.fullmatch('\S+', prefix):
			return False

		with self.dbcon:
			c = self.dbcon.cursor()
			c.execute("SELECT command_prefix FROM "+self.dbprefix+"servers WHERE discord_sid = ?", [int(server.id)])
			r = c.fetchone()
			if r:
				self.dbcon.execute("UPDATE "+self.dbprefix+"servers SET command_prefix = ? WHERE discord_sid = ?", [str(prefix), int(server.id)])
			else:
				self.dbcon.execute("INSERT INTO "+self.dbprefix+"servers (discord_sid, command_prefix) VALUES (?, ?)", [int(server.id), str(prefix)])
			return True

		return False

	async def send_message(self, channel, text, e=None):
		if e:
			return await self.client.send_message(channel, text, embed=e)
		else:
			return await self.client.send_message(channel, text)

	async def add_roles(self, member, roles):
		try:
			await self.client.add_roles(member, *roles)
		except:
			pass
			return False
		return True

	async def remove_roles(self, member, roles):
		try:
			await self.client.remove_roles(member, *roles)
		except:
			pass
			return False
		return True

	async def change_roles(self, member, rolesToAdd, rolesToRemove):

		roles = member.roles
		rolesAdded = []
		rolesRemoved = []
		for r in rolesToRemove:
			if r in roles:
				roles.remove(r)
				rolesRemoved.append(r)
		for r in rolesToAdd:
			if not r in roles:
				roles.append(r)
				rolesAdded.append(r)

		await self.client.replace_roles(member, *roles)
		return (rolesAdded, rolesRemoved)
