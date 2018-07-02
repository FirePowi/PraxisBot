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
import asyncio
import datetime
import copy
import io
from pytz import timezone
import praxisbot

class TriggerPlugin(praxisbot.Plugin):
	"""
	Trigger commands
	"""

	name = "Trigger"

	def __init__(self, shell):
		super().__init__(shell)

		self.time_triggers = {}

		self.shell.create_sql_table("triggers", ["id INTEGER PRIMARY KEY", "discord_sid INTEGER", "command TEXT", "script TEXT"])
		self.shell.create_sql_table("time_triggers", ["id INTEGER PRIMARY KEY", "discord_sid INTEGER", "script TEXT", "start_time DATETIME", "num_iterations INTEGER"])

		self.add_command("create_trigger", self.execute_create_trigger)
		self.add_command("edit_trigger", self.execute_edit_trigger)
		self.add_command("delete_trigger", self.execute_delete_trigger)
		self.add_command("show_trigger", self.execute_show_trigger)
		self.add_command("time_triggers", self.execute_time_triggers)
		self.add_command("create_time_trigger", self.execute_create_time_trigger)
		self.add_command("commands", self.execute_commands)

	async def execute_unregistered_command(self, scope, command, options, lines):
		return await self.execute_trigger_script(scope, command, options, lines)

	async def on_loop(self, scope):

		triggersToUpdate = {}

		c = scope.shell.dbcon.cursor()
		for row in c.execute("SELECT id, script, num_iterations, start_time, datetime('now') FROM "+scope.shell.dbtable("time_triggers")+" WHERE discord_sid = ? AND start_time < datetime('now')", [int(scope.server.id)]):
			triggersToUpdate[row[0]] = row[2]

			subScope = scope.create_subscope()
			subScope.prefixes = [""]
			await scope.shell.execute_script(subScope, row[1])


		for t in triggersToUpdate:
			if triggersToUpdate[t] <= 1:
				scope.shell.delete_sql_data("time_triggers", {"id": t})
			else:
				scope.shell.update_sql_data("time_triggers", {"num_iterations": int(triggersToUpdate[t]-1)}, {"id": t})

		return

	async def on_member_join(self, scope):
		await self.execute_trigger_script(scope, "@join", "", [])
		return True

	async def on_member_leave(self, scope):
		await self.execute_trigger_script(scope, "@leave", "", [])
		return True

	async def on_ban(self, scope):
		await self.execute_trigger_script(scope, "@ban", "", [])
		return True

	async def on_unban(self, scope):
		await self.execute_trigger_script(scope, "@unban", "", [])
		return True

	async def execute_trigger_script(self, scope, command, options, lines, **kwargs):
		script = scope.shell.get_sql_data("triggers", ["script"], {"discord_sid":int(scope.server.id), "command":command})
		if not script:
			return False

		subScope = scope.create_subscope()
		subScope.prefixes = [""]
		subScope.vars["params"] = options.strip()
		await scope.shell.execute_script(subScope, script[0])
		scope.continue_from_subscope(subScope)
		return True

	@praxisbot.command
	@praxisbot.permission_admin
	async def execute_create_trigger(self, scope, command, options, lines, **kwargs):
		"""
		Associate a script to a trigger. The script must be written on the line after the command.
		"""

		parser = argparse.ArgumentParser(description=kwargs["description"], prog=command)
		parser.add_argument('command', help='Name of the trigger')
		parser.add_argument('--force', '-f', action='store_true', help='Replace the trigger if it already exists')
		args = await self.parse_options(scope, parser, options)
		if not args:
			return

		if len(lines) == 0:
			await scope.shell.print_error(scope, "Missing script. Please write the script in the same message, just the line after the command. Ex.:```\ncreate_trigger my_new_command\nsay \"Hi {{@user}}!\"\nsay \"How are you?\"```")
			return

		if args.command not in ["@join", "@leave", "@ban", "@unban"]:
			self.ensure_object_name("Command name", args.command)

		trigger = scope.shell.get_sql_data("triggers", ["id"], {"discord_sid":int(scope.server.id), "command":str(args.command)})
		if trigger and not args.force:
			await scope.shell.print_error(scope, "Trigger `"+args.command+"` already exists. Please use --force to replace it.")
			return

		scope.shell.set_sql_data("triggers", {"script": "\n".join(lines)}, {"discord_sid":int(scope.server.id), "command":str(args.command)})
		if trigger:
			await scope.shell.print_success(scope, "Trigger `"+args.command+"` edited.")
		else:
			await scope.shell.print_success(scope, "Trigger `"+args.command+"` created.")

	@praxisbot.command
	@praxisbot.permission_script
	async def execute_create_time_trigger(self, scope, command, options, lines, **kwargs):
		"""
		Execute a script at a specified time.
		"""

		parser = argparse.ArgumentParser(description=kwargs["description"], prog=command)
		parser.add_argument('--time', help='Date and time. Must be in the format "YYYY-MM-DD HH-MM-SS".')
		parser.add_argument('--command', help='Command to execute.')
		args = await self.parse_options(scope, parser, options)
		if not args:
			return

		if len(lines) == 0:
			return

			await scope.shell.print_error(scope, "Time option not provided. Please use --time.")
			return

		num_iterations = 1
		try:
			if args.time:
				start_time = datetime.datetime.strptime(args.time, "%Y-%m-%d %H:%M:%S")
				start_time = timezone('Europe/Paris').localize(start_time)
				start_time = start_time.astimezone(timezone('UTC'))
			else:
				start_time = datetime.datetime.now(timezone('UTC'))
		except ValueError:
			await scope.shell.print_error(scope, "Date and time must be in the format \"yyyy-mm-dd HH:MM:SS\". Ex.: 2018-06-19 20:01:56.")
			return

		if args.command:
			script = args.command
		elif len(lines) > 0:
			script = "\n".join(lines)
		else:
			await scope.shell.print_error(scope, "Missing script. Please write the script in the same message, just the line after the command. Ex.:```\ncreate_time_trigger --time \"2018-06-19 20:01:56\"\nsay \"Hi {{@user}}!\"\nsay \"How are you?\"```")

		scope.shell.add_sql_data("time_triggers", {"discord_sid": int(scope.server.id), "script": script,  "start_time": str(start_time),  "num_iterations": num_iterations})
		await scope.shell.print_success(scope, "The script will be executed "+str(num_iterations)+" time at "+str(start_time)+".")

	@praxisbot.command
	@praxisbot.permission_admin
	async def execute_edit_trigger(self, scope, command, options, lines, **kwargs):
		"""
		Edit the script associated to a trigger. The script must be written on the line after the command.
		"""

		parser = argparse.ArgumentParser(description=kwargs["description"], prog=command)
		parser.add_argument('command', help='Name of the trigger')
		args = await self.parse_options(scope, parser, options)
		if not args:
			return

		if len(lines) == 0:
			await scope.shell.print_error(scope, "Missing script. Please write the script in the same message, just the line after the command. Ex.:```\nedit_trigger my_new_command\nsay \"Hi {{@user}}!\"\nsay \"How are you?\"```")
			return

		if args.command not in ["@join", "@leave", "@ban", "@unban"]:
			self.ensure_object_name("Command name", args.command)

		trigger = scope.shell.get_sql_data("triggers", ["id"], {"discord_sid":int(scope.server.id), "command":str(args.command)})
		if not trigger:
			await scope.shell.print_error(scope, "Trigger `"+args.command+"` not found.")
			return

		scope.shell.set_sql_data("triggers", {"script": "\n".join(lines)}, {"id":trigger[0]})
		await scope.shell.print_success(scope, "Trigger `"+args.command+"` edited.")

	@praxisbot.command
	@praxisbot.permission_admin
	async def execute_delete_trigger(self, scope, command, options, lines, **kwargs):
		"""
		Delete a trigger.
		"""

		parser = argparse.ArgumentParser(description=kwargs["description"], prog=command)
		parser.add_argument('command', help='Name of the trigger')
		args = await self.parse_options(scope, parser, options)
		if not args:
			return

		if args.command not in ["@join", "@leave", "@ban", "@unban"]:
			self.ensure_object_name("Command name", args.command)

		trigger = scope.shell.get_sql_data("triggers", ["id"], {"discord_sid":int(scope.server.id), "command":str(args.command)})
		if not trigger:
			await scope.shell.print_error(scope, "Trigger `"+args.command+"` not found.")
			return

		scope.shell.delete_sql_data("triggers", {"id":trigger[0]})
		await scope.shell.print_success(scope, "Trigger `"+args.command+"` deleted.")

	@praxisbot.command
	async def execute_show_trigger(self, scope, command, options, lines, **kwargs):
		"""
		Show the script associated to a trigger.
		"""

		parser = argparse.ArgumentParser(description=kwargs["description"], prog=command)
		parser.add_argument('command', help='Name of the trigger')
		args = await self.parse_options(scope, parser, options)
		if not args:
			return

		if args.command not in ["@join", "@leave", "@ban", "@unban"]:
			self.ensure_object_name("Command name", args.command)

		trigger = scope.shell.get_sql_data("triggers", ["script"], {"discord_sid":int(scope.server.id), "command":str(args.command)})
		if not trigger:
			await scope.shell.print_error(scope, "Trigger `"+args.command+"` not found.")
			return

		await scope.shell.print_info(scope, "```"+trigger[0]+"```")

	@praxisbot.command
	async def execute_commands(self, scope, command, options, lines, **kwargs):
		"""
		List all custom commands.
		"""

		parser = argparse.ArgumentParser(description=kwargs["description"], prog=command)
		args = await self.parse_options(scope, parser, options)
		if not args:
			return

		stream = praxisbot.MessageStream(scope)
		await stream.send("**List of commands**\n")

		with scope.shell.dbcon:
			c = scope.shell.dbcon.cursor()
			for row in c.execute("SELECT command FROM "+scope.shell.dbtable("triggers")+" WHERE discord_sid = ? ORDER BY command", [int(scope.server.id)]):
				if row[0].find("@") != 0:
					await stream.send("\n - "+row[0])

		await stream.finish()

	@praxisbot.command
	async def execute_time_triggers(self, scope, command, options, lines, **kwargs):
		"""
		List all time triggers.
		"""

		parser = argparse.ArgumentParser(description=kwargs["description"], prog=command)
		args = await self.parse_options(scope, parser, options)
		if not args:
			return

		stream = praxisbot.MessageStream(scope)
		await stream.send("**List of time triggers**\n")

		with scope.shell.dbcon:
			c = scope.shell.dbcon.cursor()
			for row in c.execute("SELECT script, start_time FROM "+scope.shell.dbtable("time_triggers")+" WHERE discord_sid = ? ORDER BY start_time", [int(scope.server.id)]):
				await stream.send("\n"+row[1]+"\n```"+row[0]+"```")

		await stream.finish()
