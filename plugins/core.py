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
from pytz import timezone
from dateutil.relativedelta import relativedelta
import praxisbot
from io import StringIO
import asyncio

class HelpMessage():
	def __init__(self, guild, plugins):
		self.emojis = ["0️⃣","1️⃣","2️⃣","3️⃣","4️⃣","5️⃣","6️⃣","7️⃣","8️⃣","9️⃣"]
		self.home = "🏠"
		self.arrows = ["◀","▶"]
		self.guild = guild
		self.plugins = plugins
		
		self.last = None
		self.page = 0
		self.message = ""
		self.reactions = []
		self.pageMax = 0
		self.holdOn = True
		self.taskAddReaction = None
	
	def reset(self):
		self.last = None
		self.page = 0
		self.message = ""
		self.reactions = []
	
	def set_plugins(self,plugins):
		self.plugins = plugins
		self.pageMax = int(len(plugins)/len(self.emojis))
	
	def get_page_from_reaction(self,reaction):
		if reaction in self.arrows:
			if reaction == self.arrows[0]:
				self.page -= 1
			else:
				self.page += 1
			return
		
		elif reaction in self.emojis:
			self.page = self.plugins[self.emojis.index(reaction)]
			
		elif reaction == self.home:
			self.page = 0
		return self.page
	
	def menu(self):
		nbPlugins = len(self.plugins)
		perPage = len(self.emojis)
		stillToShow = len(self.plugins) - perPage * self.page ## Page 1 == 16 - 10 * 0 = 16 || Page 2 == 16 - 10 * 1 = 6
		
		minX = self.page * perPage
		maxX = minX + min(stillToShow,perPage)
		lines = []
		if self.page > 0:
			self.reactions.append(self.arrows[0])
			lines.append("‧{} Page précédente".format(self.arrows[0]))
			
		for i in range(minX,maxX):
			line = "‧{} {}".format(self.emojis[i%perPage],self.plugins[i].name)
			lines.append(line)		
		self.reactions += self.emojis[:maxX-minX]	
		
		if self.page < self.pageMax:
			self.reactions.append(self.arrows[1])
			lines.append("‧{} Page suivant".format(self.arrows[1]))
		
		self.message = "Menu d’aide, page {}/{} :\n\n{}".format(self.page+1,self.pageMax+1,"\n".join(lines))
	
	def plugin(self):
		p = self.page
		self.message = "\n**{}**\n\n".format(p.name)
		for c in p.cmds:
			desc =	inspect.getdoc(p.cmds[c])
			if desc:
				self.message += " – `{}` : {}\n".format(c,desc)
			else:
				self.message += " - `{}`\n".format(c)
		self.reactions = [self.home]
		
	async def add_reactions(self):
		try:
			for r in self.reactions:
				await self.last.add_reaction(r)
		except asyncio.CancelledError:
			return
		
	async def print(self,channel=None):
		if channel == None and not self.last:
			return
		elif channel == None:
			channel = self.last.channel
		
		self.message = ""
		self.reactions = []
		
		if type(self.page) == int:
			self.menu()
		else:
			self.plugin()
		if not self.last:
			self.last = await channel.send(self.message)
		else:
			await self.last.clear_reactions()
			await self.last.edit(content=self.message)
		
		if self.taskAddReaction:
			self.taskAddReaction.cancel()
		self.taskAddReaction = asyncio.create_task(self.add_reactions())

