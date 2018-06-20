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
import traceback
import datetime
import io
import sqlite3
from io import StringIO
from plugin import Plugin
from scope import UserPermission
from scope import ExecutionScope
from scope import ExecutionBlock

class PollPlugin(Plugin):
	"""
	Moderation commands
	"""

	name = "Poll"

	def __init__(self, ctx, shell):
		super().__init__(ctx)

		try:
			with self.ctx.dbcon:
				self.ctx.dbcon.execute("CREATE TABLE IF NOT EXISTS "+self.ctx.dbprefix+"polls(id INTEGER PRIMARY KEY, discord_sid INTEGER, start_time DATETIME, duration INTEGER, description TEXT)");
				self.ctx.dbcon.execute("CREATE TABLE IF NOT EXISTS "+self.ctx.dbprefix+"votes(id INTEGER PRIMARY KEY, poll INTEGER, discord_uid INTEGER, value INTEGER, vote_time DATETIME)");

		except:
			print(traceback.format_exc())

	async def execute_start_poll(self, command, options, scope):
		parser = argparse.ArgumentParser(description='Start a poll.', prog=command)
		parser.add_argument('--force', '-f', action='store_true', help='Replace the trigger if it already exists')

		args = await self.parse_options(scope.channel, parser, options)

		if not args:
			return scope

		return scope

	async def list_commands(self, server):
		return ["start_poll"]

	async def execute_command(self, shell, command, options, scope):
		if command == "start_poll":
			scope.iter = scope.iter+1
			return await self.execute_start_poll(command, options, scope)

		return scope
