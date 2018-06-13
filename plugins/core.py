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
from io import StringIO
from plugin import Plugin
from scope import UserPermission
from scope import ExecutionScope
from scope import ExecutionBlock

class CorePlugin(Plugin):
	"""
	Core commands
	"""

	name = "Core"

	def __init__(self, ctx):
		super().__init__(ctx)

	async def execute_say(self, command, options, scope):
		parser = argparse.ArgumentParser(description='Send a message.', prog=command)
		parser.add_argument('message', help='Text to send')
		parser.add_argument('--channel', '-c', help='Channel where to send the message')
		parser.add_argument('--title', '-t', help='Embed title')
		parser.add_argument('--description', '-d', help='Embed description')
		parser.add_argument('--footer', '-f', help='Embed footer')
		parser.add_argument('--image', '-i', help='Embed image')
		parser.add_argument('--thumbnail', '-m', help='Embed thumbnail')

		args = await self.parse_options(scope.channel, parser, options)

		if args:
			subScope = scope
			if args.channel:
				c = self.ctx.find_channel(self.ctx.format_text(args.channel, scope), scope.server)
				if c:
					subScope.channel = c

			formatedText = self.ctx.format_text(args.message, subScope)

			e = None
			if args.title or args.description or args.footer or args.image or args.thumbnail:
				e = discord.Embed();
				e.type = "rich"
				if args.title:
					e.title = self.ctx.format_text(args.title, subScope)
				if args.description:
					e.description = self.ctx.format_text(args.description, subScope)
				if args.footer:
					e.set_footer(text=self.ctx.format_text(args.footer, subScope))
				if args.image:
					e.set_image(url=self.ctx.format_text(args.image, subScope))
				if args.thumbnail:
					e.set_thumbnail(url=self.ctx.format_text(args.thumbnail, subScope))

			await self.ctx.send_message(subScope.channel, formatedText, e)

		return scope

	async def execute_set_variable(self, command, options, scope):
		parser = argparse.ArgumentParser(description='Set a variable.', prog=command)
		parser.add_argument('name', help='Variable name')
		parser.add_argument('value', help='Variable value')

		args = await self.parse_options(scope.channel, parser, options)

		if args:
			var = self.ctx.format_text(args.name, scope)
			val = self.ctx.format_text(args.value, scope)
			if not re.fullmatch('[a-zA-Z_][a-zA-Z0-9_]*', var):
				await self.ctx.send_message(scope.channel, "Variables must be alphanumeric.")
				return scope
			if var in ["user", "channel", "server", "user_avatar", "user_time", "params", "n"]:
				await self.ctx.send_message(scope.channel, "This variable is reserved.")
				return scope

			scope.vars[var] = val

		return scope

	async def execute_if(self, command, options, scope):
		parser = argparse.ArgumentParser(description='Perform tests. Don\'t forget to add a endif line.', prog=command)
		parser.add_argument('a', help='Value A')
		parser.add_argument('b', help='Value B')
		parser.add_argument('--equal', '-e', action='store_true', help='Test if A = B')
		parser.add_argument('--nequal', '-n', action='store_true', help='Test if A = B')

		args = await self.parse_options(scope.channel, parser, options)

		if args:
			a = self.ctx.format_text(args.a, scope)
			b = self.ctx.format_text(args.b, scope)
			if args.equal:
				newScope = scope
				newScope.blocks.append(ExecutionBlock("endif", (a == b)))
			elif args.nequal:
				newScope = scope
				newScope.blocks.append(ExecutionBlock("endif", (a != b)))
		return scope

	async def execute_add_role(self, command, options, scope):
		if scope.permission < UserPermission.Script:
			return scope

		parser = argparse.ArgumentParser(description='Add a role to an user.', prog=command)
		parser.add_argument('user', help='User name')
		parser.add_argument('role', help='Role name')

		args = await self.parse_options(scope.channel, parser, options)

		if args:
			u = self.ctx.format_text(args.user, scope)
			r = self.ctx.format_text(args.role, scope)
			if await self.ctx.add_role(scope.server, u, r):
				return scope
			else:
				await self.ctx.send_message(scope.channel, "Can't add role `"+r+"` to `"+u+"`.")

		return scope

	async def execute_remove_role(self, command, options, scope):
		if scope.permission < UserPermission.Script:
			return scope

		parser = argparse.ArgumentParser(description='Remove a role to an user.', prog=command)
		parser.add_argument('user', help='User name')
		parser.add_argument('role', help='Role name')

		args = await self.parse_options(scope.channel, parser, options)

		if args:
			u = self.ctx.format_text(args.user, scope)
			r = self.ctx.format_text(args.role, scope)
			if await self.ctx.remove_role(scope.server, u, r):
				return scope
			else:
				await self.ctx.send_message(scope.channel, "Can't remove role `"+r+"` to `"+u+"`.")

		return scope

	async def execute_set_command_prefix(self, command, options, scope):
		if scope.permission < UserPermission.Admin:
			return scope

		parser = argparse.ArgumentParser(description='Set the prefix used to write commands.', prog=command)
		parser.add_argument('prefix', help='Prefix')

		args = await self.parse_options(scope.channel, parser, options)

		if args:
			if self.ctx.set_command_prefix(scope.server, args.prefix):
				await self.ctx.send_message(scope.channel, "Command prefix changed to ``"+args.prefix+"``.")
				return scope

		await self.ctx.send_message(scope.channel, "Can't change the command prefix.")
		return scope

	async def execute_command(self, shell, command, options, scope):
		if command == "say":
			scope.iter = scope.iter+1
			return await self.execute_say(command, options, scope)
		elif command == "if":
			scope.iter = scope.iter+1
			return await self.execute_if(command, options, scope)
		elif command == "set_variable":
			scope.iter = scope.iter+1
			return await self.execute_set_variable(command, options, scope)
		elif command == "add_role":
			scope.iter = scope.iter+1
			return await self.execute_add_role(command, options, scope)
		elif command == "remove_role":
			scope.iter = scope.iter+1
			return await self.execute_remove_role(command, options, scope)
		elif command == "set_command_prefix":
			scope.iter = scope.iter+1
			return await self.execute_set_command_prefix(command, options, scope)

		return scope
