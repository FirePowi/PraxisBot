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

class CorePlugin(Plugin):
	"""
	Core commands
	"""
	
	name = "Core"
	
	def __init__(self, ctx):
		super().__init__(ctx)
	
	async def execute_say(self, command, options, server, channel, author, perm, level):
		parser = argparse.ArgumentParser(description='Send a message.', prog=command)
		parser.add_argument('message', help='Text to send')
		parser.add_argument('--channel', '-c', help='Channel where to send the message')
		
		args = await self.parse_options(channel, parser, options)
		
		if args:
			dest_chan = self.ctx.find_channel(args.channel, server)
			if not dest_chan:
				dest_chan = channel
		
			formatedText = self.ctx.format_text(args.message, arg_channel=channel, arg_user=author)
			await self.ctx.send_message(dest_chan, formatedText)
		
		return True
	
	async def execute_add_role(self, command, options, server, channel, author, perm, level):
		if perm < UserPermission.Script:
			return True
		
		parser = argparse.ArgumentParser(description='Add a role to an user.', prog=command)
		parser.add_argument('user', help='User name')
		parser.add_argument('role', help='Role name')
		
		args = await self.parse_options(channel, parser, options)
		
		if args:
			if await self.ctx.add_role(server, args.user, args.role):
				return True
			else:
				await self.ctx.send_message(channel, "Can't add role `"+args.role+"` to `"+args.user+"`.")
		
		return True
		
	async def execute_remove_role(self, command, options, server, channel, author, perm, level):
		if perm < UserPermission.Script:
			return True
		
		parser = argparse.ArgumentParser(description='Remove a role to an user.', prog=command)
		parser.add_argument('user', help='User name')
		parser.add_argument('role', help='Role name')
		
		args = await self.parse_options(channel, parser, options)
		
		if args:
			if await self.ctx.remove_role(server, args.user, args.role):
				return True
			else:
				await self.ctx.send_message(channel, "Can't remove role `"+args.role+"` to `"+args.user+"`.")
		
		return True
		
	async def execute_set_command_prefix(self, command, options, server, channel, author, perm, level):
		if perm < UserPermission.Admin:
			return True
		
		parser = argparse.ArgumentParser(description='Set the prefix used to write commands.', prog=command)
		parser.add_argument('prefix', help='Prefix')
		
		args = await self.parse_options(channel, parser, options)
		
		if args:
			if self.ctx.set_command_prefix(server, args.prefix):
				await self.ctx.send_message(channel, "Command prefix changed to ``"+args.prefix+"``.")
				return True
		
		await self.ctx.send_message(channel, "Can't change the command prefix.")
		return True
		
	async def execute_command(self, shell, command, options, server, channel, author, perm, level):
		if command == "say":
			return await self.execute_say(command, options, server, channel, author, perm, level)
		elif command == "add_role":
			return await self.execute_add_role(command, options, server, channel, author, perm, level)
		elif command == "remove_role":
			return await self.execute_remove_role(command, options, server, channel, author, perm, level)
		elif command == "set_command_prefix":
			return await self.execute_set_command_prefix(command, options, server, channel, author, perm, level)
		
		return False