class CorePlugin(praxisbot.Plugin):
	"""
	Core commands
	"""

	name = "Core"

	def __init__(self, shell):
		super().__init__(shell)

		self.shell.create_sql_table("variables", ["id INTEGER PRIMARY KEY", "discord_sid INTEGER", "name TEXT", "value TEXT"])
		self.helpMessages = {}
		for g in shell.client.guilds:
			self.helpMessages[g] = HelpMessage(g,None)

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
		self.add_command("verbose", self.execute_verbose)
		self.add_command("silent", self.execute_silent)
		self.add_command("cite", self.execute_cite)
		
	async def on_reaction(self, scope, reaction):
		helpMessage = self.helpMessages[scope.guild]
		
		if reaction.message.id != helpMessage.last.id:
			print("Reaction added to another message : Waited in {}, got in {}".format(reaction.message.id,helpMessage.last.id))
			return

		if reaction.emoji not in helpMessage.reactions:
			print("Reaction not in base")
			return
		
		helpMessage.reactions = []
		helpMessage.get_page_from_reaction(reaction.emoji)
		print("Attempt to print page : {}".format(helpMessage.page))
		await helpMessage.print()
	
	@praxisbot.command
	async def execute_help(self, scope, command, options, lines, **kwargs):
		"""
		Help page of PraxisBot.
		"""
		
		helpMessage = self.helpMessages[scope.guild]
		helpMessage.reset()
		
		helpMessage.set_plugins(scope.shell.plugins)
		await helpMessage.print(scope.channel)

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
		subScope.verbose = 1
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
		parser.add_argument('--iswritable', action='store_true', help='Test if a parameter is a writable text channel')
		parser.add_argument('--isrole', action='store_true', help='Test if a parameter is a valid role')
		parser.add_argument('--isdate', action='store_true', help='Test if a parameter is a valid date')
		parser.add_argument('--not', dest='inverse', action='store_true', help='Inverse the result of the test')
		parser.add_argument('--find', help='Return truc if an occurence of B is found in A (case insensitive)')
		parser.add_argument('--inset', help='Return truc if B is in the set A')
		parser.add_argument('--regex', help='Return true if A match the regular expression B')
		parser.add_argument('--inf', help='Return true if A is inferior to B')
		parser.add_argument('--sup', help='Return true if A is superior to B')
		args = await self.parse_options(scope, parser, options)
		if not args:
			return

		res = False
		if args.equal:
			a = scope.format_text(args.firstvar)
			b = scope.format_text(args.equal)
			res = (a == b)
		elif args.inf:
			a = scope.format_text(args.firstvar)
			b = scope.format_text(args.inf)

			try:
				ia = int(a)
				ib = int(b)
				res = (ia < ib)
			except:
				res = (a < b)
		elif args.sup:
			a = scope.format_text(args.firstvar)
			b = scope.format_text(args.sup)

			try:
				ia = int(a)
				ib = int(b)
				res = (ia > ib)
			except:
				res = (a > b)
		elif args.find:
			a = scope.format_text(args.firstvar).lower()
			b = scope.format_text(args.find).lower()
			res = (a.find(b) >= 0)
		elif args.inset:
			a = scope.format_text(args.firstvar).split("\n")
			b = scope.format_text(args.inset)
			res = (b in a)
		elif args.regex:
			a = scope.format_text(args.firstvar)
			b = scope.format_text(args.regex)
			try:
				if re.search(b, a):
					res = True
				else:
					res = False
			except:
				await scope.shell.print_error(scope, "The regular expression seems wrong.")
				res = False
		elif args.ismember:
			u = scope.shell.find_member(scope.format_text(args.firstvar), scope.guild)
			res = (u != None)
		elif args.iswritable:
			c = scope.shell.find_channel(scope.format_text(args.firstvar), scope.guild)
			res = (c and c.permissions_for(scope.user).send_messages and c.permissions_for(scope.user).read_messages)
		elif args.isrole:
			u = scope.shell.find_role(scope.format_text(args.firstvar), scope.guild)
			res = (u != None)
		elif args.isdate:
			try:
				start_time = datetime.datetime.strptime(scope.format_text(args.firstvar), "%Y-%m-%d %H:%M:%S")
				res = True
			except ValueError:
				res = False
		elif args.hasroles:
			u = scope.shell.find_member(scope.format_text(args.firstvar), scope.guild)
			r = []
			for i in args.hasroles:
				formatedRole = scope.format_text(i)
				role = scope.shell.find_role(formatedRole, scope.guild)
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
			val = scope.vars.get(args.inset, "")
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
		parser.add_argument('value', nargs='?', help='Variable value')
		parser.add_argument('--global', dest='glob', action='store_true', help='Set the variable for all commands on this server')
		parser.add_argument('--delete_global', dest='del_glob', action='store_true', help='Delete the variable for all commands on this server')
		parser.add_argument('--session', action='store_true', help='Set the variable for an user session')
		parser.add_argument('--dateadd', help='Add a duration to a date. YYYY-MM-DD HH:MM:SS')
		parser.add_argument('--intadd', help='Add the integer value to the variable')
		parser.add_argument('--intremove', help='Remove the integer value from the variable')
		parser.add_argument('--setadd', nargs='+', help='Add elements in the set')
		parser.add_argument('--setremove', nargs='+', help='Remove elements from the set')
		parser.add_argument('--members', nargs='*', help='Get all members that are at least in one of the listed groups')
		args = await self.parse_options(scope, parser, options)
		if not args:
			return

		if args.glob and scope.permission < praxisbot.UserPermission.Script:
			raise praxisbot.ParameterPermissionError("--global")

		var = scope.format_text(args.name)
		self.ensure_object_name("Variable name", var)

		if args.dateadd:
			try:
				d = datetime.datetime.strptime(scope.vars.get(var, ""), "%Y-%m-%d %H:%M:%S")
				d = timezone('Europe/Paris').localize(d)
			except:
				d = datetime.datetime.now(timezone('Europe/Paris'))

			r = re.match("([0-9]+)-([0-9]+)-([0-9]+) ([0-9]+):([0-9]+):([0-9]+)", scope.format_text(args.dateadd))
			if r:
				years = int(r.group(1))
				months = int(r.group(2))
				days = int(r.group(3))
				hours = int(r.group(4))
				minutes = int(r.group(5))
				seconds = int(r.group(6))
				delta = relativedelta(years=years, months=months, days=days, hours=hours, minutes=minutes, seconds=seconds)
				new_time = d + delta
				val = new_time.strftime("%Y-%m-%d %H:%M:%S")
			#except:
			#	val = scope.vars.get(var, "")

		elif args.intadd:
			val = scope.format_text(args.intadd)
			try:
				val = str(int(scope.vars.get(var, 0)) + int(val))
			except ValueError:
				val = str(scope.vars.get(var, ""))
				pass
		elif args.intremove:
			val = scope.format_text(args.intremove)
			try:
				val = str(int(scope.vars.get(var, 0)) - int(val))
			except ValueError:
				val = str(scope.vars.get(var, ""))
				pass
		elif args.setadd:
			try:
				if var in scope.vars:
					s = set(str(scope.vars[var]).split("\n"))
				else:
					s = set()

				for v in args.setadd:
					s.add(scope.format_text(v))
				val = "\n".join(s)
			except ValueError:
				val = str(scope.vars[var])
				pass
		elif args.setremove:
			try:
				if var in scope.vars:
					s = set(str(scope.vars[var]).split("\n"))
				else:
					s = set()

				for v in args.setremove:
					s.discard(scope.format_text(v))
				val = "\n".join(s)
			except ValueError:
				val = str(scope.vars[var])
				pass
		elif args.members != None:
			if scope.permission < praxisbot.UserPermission.Script:
				raise praxisbot.ScriptPermissionError()

			role_list = set()
			member_list = []
			error = False
			for r in args.members:
				r_name = scope.format_text(r)
				r_found = scope.shell.find_role(r_name, scope.guild)
				if r_found:
					role_list.add(r_found)
				else:
					await scope.shell.print_error(scope, "`"+r_name+"` is not a valid role")
					error = True
			for m in scope.guild.members:
				if len(role_list) > 0:
					for r in m.roles:
						if not r.is_default() and r in role_list:
							member_list.append(m.name+"#"+m.discriminator)
							break
				elif not error:
					member_list.append(m.name+"#"+m.discriminator)
			val = "\n".join(member_list)

		elif args.value:
			val = scope.format_text(args.value)
		else:
			val = ""

		scope.vars[var] = val

		if args.session:
			scope.session_vars[var] = val

		if args.glob:
			scope.shell.set_sql_data("variables", {"value":str(val)}, {"discord_sid": int(scope.guild.id), "name": str(var)})
		elif args.del_glob:
			scope.shell.delete_sql_data("variables", {"discord_sid": int(scope.guild.id), "name": str(var)})
			await scope.shell.print_success(scope, "{} is now deleted".format(var))
			return

		await scope.shell.print_success(scope, "`{}` is now equal to:\n```\n{}```".format(var,val))


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
		parser.add_argument('message', nargs="?", help='Text to send')
		parser.add_argument('--channel', '-c', help='Channel where to send the message')
		parser.add_argument('--title', '-t', help='Embed title')
		parser.add_argument('--description', '-d', help='Embed description')
		parser.add_argument('--footer', '-f', help='Embed footer')
		parser.add_argument('--footerimage', help='Embed footer image')
		parser.add_argument('--image', '-i', help='Embed image')
		parser.add_argument('--thumbnail', '-m', help='Embed thumbnail')
		parser.add_argument('--author', '-a', help='Embed author name')
		parser.add_argument('--authorimage', help='Embed author image')
		parser.add_argument('--authorurl', help='Embed author URL')
		parser.add_argument('--fields', nargs="+", help='List of key/value')
		parser.add_argument('--reactions', nargs='+', help='Name of a variable containing a set', metavar='EMOJI')
		args = await self.parse_options(scope, parser, options)
		if not args:
			return

		if args.channel:
			chan = scope.shell.find_channel(scope.format_text(args.channel).strip(), scope.guild)
		else:
			chan = scope.channel

		if not chan:
			await scope.shell.print_error(scope, "Unknown channel. {}".format(args.channel))
			return

		if scope.permission < praxisbot.UserPermission.Script and not chan.permissions_for(scope.user).send_messages:
			await scope.shell.print_permission(scope, "You don't have write permission in this channel.")
			return

		subScope = scope.create_subscope()
		subScope.channel = chan

		formatedText = ""
		if args.message:
			formatedText = subScope.format_text(args.message)

		e = None
		if args.title or args.description or args.footer or args.footerimage or args.image or args.thumbnail or args.author or args.authorimage or args.authorurl or args.fields:
			e = discord.Embed();
			e.type = "rich"

			if args.title:
				e.title = subScope.format_text(args.title)
			if args.description:
				e.description = subScope.format_text(args.description)
			if args.image:
				e.set_image(url=subScope.format_text(args.image))
			if args.thumbnail:
				e.set_thumbnail(url=subScope.format_text(args.thumbnail))

			footer_params = {}
			if args.footer:
				footer_params["text"] = subScope.format_text(args.footer)
			if args.footerimage:
				footer_params["icon_url"] = subScope.format_text(args.footerimage)
			if len(footer_params) > 0:
				e.set_footer(**footer_params)

			author_params = {}
			if args.author:
				author_params["name"] = subScope.format_text(args.author)
			if args.authorimage:
				author_params["icon_url"] = subScope.format_text(args.authorimage)
			if args.authorurl:
				author_params["url"] = subScope.format_text(args.authorurl)
			if len(author_params) > 0:
				e.set_author(**author_params)

			if args.fields:
				field_key = None
				for f in args.fields:
					if not field_key:
						field_key = f
					else:
						e.add_field(name=subScope.format_text(field_key), value=subScope.format_text(f))
						field_key = None

		if e or len(formatedText) > 0:
			msg = await subScope.channel.send(formatedText, embed=e)
			if args.reactions:
				for emoji in args.reactions:
					try:
						await scope.shell.client.add_reaction(msg, emoji)
					except:
						pass

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
		u = scope.shell.find_member(formatedUser, scope.guild)
		if not u:
			await scope.shell.print_error(scope, "Member `"+formatedUser+"` not found.")
			return

		rolesToAdd = []
		rolesToRemove = []
		for a in args.add:
			formatedRole = scope.format_text(a)
			role = scope.shell.find_role(formatedRole, scope.guild)
			if role:
				rolesToAdd.append(role)
		for a in args.remove:
			formatedRole = scope.format_text(a)
			role = scope.shell.find_role(formatedRole, scope.guild)
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

		scope.shell.set_sql_data("servers", {"command_prefix": str(args.prefix)}, {"discord_sid": int(scope.guild.id)}, "discord_sid")
		await scope.shell.print_success(scope, "Command prefix changed to ``"+args.prefix+"``.")

	@praxisbot.command
	async def execute_regex(self, scope, command, options, lines, **kwargs):
		"""
		Extract data from a string using regular expression.
		"""

		parser = argparse.ArgumentParser(description=kwargs["description"], prog=command)
		parser.add_argument('regex', help='Regular expression')
		parser.add_argument('data', help='Target string')
		parser.add_argument('--var', help='Variable that will contains the result')
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
			varName = "result"
			if args.var:
				varName = args.var
			scope.vars[varName] = res.group(0)
			counter = 0
			for g in res.groups():
				scope.vars[varName+str(counter)] = g
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
		parser.add_argument('--channel', '-c', help='Channel where to send the message')
		args = await self.parse_options(scope, parser, options)
		if not args:
			return

		if args.channel:
			chan = scope.shell.find_channel(scope.format_text(args.channel).strip(), scope.guild)
		else:
			chan = scope.channel

		if not chan:
			await scope.shell.print_error(scope, "Unknown channel. {}".format(args.channel))
			return

		if scope.permission < praxisbot.UserPermission.Script and not chan.permissions_for(scope.user).send_messages:
			await scope.shell.print_permission(scope, "You don't have write permission in this channel.")
			return

		u = scope.shell.find_member(scope.format_text(args.user), scope.guild)
		if not u:
			await scope.shell.print_error(scope, "User not found. User name must be of the form `@User#1234` or `User#1234`.")
			return

		e = discord.Embed();
		e.type = "rich"
		e.set_author(name="{}#{}".format(u.name,u.discriminator), icon_url=u.avatar_url_as(format="png"))
		e.set_thumbnail(url=u.avatar_url_as(format="png"))

		e.add_field(name="Nickname", value=str(u.display_name))
		e.add_field(name="Discord ID", value=str(u.id))
		if u.colour.value != 0:
			e.colour = u.colour

		e.add_field(name="Created since", value=str(datetime.datetime.utcnow() - u.created_at))
		e.add_field(name="Joined since", value=str(datetime.datetime.utcnow() - u.joined_at))

		if u.guild_permissions.administrator:
			e.add_field(name="Administrator", value=":crown: Yes")
		if u.guild_permissions.manage_guild:
			e.add_field(name="Manage guild", value=":tools: Yes")
		if u.guild_permissions.manage_channels:
			e.add_field(name="Manage channels", value=":tools: Yes")
		if u.guild_permissions.manage_messages:
			e.add_field(name="Manage messages", value=":speech_balloon: Yes")
		if u.guild_permissions.view_audit_log:
			e.add_field(name="View audit log", value=":eye: Yes")
		if u.guild_permissions.ban_members:
			e.add_field(name="Ban members", value=":punch: Yes")
		if u.guild_permissions.kick_members:
			e.add_field(name="Kick members", value=":punch: Yes")
		if u.guild_permissions.mention_everyone:
			e.add_field(name="Mention everyone", value=":loudspeaker: Yes")

		roles = []
		for r in u.roles:
			if not r.is_default():
				roles.append(r.name)
		if len(roles):
			e.add_field(name="Roles", value=", ".join(roles))

		await chan.send("", embed=e)

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
	async def execute_verbose(self, scope, command, options, lines, **kwargs):
		"""
		Print all messages.
		"""

		parser = argparse.ArgumentParser(description=kwargs["description"], prog=command)
		args = await self.parse_options(scope, parser, options)
		if not args:
			return

		scope.verbose = 2

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

	@praxisbot.command
	async def execute_cite(self, scope, command, options, lines, **kwargs):
		"""
		Cite a message.
		"""

		parser = argparse.ArgumentParser(description=kwargs["description"], prog=command)
		parser.add_argument('messageid', help='Message ID or URL to cite')
		parser.add_argument('--channel', help='Channel where the cited message is')
		parser.add_argument('--server', help='Server where the cited message is')
		args = await self.parse_options(scope, parser, options)
		if not args:
			return

		urlParser = re.match("https\:\/\/discordapp.com\/channels\/([0-9]+)\/([0-9]+)\/([0-9]+)", args.messageid)
		if urlParser:
			args.guild = urlParser.group(1)
			args.channel = urlParser.group(2)
			args.messageid = urlParser.group(3)

		if args.guild:
			server = scope.shell.find_server(scope.format_text(args.guild).strip())
		else:
			server = scope.guild

		if not server:
			await scope.shell.print_error(scope, "Unknown server `"+args.guild+"`.")
			return

		if args.channel:
			chan = scope.shell.find_channel(scope.format_text(args.channel).strip(), server)
		else:
			chan = scope.channel

		if not chan:
			await scope.shell.print_error(scope, "Unknown channel `"+args.channel+"`.")
			return

		member = scope.shell.find_member(scope.user.id, server)
		if not member:
			await scope.shell.print_error(scope, "Your are not a member of the server.")
			return

		if not chan.permissions_for(member).read_messages:
			await scope.shell.print_permission(scope, "You don't have read permission in this channel.")
			return

		msg = None
		try:
			msg = await scope.shell.client.get_message(chan, args.messageid)
		except discord.errors.NotFound:
			msg = None

		if not msg:
			await scope.shell.print_error(scope, "Message not found `"+args.messageid+"` in channel "+chan.mention+".")
			return

		msg_deltatime = datetime.datetime.utcnow() - msg.timestamp
		duration = ""
		if msg_deltatime.days > 1:
			duration = ", "+str(msg_deltatime.days)+" days ago"
		elif msg_deltatime.days == 1:
			duration = ", yesterday"
		elif msg_deltatime.seconds > 3600:
			hours = int(msg_deltatime.seconds/3600)
			if hours == 1:
				duration = ", one hour ago"
			else:
				duration = ", "+str(hours)+" hours ago"
		elif msg_deltatime.seconds > 60:
			minutes = int(msg_deltatime.seconds/60)
			if minutes == 1:
				duration = ", one minute ago"
			else:
				duration = ", "+str(minutes)+" minutes ago"
		else:
			duration = ", "+str(msg_deltatime.seconds)+" seconds ago"

		e = discord.Embed();
		e.type = "rich"
		chan_name = "#"+chan.name
		if server.id != scope.guild.id:
			chan_name = chan_name+" ("+server.name+")"
		e.set_author(name=msg.author.display_name+duration+" in "+chan_name, icon_url=msg.author.avatar_url.replace(".webp", ".png"))
		e.description = msg.content
		e.set_footer(text="Cited by "+scope.user.display_name)

		await scope.channel.send("", embed=e)
		scope.deletecmd = True
