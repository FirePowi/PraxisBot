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
from plugin import Plugin
from scope import UserPermission
from scope import ExecutionScope
from scope import ExecutionBlock

class HTTPPlugin(Plugin):
	"""
	HTTP commands
	"""

	name = "HTTP"

	def __init__(self, ctx, shell):
		super().__init__(ctx)

		self.cookiename_regex = re.compile('[a-zA-Z0-9_-]+')

		self.ctx.dbcon.execute("CREATE TABLE IF NOT EXISTS "+self.ctx.dbprefix+"cookies(id INTEGER PRIMARY KEY, nameid TEXT, discord_sid INTEGER, name TEXT, content TEXT, filter TEXT)");

	async def execute_add_cookie(self, command, options, scope):
		scope.deletecmd = True

		if scope.permission < UserPermission.Admin:
			await self.ctx.send_message(scope.channel, "Only admins can use this command.")
			return scope

		content = options.split("\n");
		if len(content) > 1:
			options = content[0]
			content = content[1:]
		else:
			await self.ctx.send_message(scope.channel, "Missing cookie content. Please write the content in the same message, just the line after the command. Ex.:```\nadd_cookie my_new_cookie\nCONTENT\"```")

		parser = argparse.ArgumentParser(description='Add a cookie for HTTP requests.', prog=command)
		parser.add_argument('id', help='ID of the cookie. This ID is used to delete the cookie.')
		parser.add_argument('name', help='Name of the cookie.')
		parser.add_argument('filter', help='Regular expression that restrict usage of the cookie.')

		args = await self.parse_options(scope.channel, parser, options)

		if not args:
			return scope

		if not self.cookiename_regex.fullmatch(args.id):
			await self.ctx.send_message(scope.channel, "The cookie ID must be alphanumeric")
			return scope

		try:
			with self.ctx.dbcon:
				c = self.ctx.dbcon.cursor()
				c.execute("SELECT id FROM "+self.ctx.dbprefix+"cookies WHERE discord_sid = ? AND nameid = ?", [int(scope.server.id), str(args.id)])
				r = c.fetchone()
				if r:
					await self.ctx.send_message(scope.channel, "The cookie `"+args.id+"` already exists.")
					return scope

				if not self.ctx.dbcon.execute("INSERT INTO "+self.ctx.dbprefix+"cookies (nameid, name, discord_sid, content, filter) VALUES (?, ?, ?, ?, ?)", [str(args.id), str(args.name), int(scope.server.id), str(content), str(args.filter)]):
					await self.ctx.send_message(scope.channel, "The cookie `"+args.id+"` can't be created.")
		except:
			await self.ctx.send_message(scope.channel, "The cookie `"+args.name+"` can't be created.")

		return scope

	async def execute_cookies(self, command, options, scope):
		if scope.permission < UserPermission.Admin:
			await self.ctx.send_message(scope.channel, "Only admins can use this command.")
			return scope

		text = "**List of HTTP cookies**\n"

		with self.ctx.dbcon:
			c = self.ctx.dbcon.cursor()
			for row in c.execute("SELECT nameid FROM "+self.ctx.dbprefix+"cookies WHERE discord_sid = ? ORDER BY name", [int(scope.server.id)]):
				text = text+"\n - "+row[0]

		await self.ctx.send_message(scope.channel, text)

		return scope

	async def execute_if_http(self, command, options, scope):
		if scope.permission < UserPermission.Script:
			await self.ctx.send_message(scope.channel, "Only scripts can use this command.")
			return scope

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

			scope.blocks.append(ExecutionBlock("endif", "else", res))
			return scope

		return scope

	async def execute_download(self, command, options, scope):
		if scope.permission < UserPermission.Script:
			await self.ctx.send_message(scope.channel, "Only scripts can use this command.")
			return scope

		parser = argparse.ArgumentParser(description='Download from an URL.', prog=command)
		parser.add_argument('url', help='URL to download')
		parser.add_argument('filename', help='Filename sent in Discord')
		parser.add_argument('--cookie', help='Name of a cookie to send with the request.')

		args = await self.parse_options(scope.channel, parser, options)

		if not args:
			return scope

		url = self.ctx.format_text(args.url, scope)
		result = None
		try:
			cookies = {}
			if args.cookie:
				with self.ctx.dbcon:
					c = self.ctx.dbcon.cursor()
					c.execute("SELECT name, content, filter FROM "+self.ctx.dbprefix+"cookies WHERE discord_sid = ? AND nameid = ?", [int(scope.server.id), str(args.cookie)])
					row = c.fetchone()
					if row:
						if re.fullmatch(row[2], args.url):
							cookies[row[0]] = row[1]
						else:
							await self.ctx.send_message(scope.channel, "This cookie can't be used with this URL.")

			result = requests.get(url, allow_redirects=True, cookies=cookies, stream=True)
			if not result.ok:
				await self.ctx.send_message(scope.channel, "The page `"+url+"` can't be loaded ("+result.status_code+").")
				return scope

		except:
			print(traceback.format_exc())
			await self.ctx.send_message(scope.channel, "The page `"+url+"` can't be loaded.")
			return scope

		if not result:
			await self.ctx.send_message(scope.channel, "The page `"+url+"` can't be loaded.")
			return scope

		f = io.BytesIO(result.content)
		await self.ctx.client.send_file(scope.channel, f, filename=args.filename)
		f.close()

		return scope

	async def execute_parse_http(self, command, options, scope):
		if scope.permission < UserPermission.Script:
			await self.ctx.send_message(scope.channel, "Only scripts can use this command.")
			return scope

		parser = argparse.ArgumentParser(description='Download and parse using REGEX from an URL.', prog=command)
		parser.add_argument('url', help='URL to download')
		parser.add_argument('regex', help='Regular expression to apply on the downloaded file.')
		parser.add_argument('--group', help='Group of the regular expression to return. Must be a number.', default=0)
		parser.add_argument('--output', help='Format of the output. Use {{result}} to get the groups.', default="{{result}}")
		parser.add_argument('--cookie', help='Name of a cookie to send with the request.')

		args = await self.parse_options(scope.channel, parser, options)

		if not args:
			return scope

		url = self.ctx.format_text(args.url, scope)
		result = None
		try:
			cookies = {}
			if args.cookie:
				with self.ctx.dbcon:
					c = self.ctx.dbcon.cursor()
					c.execute("SELECT name, content, filter FROM "+self.ctx.dbprefix+"cookies WHERE discord_sid = ? AND nameid = ?", [int(scope.server.id), str(args.cookie)])
					row = c.fetchone()
					if row:
						if re.fullmatch(row[2], args.url):
							cookies[row[0]] = row[1]
						else:
							await self.ctx.send_message(scope.channel, "This cookie can't be used with this URL.")

			result = requests.get(url, allow_redirects=True, cookies=cookies)
			if not result.ok:
				await self.ctx.send_message(scope.channel, "The page `"+url+"` can't be loaded ("+result.status_code+").")
				return scope

		except:
			print(traceback.format_exc())
			await self.ctx.send_message(scope.channel, "The page `"+url+"` can't be loaded.")
			return scope

		if not result:
			await self.ctx.send_message(scope.channel, "The page `"+url+"` can't be loaded.")
			return scope

		try:
			res = re.search(args.regex, result.text)
			if res:
				scope.vars["result"] = res.group(int(args.group))
				if args.output and len(args.output)>0:
					await self.ctx.send_message(scope.channel, self.ctx.format_text(args.output, scope))
			else:
				await self.ctx.send_message(scope.channel, "The regular expression didn't match anything.")
		except:
			await self.ctx.send_message(scope.channel, "The page `"+url+"` can't be parsed.")
			return scope

		return scope

	async def list_commands(self, server):
		return ["if_http", "parse_http", "add_cookie", "cookies", "download"]

	async def execute_command(self, shell, command, options, scope):
		if command == "if_http":
			scope.iter = scope.iter+1
			return await self.execute_if_http(command, options, scope)
		elif command == "parse_http":
			scope.iter = scope.iter+1
			return await self.execute_parse_http(command, options, scope)
		elif command == "add_cookie":
			scope.iter = scope.iter+1
			return await self.execute_add_cookie(command, options, scope)
		elif command == "cookies":
			scope.iter = scope.iter+1
			return await self.execute_cookies(command, options, scope)
		elif command == "download":
			scope.iter = scope.iter+1
			return await self.execute_download(command, options, scope)

		return scope
