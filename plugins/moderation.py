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
from pytz import timezone
import io
import sqlite3
import praxisbot

class ModLevelType:
	User=0
	Role=1
	Channel=2

class ModerationPlugin(praxisbot.Plugin):
	"""
	Moderation commands
	"""

	name = "Moderation"

	def __init__(self, shell):
		super().__init__(shell)

		self.shell.create_sql_table("mod_levels", ["id INTEGER PRIMARY KEY", "discord_sid INTEGER", "name TEXT", "priority INTEGER", "type INTEGER", "value TEXT", "ban_timelimit INTEGER", "ban_prioritylimit INTEGER", "purge INTEGER"])
		self.shell.create_sql_table("ban_time", ["id INTEGER PRIMARY KEY", "discord_sid INTEGER", "discord_uid INTEGER", "last_time DATETIME"])

		self.add_command("ban", self.execute_ban)
		self.add_command("last_bans", self.execute_last_bans)
		self.add_command("kick", self.execute_kick)
		self.add_command("list_channels", self.execute_list_channels)
		self.add_command("create_mod_level", self.execute_create_mod_level)
		self.add_command("delete_mod_level", self.execute_delete_mod_level)
		self.add_command("mod_levels", self.execute_mod_levels)
		self.add_command("get_mod_level", self.execute_get_mod_level)
		self.add_command("set_mod_options", self.execute_set_mod_options)
		self.add_command("purge", self.execute_purge)

	def get_mod_level(self, member):
		if not member:
			return {
				"name":"",
				"priority":-1,
				"ban_timelimit":0,
				"ban_prioritylimit":-1,
				"purge":False
			}

		with self.shell.dbcon:
			c = self.shell.dbcon.cursor()
			for row in c.execute("SELECT type, value, name, priority, ban_timelimit, ban_prioritylimit, purge FROM "+self.shell.dbtable("mod_levels")+" WHERE discord_sid = ? ORDER BY priority DESC", [int(member.server.id)]):
				res = {
					"name":row[2],
					"priority":row[3],
					"ban_timelimit":row[4],
					"ban_prioritylimit":row[5],
					"purge":row[6]
				}

				if not row[4] or row[4] < 0:
					res["ban_timelimit"] = 0
				if not row[5] or row[5] < 0:
					res["ban_prioritylimit"] = 0
				if row[5] > res["priority"]:
					res["ban_prioritylimit"] = res["priority"]
				if row[6] and row[6] != 0:
					res["purge"] = 1
				else:
					res["purge"] = 0

				if row[0] == ModLevelType.User:
					if row[1] == member.id:
						return res
				if row[0] == ModLevelType.Role:
					for r in member.roles:
						if r.id == row[1]:
							return res
				if row[0] == ModLevelType.Channel:
					chan = self.shell.find_channel("<#"+row[1]+">", member.server)
					if chan and chan.permissions_for(member).send_messages:
						return res

		return {
			"name":"",
			"priority": 0,
			"ban_timelimit": 0,
			"ban_prioritylimit": -1,
			"purge": False
		}

	async def dump(self, server):
		text = []

		with self.shell.dbcon:
			c = self.shell.dbcon.cursor()
			for row in c.execute("SELECT name, priority, type, value, ban_timelimit, ban_prioritylimit, purge FROM "+self.ctx.dbprefix+"mod_levels WHERE discord_sid = ? ORDER BY priority DESC", [int(server.id)]):
				option = ""
				if row[2] == ModLevelType.User:
					option = " --user <@"+row[3]+">"
				elif row[2] == ModLevelType.Role:
					r = self.shell.find_role(row[3], server)
					if r:
						option = " --role \""+r.name+"\""
					else:
						option = " --role <@&"+row[3]+">"
				elif row[2] == ModLevelType.Channel:
					c = self.shell.find_channel(row[3], server)
					if c:
						option = " --channel \""+c.name+"\""
					else:
						option = " --channel <#"+row[3]+">"
				text.append("create_mod_level \""+row[0]+"\" "+str(row[1])+option)

				if row[6] and row[6] != 0:
					purge = 1
				else:
					purge = 0
				text.append("set_mod_options \""+row[0]+"\" --banpriority "+str(row[4])+" --bantime "+str(row[5])+" --purge "+str(purge))

		return text

	@praxisbot.command
	async def execute_list_channels(self, scope, command, options, lines, **kwargs):
		"""
		List all channels of the server.
		"""

		parser = argparse.ArgumentParser(description=kwargs["description"], prog=command)
		parser.add_argument('--user', help='List channels from the point of view of this user.')
		args = await self.parse_options(scope, parser, options)
		if not args:
			return

		if not args.user:
			user = scope.user
		else:
			user = scope.shell.find_member(args.user, scope.server)
			if not user:
				await scope.shell.print_error(scope, "User not found.")
				return

		clist = []
		for c in scope.server.channels:
			if c.permissions_for(scope.user).read_messages and c.permissions_for(user).read_messages:
				if c.type == discord.ChannelType.text:
					pos = (c.position+1)*10
					cat = c.server.get_channel(c.parent_id)
					if cat:
						pos = pos+1000*(cat.position+1)

					if c.permissions_for(user).send_messages:
						clist.append((pos, " :pencil2: "+c.name))
					else:
						clist.append((pos, " :eye: "+c.name))
				elif c.type == discord.ChannelType.voice:
					pos = (c.position+1)*10
					cat = c.server.get_channel(c.parent_id)
					if cat:
						pos = pos+1000*(cat.position+1)

					clist.append((pos, " :microphone2: "+c.name))
				elif c.type == discord.ChannelType.category:
					pos = (c.position+1)*1000
					clist.append((pos, "\n**"+c.name+"**"))

		clist = sorted(clist, key=lambda x: x[0])

		stream = praxisbot.MessageStream(scope)
		for c in clist:
			await stream.send(c[1]+"\n")
		await stream.finish()

	@praxisbot.command
	@praxisbot.permission_admin
	async def execute_create_mod_level(self, scope, command, options, lines, **kwargs):
		"""
		Create a moderator level.
		"""

		parser = argparse.ArgumentParser(description=kwargs["description"], prog=command)
		parser.add_argument('name', help='Name of the moderator level.')
		parser.add_argument('priority', help='Priority of the moderator level.')
		parser.add_argument('--channel', help='All members that can write in this channel.')
		parser.add_argument('--role', help='All members of this role.')
		parser.add_argument('--user', help='A specific user.')
		args = await self.parse_options(scope, parser, options)
		if not args:
			return

		numOptions = 0
		if args.channel:
			numOptions = numOptions+1
		if args.role:
			numOptions = numOptions+1
		if args.user:
			numOptions = numOptions+1

		if numOptions != 1:
			await scope.shell.print_error(scope, "You must use one and only one of this options: --role, --channel, --user.")
			return

		modData = scope.shell.get_sql_data("mod_levels", ["id"], {"discord_sid": int(scope.server.id), "name": str(args.name)})
		if modData:
			await scope.shell.print_error(scope, "The moderator level `"+args.name+"` already exists.")
			return

		if args.channel:
			chan = scope.shell.find_channel(args.channel, scope.server)
			if not chan:
				await scope.shell.print_error(scope, "Channel not found.")
				return

			scope.shell.add_sql_data("mod_levels", {"name": str(args.name), "discord_sid": int(scope.server.id), "type": ModLevelType.Channel, "value": int(chan.id), "priority": int(args.priority), "ban_timelimit": 0, "ban_prioritylimit": -1, "purge": 0, })

		elif args.role:
			role = scope.shell.find_role(args.role, scope.server)
			if not role:
				await scope.shell.print_error(scope, "Role not found.")
				return

			scope.shell.add_sql_data("mod_levels", {"name": str(args.name), "discord_sid": int(scope.server.id), "type": ModLevelType.Role, "value": int(role.id), "priority": int(args.priority), "ban_timelimit": 0, "ban_prioritylimit": -1, "purge": 0, })

		elif args.user:
			user = scope.shell.find_member(args.user, scope.server)
			if not user:
				await scope.shell.print_error(scope, "User not found.")
				return

			scope.shell.add_sql_data("mod_levels", {"name": str(args.name), "discord_sid": int(scope.server.id), "type": ModLevelType.User, "value": int(user.id), "priority": int(args.priority), "ban_timelimit": 0, "ban_prioritylimit": -1, "purge": 0, })

		await scope.shell.print_success(scope, "Moderator level created.")

	@praxisbot.command
	@praxisbot.permission_admin
	async def execute_delete_mod_level(self, scope, command, options, lines, **kwargs):
		"""
		Delete a moderator level.
		"""

		parser = argparse.ArgumentParser(description=kwargs["description"], prog=command)
		parser.add_argument('name', help='Name of the moderator level.')
		args = await self.parse_options(scope, parser, options)
		if not args:
			return

		modData = scope.shell.get_sql_data("mod_levels", ["id"], {"discord_sid": int(scope.server.id), "name": str(args.name)})
		if not modData:
			await scope.shell.print_error(scope, "Moderator level `"+args.name+"` not found.")
			return

		scope.shell.delete_sql_data("mod_levels", {"id": modData[0]})
		await scope.shell.print_success(scope, "Moderator level deleted.")

	@praxisbot.command
	async def execute_mod_levels(self, scope, command, options, lines, **kwargs):
		"""
		List all moderator levels.
		"""

		parser = argparse.ArgumentParser(description=kwargs["description"], prog=command)
		args = await self.parse_options(scope, parser, options)
		if not args:
			return scope

		stream = praxisbot.MessageStream(scope)
		await stream.send("**__List of moderator levels__**\n")

		with scope.shell.dbcon:
			c = scope.shell.dbcon.cursor()
			for row in c.execute("SELECT name, priority, ban_timelimit, ban_prioritylimit, purge FROM "+scope.shell.dbtable("mod_levels")+" WHERE discord_sid = ? ORDER BY priority DESC", [int(scope.server.id)]):
				await stream.send("\n:label: **"+row[0]+"**")
				await stream.send("\n   - Priority: "+str(row[1]))
				if not row[2] or row[2] < 0:
					tlimit = 0
				else:
					tlimit = row[2]
				await stream.send("\n   - Duration bewteen two bans: "+str(tlimit)+"h")
				if not row[3] or row[3] < 0:
					plimit = row[1]-1
				else:
					plimit = min(row[3], row[1])
				await stream.send("\n   - Maximum priority that can be banned: "+str(plimit))
				if not row[4] or row[4] <= 0:
					purge = "Can't use purge command"
				else:
					purge = "Can use purge command"
				await stream.send("\n   - "+purge)

		await stream.finish()

	@praxisbot.command
	async def execute_get_mod_level(self, scope, command, options, lines, **kwargs):
		"""
		Give the highest moderator level of a member.
		"""

		parser = argparse.ArgumentParser(description=kwargs["description"], prog=command)
		parser.add_argument('member', help='A member of the server.')
		args = await self.parse_options(scope, parser, options)
		if not args:
			return

		member = scope.shell.find_member(scope.format_text(args.member), scope.server)
		if not member:
			await scope.shell.print_error(scope, "User not found.")
			return

		userLevel = self.get_mod_level(member)

		await scope.shell.print_info(scope, member.name+"#"+member.discriminator+" moderator level is: "+userLevel["name"]+".")

	async def execute_kick_or_ban(self, scope, command, options, lines, **kwargs):
		action_name = kwargs["action_name"]

		parser = argparse.ArgumentParser(description=kwargs["description"], prog=command)
		parser.add_argument('member', help='Name of the member to '+action_name+'.')
		parser.add_argument('--reason', help='Reason for the '+action_name+'.')
		args = await self.parse_options(scope, parser, options)
		if not args:
			return

		u = scope.shell.find_member(scope.format_text(args.member), scope.server)
		if not u:
			await scope.shell.print_error(scope, "User not found. User name must be of the form `@User#1234` or `User#1234`.")
			return

		if scope.user.id == u.id:
			await scope.shell.print_error(scope, "You can't "+action_name+" yourself.")
			return

		userLevel = self.get_mod_level(scope.user)
		targetLevel = self.get_mod_level(u)

		if targetLevel["priority"] > userLevel["ban_prioritylimit"]:
			await scope.shell.print_error(scope, "You can't "+action_name+" "+u.display_name+" with your level.")
			return

		banData = scope.shell.get_sql_data("ban_time", ["id", "last_time as 'last_time_ [timestamp]'"], {"discord_sid": int(scope.server.id), "discord_uid": int(scope.user.id)})
		if banData:

			last_time = timezone('UTC').localize(banData[1])
			now_time = datetime.datetime.now(timezone('UTC'))

			end_time = last_time + datetime.timedelta(hours=userLevel["ban_timelimit"])
			if end_time > now_time:
				await scope.shell.print_error(scope, "You already used your right to "+action_name+" someone. Please wait until "+str(end_time)+".")
				return

		try:
			if action_name == "ban":
				reason = scope.user.name+"#"+scope.user.discriminator+" using ban command"
				if args.reason:
					reason = reason+": "+args.reason
				elif len(lines) > 0:
					reason = reason+": "+"\n".join(lines)

				await scope.shell.client.ban(u, delete_message_days=0, reason=reason)
			else:
				await scope.shell.client.kick(u)
		except:
			await scope.shell.print_error(scope, "You can't "+action_name+" "+u.display_name+" (please check that PraxisBot role is high enough).")
			return

		last_time = datetime.datetime.now(timezone('UTC'))

		scope.shell.set_sql_data("ban_time", {"last_time": str(last_time)}, {"discord_sid": int(scope.server.id), "discord_uid": int(scope.user.id)})
		if action_name == "ban":
			await scope.shell.print_success(scope, ""+u.display_name+" banned.")
		else:
			await scope.shell.print_success(scope, ""+u.display_name+" kicked.")
		scope.deletecmd = True

	@praxisbot.command
	async def execute_ban(self, scope, command, options, lines, **kwargs):
		"""
		Ban a member.
		"""

		await self.execute_kick_or_ban(scope, command, options, lines, action_name="ban", **kwargs)

	@praxisbot.command
	async def execute_kick(self, scope, command, options, lines, **kwargs):
		"""
		Kick a member.
		"""

		await self.execute_kick_or_ban(scope, command, options, lines, action_name="kick", **kwargs)

	@praxisbot.command
	@praxisbot.permission_admin
	async def execute_last_bans(self, scope, command, options, lines, **kwargs):
		"""
		List last bans.
		"""

		parser = argparse.ArgumentParser(description=kwargs["description"], prog=command)
		args = await self.parse_options(scope, parser, options)
		if not args:
			return scope

		stream = praxisbot.MessageStream(scope)
		await stream.send("**__Last bans__**")

		bans = await scope.shell.client.get_ban_logs(scope.server, limit=5)
		for b in bans:
			author = b.author
			target = b.target
			reason = b.reason

			if b.author.id == scope.shell.client.user.id:
				#Try to find the true author in the reason
				res = re.search("(.+#[0-9][0-9][0-9][0-9]) using ban command", b.reason)
				if res:
					u = scope.shell.find_member(res.group(1), scope.server)
					if u:
						author = u

				res = re.search("using ban command:(.+)", b.reason)
				if res:
					reason = res.group(1).strip()

			await stream.send("\n\n**"+target.name+"#"+target.discriminator+" by "+author.name+"#"+author.discriminator+"**\n"+reason)

		await stream.finish()

	@praxisbot.command
	async def execute_set_mod_options(self, scope, command, options, lines, **kwargs):
		"""
		Configure options for a moderation level.
		"""

		parser = argparse.ArgumentParser(description=kwargs["description"], prog=command)
		parser.add_argument('name', help='Name of moderation level.')
		parser.add_argument('--bantime', help='Minimum duration between two bans in hours.')
		parser.add_argument('--banpriority', help='Maximum level priority than can be banned.')
		parser.add_argument('--purge', help='Enable or disable purge command.')
		args = await self.parse_options(scope, parser, options)
		if not args:
			return

		modLevel = scope.shell.get_sql_data("mod_levels", ["id", "ban_timelimit", "ban_prioritylimit", "purge"], {"discord_sid":int(scope.server.id), "name": str(args.name)})
		if not modLevel:
			scope.shell.print_error(scope, "Mod level `"+str(args.name)+"` not found.")
			return

		newBanTime = modLevel[1]
		if args.bantime:
			newBanTime = int(args.bantime)

		newBanPriority = modLevel[2]
		if args.banpriority:
			newBanPriority = int(args.banpriority)

		newPurge = modLevel[3]
		if args.purge:
			newPurge = int(args.purge)

		scope.shell.set_sql_data("mod_levels", {"ban_timelimit": newBanTime, "ban_prioritylimit": newBanPriority, "purge": newPurge}, {"id":modLevel[0]})

		row = scope.shell.get_sql_data("mod_levels", ["name", "priority", "ban_timelimit", "ban_prioritylimit", "purge"], {"id":modLevel[0]})

		text = "Mod level `"+str(args.name)+"` edited."
		text = text+"\n:label: **"+row[0]+"**"
		text = text+"\n   - Priority: "+str(row[1])
		if not row[2] or row[2] < 0:
			tlimit = 0
		else:
			tlimit = row[2]
		text = text+"\n   - Duration bewteen two bans: "+str(tlimit)+"h"
		if not row[3] or row[3] < 0:
			plimit = row[1]-1
		else:
			plimit = min(row[3], row[1])
		text = text+"\n   - Maximum priority that can be banned: "+str(plimit)
		if not row[4] or row[4] <= 0:
			purge = "Can't use purge command"
		else:
			purge = "Can use purge command"
		text = text+"\n   - "+purge

		await scope.shell.print_success(scope, text)

	@praxisbot.command
	async def execute_purge(self, scope, command, options, lines, **kwargs):
		"""
		Purge last messages in a channel.
		"""

		if scope.permission < praxisbot.UserPermission.Script:
			userLevel = self.get_mod_level(scope.user)
			if userLevel["purge"] == 0:
				await scope.shell.print_permission(scope, "You can't purge messages with your level.")
				return

		parser = argparse.ArgumentParser(description=kwargs["description"], prog=command)
		parser.add_argument('num', help='Number of messages to purge.')
		parser.add_argument('--all', action='store_true', help='Remove all messages, including pinned messages.')
		parser.add_argument('--before', help='Remove only messages before a specific message.')
		parser.add_argument('--after', help='Remove only messages after a specific message.')
		parser.add_argument('--onebyone', action='store_true', help='Remove messages one by one. Useful to bypass Discord limitations.')
		args = await self.parse_options(scope, parser, options)
		if not args:
			return

		self.ensure_integer("Number of messages", args.num)
		n = int(args.num)
		if n < 1:
			await scope.shell.print_error(scope, "Invalid number of messages.")
			return

		after=None
		if args.after:
			try:
				after = await scope.shell.client.get_message(scope.channel, args.after)
			except:
				after = None
			if not after:
				await scope.shell.print_error(scope, "Message not found.")
				return

		before=None
		if args.before:
			try:
				before = await scope.shell.client.get_message(scope.channel, args.before)
			except:
				before = None
			if not before:
				await scope.shell.print_error(scope, "Message not found.")
				return

		def check_function(m):
			if not args.all:
				return m.pinned == False
			else:
				return True

		if args.onebyone:
			message_left = n
			newmessages = True
			curr_before = before
			curr_after = after
			while message_left > 0 and newmessages:
				newmessages = False
				b = before
				async for m in scope.shell.client.logs_from(scope.channel, limit=min(200, message_left), before=curr_before, after=curr_after):
					message_left = message_left-1
					if args.after:
						curr_after = m
					else:
						curr_before = m
					newmessages = True
					if check_function(m):
						await self.shell.client.delete_message(m)
		else:
			try:
				await scope.shell.client.purge_from(scope.channel, limit=n, check=check_function, after=after, before=before)
			except:
				await scope.shell.print_error(scope, "Purge failed. Please retry with the option --onebyone.")
