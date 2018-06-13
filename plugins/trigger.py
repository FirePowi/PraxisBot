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
from io import StringIO
from plugin import Plugin
from scope import UserPermission
from scope import ExecutionScope
from scope import ExecutionBlock

class TriggerPlugin(Plugin):
	"""
	Trigger commands
	"""

	name = "Trigger"

	def __init__(self, ctx):
		super().__init__(ctx)
		self.command_regex = re.compile('[a-zA-Z0-9_-]+')

		self.ctx.dbcon.execute("CREATE TABLE IF NOT EXISTS "+self.ctx.dbprefix+"triggers(id INTEGER PRIMARY KEY, discord_sid INTEGER, command TEXT, script TEXT)");

	async def get_trigger_script(self, command, server):
		with self.ctx.dbcon:
			c = self.ctx.dbcon.cursor()
			c.execute("SELECT script FROM "+self.ctx.dbprefix+"triggers WHERE discord_sid = ? AND command = ?", [int(server.id), command])
			r = c.fetchone()
			if r:
				return r[0]

		return None

	async def execute_script(self, shell, command, param, scope):
		script = await self.get_trigger_script(command, scope.server)
		if script:
			script = script.split("\n");
			subScope = scope
			subScope.level = subScope.level+1
			subScope.vars["params"] = param
			for s in script:
				args = s.split(" ");
				c = args[0]
				b = None
				if len(subScope.blocks) > 0:
					b = subScope.blocks[len(subScope.blocks)-1]
				if b and b.endname == c:
					subScope.blocks.pop()
				elif not b or b.execute:
					o = " ".join(args[1:])
					subScope = await shell.execute_command(c, o, subScope)
			scope = subScope
			scope.level = scope.level-1
		return scope


	#Command Add Trigger
	async def execute_add_trigger(self, command, options, scope):
		if scope.permission < UserPermission.Admin:
			await self.ctx.send_message(scope.channel, "Only admins can use this command.")
			return scope

		script = options.split("\n");
		if len(script) > 0:
			options = script[0]
			script = script[1:]

		parser = argparse.ArgumentParser(description='Associate a script to a trigger. The script must be written on the line after the command.', prog=command)
		parser.add_argument('command', help='Name of the trigger')
		parser.add_argument('--force', '-f', action='store_true', help='Replace the trigger if it already exists')

		args = await self.parse_options(scope.channel, parser, options)

		if args:
			if len(script) == 0:
				await self.ctx.send_message(scope.channel, "Missing script. Please write the script in the same message, just the line after the command. Ex.:```\nadd_trigger my_new_command\nsay \"Hi {{@user}}!\"\nsay \"How are you?\"```")
				return scope

			#Check if the command is valid
			if not (self.command_regex.fullmatch(args.command)) and (args.command not in ["@join", "@leave", "@ban", "@unban"]):
				await self.ctx.send_message(scope.channel, "The command `"+args.command+"` is not alphanumeric")
				return scope

			#Process
			command_chk = await self.get_trigger_script(args.command, scope.server)
			if command_chk:
				if args.force:
					with self.ctx.dbcon:
						if self.ctx.dbcon.execute("UPDATE "+self.ctx.dbprefix+"triggers SET script = ? WHERE discord_sid = ? AND command = ?", [str("\n".join(script)), int(scope.server.id), str(args.command)]):
							await self.ctx.send_message(scope.channel, "Trigger `"+args.command+"` edited.")
						else:
							await self.ctx.send_message(scope.channel, "Trigger `"+args.command+"` can't be edited (internal error).")
				else:
					await self.ctx.send_message(scope.channel, "Trigger `"+args.command+"` already exists. Please use --force to replace it.")
			else:
				with self.ctx.dbcon:
					if self.ctx.dbcon.execute("INSERT INTO "+self.ctx.dbprefix+"triggers (discord_sid, command, script) VALUES (?, ?, ?)", [int(scope.server.id), str(args.command), str("\n".join(script))]):
						await self.ctx.send_message(scope.channel, "Trigger `"+args.command+"` created.")
					else:
						await self.ctx.send_message(scope.channel, "Trigger `"+args.command+"` can't be created (internal error).")

		return scope

	#Command Delete Trigger
	async def execute_delete_trigger(self, command, options, scope):
		if scope.permission < UserPermission.Admin:
			await self.ctx.send_message(scope.channel, "Only admins can use this command.")
			return scope

		parser = argparse.ArgumentParser(description='Delete a trigger.', prog=command)
		parser.add_argument('command', help='Name of the trigger')

		args = await self.parse_options(scope.channel, parser, options)

		if args:
			#Process
			command_chk = await self.get_trigger_script(args.command, scope.server)
			if command_chk:
				with self.ctx.dbcon:
					if self.ctx.dbcon.execute("DELETE FROM "+self.ctx.dbprefix+"triggers WHERE discord_sid = ? AND command = ?", [int(scope.server.id), str(args.command)]):
						await self.ctx.send_message(scope.channel, "Trigger `"+args.command+"` deleted.")
					else:
						await self.ctx.send_message(scope.channel, "Trigger `"+args.command+"` can't be deleted (internal error).")
			else:
				await self.ctx.send_message(scope.channel, "Trigger `"+args.command+"` is unknown.")

		return scope

	#Command Show Trigger
	async def execute_show_trigger(self, command, options, scope):
		parser = argparse.ArgumentParser(description='Show the script associated to a trigger.', prog=command)
		parser.add_argument('command', help='Name of the trigger')

		args = await self.parse_options(scope.channel, parser, options)

		if args:
			#Process
			command_chk = await self.get_trigger_script(args.command, scope.server)
			if command_chk:
				await self.ctx.send_message(scope.channel, "```"+command_chk+"```")
			else:
				await self.ctx.send_message(scope.channel, "Trigger `"+args.command+"` is unknown.")

		return scope

	async def execute_command(self, shell, command, options, scope):
		if command == "add_trigger":
			scope.iter = scope.iter+1
			return await self.execute_add_trigger(command, options, scope)
		elif command == "delete_trigger":
			scope.iter = scope.iter+1
			return await self.execute_delete_trigger(command, options, scope)
		elif command == "show_trigger":
			scope.iter = scope.iter+1
			return await self.execute_show_trigger(command, options, scope)
		elif self.command_regex.fullmatch(command):
			return await self.execute_script(shell, command, options, scope)

		return scope

	async def on_member_join(self, shell, scope):
		await self.execute_script(shell, "@join", "", scope)
		return True

	async def on_member_leave(self, shell, scope):
		await self.execute_script(shell, "@leave", "", scope)
		return True

	async def on_ban(self, shell, scope):
		await self.execute_script(shell, "@ban", "", scope)
		return True

	async def on_unban(self, shell, server, scope):
		await self.execute_script(shell, "@unban", "", scope)
		return True
