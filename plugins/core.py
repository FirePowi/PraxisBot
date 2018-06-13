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
		parser.add_argument('--equal', action='store_true', help='Test if A = B')
		parser.add_argument('--hasrole', action='store_true', help='Test if the user A has the role B')
		parser.add_argument('--inverse', action='store_true', help='Inverse the result of the test')
		parser.add_argument('--exit', action='store_true', help='Abort execution if not true')

		args = await self.parse_options(scope.channel, parser, options)

		if args:
			a = self.ctx.format_text(args.a, scope)
			b = self.ctx.format_text(args.b, scope)
			
			res = False
			if args.equal:
				res = (a == b)
			elif args.hasrole:
				u = self.ctx.find_member(a, scope.server)
				r = self.ctx.find_role(b, scope.server)
				if r and u:
					for i in u.roles:
						if i.id == r.id:
							res = True
							break
			if args.inverse:
				res = not res

			newScope = scope
			if args.exit and not res:
				newScope.abort = True
			else:
				newScope.blocks.append(ExecutionBlock("endif", res))
			return newScope

		return scope

	async def execute_add_role(self, command, options, scope):
		if scope.permission < UserPermission.Script:
			return scope

		parser = argparse.ArgumentParser(description='Add a role to an user.', prog=command)
		parser.add_argument('user', help='User name')
		parser.add_argument('role', help='Role name')
		parser.add_argument('--silent', '-s', action='store_true',  help='Don\'t print errors')

		args = await self.parse_options(scope.channel, parser, options)

		if args:
			u = self.ctx.format_text(args.user, scope)
			r = self.ctx.format_text(args.role, scope)
			if await self.ctx.add_role(scope.server, u, r):
				return scope
			elif not args.silent:
				await self.ctx.send_message(scope.channel, "Can't add role `"+r+"` to `"+u+"`.")

		return scope

	async def execute_remove_role(self, command, options, scope):
		if scope.permission < UserPermission.Script:
			return scope

		parser = argparse.ArgumentParser(description='Remove a role to an user.', prog=command)
		parser.add_argument('user', help='User name')
		parser.add_argument('role', help='Role name')
		parser.add_argument('--silent', '-s', action='store_true',  help='Don\'t print errors')

		args = await self.parse_options(scope.channel, parser, options)

		if args:
			u = self.ctx.format_text(args.user, scope)
			r = self.ctx.format_text(args.role, scope)
			if await self.ctx.remove_role(scope.server, u, r):
				return scope
			elif not args.silent:
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

	async def execute_script_cmd(self, shell, command, options, scope):

		script = options.split("\n");
		if len(script) > 0:
			options = script[0]
			script = script[1:]

		parser = argparse.ArgumentParser(description='Execute all commands after the first line.', prog=command)

		args = await self.parse_options(scope.channel, parser, options)

		if args:
			if len(script) == 0:
				await self.ctx.send_message(scope.channel, "Missing script. Please write the script in the same message, just the line after the command. Ex.:```\nscript\nsay \"Hi {{@user}}!\"\nsay \"How are you?\"```")
				return scope

			return await self.execute_script(shell, script, scope)

		return scope

	async def list_commands(self, server):
		return ["say", "if", "set_variable", "add_role", "remove_role", "set_command_prefix", "script"]

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
		elif command == "script":
			scope.iter = scope.iter+1
			return await self.execute_script_cmd(shell, command, options, scope)

		return scope
