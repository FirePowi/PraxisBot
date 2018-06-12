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

import shlex
import argparse
import re
from io import StringIO
from plugin import Plugin
from plugin import UserPermission

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
	
	async def execute_script(self, shell, command, param, server, channel, author, perm, level):
		script = await self.get_trigger_script(command, server)
		if script:
			script = script.split("\n");
			for s in script:
				args = s.split(" ");
				c = args[0]
				o = " ".join(args[1:]).replace("{{param}}", param)
				await shell.execute_command(c, o, server, channel, author, perm, level+1)
			return True
		return False
		
	
	#Command Add Trigger
	async def execute_add_trigger(self, command, options, server, channel, author, perm, level):
		if level > 0:
			return True
		if perm < UserPermission.Admin:
			return True
		
		script = options.split("\n");
		if len(script) > 0:
			options = script[0]
			script = script[1:]
		
		parser = argparse.ArgumentParser(description='Associate a script to a trigger. The script must be written on the line after the command.', prog=command)
		parser.add_argument('command', help='Name of the trigger')
		parser.add_argument('--force', '-f', action='store_true', help='Replace the trigger if it already exists')
		
		args = await self.parse_options(channel, parser, options)
		
		if args:
			if len(script) == 0:
				await self.ctx.send_message(channel, "Missing script. Please write the script in the same message, just the line after the command. Ex.:```\nadd_trigger my_new_command\nsay \"Hi {{@user}}!\"\nsay \"How are you?\"```")
				return True
			
			#Check if the command is valid
			if not (self.command_regex.fullmatch(args.command)) and (args.command not in ["@join", "@leave", "@ban", "@unban"]):
				await self.ctx.send_message(channel, "The command `"+args.command+"` is not alphanumeric")
				return True
			
			#Process
			command_chk = await self.get_trigger_script(args.command, server)
			if command_chk:
				if args.force:
					with self.ctx.dbcon:
						if self.ctx.dbcon.execute("UPDATE "+self.ctx.dbprefix+"triggers SET script = ? WHERE discord_sid = ? AND command = ?", [str("\n".join(script)), int(server.id), str(args.command)]):
							await self.ctx.send_message(channel, "Trigger `"+args.command+"` edited.")
						else:
							await self.ctx.send_message(channel, "Trigger `"+args.command+"` can't be edited (internal error).")
				else:
					await self.ctx.send_message(channel, "Trigger `"+args.command+"` already exists. Please use --force to replace it.")
			else:
				with self.ctx.dbcon:
					if self.ctx.dbcon.execute("INSERT INTO "+self.ctx.dbprefix+"triggers (discord_sid, command, script) VALUES (?, ?, ?)", [int(server.id), str(args.command), str("\n".join(script))]):
						await self.ctx.send_message(channel, "Trigger `"+args.command+"` created.")
					else:
						await self.ctx.send_message(channel, "Trigger `"+args.command+"` can't be created (internal error).")
		
		return True
	
	#Command Delete Trigger
	async def execute_delete_trigger(self, command, options, server, channel, author, perm, level):
		if level > 0:
			return True
		if perm < UserPermission.Admin:
			return True
		
		parser = argparse.ArgumentParser(description='Delete a trigger.', prog=command)
		parser.add_argument('command', help='Name of the trigger')
		
		args = await self.parse_options(channel, parser, options)
		
		if args:
			#Process
			command_chk = await self.get_trigger_script(args.command, server)
			if command_chk:
				with self.ctx.dbcon:
					if self.ctx.dbcon.execute("DELETE FROM "+self.ctx.dbprefix+"triggers WHERE discord_sid = ? AND command = ?", [int(server.id), str(args.command)]):
						await self.ctx.send_message(channel, "Trigger `"+args.command+"` deleted.")
					else:
						await self.ctx.send_message(channel, "Trigger `"+args.command+"` can't be deleted (internal error).")
			else:
				await self.ctx.send_message(channel, "Trigger `"+args.command+"` is unknown.")
		
		return True
	
	#Command Show Trigger
	async def execute_show_trigger(self, command, options, server, channel, author, perm, level):
		if level > 0:
			return True
		if perm < UserPermission.Member:
			return True
		
		parser = argparse.ArgumentParser(description='Show the script associated to a trigger.', prog=command)
		parser.add_argument('command', help='Name of the trigger')
		
		args = await self.parse_options(channel, parser, options)
		
		if args:
			#Process
			command_chk = await self.get_trigger_script(args.command, server)
			if command_chk:
				await self.ctx.send_message(channel, "```"+command_chk+"```")
			else:
				await self.ctx.send_message(channel, "Trigger `"+args.command+"` is unknown.")
		
		return True
	
	async def execute_command(self, shell, command, options, server, channel, author, perm, level):
		if command == "add_trigger":
			return await self.execute_add_trigger(command, options, server, channel, author, perm, level)
		elif command == "delete_trigger":
			return await self.execute_delete_trigger(command, options, server, channel, author, perm, level)
		elif command == "show_trigger":
			return await self.execute_show_trigger(command, options, server, channel, author, perm, level)
		elif self.command_regex.fullmatch(command):
			return await self.execute_script(shell, command, options, server, channel, author, UserPermission.Script, level+1)
		
		return False
	
	async def on_member_join(self, shell, member):
		s = member.server
		await self.execute_script(shell, "@join", "", s, self.ctx.get_default_channel(s), member, UserPermission.Script, 1)
		return True
	
	async def on_member_leave(self, shell, member):
		s = member.server
		await self.execute_script(shell, "@leave", "", s, self.ctx.get_default_channel(s), member, UserPermission.Script, 1)
		return True
	
	async def on_ban(self, shell, member):
		s = member.server
		await self.execute_script(shell, "@ban", "", s, self.ctx.get_default_channel(s), member, UserPermission.Script, 1)
		return True
	
	async def on_unban(self, shell, server, user):
		s = server
		await self.execute_script(shell, "@unban", "", s, self.ctx.get_default_channel(s), user, UserPermission.Script, 1)
		return True
