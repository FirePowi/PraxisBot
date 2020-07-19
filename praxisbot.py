"""

Copyright (C) 2018 MonaIzquierda (mona.izquierda@gmail.com)
Copyright (C) 2020 Powi (powi@powi.fr)

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
	def __init__(self, shell, guild, prefixes):
		self.shell = shell
		self.prefixes = prefixes
		self.guild = guild
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
		subScope = ExecutionScope(self.shell, self.guild, self.prefixes)

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
				u = self.shell.find_member(subUser, self.guild)
				tag = user_chk.group(1)

			c = self.channel
			channel_chk = re.fullmatch('([*#]?channel)=(.*)', tag)
			if channel_chk:
				subChan = channel_chk.group(2).strip()
				if subChan in self.vars:
					subChan = self.vars[subChan]
				c = self.shell.find_channel(subChan, self.guild)
				tag = channel_chk.group(1)

			r = None
			role_chk = re.fullmatch('([*@]?role)=(.*)', tag)
			if role_chk:
				subRole = role_chk.group(2).strip()
				if subRole in self.vars:
					subRole = self.vars[subRole]
				r = self.shell.find_role(subRole, self.guild)
				tag = role_chk.group(1)

			if tag.lower() == "server" and self.guild:
				tagOutput = self.guild.name
			elif tag.lower() == "*server" and self.guild:
				tagOutput = self.guild.id
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
				tagOutput = "{}#{}".format(u.name,u.discriminator)
			elif tag.lower() == "@user" and u:
				tagOutput = u.mention
			elif tag.lower() == "*user" and u:
				tagOutput = u.id
			elif tag.lower() == "user" and u:
				tagOutput = u.display_name
			elif tag.lower() == "user_time" and u:
				tagOutput = str(u.created_at)
			elif tag.lower() == "user_avatar" and u:
				tagOutput = str(u.avatar_url_as(format="png"))
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
	def __init__(self, client, dbprefix, dbcon, dbfile):
		self.plugins = []
		self.client = client
		self.dbprefix = dbprefix
		self.dbcon = dbcon
		self.dbfile = dbfile

	async def print_info(self, scope, msg):
		if scope.verbose >= 2:
			await scope.channel.send(msg)
		return

	async def print_debug(self, scope, msg):
		if scope.verbose >= 3:
			await scope.channel.send(":large_blue_circle: {}".format(msg))
		return

	async def print_success(self, scope, msg):
		if scope.verbose >= 2:
			await scope.channel.send(":white_check_mark: {}".format(msg))
		return

	async def print_permission(self, scope, msg):
		if scope.verbose >= 1:
			await scope.channel.send(":closed_lock_with_key: {}".format(msg))
		return

	async def print_error(self, scope, msg):
		if scope.verbose >= 1:
			await scope.channel.send(":no_entry: {}".format(msg))
		return

	async def print_fatal(self, scope, msg):
		if scope.verbose >= 1:
			await scope.channel.send(":skull_crossbones: {}".format(msg))
		return
	
	def is_plugin_loaded(self, plugin):
		for p in self.plugins:
			if type(p) == plugin:
				return True
		return False

	def load_plugin(self, plugin):
		"""
		Create an instance of a plugin and register it
		"""
		if self.is_plugin_loaded(plugin):
			print("Plugin {} already loaded".format(plugin.name))
			return
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
			for row in c.execute("SELECT name, value FROM {} WHERE discord_sid = {}".format(self.dbtable("variables"),scope.guild.id)):
				scope.vars[row[0]] = row[1]

		return scope

	async def execute_command(self, scope, commandline):
		try:
			if scope.iter > 128:
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
			await self.print_error(scope, "Command `{}` not found.".format(e.command))
			scope.abort = True
		except AdminPermissionError as e:
			await self.print_permission(scope, "This command is restricted to administrators.")
			scope.abort = True
		except ScriptPermissionError as e:
			await self.print_permission(scope, "This command is restricted to scripts and administrators.")
			scope.abort = True
		except ParameterPermissionError as e:
			await self.print_permission(scope, "You are not allowed to use the parameter `{}`.".format(e.parameter))
			scope.abort = True
		except ObjectNameError as e:
			await self.print_error(scope, "{} must be a letter followed by alphanumeric characters.".format(e.parameter))
			scope.abort = True
		except ObjectIdError as e:
			await self.print_error(scope, "{} must be a number.".format(e.parameter))
			scope.abort = True
		except IntegerError as e:
			await self.print_error(scope, "{} must be a number.".format(e.parameter))
			scope.abort = True
		except RegexError as e:
			await self.print_error(scope, "`{}` is not a valid regular expression.".format(e.regex))
			scope.abort = True
		except sqlite3.OperationalError as e:
			print(traceback.format_exc())
			await self.print_fatal(scope, "**SQL error.** Please contact <@203135242813440001>.\nCommand line: `{}`".format(commandline))
			scope.abort = True
		except Exception as e:
			print(traceback.format_exc())
			await self.print_fatal(scope, "**PraxisBot Internal Error.** Please contact <@203135242813440001>.\nException: ``{}``\nCommand line: `{}`".format(type(e).__name__,commandline))
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

	async def send(self, channel, text, e=None):
		if e:
			return await self.client.send(channel, text, embed=e)
		else:
			return await self.client.send(channel, text)

	def find_server(self, server_name):
		for s in self.client.guilds:
			if s.id == server_name:
				return s
		return None

	def find_channel(self, chan_name, server):
		if not chan_name:
			return None
		print("searching for chan {}".format(chan_name))
		chan_name = str(chan_name).strip()
		for c in server.channels:
			if c.name == chan_name:
				return c
			elif str(c.id) == chan_name:
				return c
			elif "<#{}>".format(c.id) == chan_name:
				return c
			elif "#{}".format(c.id) == chan_name:
				return c
		print("No chan found")
		return None

	def find_member(self, member_name, server):
		if not member_name:
			return None

		member_name = member_name.strip()

		for m in server.members:
			if "<@{}>".format(m.id) == member_name:
				return m
			if "<@!{}>".format(m.id) == member_name:
				return m
			elif "{}#{}".format(m.name,m.discriminator) == member_name:
				return m
			elif m.id == member_name:
				return m

		return None

	def find_role(self, role_name, server):
		if not role_name:
			return None

		for r in server.roles:
			if "<@&{}>".format(r.id) == role_name:
				return r
			elif r.id == role_name:
				return r
			elif r.name == role_name:
				return r

		return None

	def find_emoji(self, emoji_name, guild):
		if not emoji_name:
			return None

		for e in guild.emojis:
			if "<:{}:{}>".format(e.name,e.id) == emoji_name:
				return e
			elif e.id == emoji_name:
				return e
			elif e.name == emoji_name:
				return e

		return None

	def get_default_channel(self, guild):
		for c in guild.channels:
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

		await member.edit(roles=roles)
		return (rolesAdded, rolesRemoved)

	def dbtable(self, name):
		return self.dbprefix+name

	def create_sql_table(self, tablename, fields):
		sqlQuery = "CREATE TABLE IF NOT EXISTS {} ({})".format(self.dbtable(tablename),", ".join(fields))
		self.dbcon.execute(sqlQuery);

		for f in fields:
			try:
				sqlQuery = "ALTER TABLE {} ADD {}".format(self.dbtable(tablename),f)
				self.dbcon.execute(sqlQuery);
			except sqlite3.OperationalError:
				pass

	def get_sql_data(self, tablename, fields, where, array=False):
		sqlQuery = "SELECT {} FROM {}".format(", ".join(fields),self.dbtable(tablename))
		vars = list(where.values())
		if where:
			sqlQuery+=" WHERE {} = ?".format(" = ? AND ".join(where.keys()))

		c = self.dbcon.cursor()
		print("REQUEST : {}; with {}".format(sqlQuery,vars))
		datas = c.execute(sqlQuery,vars)
		r = c.fetchall() if array else c.fetchone()
		if r:
			print("RÉSULTS : {}".format(r))
			return r

		return None

	def set_sql_data(self, tablename, fields, where, id="id"):
		idFound = self.get_sql_data(tablename, [id], where)
		db = self.dbtable(tablename)
		if idFound:
			sqlQuery = "UPDATE {} SET {} = ? WHERE {} = ?".format(db," = ?, ".join(fields.keys()),id)
			vars = list(fields.values()) + list(idFound)
			print("REQUEST : {}; with {}".format(sqlQuery,vars))
			self.dbcon.execute(sqlQuery, vars)
		else:
			fnw = list(fields)+list(where)
			sqlQuery = "INSERT INTO {} ({}) VALUES ({})".format(db,", ".join(fnw),", ".join(["?"]*len(fnw)))
			vars = list(fields.values()) + list(where.values())
			print("REQUEST : {}; with {}".format(sqlQuery,vars))
			self.dbcon.execute(sqlQuery, vars)

	def update_sql_data(self, tablename, fields, where):
		db = self.dbtable(tablename)
		sqlQuery = "UPDATE {} SET {} = ?".format(db, " = ?, ".join(fields.keys()))
		vars = list(fields.values()) + list(where.values())
		first = True
		if where:
			sqlQuery += " WHERE {} = ?".format(" = ? AND ".join(where))
		print("REQUEST : {}; with {}".format(sqlQuery,vars))
		self.dbcon.execute(sqlQuery, vars)

	def add_sql_data(self, tablename, fields):
		sqlQuery = "INSERT INTO {} ({}) VALUES ({})".format(self.dbtable(tablename),", ".join(fields.keys()),", ".join(["?"]*len(fields)))
		vars = list(fields.values())
		print("REQUEST : {}; with {}".format(sqlQuery,vars))
		c = self.dbcon.cursor()
		c.execute(sqlQuery, vars)
		print("RESULT : {}".format(c.lastrowid))
		return c.lastrowid

	def delete_sql_data(self, tablename, where):
		sqlQuery = "DELETE FROM {} WHERE {} = ?".format(self.dbtable(tablename)," = ? AND ".join(where.keys()))
		vars = list(where.values())
		print("REQUEST : {}; with {}".format(sqlQuery,vars))

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
		await self.scope.channel.send(self.text)
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
