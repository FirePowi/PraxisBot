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
import traceback
import io
import praxisbot

class HTTPPlugin(praxisbot.Plugin):
	"""
	HTTP commands
	"""

	name = "HTTP"

	def __init__(self, shell):
		super().__init__(shell)

		self.cookiename_regex = re.compile('[a-zA-Z0-9_-]+')

		self.shell.create_sql_table("cookies", ["id INTEGER PRIMARY KEY", "nameid TEXT", "discord_sid INTEGER", "name TEXT", "content TEXT", "filter TEXT"])

		self.add_command("if_http", self.execute_if_http)
		self.add_command("parse_http", self.execute_parse_http)
		self.add_command("create_cookie", self.execute_create_cookie)
		self.add_command("cookies", self.execute_cookies)
		self.add_command("download", self.execute_download)

	@praxisbot.command
	async def execute_create_cookie(self, scope, command, options, lines, **kwargs):
		"""
		Create a cookie for HTTP requests.
		"""

		scope.deletecmd = True

		parser = argparse.ArgumentParser(description=kwargs["description"], prog=command)
		parser.add_argument('id', help='ID of the cookie. This ID is used to delete the cookie.')
		parser.add_argument('name', help='Name of the cookie.')
		parser.add_argument('filter', help='Regular expression that restrict usage of the cookie.')
		args = await self.parse_options(scope, parser, options)
		if not args:
			return

		if len(lines) == 0:
			await self.shell.print_error(scope, "Missing cookie content. Please write the content in the same message, just the line after the command. Ex.:```\nadd_cookie my_new_cookie\nCONTENT\"```")
			return

		self.ensure_object_name("Cookie ID", args.id)

		cookieID = scope.shell.get_sql_data("cookies", ["id"], {"discord_sid": int(scope.server.id), "nameid": str(args.id)})
		if cookieID:
			await scope.shell.print_error(scope, "The cookie `"+str(args.id)+"` already exists.")
			return

		scope.shell.set_sql_data("cookies", {"name": str(args.name), "content": str("\n".join(lines)), "filter": str(args.filter)}, {"discord_sid": int(scope.server.id), "nameid": str(args.id)})
		await scope.shell.print_success(scope, "Cookie `"+str(args.id)+"` added.")

	@praxisbot.command
	@praxisbot.permission_admin
	async def execute_cookies(self, scope, command, options, lines, **kwargs):
		"""
		List all cookies.
		"""

		parser = argparse.ArgumentParser(description=kwargs["description"], prog=command)
		args = await self.parse_options(scope, parser, options)
		if not args:
			return

		stream = praxisbot.MessageStream(scope)
		await stream.send("**List of HTTP cookies**\n")

		with scope.shell.dbcon:
			c = scope.shell.dbcon.cursor()
			for row in c.execute("SELECT nameid, filter FROM "+scope.shell.dbtable("cookies")+" WHERE discord_sid = ? ORDER BY name", [int(scope.server.id)]):
				await stream.send("\n - "+row[0]+": `"+row[1]+"`")

		await stream.finish()

	@praxisbot.command
	@praxisbot.permission_script
	async def execute_if_http(self, scope, command, options, lines, **kwargs):
		"""
		Perform tests on URLs. Used with `endif`.
		"""

		parser = argparse.ArgumentParser(description=kwargs["description"], prog=command)
		parser.add_argument('url', help='First values', metavar='VALUE')
		parser.add_argument('--valid', action='store_true', help='Test if the URL is valid.')
		parser.add_argument('--not', dest='inverse', action='store_true', help='Inverse the result of the test')
		args = await self.parse_options(scope, parser, options)
		if not args:
			return


		res = False
		if args.valid:
			url = scope.format_text(args.url)
			httpResult = requests.head(url, allow_redirects=True)
			res = httpResult.ok

		if args.inverse:
			res = not res

		scope.blocks.append(praxisbot.ExecutionBlockIf(res))

	@praxisbot.command
	@praxisbot.permission_script
	async def execute_download(self, scope, command, options, lines, **kwargs):
		"""
		Download from an URL.
		"""

		parser = argparse.ArgumentParser(description=kwargs["description"], prog=command)
		parser.add_argument('url', help='URL to download')
		parser.add_argument('filename', help='Filename sent in Discord')
		parser.add_argument('--cookie', help='Name of a cookie to send with the request.')
		args = await self.parse_options(scope, parser, options)
		if not args:
			return

		url = scope.format_text(args.url)
		result = None
		cookies = {}
		if args.cookie:
			cookieData = scope.shell.get_sql_data("cookies", ["name", "content", "filter"], {"discord_sid": int(scope.server.id), "nameid": str(args.cookie)})
			if not cookieData:
				await scope.shell.print_error(scope, "Cookie `"+args.cookie+"` not found.")
				return
			if not re.fullmatch(cookieData[2], url):
				await scope.shell.print_error(scope, "This cookie can't be used with this URL.")
				return

			cookies[cookieData[0]] = cookieData[1]

		try:
			result = requests.get(url, allow_redirects=True, cookies=cookies, stream=True)
			if not result.ok:
				result = None

		except:
			result = None

		if not result:
			await scope.shell.print_error(scope, "The page `"+url+"` can't be loaded.")
			return

		f = io.BytesIO(result.content)
		await scope.shell.client.send_file(scope.channel, f, filename=args.filename)
		f.close()

	@praxisbot.command
	@praxisbot.permission_script
	async def execute_parse_http(self, scope, command, options, lines, **kwargs):
		"""
		Download and parse using REGEX from an URL.
		"""

		parser = argparse.ArgumentParser(description=kwargs["description"], prog=command)
		parser.add_argument('url', help='URL to download')
		parser.add_argument('regex', help='Regular expression to apply on the downloaded file.')
		parser.add_argument('--output', help='Format of the output. Use {{result}}, {{result0}}, {{result1}}, ....', default="{{result}}")
		parser.add_argument('--cookie', help='Name of a cookie to send with the request.')
		args = await self.parse_options(scope, parser, options)
		if not args:
			return

		url = scope.format_text(args.url)
		result = None
		cookies = {}
		if args.cookie:
			cookieData = scope.shell.get_sql_data("cookies", ["name", "content", "filter"], {"discord_sid": int(scope.server.id), "nameid": str(args.cookie)})
			if not cookieData:
				await scope.shell.print_error(scope, "Cookie `"+args.cookie+"` not found.")
				return
			if not re.fullmatch(cookieData[2], url):
				await scope.shell.print_error(scope, "This cookie can't be used with this URL.")
				return

			cookies[cookieData[0]] = cookieData[1]

		try:
			result = requests.get(url, allow_redirects=True, cookies=cookies)
			if not result.ok:
				result = None

		except:
			result = None

		if not result:
			await scope.shell.print_error(scope, "The page `"+url+"` can't be loaded.")
			return

		res = None
		try:
			res = re.search(args.regex, result.text)
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
