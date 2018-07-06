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
import requests
import praxisbot

class RoleType:
	Default=0
	Separator=1

class RoleListPlugin(praxisbot.Plugin):
	"""
	Role list commands
	"""

	name = "RoleList"

	def __init__(self, shell):
		super().__init__(shell)

		self.shell.create_sql_table("role_options", ["id INTEGER PRIMARY KEY", "discord_sid INTEGER", "discord_rid INTEGER", "description TEXT", "type INTEGER", "autosort INTEGER", "autosync INTEGER"])

		self.add_command("edit_role", self.execute_edit_role)
		self.add_command("roles", self.execute_roles)

	async def on_loop(self, scope):
		roles = {}

		for r in scope.server.roles:
			if r.is_everyone:
				continue

			roles[r.id] = {
				"id":r.id,
				"name":r.name,
				"position":r.position,
				"type":RoleType.Default,
				"autosort":0,
				"autosync":0,
				"object":r
			}

		with scope.shell.dbcon:
			c = scope.shell.dbcon.cursor()
			for row in c.execute("SELECT discord_rid, type, autosync, autosort FROM "+scope.shell.dbtable("role_options")+" WHERE discord_sid = ?", [int(scope.server.id)]):
				rid = str(row[0])
				if rid in roles:
					roles[rid]["type"] = row[1]
					roles[rid]["autosync"] = row[2]
					roles[rid]["autosort"] = row[3]

		sorted_roles = sorted(roles.values(), key=lambda a: a["position"], reverse=True)

		role_tree = [{"separator":None, "list":[]}]
		current_block = 0
		for r in sorted_roles:
			if r["type"] == RoleType.Separator:
				current_block = current_block+1
				role_tree.append({"separator":r, "list":[]})
			else:
				role_tree[current_block]["list"].append(r)

		for b in role_tree:
			if not b["separator"] or len(b["list"]) == 0:
				continue
			if b["separator"]["autosort"] != 1:
				continue

			current_position = b["list"][0]["position"]
			sorted_subroles = sorted(b["list"], key=lambda a: a["name"])
			i = 0

			while i < len(sorted_subroles):
				if sorted_subroles[i]["position"] != current_position:
					await scope.shell.client.move_role(scope.server, sorted_subroles[i]["object"], current_position)
					return #To only one modification each on_loop iteration
				current_position = current_position-1
				i = i+1

	@praxisbot.command
	@praxisbot.permission_admin
	async def execute_edit_role(self, scope, command, options, lines, **kwargs):
		"""
		Edit role.
		"""

		parser = argparse.ArgumentParser(description=kwargs["description"], prog=command)
		parser.add_argument('role', help='Role to edit.')
		parser.add_argument('--name', help='Name of the role.')
		parser.add_argument('--mentionable', help='Set if the role can be mentioned. 0 or 1.')
		parser.add_argument('--onlinelist', help='Set if the role must be displayed in the online list. 0 or 1.')
		parser.add_argument('--description', help='Description of the role.')
		parser.add_argument('--normal', action='store_true', help='Set this role as a normal role.')
		parser.add_argument('--separator', action='store_true', help='Set this role as a separator.')
		parser.add_argument('--autosort', help='Sort all sub-roles. For separators only. 0 or 1.')
		parser.add_argument('--autosync', help='Sync permissions of all sub-roles. For separators only. 0 or 1.')
		args = await self.parse_options(scope, parser, options)
		if not args:
			return

		r = scope.shell.find_role(args.role, scope.server)
		if not r:
			await scope.shell.print_error(scope, "Role `"+args.role+"` not found.")
			return

		edit_role_args = {}

		if args.mentionable != None:
			if args.mentionable == "1":
				edit_role_args["mentionable"] = True
			elif args.mentionable == "0":
				edit_role_args["mentionable"] = False
			else:
				await scope.shell.print_error(scope, "Parameter --mentionable must be 0 or 1.")
				return

		if args.onlinelist != None:
			if args.onlinelist == "1":
				edit_role_args["hoist"] = True
			elif args.onlinelist == "0":
				edit_role_args["hoist"] = False
			else:
				await scope.shell.print_error(scope, "Parameter --onlinelist must be 0 or 1.")
				return

		if args.name:
			edit_role_args["name"] = args.name

		description = ""
		type = RoleType.Default
		autosort = 0
		autosync = 0

		options = scope.shell.get_sql_data("role_options", ["description", "type", "autosort", "autosync"], {"discord_sid": int(scope.server.id), "discord_rid":int(r.id)})
		if options:
			description = options[0]
			type = options[1]
			autosort = options[2]
			autosync = options[3]

		if args.description:
			description = args.description

		if args.separator:
			type = RoleType.Separator
		elif args.normal:
			type = RoleType.Default

		if type == RoleType.Separator:
			if args.autosort != None:
				if args.autosort == "1":
					autosort = 1
				elif args.autosort == "0":
					autosort = 0
				else:
					await scope.shell.print_error(scope, "Parameter --autosort must be 0 or 1.")
					return
			if args.autosync != None:
				if args.autosync == "1":
					autosync = 1
				elif args.autosync == "0":
					autosync = 0
				else:
					await scope.shell.print_error(scope, "Parameter --autosync must be 0 or 1.")
					return
		else:
			autosort = 0
			autosync = 0

		if len(edit_role_args) > 0:
			try:
				await scope.shell.client.edit_role(scope.server, r, **edit_role_args)
			except:
				await scope.shell.print_error(scope, "The role "+r.name+" can't be edited.")
				return

		scope.shell.set_sql_data("role_options", {"description":description, "type":type, "autosort":autosort, "autosync":autosync}, {"discord_sid": int(scope.server.id), "discord_rid":int(r.id)})

		await scope.shell.print_success(scope, "Role edited.")

	@praxisbot.command
	async def execute_roles(self, scope, command, options, lines, **kwargs):
		"""
		List all roles.
		"""

		parser = argparse.ArgumentParser(description=kwargs["description"], prog=command)
		args = await self.parse_options(scope, parser, options)
		if not args:
			return

		roles = {}

		for r in scope.server.roles:
			if r.is_everyone:
				continue

			roles[r.id] = {
				"id":r.id,
				"name":r.name,
				"members":0,
				"position":r.position,
				"type":RoleType.Default,
				"description":"",
				"mentionable":r.mentionable,
				"onlinelist":r.hoist,
				"autosort":0,
				"autosync":0,
				"color":r.colour.value
			}

		for m in scope.server.members:
			for r in m.roles:
				if r.id in roles:
					roles[r.id]["members"] = roles[r.id]["members"]+1

		with scope.shell.dbcon:
			c = scope.shell.dbcon.cursor()
			for row in c.execute("SELECT discord_rid, type, description, autosync, autosort FROM "+scope.shell.dbtable("role_options")+" WHERE discord_sid = ?", [int(scope.server.id)]):
				rid = str(row[0])
				if rid in roles:
					roles[rid]["type"] = row[1]
					roles[rid]["description"] = row[2]
					roles[rid]["autosync"] = row[3]
					roles[rid]["autosort"] = row[4]

		sorted_roles = sorted(roles.values(), key=lambda a: a["position"], reverse=True)

		stream = praxisbot.MessageStream(scope)
		await stream.send("__**List of roles**__\n")
		await stream.send("\n**Properties:** :medal: visible in online list, :label: invisible in online list, :bell: mentionable, :no_bell: not mentionable, :art: colored, :black_circle: default color\n")

		role_above = 0

		for r in sorted_roles:
			if r["type"] == RoleType.Separator:
				text = "\n\n**"+r["name"]+"**"
				if len(r["description"]) > 0:
					text = text+"\n"+r["description"]
				if r["autosort"] == 1:
					text = text+"\n:twisted_rightwards_arrows: Roles in this section are automatically sorted"
				if r["autosync"] == 1:
					text = text+"\n:arrows_counterclockwise: Permissions of roles in this section are automatically synced"
				text = text+"\n"
				await stream.send(text)
			else:
				icon = ""

				if r["onlinelist"]:
					icon = icon+":medal:"
				else:
					icon = icon+":label:"

				if r["mentionable"]:
					icon = icon+":bell:"
				else:
					icon = icon+":no_bell:"

				if r["color"] == 0:
					icon = icon+":black_circle:"
				else:
					icon = icon+":art:"

				description = ""
				if len(r["description"]) > 0:
					description = ": "+r["description"]
				await stream.send("\n"+icon+" **"+r["name"]+"**, "+str(r["members"])+" members"+description)

		await stream.finish()
