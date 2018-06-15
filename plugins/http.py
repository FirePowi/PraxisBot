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
import requests
from plugin import Plugin
from scope import UserPermission
from scope import ExecutionScope
from scope import ExecutionBlock

class HTTPPlugin(Plugin):
	"""
	HTTP commands
	"""

	name = "HTTP"

	def __init__(self, ctx):
		super().__init__(ctx)

	async def execute_if_http(self, command, options, scope):
		parser = argparse.ArgumentParser(description='Perform tests on URLs. Don\'t forget to add an endif line.', prog=command)
		parser.add_argument('url', help='First values', metavar='VALUE')
		parser.add_argument('--valid', action='store_true', help='Test if the URL is valid.')
		parser.add_argument('--not', dest='inverse', action='store_true', help='Inverse the result of the test')

		args = await self.parse_options(scope.channel, parser, options)

		if args:
			res = False
			if args.valid:
				url = self.ctx.format_text(args.url, scope)
				httpResult = requests.head(url, allow_redirects=True)
				res = httpResult.ok
			if args.inverse:
				res = not res

			newScope = scope
			newScope.blocks.append(ExecutionBlock("endif", res))
			return newScope

		return scope


	async def list_commands(self, server):
		return ["if_http"]

	async def execute_command(self, shell, command, options, scope):
		if command == "if_http":
			scope.iter = scope.iter+1
			return await self.execute_if_http(command, options, scope)

		return scope
