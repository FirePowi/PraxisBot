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

import sys
import io
import context
import traceback
import shlex

class RedirectOutput():
	def __init__(self, dest):
		self.dest = dest
		self.old_stdout = sys.stdout
		self.old_stderr = sys.stderr
	
	def __enter__(self):
		sys.stdout = self.dest
		sys.stderr = self.dest
	
	def __exit__(self, *args):
		sys.stdout = self.old_stdout
		sys.stderr = self.old_stderr

class UserPermission:
	Member=0
	Script=1
	Admin=2
	
class Plugin:
		
	"""
	Base class of all plugins
	"""
	def __init__(self, ctx):
		self.ctx = ctx
		
	async def parse_options(self, channel, parser, options):
		isValid = False
		
		argParseOutput = io.StringIO()
		try:
			with RedirectOutput(argParseOutput):
				args = parser.parse_args(shlex.split(options))
				return args
		except:
			await self.ctx.send_message(channel, argParseOutput.getvalue())
			pass
		
		return None
	
	async def execute_command(self, shell, command, server, channel, author, perm, level):
		return False
	
	async def on_member_join(self, shell, member):
		return False
	
	async def on_member_leave(self, shell, member):
		return False
	
	async def on_ban(self, shell, member):
		return False
	
	async def on_unban(self, shell, server, user):
		return False
