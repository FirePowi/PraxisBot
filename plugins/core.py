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
		parser = argparse.ArgumentParser(description='Perform tests. Don\'t forget to add an endif line.', prog=command)
		parser.add_argument('firstvar', help='First values', metavar='VALUE')
		parser.add_argument('--equal', help='Test if A = B', metavar='VALUE')
		parser.add_argument('--hasroles', nargs='+', help='Test if a member has one of the listed roles', metavar='ROLE')
		parser.add_argument('--ismember', action='store_true', help='Test if a parameter is a valid member')
		parser.add_argument('--not', dest='inverse', action='store_true', help='Inverse the result of the test')

		args = await self.parse_options(scope.channel, parser, options)

		if args:
			res = False
			if args.equal:
				a = self.ctx.format_text(args.firstvar, scope)
				b = self.ctx.format_text(args.equal, scope)
				res = (a == b)
			elif args.ismember:
				u = self.ctx.find_member(self.ctx.format_text(args.firstvar, scope), scope.server)
				res = (u != None)
			elif args.hasroles:
				u = self.ctx.find_member(self.ctx.format_text(args.firstvar, scope), scope.server)
				r = []
				for i in args.hasroles:
					formatedRole = self.ctx.format_text(i, scope)
					role = self.ctx.find_role(formatedRole, scope.server)
					if role:
						r.append(role)
				if u:
					for i in u.roles:
						for j in r:
							if i.id == j.id:
								res = True
								break
						if res:
							break

			if args.inverse:
				res = not res

			newScope = scope
			newScope.blocks.append(ExecutionBlock("endif", res))
			return newScope

		return scope

	async def execute_add_roles(self, command, options, scope):
		if scope.permission < UserPermission.Script:
			return scope

		parser = argparse.ArgumentParser(description='Add roles to a member.', prog=command)
		parser.add_argument('user', help='User name')
		parser.add_argument('roles', nargs='+', help='A list of roles')
		parser.add_argument('--silent', '-s', action='store_true',  help='Don\'t print messages')

		args = await self.parse_options(scope.channel, parser, options)

		if args:
			formatedUser = self.ctx.format_text(args.user, scope)
			u = self.ctx.find_member(formatedUser, scope.server)
			if not u:
				return scope

			r = []
			for a in args.roles:
				formatedRole = self.ctx.format_text(a, scope)
				role = self.ctx.find_role(formatedRole, scope.server)
				if role:
					r.append(role)

			res = await self.ctx.add_roles(u, r)
			if not args.silent:
				if res:
					output = "The following roles has been added to "+u.display_name+":"
					for i in r:
						output = output + "\n :white_check_mark: " + i.name
					await self.ctx.send_message(scope.channel, output)
				else:
					output = "The following roles has not been added to "+u.display_name+":"
					for i in r:
						output = output + "\n :x: " + r.name
					await self.ctx.send_message(scope.channel, output)

		return scope

	async def execute_remove_roles(self, command, options, scope):
		if scope.permission < UserPermission.Script:
			return scope

		parser = argparse.ArgumentParser(description='Remove roles to a member.', prog=command)
		parser.add_argument('user', help='User name')
		parser.add_argument('roles', nargs='+', help='A list of roles')
		parser.add_argument('--silent', '-s', action='store_true',  help='Don\'t print messages')

		args = await self.parse_options(scope.channel, parser, options)

		if args:
			formatedUser = self.ctx.format_text(args.user, scope)
			u = self.ctx.find_member(formatedUser, scope.server)
			r = []
			for a in args.roles:
				formatedRole = self.ctx.format_text(a, scope)
				role = self.ctx.find_role(formatedRole, scope.server)
				if role:
					r.append(role)

			res = await self.ctx.remove_roles(u, r)
			if not args.silent:
				if res:
					output = "The following roles has been removed from "+u.display_name+":"
					for i in r:
						output = output + "\n :white_check_mark: " + i.name
					await self.ctx.send_message(scope.channel, output)
				else:
					output = "The following roles has not been removed from "+u.display_name+":"
					for i in r:
						output = output + "\n :x: " + r.name
					await self.ctx.send_message(scope.channel, output)

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

		if len(script) == 0:
			await self.ctx.send_message(scope.channel, "Missing script. Please write the script in the same message, just the line after the command. Ex.:```\nscript\nsay \"Hi {{@user}}!\"\nsay \"How are you?\"```")
			return scope

		return await self.execute_script(shell, script, scope)

	async def execute_for_members(self, shell, command, options, scope):

		if scope.permission < UserPermission.Owner:
			await self.ctx.send_message(scope.channel, "Only server owner can run this command.")
			return scope

		subScope = scope
		for m in scope.server.members:
			if not m.bot:
				subScope.vars["iter"] = m.mention
				subScope.level = subScope.level+1
				c = options.strip().split(" ")
				o = c[1:]
				c = c[0]
				subScope = await shell.execute_command(c, " ".join(o).replace("{{iter}}", m.mention), subScope)

		newScope = subScope
		newScope.level = newScope.level-1
		return newScope

	async def execute_exit(self, shell, command, options, scope):

		newScope = scope
		newScope.abort = True
		return newScope

	async def list_commands(self, server):
		return ["say", "if", "set_variable", "add_roles", "remove_roles", "set_command_prefix", "script", "exit", "for_members"]

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
		elif command == "add_roles":
			scope.iter = scope.iter+1
			return await self.execute_add_roles(command, options, scope)
		elif command == "remove_roles":
			scope.iter = scope.iter+1
			return await self.execute_remove_roles(command, options, scope)
		elif command == "set_command_prefix":
			scope.iter = scope.iter+1
			return await self.execute_set_command_prefix(command, options, scope)
		elif command == "script":
			scope.iter = scope.iter+1
			return await self.execute_script_cmd(shell, command, options, scope)
		elif command == "exit":
			scope.iter = scope.iter+1
			return await self.execute_exit(shell, command, options, scope)
		elif command == "for_members":
			scope.iter = scope.iter+1
			return await self.execute_for_members(shell, command, options, scope)

		return scope
