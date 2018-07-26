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

import sys
import io
import traceback
import shlex
import copy
import inspect
import re
import random
import sqlite3
import discord
import datetime
from pytz import timezone
from functools import wraps

class RedirectOutput():
	def __init__(self, destout, desterr):
		self.destout = destout
		self.desterr = desterr
		self.old_stdout = sys.stdout
		self.old_stderr = sys.stderr

	def __enter__(self):
		sys.stdout = self.destout
		sys.stderr = self.desterr

	def __exit__(self, *args):
		sys.stdout = self.old_stdout
		sys.stderr = self.old_stderr

################################################################################
# Exceptions
################################################################################

class Error(Exception):
    pass

class TooLongScriptError(Error):
	pass

class AdminPermissionError(Error):
	pass

class ScriptPermissionError(Error):
	pass

class ParameterPermissionError(Error):
	def __init__(self, parameter):
		self.parameter = parameter

class CommandNotFoundError(Error):
	def __init__(self, command):
		self.command = command

class ObjectNameError(Error):
	def __init__(self, parameter, name):
		self.parameter = parameter
		self.name = name

class ObjectIdError(Error):
	def __init__(self, parameter, name):
		self.parameter = parameter
		self.name = name

class IntegerError(Error):
	def __init__(self, name):
		self.name = name

class RegexError(Error):
	def __init__(self, regex):
		self.regex = regex

################################################################################
# Decorators
################################################################################

def command(func):
	@wraps(func)
	def wrapper(self, scope, command, options, lines, **kwargs):
		d = inspect.getdoc(func)
		return func(self, scope, command, options, lines, description=d, **kwargs)

	return wrapper

def permission_admin(func):
	@wraps(func)
	def wrapper(self, scope, command, options, lines, **kwargs):
		if scope.permission < UserPermission.Admin:
			raise AdminPermissionError()
		return func(self, scope, command, options, lines, **kwargs)
	return wrapper

def permission_script(func):
	@wraps(func)
	def wrapper(self, scope, command, options, lines, **kwargs):
		if scope.permission < UserPermission.Script:
			raise ScriptPermissionError()
		return func(self, scope, command, options, lines, **kwargs)
	return wrapper

################################################################################
# Scope
################################################################################

class ExecutionBlockIf:
	def __init__(self, e):
		self.execute = e
		self.terminated = False

	async def execute_script(self, scope, command, commandline):
		if command == "endif":
			self.terminated = True
			return

		if command == "else":
			self.execute = not self.execute
			return

		if self.execute:
			await scope.shell.execute_command(scope, commandline)

class ExecutionBlockFor:
	def __init__(self, var, list):
		self.var = var
		self.list = list
		self.cmds = []
		self.terminated = False

	async def execute_script(self, scope, command, commandline):
		if command == "endfor":
			self.terminated = True
			for i in self.list:
				scope.vars[self.var] = i
				for c in self.cmds:
					await scope.shell.execute_command(scope, c)
					if scope.abort:
						return

		elif len(self.list):
			self.cmds.append(commandline)

