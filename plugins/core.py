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
import copy
import inspect
import datetime
import praxisbot
from io import StringIO

class CorePlugin(praxisbot.Plugin):
	"""
	Core commands
	"""

	name = "Core"

	def __init__(self, shell):
		super().__init__(shell)

		self.shell.create_sql_table("variables", ["id INTEGER PRIMARY KEY", "discord_sid INTEGER", "name TEXT", "value TEXT"])

		self.add_command("help", self.execute_help)
		self.add_command("say", self.execute_say)
		self.add_command("if", self.execute_if)
		self.add_command("set_variable", self.execute_set_variable)
		self.add_command("variables", self.execute_variables)
		self.add_command("change_roles", self.execute_change_roles)
		self.add_command("set_command_prefix", self.execute_set_command_prefix)
		self.add_command("script", self.execute_script)
		self.add_command("exit", self.execute_exit)
		self.add_command("for", self.execute_for)
		self.add_command("regex", self.execute_regex)
		self.add_command("whois", self.execute_whois)
		self.add_command("delete_message", self.execute_delete_message)
		self.add_command("silent", self.execute_silent)

	@praxisbot.command
	async def execute_help(self, scope, command, options, lines, **kwargs):
		"""
		Help page of PraxisBot.
		"""

		stream = praxisbot.MessageStream(scope)
		for p in scope.shell.plugins:
			await stream.send("\n**"+p.name+"**\n\n")
			for c in p.cmds:
				desc =	inspect.getdoc(p.cmds[c])
				if desc:
					await stream.send(" - `"+c+"` : "+desc+"\n")
				else:
					await stream.send(" - `"+c+"`\n")

		await stream.finish()

	@praxisbot.command
	async def execute_script(self, scope, command, options, lines, **kwargs):
		"""
		Execute a list of commands.
		"""

		parser = argparse.ArgumentParser(description=kwargs["description"], prog=command)
		args = await self.parse_options(scope, parser, options)
		if not args:
			return

		if len(lines) == 0:
			await scope.shell.print_error(scope, "Missing script. Please write the script in the same message, just the line after the command. Ex.:```\nscript\nsay \"Hi {{@user}}!\"\nsay \"How are you?\"```")
			return

		subScope = scope.create_subscope()
		subScope.prefixes = [""]
		await scope.shell.execute_script(subScope, "\n".join(lines))
		scope.continue_from_subscope(subScope)


	@praxisbot.command
	async def execute_exit(self, scope, command, options, lines, **kwargs):
		"""
		Stop the execution of the current script.
		"""

		parser = argparse.ArgumentParser(description=kwargs["description"], prog=command)
		args = await self.parse_options(scope, parser, options)
		if not args:
			return

		scope.abort = True
		return scope

	@praxisbot.command
	async def execute_if(self, scope, command, options, lines, **kwargs):
		"""
		Check conditions. Used with `else` and `endif`.
		"""

		parser = argparse.ArgumentParser(description=kwargs["description"], prog=command)
		parser.add_argument('firstvar', help='First values', metavar='VALUE')
		parser.add_argument('--equal', help='Test if A = B', metavar='VALUE')
		parser.add_argument('--hasroles', nargs='+', help='Test if a member has one of the listed roles', metavar='ROLE')
		parser.add_argument('--ismember', action='store_true', help='Test if a parameter is a valid member')
		parser.add_argument('--not', dest='inverse', action='store_true', help='Inverse the result of the test')
		parser.add_argument('--find', help='Return truc if an occurence of B is found in A (case insensitive)')
		args = await self.parse_options(scope, parser, options)
		if not args:
			return

		res = False
		if args.equal:
			a = scope.format_text(args.firstvar)
			b = scope.format_text(args.equal)
			res = (a == b)
		elif args.find:
			a = scope.format_text(args.firstvar).lower()
			b = scope.format_text(args.find).lower()
			res = (a.find(b) >= 0)
		elif args.ismember:
			u = scope.shell.find_member(scope.format_text(args.firstvar), scope.server)
			res = (u != None)
		elif args.hasroles:
			u = scope.shell.find_member(scope.format_text(args.firstvar), scope.server)
			r = []
			for i in args.hasroles:
				formatedRole = scope.format_text(i)
				role = scope.shell.find_role(formatedRole, scope.server)
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

		scope.blocks.append(praxisbot.ExecutionBlockIf(res))

	@praxisbot.command
	async def execute_for(self, scope, command, options, lines, **kwargs):
		"""
		Execute commands until condition. Used with `endfor`.
		"""

		for b in scope.blocks:
			print(type(b).__name__)
			if type(b).__name__ == "ExecutionBlockFor":
				await scope.shell.print_error(scope, "Only one level of loop is allowed.")
				scope.abort = True
				return

		parser = argparse.ArgumentParser(description=kwargs["description"], prog=command)
		parser.add_argument('name', help='Name of the iterator', metavar='VALUE')
		parser.add_argument('--in', dest="list", nargs='+', help='List of elements', metavar='ELEMENT')
		parser.add_argument('--inset', help='Name of a variable containing a set', metavar='VARIABLE')
		args = await self.parse_options(scope, parser, options)
		if not args:
			return

		var = scope.format_text(args.name)
		self.ensure_object_name("Variable name", var)

		if args.list:
			list = args.list
		elif args.inset:
			val = scope.vars[args.inset]
			list = val.split("\n")
		else:
			list = []

		scope.blocks.append(praxisbot.ExecutionBlockFor(var, list))

	@praxisbot.command
	async def execute_set_variable(self, scope, command, options, lines, **kwargs):
		"""
		Update local and global variables.
		"""

		parser = argparse.ArgumentParser(description=kwargs["description"], prog=command)
		parser.add_argument('name', help='Variable name')
		parser.add_argument('value', help='Variable value')
		parser.add_argument('--global', dest='glob', action='store_true', help='Set the variable for all commands on this server')
		parser.add_argument('--intadd', action='store_true', help='Add the integer value to the variable')
		parser.add_argument('--intremove', action='store_true', help='Remove the integer value from the variable')
		parser.add_argument('--setadd', action='store_true', help='Add element in the set')
		parser.add_argument('--setremove', action='store_true', help='Remove element from the set')
		args = await self.parse_options(scope, parser, options)
		if not args:
			return

		if args.glob and scope.permission < praxisbot.UserPermission.Script:
			raise praxisbot.ParameterPermissionError("--global")

		var = scope.format_text(args.name)
		self.ensure_object_name("Variable name", var)

		val = scope.format_text(args.value)

		if args.intadd:
			try:
				val = str(int(scope.vars[var]) + int(val))
			except ValueError:
				val = str(scope.vars[var])
				pass
		elif args.intremove:
			try:
				val = str(int(scope.vars[var]) - int(val))
			except ValueError:
				val = str(scope.vars[var])
				pass
		elif args.setadd:
			try:
				if var in scope.vars:
					s = set(str(scope.vars[var]).split("\n"))
					s.add(val)
					val = "\n".join(s)
			except ValueError:
				val = str(scope.vars[var])
				pass
		elif args.setremove:
			try:
				if var in scope.vars:
					s = set(str(scope.vars[var]).split("\n"))
					s.discard(val)
					val = "\n".join(s)
			except ValueError:
				val = str(scope.vars[var])
				pass

		scope.vars[var] = val

		if args.glob:
			scope.shell.set_sql_data("variables", {"discord_sid": int(scope.server.id), "name": str(var)}, {"value":str(val)})

		await scope.shell.print_success(scope, "`"+str(var)+"` is now equal to:\n```"+str(val)+"```")


	@praxisbot.command
	async def execute_variables(self, scope, command, options, lines, **kwargs):
		"""
		List all current variables.
		"""

		parser = argparse.ArgumentParser(description=kwargs["description"], prog=command)
		args = await self.parse_options(scope, parser, options)
		if not args:
			return

		stream = praxisbot.MessageStream(scope)
		await stream.send("**List of variables**\n")
		for v in scope.vars:
			if scope.vars[v].find("\n") >= 0:
				await stream.send("\n"+v+" = \n```"+scope.vars[v]+"```")
			else:
				await stream.send("\n"+v+" = `"+scope.vars[v]+"`")
		await stream.finish()


	@praxisbot.command
	async def execute_say(self, scope, command, options, lines, **kwargs):
		"""
		Send a message.
		"""

		parser = argparse.ArgumentParser(description=kwargs["description"], prog=command)
		parser.add_argument('message', help='Text to send')
		parser.add_argument('--channel', '-c', help='Channel where to send the message')
		parser.add_argument('--title', '-t', help='Embed title')
		parser.add_argument('--description', '-d', help='Embed description')
		parser.add_argument('--footer', '-f', help='Embed footer')
		parser.add_argument('--image', '-i', help='Embed image')
		parser.add_argument('--thumbnail', '-m', help='Embed thumbnail')
		args = await self.parse_options(scope, parser, options)
		if not args:
			return

		if args.channel:
			chan = scope.shell.find_channel(args.channel, scope.server)
		else:
			chan = scope.channel

		if not chan:
			await scope.shell.print_error(scope, "Unknown channel.")
			return

		if not chan.permissions_for(scope.user).send_messages:
			await scope.shell.print_permission(scope, "You don't have write permission in this channel.")
			return

		subScope = scope.create_subscope()
		subScope.channel = chan

		formatedText = subScope.format_text(args.message)

		e = None
		if args.title or args.description or args.footer or args.image or args.thumbnail:
			e = discord.Embed();
			e.type = "rich"
			if args.title:
				e.title = subScope.format_text(args.title)
			if args.description:
				e.description = subScope.format_text(args.description)
			if args.footer:
				e.set_footer(text=subScope.format_text(args.footer))
			if args.image:
				e.set_image(url=subScope.format_text(args.image))
			if args.thumbnail:
				e.set_thumbnail(url=subScope.format_text(args.thumbnail))

		await scope.shell.send_message(subScope.channel, formatedText, e)

	@praxisbot.command
	@praxisbot.permission_script
	async def execute_change_roles(self, scope, command, options, lines, **kwargs):
		"""
		Change roles of a member.
		"""

		parser = argparse.ArgumentParser(description=kwargs["description"], prog=command)
		parser.add_argument('user', help='User name')
		parser.add_argument('--add', nargs='*', help='A list of roles to add', default=[])
		parser.add_argument('--remove', nargs='*', help='A list of roles to remove', default=[])
		args = await self.parse_options(scope, parser, options)
		if not args:
			return

		formatedUser = scope.format_text(args.user)
		u = scope.shell.find_member(formatedUser, scope.server)
		if not u:
			await scope.shell.print_error(scope, "Member `"+formatedUser+"` not found.")
			return

		rolesToAdd = []
		rolesToRemove = []
		for a in args.add:
			formatedRole = scope.format_text(a)
			role = scope.shell.find_role(formatedRole, scope.server)
			if role:
				rolesToAdd.append(role)
		for a in args.remove:
			formatedRole = scope.format_text(a)
			role = scope.shell.find_role(formatedRole, scope.server)
			if role:
				rolesToRemove.append(role)

		res = await scope.shell.change_roles(u, rolesToAdd, rolesToRemove)
		if res:
			output = "The following roles has been changed from "+u.display_name+":"
			for i in res[0]:
				output = output + "\n + " + i.name
			for i in res[1]:
				output = output + "\n - " + i.name
			await scope.shell.print_success(scope, output)
		else:
			await scope.shell.print_error(scope, "Roles can't be changed")

	@praxisbot.command
	@praxisbot.permission_admin
	async def execute_set_command_prefix(self, scope, command, options, lines, **kwargs):
		"""
		Set the prefix used to send commands.
		"""

		parser = argparse.ArgumentParser(description=kwargs["description"], prog=command)
		parser.add_argument('prefix', help='Prefix')
		args = await self.parse_options(scope, parser, options)
		if not args:
			return

		scope.shell.set_sql_data("servers", {"command_prefix": str(args.prefix)}, {"discord_sid": int(scope.server.id)}, "discord_sid")
		await scope.shell.print_success(scope, "Command prefix changed to ``"+args.prefix+"``.")

	@praxisbot.command
	async def execute_regex(self, scope, command, options, lines, **kwargs):
		"""
		Extract data from a string using regular expression.
		"""

		parser = argparse.ArgumentParser(description=kwargs["description"], prog=command)
		parser.add_argument('regex', help='Regular expression')
		parser.add_argument('data', help='Target string')
		parser.add_argument('--output', help='Format of the output. Use {{result}}, {{result0}}, {{result1}}, ....', default="{{result}}")
		args = await self.parse_options(scope, parser, options)
		if not args:
			return

		data = scope.format_text(args.data)
		res = None
		try:
			res = re.search(args.regex, data)
		except:
			await scope.shell.print_error(scope, "The regular expression seems wrong.")
			return

		if res:
			scope.vars["result"] = res.group(0)
			counter = 0
			for g in res.groups():
				scope.vars["result"+str(counter)] = g
				counter = counter+1
			if args.output and len(args.output)>0:
				await scope.shell.print_info(scope, scope.format_text(args.output))
		else:
			await scope.shell.print_error(scope, "The regular expression didn't match anything.")
			return

	@praxisbot.command
	async def execute_whois(self, scope, command, options, lines, **kwargs):
		"""
		Get all available informations about an user.
		"""

		parser = argparse.ArgumentParser(description=kwargs["description"], prog=command)
		parser.add_argument('user', help='An user')
		args = await self.parse_options(scope, parser, options)
		if not args:
			return

		u = scope.shell.find_member(scope.format_text(args.user), scope.server)
		if not u:
			await scope.shell.print_error(scope, "User not found. User name must be of the form `@User#1234` or `User#1234`.")
			return

		e = discord.Embed();
		e.type = "rich"
		e.title = u.name+"#"+u.discriminator
		e.set_thumbnail(url=u.avatar_url.replace(".webp", ".png"))

		e.add_field(name="Nickname", value=str(u.display_name))
		e.add_field(name="Discord ID", value=str(u.id))
		e.add_field(name="Created since", value=str(datetime.datetime.now() - u.created_at))
		e.add_field(name="Joined since", value=str(datetime.datetime.now() - u.joined_at))
		roles = []
		for r in u.roles:
			if not r.is_everyone:
				roles.append(r.name)
		e.add_field(name="Roles", value=", ".join(roles))

		try:
			profile = await scope.shell.client_human.get_user_profile(u.id)

			stream = praxisbot.MessageStream(scope)
			for ca in profile.connected_accounts:
				url = ca.url
				if url:
					e.add_field(name=ca.provider_name, value=url)
				else:
					e.add_field(name=ca.provider_name, value=ca.name)
		except:
			pass

		await scope.shell.client.send_message(scope.channel, "", embed=e)

	@praxisbot.command
	async def execute_delete_message(self, scope, command, options, lines, **kwargs):
		"""
		Delete the message that trigger the current execution.
		"""

		parser = argparse.ArgumentParser(description=kwargs["description"], prog=command)
		args = await self.parse_options(scope, parser, options)
		if not args:
			return

		scope.deletecmd = True

	@praxisbot.command
	async def execute_silent(self, scope, command, options, lines, **kwargs):
		"""
		Don't print any feedback during execution.
		"""

		parser = argparse.ArgumentParser(description=kwargs["description"], prog=command)
		args = await self.parse_options(scope, parser, options)
		if not args:
			return

		scope.verbose = 0
