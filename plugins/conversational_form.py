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
import requests
import traceback
import io
import datetime
from pytz import timezone
import praxisbot

class LinkType:
	UserRegex=0
	Timeout=1

class Session:
	def __init__(self, node_start):
		self.vars = {}
		self.current_node = node_start
		self.start_time = datetime.datetime.now()
		self.last_time = self.start_time

class ConversationalFormPlugin(praxisbot.Plugin):
	"""
	ConversationalForm commands
	"""

	name = "ConversationalForm"

	def __init__(self, shell):
		super().__init__(shell)

		self.shell.create_sql_table("cf_nodes", ["id INTEGER PRIMARY KEY", "name TEXT", "discord_sid INTEGER", "script TEXT"])
		self.shell.create_sql_table("cf_links", ["id INTEGER PRIMARY KEY", "node_start TEXT", "node_end TEXT", "discord_sid INTEGER", "script TEXT", "type INTEGER", "value TEXT"])

		self.sessions = {}

		self.add_command("create_cf_node", self.execute_create_cf_node)
		self.add_command("create_cf_link", self.execute_create_cf_link)
		self.add_command("delete_cf_node", self.execute_delete_cf_node)
		self.add_command("delete_cf_link", self.execute_delete_cf_link)
		self.add_command("cf_nodes", self.execute_cf_nodes)
		self.add_command("start_cf_session", self.execute_start_cf_session)
		self.add_command("end_cf_session", self.execute_end_cf_session)
		self.add_command("cf_sessions", self.execute_cf_sessions)

	def start_session(self, user, channel, server, node_start):
		key = (user.id, channel.id, server.id)
		self.sessions[key] = Session(node_start)

	def end_session(self, user, channel, server):
		key = (user.id, channel.id, server.id)
		if key in self.sessions:
			del(self.sessions[key])

	def get_session(self, user, channel, server):
		key = (user.id, channel.id, server.id)
		if key in self.sessions:
			return self.sessions[key]
		else:
			return None

	async def execute_session_script(self, user, channel, server, scope, script):
		key = (user.id, channel.id, server.id)
		if key not in self.sessions:
			return

		subScope = scope.create_subscope()
		subScope.prefixes = [""]
		subScope.user = user
		subScope.channel = channel
		subScope.permission = praxisbot.UserPermission.Script
		subScope.verbose = 1

		for v in self.sessions[key].vars:
			subScope.session_vars[v] = self.sessions[key].vars[v]
			subScope.vars[v] = self.sessions[key].vars[v]

		await scope.shell.execute_script(subScope, script)

		for v in subScope.session_vars:
			self.sessions[key].vars[v] = subScope.session_vars[v]
		self.sessions[key].last_time = datetime.datetime.now()

	async def execute_session_node(self, user, channel, server, scope):
		key = (user.id, channel.id, server.id)
		if key not in self.sessions:
			return

		node = self.sessions[key].current_node
		node_data = scope.shell.get_sql_data("cf_nodes", ["script"], {"discord_sid":int(scope.server.id), "name":str(node)})
		if not node_data:
			del(self.sessions[key])
			return

		await self.execute_session_script(user, channel, server, scope, node_data[0])

	async def on_loop(self, scope):
		sessions_to_delete = set()
		for s in self.sessions:
			timeout_time = self.sessions[s].last_time + datetime.timedelta(minutes=10)
			if timeout_time < datetime.datetime.now():
				sessions_to_delete.add(s)

		for s in sessions_to_delete:
			if s in self.sessions:
				del(self.sessions[s])

	async def on_message(self, scope, message, command_found):
		if command_found:
			return

		session = self.get_session(scope.user, scope.channel, scope.server)
		if not session:
			return

		node = session.current_node
		with scope.shell.dbcon:
			c = scope.shell.dbcon.cursor()
			for row in c.execute("SELECT node_end, script, type, value FROM "+scope.shell.dbtable("cf_links")+" WHERE discord_sid = ? AND node_start = ?", [int(scope.server.id), str(node)]):
				if row[2] != LinkType.UserRegex:
					continue

				try:
					if not re.search(row[3], message.content):
						continue
				except:
					continue

				subScope = scope.create_subscope()
				subScope.vars["message"] = message.content
				await self.execute_session_script(scope.user, scope.channel, scope.server, subScope, row[1])

				session.current_node = row[0]
				await self.execute_session_node(scope.user, scope.channel, scope.server, scope)

	@praxisbot.command
	@praxisbot.permission_admin
	async def execute_create_cf_node(self, scope, command, options, lines, **kwargs):
		"""
		Create a new node.
		"""

		parser = argparse.ArgumentParser(description=kwargs["description"], prog=command)
		parser.add_argument('name', help='Text to send')
		args = await self.parse_options(scope, parser, options)
		if not args:
			return

		self.ensure_object_name("Node name", args.name)

		#node = scope.shell.get_sql_data("cf_nodes", ["id"], {"discord_sid":int(scope.server.id), "name":str(args.name)})
		#if node:
		#	await scope.shell.print_error(scope, "Node `"+args.name+"` already exists.")
		#	return

		scope.shell.set_sql_data("cf_nodes", {"script": "\n".join(lines)}, {"discord_sid":int(scope.server.id), "name":str(args.name)})
		await scope.shell.print_success(scope, "Node `"+args.name+"` created.")

	@praxisbot.command
	@praxisbot.permission_admin
	async def execute_create_cf_link(self, scope, command, options, lines, **kwargs):
		"""
		Create a link between to nodes.
		"""

		parser = argparse.ArgumentParser(description=kwargs["description"], prog=command)
		parser.add_argument('start', help='Name of the starting node')
		parser.add_argument('end', help='Name of the final node')
		parser.add_argument('--message', help='Link activated if a message match a regular expression')
		args = await self.parse_options(scope, parser, options)
		if not args:
			return

		self.ensure_object_name("Node name", args.start)
		self.ensure_object_name("Node name", args.end)

		node_start = scope.shell.get_sql_data("cf_nodes", ["id"], {"discord_sid":int(scope.server.id), "name":str(args.start)})
		if not node_start:
			await scope.shell.print_error(scope, "Node `"+args.start+"` not found.")
			return

		node_end = scope.shell.get_sql_data("cf_nodes", ["id"], {"discord_sid":int(scope.server.id), "name":str(args.end)})
		if not node_end:
			await scope.shell.print_error(scope, "Node `"+args.end+"` not found.")
			return

		if not args.message:
			await scope.shell.print_error(scope, "Missing type of link. Please use --message option.")
			return

		self.ensure_regex(args.message)

		if args.message:
			scope.shell.set_sql_data("cf_links", {"script": "\n".join(lines), "type": LinkType.UserRegex, "value": args.message}, {"discord_sid":int(scope.server.id), "node_start":str(args.start), "node_end":str(args.end)})

		await scope.shell.print_success(scope, "Link between `"+args.start+"` and `"+args.end+"` created.")

	@praxisbot.command
	@praxisbot.permission_admin
	async def execute_delete_cf_node(self, scope, command, options, lines, **kwargs):
		"""
		Delete a node.
		"""

		parser = argparse.ArgumentParser(description=kwargs["description"], prog=command)
		parser.add_argument('name', help='Text to send')
		args = await self.parse_options(scope, parser, options)
		if not args:
			return

		self.ensure_object_name("Node name", args.name)

		node = scope.shell.get_sql_data("cf_nodes", ["id"], {"discord_sid":int(scope.server.id), "name":str(args.name)})
		if not node:
			await scope.shell.print_error(scope, "Node `"+args.name+"` not found.")
			return

		scope.shell.delete_sql_data("cf_nodes", {"discord_sid":int(scope.server.id), "name":str(args.name)})
		await scope.shell.print_success(scope, "Node `"+args.name+"` delete.")

	@praxisbot.command
	@praxisbot.permission_admin
	async def execute_delete_cf_link(self, scope, command, options, lines, **kwargs):
		"""
		Delete a link between to nodes.
		"""

		parser = argparse.ArgumentParser(description=kwargs["description"], prog=command)
		parser.add_argument('start', help='Name of the starting node')
		parser.add_argument('end', help='Name of the final node')
		args = await self.parse_options(scope, parser, options)
		if not args:
			return

		self.ensure_object_name("Node name", args.start)
		self.ensure_object_name("Node name", args.end)

		link = scope.shell.get_sql_data("cf_links", ["id"], {"discord_sid":int(scope.server.id), "node_start":str(args.start), "node_end":str(args.end)})
		if not link:
			await scope.shell.print_error(scope, "Link `"+args.start+" → "+args.end+"` not found.")
			return

		scope.shell.delete_sql_data("cf_links", {"discord_sid":int(scope.server.id), "node_start":str(args.start), "node_end":str(args.end)})
		await scope.shell.print_success(scope, "Link `"+args.start+" → "+args.end+"` delete.")

	@praxisbot.command
	@praxisbot.permission_admin
	async def execute_cf_nodes(self, scope, command, options, lines, **kwargs):
		"""
		List all nodes and links
		"""

		parser = argparse.ArgumentParser(description=kwargs["description"], prog=command)
		args = await self.parse_options(scope, parser, options)
		if not args:
			return

		stream = praxisbot.MessageStream(scope)

		with scope.shell.dbcon:
			c0 = scope.shell.dbcon.cursor()
			c1 = scope.shell.dbcon.cursor()

			await stream.send("__**List of nodes**__")
			for row in c0.execute("SELECT name, script FROM "+scope.shell.dbtable("cf_nodes")+" WHERE discord_sid = ? ORDER BY name", [int(scope.server.id)]):
				await stream.send("\n\n:triangular_flag_on_post: **"+row[0]+"**")
				for link in c1.execute("SELECT node_start, script FROM "+scope.shell.dbtable("cf_links")+" WHERE discord_sid = ? AND node_start = ? AND node_end == node_start ORDER BY node_start", [int(scope.server.id), str(row[0])]):
					await stream.send("\n - Self link: **"+str(row[0])+"** → **"+str(row[0])+"**")
				for link in c1.execute("SELECT node_start, script FROM "+scope.shell.dbtable("cf_links")+" WHERE discord_sid = ? AND node_end = ? AND node_end != node_start ORDER BY node_start", [int(scope.server.id), str(row[0])]):
					await stream.send("\n - Incoming link: "+link[0]+" → **"+str(row[0])+"**")
				for link in c1.execute("SELECT node_end, script FROM "+scope.shell.dbtable("cf_links")+" WHERE discord_sid = ? AND node_start = ? AND node_end != node_start ORDER BY node_end", [int(scope.server.id), str(row[0])]):
					await stream.send("\n - Outcoming link: **"+str(row[0])+"** → "+link[0])
				if len(row[1]) > 0:
					await stream.send("\n - Script:")
					await stream.send("\n```\n"+row[1]+"\n```")

			await stream.send("\n\n__**List of links**__")
			for row in c0.execute("SELECT node_start, node_end, script, type, value FROM "+scope.shell.dbtable("cf_links")+" WHERE discord_sid = ? ORDER BY node_start, node_end", [int(scope.server.id)]):
				await stream.send("\n\n:link: **"+row[0]+" → "+row[1]+"**")
				if row[3] == LinkType.UserRegex:
					await stream.send("\n - Condition: user message match `"+row[4]+"`")
				elif row[3] == LinkType.Timeout:
					await stream.send("\n - Condition: timeout of "+row[4]+"")
				if len(row[2]) > 0:
					await stream.send("\n - Script:")
					await stream.send("\n```\n"+row[2]+"\n```")

		await stream.finish()

	@praxisbot.command
	@praxisbot.permission_script
	async def execute_start_cf_session(self, scope, command, options, lines, **kwargs):
		"""
		Start a conversational session
		"""

		parser = argparse.ArgumentParser(description=kwargs["description"], prog=command)
		parser.add_argument('node', help='Name of the starting node')
		args = await self.parse_options(scope, parser, options)
		if not args:
			return

		self.ensure_object_name("Node name", args.node)
		node_start = scope.shell.get_sql_data("cf_nodes", ["id"], {"discord_sid":int(scope.server.id), "name":str(args.node)})
		if not node_start:
			await scope.shell.print_error(scope, "Node `"+args.node+"` not found.")
			return

		self.start_session(scope.user, scope.channel, scope.server, args.node)
		await self.execute_session_node(scope.user, scope.channel, scope.server, scope)

	@praxisbot.command
	@praxisbot.permission_script
	async def execute_end_cf_session(self, scope, command, options, lines, **kwargs):
		"""
		End a conversational session
		"""

		parser = argparse.ArgumentParser(description=kwargs["description"], prog=command)
		args = await self.parse_options(scope, parser, options)
		if not args:
			return

		if not self.get_session(scope.user, scope.channel, scope.server):
			await scope.shell.print_error(scope, "No active conversational session found for you in this channel.")
			return

		self.end_session(scope.user, scope.channel, scope.server)


	@praxisbot.command
	async def execute_cf_sessions(self, scope, command, options, lines, **kwargs):
		"""
		List active conversational sessions
		"""

		parser = argparse.ArgumentParser(description=kwargs["description"], prog=command)
		args = await self.parse_options(scope, parser, options)
		if not args:
			return

		stream = praxisbot.MessageStream(scope)

		await stream.send("__**List of conversational sessions**__")

		for s in self.sessions:
			if scope.server.id != s[2]:
				continue

			user = scope.shell.find_member(s[0], scope.server)
			if not user:
				continue
			channel = scope.shell.find_channel(s[1], scope.server)
			if not channel:
				continue

			await stream.send("\n\n:speech_balloon: **Session with "+user.name+"#"+user.discriminator+" in "+channel.mention+"**")
			await stream.send("\n - Current node: "+self.sessions[s].current_node)
			await stream.send("\n - Start time: "+self.sessions[s].start_time.strftime("%Y-%m-%d %H:%M:%S"))
			await stream.send("\n - Last execution time: "+self.sessions[s].last_time.strftime("%Y-%m-%d %H:%M:%S"))

		await stream.finish()