class ExecutionScope:
	def __init__(self, shell, server, prefixes):
		self.shell = shell
		self.prefixes = prefixes
		self.server = server
		self.channel = None
		self.user = None

		self.permission = UserPermission.Member

		self.iter = 0
		self.vars = {}
		self.session_vars = {}
		self.blocks = []
		self.abort = False
		self.deletecmd = False
		self.verbose = 2

	async def execute_script(self, command, commandline):
		"""
		Take care of conditions (if, for, ...). Return True if the command must not be executed
		"""
		if not len(self.blocks):
			await self.shell.execute_command(self, commandline)
			return

		b = self.blocks[len(self.blocks)-1]
		await b.execute_script(self, command, commandline)
		if b.terminated:
			self.blocks.pop()

	def create_subscope(self):
		subScope = ExecutionScope(self.shell, self.server, self.prefixes)

		subScope.channel = self.channel
		subScope.user = self.user

		subScope.permission = self.permission

		subScope.iter = self.iter
		subScope.vars = self.vars
		subScope.session_vars = self.session_vars
		subScope.blocks = self.blocks
		subScope.abort = self.abort
		subScope.deletecmd = self.deletecmd

		return subScope

	def continue_from_subscope(self, subScope):
		self.iter = subScope.iter
		self.vars = subScope.vars
		self.session_vars = subScope.session_vars
		self.abort = subScope.abort
		self.deletecmd = subScope.deletecmd

	def format_text(self, text):
		if not text:
			return ""

		p = re.compile("\{\{([^\}]+)\}\}")

		formatedText = ""
		textIter = 0
		mi = p.finditer(text)
		for m in mi:
			formatedText = formatedText + text[textIter:m.start()]
			textIter = m.end()

			#Process tag
			tag = m.group(1).strip()
			tagOutput = m.group()

			if tag.find('|') >= 0:
				tag = random.choice(tag.split("|"))
				tagOutput = tag

			u = self.user
			user_chk = re.fullmatch('([*@#]?user(?:_time|_avatar)?)=(.*)', tag)
			if user_chk:
				subUser = user_chk.group(2).strip()
				if subUser in self.vars:
					subUser = self.vars[subUser].strip()
				u = self.shell.find_member(subUser, self.server)
				tag = user_chk.group(1)

			c = self.channel
			channel_chk = re.fullmatch('([*#]?channel)=(.*)', tag)
			if channel_chk:
				subChan = channel_chk.group(2).strip()
				if subChan in self.vars:
					subChan = self.vars[subChan]
				c = self.shell.find_channel(subChan, self.server)
				tag = channel_chk.group(1)

			r = None
			role_chk = re.fullmatch('([*@]?role)=(.*)', tag)
			if role_chk:
				subRole = role_chk.group(2).strip()
				if subRole in self.vars:
					subRole = self.vars[subRole]
				r = self.shell.find_role(subRole, self.server)
				tag = role_chk.group(1)

			if tag.lower() == "server" and self.server:
				tagOutput = self.server.name
			elif tag.lower() == "*server" and self.server:
				tagOutput = self.server.id
			elif tag.lower() == "n":
				tagOutput = "\n"
			elif tag.lower() == "now":
				d = datetime.datetime.now(timezone('Europe/Paris'))
				tagOutput = d.strftime("%Y-%m-%d %H:%M:%S")
			elif tag.lower() == "channel" and c:
				tagOutput = c.name
			elif tag.lower() == "#channel" and c:
				tagOutput = c.mention
			elif tag.lower() == "*channel" and c:
				tagOutput = c.id
			elif tag.lower() == "role" and r:
				tagOutput = r.name
			elif tag.lower() == "@role" and r:
				tagOutput = r.mention
			elif tag.lower() == "*role" and r:
				tagOutput = r.id
			elif tag.lower() == "#user" and u:
				tagOutput = u.name+"#"+u.discriminator
			elif tag.lower() == "@user" and u:
				tagOutput = u.mention
			elif tag.lower() == "*user" and u:
				tagOutput = u.id
			elif tag.lower() == "user" and u:
				tagOutput = u.display_name
			elif tag.lower() == "user_time" and u:
				tagOutput = str(u.created_at)
			elif tag.lower() == "user_avatar" and u:
				tagOutput = str(u.avatar_url.replace(".webp", ".png"))
			elif tag[0] == "*" and tag[1:] in self.vars:
				if len(self.vars[tag[1:]].strip()) == 0:
					tagOutput = 0
				else:
					s = self.vars[tag[1:]].split("\n")
					tagOutput = str(len(s))
			elif tag[0] == "," and tag[1:] in self.vars:
				s = self.vars[tag[1:]].split("\n")
				tagOutput = ", ".join(s)
			elif tag in self.vars:
				tagOutput = self.vars[tag]
			else:
				tagOutput = tag
			formatedText = formatedText + str(tagOutput)

		formatedText = formatedText + text[textIter:]

		return formatedText

################################################################################
# Shell
################################################################################

class UserPermission:
	Member=0
	Script=1
	Admin=2
	Owner=3

