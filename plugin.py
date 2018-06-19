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
import context
import traceback
import shlex
import copy

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

	async def execute_script(self, shell, script, scope):
		subScope = copy.deepcopy(scope)
		subScope.level = subScope.level+1
		for s in script:
			s = s.strip()

			args = s.split(" ");
			c = args[0]
			b = None
			if len(subScope.blocks) > 0:
				b = subScope.blocks[len(subScope.blocks)-1]
			if b and b.endname == c:
				subScope.blocks.pop()
			elif b and b.elsename == c:
				subScope.blocks[len(subScope.blocks)-1].execute = not subScope.blocks[len(subScope.blocks)-1].execute
			elif not b or b.execute:
				o = " ".join(args[1:])
				subScope = await shell.execute_command(c, o, subScope)
				if subScope.abort:
					break
		newScope = copy.deepcopy(subScope)
		newScope.level = newScope.level-1
		return newScope

	async def dump(self, server):
		return []

	async def list_commands(self, server):
		return []

	async def execute_command(self, shell, command, scope):
		return scope

	async def on_member_join(self, shell, scope):
		return False

	async def on_member_leave(self, shell, scope):
		return False

	async def on_ban(self, shell, scope):
		return False

	async def on_unban(self, shell, scope):
		return False
