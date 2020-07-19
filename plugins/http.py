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

import shlex
import argparse
import re
import requests
import traceback
import io
import praxisbot
import discord
import lxml.html
import os

class HTTPPlugin(praxisbot.Plugin):
	"""
	HTTP commands
	"""

	name = "HTTP"

	def __init__(self, shell):
		super().__init__(shell)

		self.cookiename_regex = re.compile('[a-zA-Z0-9_-]+')

		self.shell.create_sql_table("cookies", ["id INTEGER PRIMARY KEY", "nameid TEXT", "discord_sid INTEGER", "name TEXT", "content TEXT", "filter TEXT"])
		self.shell.create_sql_table("cookies_groups", ["id INTEGER_PRIMARY_KEY", "name TEXT", "discord_sid INTEGER", "nameid TEXT"])

		self.add_command("if_http", self.execute_if_http)
		self.add_command("create_cookie", self.execute_create_cookie)
		self.add_command("group_cookies", self.execute_group_cookies)
		self.add_command("delete_cookie", self.execute_delete_cookie)
		self.add_command("cookies", self.execute_cookies)
		self.add_command("download", self.execute_download)
		self.add_command("upload", self.execute_upload)
		self.add_command("css_selector",self.execute_css_selector)
		self.add_command("extract_attribute",self.execute_extract_attribute)
		self.add_command("extract_text",self.execute_extract_text)

	@praxisbot.command
	@praxisbot.permission_admin
	async def execute_create_cookie(self, scope, command, options, lines, **kwargs):
		"""
		Create a cookie for HTTP requests.
		"""

		scope.deletecmd = True

		parser = argparse.ArgumentParser(description=kwargs["description"], prog=command)
		parser.add_argument('id', help='ID of the cookie. This ID is used to delete the cookie.')
		parser.add_argument('name', help='Name of the cookie.')
		parser.add_argument('filter', help='Regular expression that restrict usage of the cookie.')
		parser.add_argument('--force', '-f', action='store_true', help='Replace the cookie if it already exists')
		args = await self.parse_options(scope, parser, options)
		if not args:
			return

		if len(lines) == 0:
			await self.shell.print_error(scope, "Missing cookie content. Please write the content in the same message, just the line after the command. Ex.:```\nadd_cookie my_new_cookie\nCONTENT\"```")
			return

		self.ensure_object_name("Cookie ID", args.id)

		cookieID = scope.shell.get_sql_data("cookies", ["id"], {"discord_sid": int(scope.guild.id), "nameid": str(args.id)})
		if cookieID and not args.force:
			await scope.shell.print_error(scope, "The cookie `{}` already exists.".format(args.id))
			return

		scope.shell.set_sql_data("cookies", {"name": str(args.name), "content": str("\n".join(lines)), "filter": str(args.filter)}, {"discord_sid": int(scope.guild.id), "nameid": str(args.id)})
		if cookieID:
			await scope.shell.print_success(scope, "Cookie `{}` edited.".format(args.id))
		else:
			await scope.shell.print_success(scope, "Cookie `{}` added.".format(args.id))
	
	@praxisbot.command
	@praxisbot.permission_admin
	async def execute_group_cookies(self, scope, command, options, lines, **kwargs):
		"""
		Create a group of cookies
		"""
		
		scope.delete_cookie = True
		
		parser = argparse.ArgumentParser(description=kwargs["description"], prog=command)
		parser.add_argument('name', help='Name of the group of cookies.')
		parser.add_argument('cookiesID', nargs="*", help='IDs of cookies to group together')
		parser.add_argument('--force', '-f', action='store_true', help='Replace the group if it already exists')
		parser.add_argument('--append', '-a', action='store_true', help='Append to the group if it already exists')
		args = await self.parse_options(scope, parser, options)
		if not args:
			return
			
		groupID = scope.shell.get_sql_data("cookies_groups", ["id"], {"discord_sid": int(scope.guild.id), "name": str(args.name)})
		if groupID and not args.force and not args.append:
			await scope.shell.print_error(scope, "The group `{}` already exists.".format(args.name))
			return
		elif args.force:
			scope.shell.delete_sql_data("cookies_groups", {"discord_sid": scope.guild.id, "name": str(args.name)})
		
		for cookie in args.cookiesID:
			scope.shell.set_sql_data("cookies_groups", {}, {"name": str(args.name), "discord_sid": scope.guild.id, "nameid": str(cookie)})
			
		if groupID:
			await scope.shell.print_success(scope, "Group `{}` edited.".format(args.name))
		else:
			await scope.shell.print_success(scope, "Group `{}` added.".format(args.name))
		

	@praxisbot.command
	async def execute_delete_cookie(self, scope, command, options, lines, **kwargs):
		"""
		Delete a cookie.
		"""

		scope.deletecmd = True

		parser = argparse.ArgumentParser(description=kwargs["description"], prog=command)
		parser.add_argument('id', help='ID of the cookie. This ID is used to delete the cookie.')
		args = await self.parse_options(scope, parser, options)
		if not args:
			return

		self.ensure_object_name("Cookie ID", args.id)

		cookieID = scope.shell.get_sql_data("cookies", ["id"], {"discord_sid": int(scope.guild.id), "nameid": str(args.id)})
		if not cookieID:
			await scope.shell.print_error(scope, "The cookie `{}` doesn't exists.".format(args.id))
			return

		scope.shell.delete_sql_data("cookies", {"discord_sid": scope.guild.id, "nameid": str(args.id)})
		await scope.shell.print_success(scope, "Cookie `{}` deleted.".format(args.id))

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

		cookies = scope.shell.get_sql_data("cookies",["nameid","filter"],{"discord_sid":scope.guild.id},True)
		if not cookies:
			await stream.finish()
			return
		for row in cookies:
			await stream.send("\n - {}: `{}`".format(row[0],row[1]))

		groups = scope.shell.get_sql_data("cookies_groups",["name","nameid"], {"discord_sid":scope.guild.id}, True)
		if groups:
			await stream.send("\n\n**List of cookies groups**\n")
			g_names = []
			
			# Get groups names
			for g in groups:
				g_names.append(g[0])
			g_names = list(set(g_names)) # From many iteratinos to one
			
			
			for g in g_names:
				await stream.send("\nGroup : **{}**".format(g))
				cookies = scope.shell.get_sql_data("cookies_groups",["nameid"], {"discord_sid":scope.guild.id,"name":g}, True)
				for c in cookies:
					await stream.send("\n·{}".format(c[0]))
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
		parser_group = parser.add_mutually_exclusive_group()
		parser.add_argument('url', help='URL to download')
		parser.add_argument('--pdf', action="store_true", help='Send result as a pdf file (if possible)')
		parser.add_argument('--filename', help='Filename sent in Discord')
		parser.add_argument('--var', help='Variable that will contains the file')
		parser_group.add_argument('--cookie', help='Name of a cookie to send with the request.')
		parser_group.add_argument('--cookies_group', '-cg', type=str, help='Name of a goup of cookies to send with the request.')
		args = await self.parse_options(scope, parser, options)
		if not args:
			return
		
		url = scope.format_text(args.url)
		result = None
		cookies = {}
		if args.cookie:
			cookieData = scope.shell.get_sql_data("cookies", ["name", "content", "filter"], {"discord_sid": scope.guild.id, "nameid": str(args.cookie)})
			if not cookieData:
				await scope.shell.print_error(scope, "Cookie `{}` not found.".format(args.cookie))
				return
			if not re.fullmatch(cookieData[2], url):
				await scope.shell.print_error(scope, "This cookie can't be used with this URL.")
				return

			cookies[cookieData[0]] = cookieData[1]
			print("Using cookies {}".format(cookies))
		elif args.cookies_group:
			cookiesID = scope.shell.get_sql_data("cookies_groups", ["nameid"], {"discord_sid": scope.guild.id, "name": args.cookies_group},True)
			for id in cookiesID:
				nameid = id[0]
				cookieData = scope.shell.get_sql_data("cookies", ["name", "content", "filter"], {"discord_sid": scope.guild.id, "nameid": nameid})
				if not cookieData:
					await scope.shell.print_error(scope, "Cookie `{}` not found.".format(nameid))
					return
				if not re.fullmatch(cookieData[2], url):
					await scope.shell.print_error(scope, "This cookie can't be used with this URL.")
					return
				
				cookies[cookieData[0]] = cookieData[1]
			print("Using cookies {}".format(cookies))

		try:
			result = requests.get(url, allow_redirects=True, cookies=cookies, stream=True)
			if not result.ok:
				result = None

		except:
			result = None

		if not result:
			await scope.shell.print_error(scope, "The page `{}` can't be loaded.".format(url))
			return

		if args.pdf or args.filename:
			f = io.BytesIO(result.content)
			try:
				if args.filename:
					await scope.channel.send(file=discord.File(f,filename=args.filename))
				else:
					await scope.channel.send(file=discord.File(f,filename="article.pdf"))
			except discord.errors.HTTPException:
				await scope.shell.print_error(scope, "File impossible to send using discord (Due to 8Mo limit)")
			f.close()
		elif args.var:
			scope.vars[args.var] = result.text
		else:
			scope.vars["result"] = result.text


	@praxisbot.command
	async def execute_upload(self, scope, command, options, lines, **kwargs):
		"""
		Upload files on Discord.
		"""

		parser = argparse.ArgumentParser(description=kwargs["description"], prog=command)
		parser.add_argument('data', help='Data that will be contains in the file')
		parser.add_argument('--filename', help='Name of the file that will be uploaded')
		args = await self.parse_options(scope, parser, options)
		if not args:
			return

		f = io.BytesIO(scope.format_text(args.data).encode('UTF-8'))
		await scope.channel.send(file=discord.File(f,filename=args.filename or "article.pdf"))
		f.close()

	@praxisbot.command
	@praxisbot.permission_script
	async def execute_css_selector(self, scope, command, options, lines, **kwargs):
		"""
		Get a HTML element, given a css selector
		"""
	
		parser = argparse.ArgumentParser(description=kwargs["description"], prog=command)
		parser.add_argument('css_selector', help='The css selector (start with `.` for a class ; start with `#` for an id).')
		parser.add_argument('--var', help='Variable that will contains the HTML element.')
		parser.add_argument('--html_var', help='Variable with the HTML content where the HTML element is.')
		parser.add_argument('--index', help='[Defaut=0] the index to find le HTML element from the cssselect returned list')
		args = await self.parse_options(scope, parser, options)
		if not args:
			return

		if args.html_var:
			html = lxml.html.fromstring(scope.vars[args.html_var])
		elif len(lines) > 0:
			html = lxml.html.fromstring("\n".join(lines))
		else:
			html = lxml.html.fromstring(scope.vars["result"])
		
		index = args.index and int(args.index) or 0
		element = html.cssselect(args.css_selector)[index]
		if args.var:
			scope.vars[args.var] = element
		else:
			scope.vars["element"] = element
	
	@praxisbot.command
	@praxisbot.permission_script
	async def execute_extract_attribute(self, scope, command, options, lines, **kwargs):
		"""
		Get an attribute, given an HTML element
		"""
		
		parser = argparse.ArgumentParser(description=kwargs["description"], prog=command)
		parser.add_argument('attribute', help="Attribute to get from the HTML element")
		parser.add_argument('--var', help='Variable that will contains the text of the attribute.')
		parser.add_argument('--element_var', help='Variable containing the HTML element.')
		args = await self.parse_options(scope, parser, options)
		if not args:
			return
			
		element_var = args.element_var or "element"
		element = scope.vars[element_var]
		
		attribute = element.get(args.attribute)
		if args.var:
			scope.vars[args.var] = attribute
		else:
			scope.shell.print_success(scope, "The attribute value `{}`".format(attribute))
	
	@praxisbot.command
	@praxisbot.permission_script
	async def execute_extract_text(self, scope, command, options, lines, **kwargs):
		"""
		Get an attribute, given an HTML element
		"""
		
		parser = argparse.ArgumentParser(description=kwargs["description"], prog=command)
		parser.add_argument('--var', help='Variable that will contains the text of the attribute.')
		parser.add_argument('--element_var', help='Variable containing the HTML element.')
		args = await self.parse_options(scope, parser, options)
		if not args:
			return
			
		element_var = args.element_var or "element"
		element = scope.vars[element_var]
		
		text = element.text
		if args.var:
			scope.vars[args.var] = text
		else:
			scope.shell.print_success(scope, "The content is `{}`".format(text))