class Shell:
	def __init__(self, client, client_humans, dbprefix, dbcon):
		self.plugins = []
		self.client = client
		self.client_humans = client_humans
		self.dbprefix = dbprefix
		self.dbcon = dbcon

	async def print_info(self, scope, msg):
		if scope.verbose >= 2:
			await self.client.send_message(scope.channel, msg)
		return

	async def print_debug(self, scope, msg):
		if scope.verbose >= 3:
			await self.client.send_message(scope.channel, ":large_blue_circle: "+msg)
		return

	async def print_success(self, scope, msg):
		if scope.verbose >= 2:
			await self.client.send_message(scope.channel, ":white_check_mark: "+msg)
		return

	async def print_permission(self, scope, msg):
		if scope.verbose >= 1:
			await self.client.send_message(scope.channel, ":closed_lock_with_key: "+msg)
		return

	async def print_error(self, scope, msg):
		if scope.verbose >= 1:
			await self.client.send_message(scope.channel, ":no_entry: "+msg)
		return

	async def print_fatal(self, scope, msg):
		if scope.verbose >= 1:
			await self.client.send_message(scope.channel, ":skull_crossbones: "+msg)
		return

	def load_plugin(self, plugin):
		"""
		Create an instance of a plugin and register it
		"""
		try:
			instance = plugin(self)
			self.plugins.append(instance)
			print("Plugin {0} loaded".format(plugin.name))
		except:
			print(traceback.format_exc())
			print("Plugin {0} can't be loaded".format(plugin.name))

	def find_command_and_options(self, commandline, prefixes):
		for prefix in prefixes:
			if commandline.find(prefix) == 0:
				commandline = commandline[len(prefix):]
				lines = commandline.split("\n")
				command = lines[0].split(" ")[0:1][0].strip()
				options = lines[0][len(command):].strip()
				if len(command.strip()) == 0:
					return None
				return (command, options, lines[1:])
		return None

	def create_scope(self, server, prefixes):
		scope = ExecutionScope(self, server, prefixes)

		with self.dbcon:
			c = self.dbcon.cursor()
			for row in c.execute("SELECT name, value FROM "+self.dbtable("variables")+" WHERE discord_sid = ?", [int(scope.server.id)]):
				scope.vars[row[0]] = row[1]

		return scope

	async def execute_command(self, scope, commandline):
		try:
			if scope.iter > 64:
				raise TooLongExecutionError()

			parsedCommand = self.find_command_and_options(commandline, scope.prefixes)
			if not parsedCommand:
				return False

			for p in self.plugins:
				if await p.execute_command(scope, parsedCommand[0], parsedCommand[1], parsedCommand[2]):
					scope.iter = scope.iter+1
					return True

			raise CommandNotFoundError(parsedCommand[0])

		except CommandNotFoundError as e:
			await self.print_error(scope, "Command `"+e.command+"` not found.")
			scope.abort = True
		except AdminPermissionError as e:
			await self.print_permission(scope, "This command is restricted to administrators.");
			scope.abort = True
		except ScriptPermissionError as e:
			await self.print_permission(scope, "This command is restricted to scripts and administrators.");
			scope.abort = True
		except ParameterPermissionError as e:
			await self.print_permission(scope, "You are not allowed to use the parameter `"+e.parameter+"`.");
			scope.abort = True
		except ObjectNameError as e:
			await self.print_error(scope, e.parameter+" must be a letter followed by alphanumeric characters.");
			scope.abort = True
		except ObjectIdError as e:
			await self.print_error(scope, e.parameter+" must be a number.");
			scope.abort = True
		except IntegerError as e:
			await self.print_error(scope, e.parameter+" must be a number.");
			scope.abort = True
		except RegexError as e:
			await self.print_error(scope, "`"+e.regex+"` is not a valid regular expression.");
			scope.abort = True
		except sqlite3.OperationalError as e:
			print(traceback.format_exc())
			await self.print_fatal(scope, "**SQL error.** Please contact <@287858556684730378>.\nCommand line: `"+commandline+"`");
			scope.abort = True
		except Exception as e:
			print(traceback.format_exc())
			await self.print_fatal(scope, "**PraxisBot Internal Error.** Please contact <@287858556684730378>.\nException: ``"+type(e).__name__+"``\nCommand line: `"+commandline+"`")
			scope.abort = True

		return False

	async def execute_script(self, scope, script):
		lines = script.split("\n");

		for l in lines:
			l = l.strip()

			parsedCommand = self.find_command_and_options(l, scope.prefixes)
			if not parsedCommand:
				continue

			await scope.execute_script(parsedCommand[0], l)

			if scope.abort:
				break

	async def send_message(self, channel, text, e=None):
		if e:
			return await self.client.send_message(channel, text, embed=e)
		else:
			return await self.client.send_message(channel, text)

	def find_server(self, server_name):
		for s in self.client.servers:
			if s.id == server_name:
				return s
		return None

	def find_channel(self, chan_name, server):
		if not chan_name:
			return None

		chan_name = chan_name.strip()

		for c in server.channels:
			if c.name == chan_name:
				return c
			elif c.id == chan_name:
				return c
			elif "<#"+c.id+">" == chan_name:
				return c
			elif "#"+c.id == chan_name:
				return c
		return None

	def find_member(self, member_name, server):
		if not member_name:
			return None

		member_name = member_name.strip()

		for m in server.members:
			if "<@"+m.id+">" == member_name:
				return m
			if "<@!"+m.id+">" == member_name:
				return m
			elif m.name+"#"+m.discriminator == member_name:
				return m
			elif m.id == member_name:
				return m

		return None

	def find_role(self, role_name, server):
		if not role_name:
			return None

		for r in server.roles:
			if "<@&"+r.id+">" == role_name:
				return r
			elif r.id == role_name:
				return r
			elif r.name == role_name:
				return r

		return None

	def find_emoji(self, emoji_name, server):
		if not emoji_name:
			return None

		for e in server.emojis:
			if "<:"+e.name+":"+e.id+">" == emoji_name:
				return e
			elif e.id == emoji_name:
				return e
			elif e.name == emoji_name:
				return e

		return None

	def get_default_channel(self, server):
		for c in server.channels:
			if c.type == discord.ChannelType.text:
				return c
		return None

	async def add_roles(self, member, roles):
		try:
			await self.client.add_roles(member, *roles)
		except:
			pass
			return False
		return True

	async def remove_roles(self, member, roles):
		try:
			await self.client.remove_roles(member, *roles)
		except:
			pass
			return False
		return True

	async def change_roles(self, member, rolesToAdd, rolesToRemove):

		roles = member.roles
		rolesAdded = []
		rolesRemoved = []
		for r in rolesToRemove:
			if r in roles:
				roles.remove(r)
				rolesRemoved.append(r)
		for r in rolesToAdd:
			if not r in roles:
				roles.append(r)
				rolesAdded.append(r)

		await self.client.replace_roles(member, *roles)
		return (rolesAdded, rolesRemoved)

	def dbtable(self, name):
		return self.dbprefix+name

	def create_sql_table(self, tablename, fields):
		sqlQuery = "CREATE TABLE IF NOT EXISTS "+self.dbtable(tablename)+" ("+", ".join(fields)+")"
		self.dbcon.execute(sqlQuery);

		for f in fields:
			try:
				sqlQuery = "ALTER TABLE "+self.dbtable(tablename)+" ADD "+f
				self.dbcon.execute(sqlQuery);
			except sqlite3.OperationalError:
				pass

	def get_sql_data(self, tablename, fields, where):
		sqlQuery = "SELECT "+", ".join(fields)+" FROM "+self.dbtable(tablename)+" "
		vars = []
		first = True
		for w in where:
			if first:
				sqlQuery = sqlQuery+" WHERE "+w+" = ?"
			else:
				sqlQuery = sqlQuery+" AND "+w+" = ?"
			vars.append(where[w])
			first = False

		c = self.dbcon.cursor()
		c.execute(sqlQuery, vars)
		r = c.fetchone()
		if r:
			return r

		return None

	def set_sql_data(self, tablename, fields, where, id="id"):
		idFound = self.get_sql_data(tablename, [id], where)
		if idFound:
			sqlQuery = "UPDATE "+self.dbtable(tablename)+" "
			vars = []
			first = True
			for f in fields:
				if first:
					sqlQuery = sqlQuery+" SET "+f+" = ?"
				else:
					sqlQuery = sqlQuery+", "+f+" = ?"
				vars.append(fields[f])
				first = False
			sqlQuery = sqlQuery+" WHERE "+id+" = ?"
			vars.append(idFound[0])

			self.dbcon.execute(sqlQuery, vars)
		else:
			sqlQuery = "INSERT INTO "+self.dbtable(tablename)+" ("
			vars = []
			first = True
			for f in fields:
				if not first:
					sqlQuery = sqlQuery+", "
				sqlQuery = sqlQuery+f
				vars.append(fields[f])
				first = False
			for w in where:
				if not first:
					sqlQuery = sqlQuery+", "
				sqlQuery = sqlQuery+w
				vars.append(where[w])
				first = False
			sqlQuery = sqlQuery+") VALUES ("
			first = True
			for f in fields:
				if not first:
					sqlQuery = sqlQuery+", "
				sqlQuery = sqlQuery+"?"
				first = False
			for w in where:
				if not first:
					sqlQuery = sqlQuery+", "
				sqlQuery = sqlQuery+"?"
				first = False
			sqlQuery = sqlQuery+")"

			self.dbcon.execute(sqlQuery, vars)

	def update_sql_data(self, tablename, fields, where):
		sqlQuery = "UPDATE "+self.dbtable(tablename)+" "
		vars = []
		first = True
		for f in fields:
			if first:
				sqlQuery = sqlQuery+" SET "+f+" = ?"
			else:
				sqlQuery = sqlQuery+", "+f+" = ?"
			vars.append(fields[f])
			first = False
		first = True
		for w in where:
			if first:
				sqlQuery = sqlQuery+" WHERE "+w+" = ?"
			else:
				sqlQuery = sqlQuery+" AND "+w+" = ?"
			vars.append(where[w])
			first = False

		self.dbcon.execute(sqlQuery, vars)

	def add_sql_data(self, tablename, fields):
		sqlQuery = "INSERT INTO "+self.dbtable(tablename)+" ("
		vars = []
		first = True
		for f in fields:
			if not first:
				sqlQuery = sqlQuery+", "
			sqlQuery = sqlQuery+f
			vars.append(fields[f])
			first = False
		sqlQuery = sqlQuery+") VALUES ("
		first = True
		for f in fields:
			if not first:
				sqlQuery = sqlQuery+", "
			sqlQuery = sqlQuery+"?"
			first = False
		sqlQuery = sqlQuery+")"
		c = self.dbcon.cursor()
		c.execute(sqlQuery, vars)
		return c.lastrowid

	def delete_sql_data(self, tablename, where):
		sqlQuery = "DELETE FROM "+self.dbtable(tablename)+" "
		vars = []
		first = True
		for w in where:
			if first:
				sqlQuery = sqlQuery+" WHERE "+w+" = ?"
			else:
				sqlQuery = sqlQuery+" AND "+w+" = ?"
			vars.append(where[w])
			first = False

		self.dbcon.execute(sqlQuery, vars)

