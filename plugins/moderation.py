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

import shlex
import argparse
import re
import discord
import traceback
import datetime
import io
from io import StringIO
from plugin import Plugin
from scope import UserPermission
from scope import ExecutionScope
from scope import ExecutionBlock

class ModLevelType:
	User=0
	Role=1
	Channel=2

class ModerationPlugin(Plugin):
	"""
	Moderation commands
	"""

	name = "Moderation"

	def __init__(self, ctx):
		super().__init__(ctx)

		self.ctx.dbcon.execute("CREATE TABLE IF NOT EXISTS "+self.ctx.dbprefix+"mod_levels(id INTEGER PRIMARY KEY, discord_sid INTEGER, name TEXT, priority INTEGER, type INTEGER, value TEXT, ban_cooldown INTEGER)");


	async def execute_list_channels(self, command, options, scope):
		parser = argparse.ArgumentParser(description='List all channels of the server.', prog=command)
		parser.add_argument('--user', help='List channels from the point of view of this user.')

		args = await self.parse_options(scope.channel, parser, options)

		if not args:
			return scope

		if not args.user:
			user = scope.user
		else:
			user = self.ctx.find_member(args.user, scope.server)
			if not user:
				user = scopre.user

		text = ""
		for c in scope.server.channels:
			if c.permissions_for(scope.user).read_messages and c.permissions_for(user).read_messages:
				if c.type == discord.ChannelType.text:
					if c.permissions_for(user).send_messages:
						text = text+" :pencil2: "+c.name+"\n"
					else:
						text = text+" :eye: "+c.name+"\n"
				elif c.type == discord.ChannelType.voice:
					text = text+" :microphone2: "+c.name+"\n"
				else:
					text = text+"\n**"+c.name+"**\n"

		await self.ctx.send_message(scope.channel, text)

		return scope

	async def execute_create_mod_level(self, command, options, scope):
		if scope.permission < UserPermission.Admin:
			await self.ctx.send_message(scope.channel, "Only admins can use this command.")
			return scope

		parser = argparse.ArgumentParser(description='Create a moderator level.', prog=command)
		parser.add_argument('name', help='Name of the moderator level.')
		parser.add_argument('priority', help='Priority of the moderator level.')
		parser.add_argument('--channel', help='All members that can write in this channel.')
		parser.add_argument('--role', help='All members of this role.')
		parser.add_argument('--user', help='A specific user.')

		args = await self.parse_options(scope.channel, parser, options)

		if not args:
			return scope

		numOptions = 0
		if args.channel:
			numOptions = numOptions+1
		if args.role:
			numOptions = numOptions+1
		if args.user:
			numOptions = numOptions+1

		if numOptions != 1:
			await self.ctx.send_message(scope.channel, "You must use one and only one of this options: --role, --channel, --user.")
			return scope

		with self.ctx.dbcon:
			c = self.ctx.dbcon.cursor()
			c.execute("SELECT id FROM "+self.ctx.dbprefix+"mod_levels WHERE discord_sid = ? AND name = ?", [int(scope.server.id), str(args.name)])
			r = c.fetchone()
			if r:
				await self.ctx.send_message(scope.channel, "The moderator level `"+args.name+"` already exists.")
				return scope

		if args.channel:
			chan = self.ctx.find_channel(args.channel, scope.server)
			if not chan:
				await self.ctx.send_message(scope.channel, "Channel not found.")
				return scope

			with self.ctx.dbcon:
				if not self.ctx.dbcon.execute("INSERT INTO "+self.ctx.dbprefix+"mod_levels (name, discord_sid, type, value, priority) VALUES (?, ?, ?, ?, ?)", [str(args.name), int(scope.server.id), ModLevelType.Channel, int(chan.id), int(args.priority)]):
					await self.ctx.send_message(scope.channel, "The moderator level can't be created.")

		elif args.role:
			role = self.ctx.find_role(args.role, scope.server)
			if not role:
				await self.ctx.send_message(scope.channel, "Role not found.")
				return scope

			with self.ctx.dbcon:
				if not self.ctx.dbcon.execute("INSERT INTO "+self.ctx.dbprefix+"mod_levels (name, discord_sid, type, value, priority) VALUES (?, ?, ?, ?, ?)", [str(args.name), int(scope.server.id), ModLevelType.Role, int(role.id), int(args.priority)]):
					await self.ctx.send_message(scope.channel, "The moderator level can't be created.")

		elif args.user:
			user = self.ctx.find_member(args.user, scope.server)
			if not user:
				await self.ctx.send_message(scope.channel, "User not found.")
				return scope

			with self.ctx.dbcon:
				if not self.ctx.dbcon.execute("INSERT INTO "+self.ctx.dbprefix+"mod_levels (name, discord_sid, type, value, priority) VALUES (?, ?, ?, ?, ?)", [str(args.name), int(scope.server.id), ModLevelType.User, int(user.id), int(args.priority)]):
					await self.ctx.send_message(scope.channel, "The moderator level can't be created.")

		return scope

	async def execute_delete_mod_level(self, command, options, scope):
		if scope.permission < UserPermission.Admin:
			await self.ctx.send_message(scope.channel, "Only admins can use this command.")
			return scope

		parser = argparse.ArgumentParser(description='Delete a moderator level.', prog=command)
		parser.add_argument('name', help='Name of the moderator level.')

		args = await self.parse_options(scope.channel, parser, options)

		if not args:
			return scope

		with self.ctx.dbcon:
			c = self.ctx.dbcon.cursor()
			c.execute("SELECT id FROM "+self.ctx.dbprefix+"mod_levels WHERE discord_sid = ? AND name = ?", [int(scope.server.id), str(args.name)])
			r = c.fetchone()
			if r:
				with self.ctx.dbcon:
					if not self.ctx.dbcon.execute("DELETE FROM "+self.ctx.dbprefix+"mod_levels WHERE id = ?", [r[0]]):
						await self.ctx.send_message(scope.channel, "The moderator level can't be deleted.")

			else:
				await self.ctx.send_message(scope.channel, "The moderator level `"+args.name+"` doesn't exist.")

		return scope

	async def execute_mod_levels(self, command, options, scope):
		text = "**List of moderator levels:**"
		with self.ctx.dbcon:
			c = self.ctx.dbcon.cursor()
			for row in c.execute("SELECT name, priority FROM "+self.ctx.dbprefix+"mod_levels WHERE discord_sid = ? ORDER BY priority DESC", [int(scope.server.id)]):
				text = text+"\n - "+row[0]+" (Priority: "+str(row[1])+")"

		await self.ctx.send_message(scope.channel, text)

		return scope

	async def execute_get_mod_level(self, command, options, scope):
		parser = argparse.ArgumentParser(description='Give the highest moderator level of a member.', prog=command)
		parser.add_argument('member', help='A member of the server.')

		args = await self.parse_options(scope.channel, parser, options)

		if not args:
			return scope

		member = self.ctx.find_member(self.ctx.format_text(args.member, scope), scope.server)
		if not member:
			await self.ctx.send_message(scope.channel, "Member not found.")
			return scope

		with self.ctx.dbcon:
			c = self.ctx.dbcon.cursor()
			for row in c.execute("SELECT name, type, value FROM "+self.ctx.dbprefix+"mod_levels WHERE discord_sid = ? ORDER BY priority DESC", [int(scope.server.id)]):
				if row[1] == ModLevelType.User:
					if row[2] == member.id:
						await self.ctx.send_message(scope.channel, member.name+"#"+member.discriminator+" moderator level is: "+row[0]+".")
						return scope
				if row[1] == ModLevelType.Role:
					for r in member.roles:
						if r.id == row[2]:
							await self.ctx.send_message(scope.channel, member.name+"#"+member.discriminator+" moderator level is: "+row[0]+".")
							return scope
				if row[1] == ModLevelType.Channel:
					chan = self.ctx.find_channel("<#"+row[2]+">", scope.server)
					if chan and chan.permissions_for(member).send_messages:
						await self.ctx.send_message(scope.channel, member.name+"#"+member.discriminator+" moderator level is: "+row[0]+".")
						return scope

		await self.ctx.send_message(scope.channel, member.name+"#"+member.discriminator+" is not in any moderator levels.")

		return scope

	async def execute_ban(self, command, options, scope):

		parser = argparse.ArgumentParser(description='Ban a member.', prog=command)
		parser.add_argument('member', help='Name of the member to ban.')

		args = await self.parse_options(scope.channel, parser, options)

		if not args:
			return scope

		u = self.ctx.find_member(self.ctx.format_text(args.user, scope), scope.server)
		if not u:
			await self.ctx.send_message(scope.channel, "Member not found. Member name must be of the form `@User#1234` or `User#1234`.")
			return scope

		if scope.permission < UserPermission.Script and not scope.user.permissions.ban_members:
			await self.ctx.send_message(scope.channel, "You don't have the permission to ban members.")
			return scope

		try:
			await self.ctx.client.ban(u)
		except:
			await self.ctx.send_message(scope.channel, "You can't ban "+u.display_name+".")
			pass

		return scope

	async def list_commands(self, server):
		return ["list_channels", "create_mod_level", "delete_mod_level", "mod_levels", "get_mod_level"]

	async def execute_command(self, shell, command, options, scope):
		#if command == "ban":
		#	scope.iter = scope.iter+1
		#	return await self.execute_ban(command, options, scope)
		if command == "list_channels":
			scope.iter = scope.iter+1
			return await self.execute_list_channels(command, options, scope)
		if command == "create_mod_level":
			scope.iter = scope.iter+1
			return await self.execute_create_mod_level(command, options, scope)
		if command == "delete_mod_level":
			scope.iter = scope.iter+1
			return await self.execute_delete_mod_level(command, options, scope)
		if command == "mod_levels":
			scope.iter = scope.iter+1
			return await self.execute_mod_levels(command, options, scope)
		if command == "get_mod_level":
			scope.iter = scope.iter+1
			return await self.execute_get_mod_level(command, options, scope)

		return scope