################################################################################
# Plugin
################################################################################

class Plugin:
	"""
	Base class of all plugins
	"""

	def __init__(self, shell):
		self.shell = shell
		self.cmds = {}

	async def on_loop(self, scope):
		return

	async def list_commands(self, server):
		return list(self.cmds.keys())

	async def execute_unregistered_command(self, scope, command, options, lines):
		return False

	async def execute_command(self, scope, command, options, lines):
		if command in self.cmds:
			scope.iter = scope.iter+1
			await self.cmds[command](scope, command, options, lines)
			return True
		return await self.execute_unregistered_command(scope, command, options, lines)

	async def on_member_join(self, scope):
		return False

	async def on_member_leave(self, scope):
		return False

	async def on_ban(self, scope):
		return False

	async def on_unban(self, scope):
		return False

	async def on_message(self, scope, message, command_found):
		return False

	async def on_reaction(self, scope, reaction):
		return False

	def add_command(self, name, cmd):
		self.cmds[name] = cmd

	async def parse_options(self, scope, parser, options):
		isValid = False

		argParseOutput = io.StringIO()
		argParseError = io.StringIO()
		try:
			with RedirectOutput(argParseOutput, argParseError):
				args = parser.parse_args(shlex.split(options))
				return args
		except:
			if argParseOutput.getvalue():
				await self.shell.print_info(scope, argParseOutput.getvalue())
			if argParseError.getvalue():
				text = argParseError.getvalue()
				if text.find(parser.prog+": error:") >= 0:
					parts = text.split(parser.prog+": error: ")
					await self.shell.print_error(scope, parts[1]+"\n"+parts[0])
				else:
					await self.shell.print_error(scope, argParseError.getvalue())
			pass

		return None

	def ensure_object_name(self, parameter, name):
		if not re.fullmatch('[a-zA-Z_][a-zA-Z0-9_]*', name):
			raise ObjectNameError(parameter, name)

	def ensure_object_id(self, parameter, name):
		if not re.fullmatch('[0-9_]+', name):
			raise ObjectIdError(parameter, name)

	def ensure_integer(self, parameter, name):
		if not re.fullmatch('[0-9_]+', name):
			raise IntegerError(parameter)

	def ensure_regex(self, regex):
		try:
		    re.compile(regex)
		except re.error:
		    raise RegexError(regex)

################################################################################
# MessageStream
################################################################################

class MessageStream:
	"""
	Send long messages. Automatic splitting of messages
	"""
	def __init__(self, scope):
		self.scope = scope
		self.text = ""
		self.monospace = False

	async def flush(self):
		if self.monospace:
			self.text = self.text+"\n```"
		await self.scope.shell.client.send_message(self.scope.channel, self.text)
		if self.monospace:
			self.text = "```\n"
		else:
			self.text = ""

	async def send(self, text):
		if self.monospace:
			self.monospace = False
			self.text = self.text+"\n```"

		if len(self.text)+len(text) < 1800:
			self.text = self.text+text
		else:
			await self.flush()
			self.text = self.text+text

	async def send_monospace(self, text):
		if not self.monospace:
			self.monospace = True
			self.text = self.text+"```\n"

		if len(self.text)+len(text) < 1800:
			self.text = self.text+text
		else:
			await self.flush()
			self.text = self.text+text

	async def finish(self):
		await self.flush()
