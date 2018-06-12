"""

Copyright (C) 2017 ManoIzquierda (manoizquierda.dev@gmail.com)

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

import re
import sqlite3
import random
import discord

class Context:
	def __init__(self, client, mode):
		self.mode = mode
		self.client = client
		self.dbprefix = "pb_"
		self.dbcon = sqlite3.connect("databases/praxisbot-"+mode+".db")
		
		with self.dbcon:
			#Server list
			self.dbcon.execute("CREATE TABLE IF NOT EXISTS "+self.dbprefix+"servers(discord_sid INTEGER PRIMARY KEY, command_prefix TEXT)");
			
	def log(self, msg):
		print(msg)
	
	def format_text(self, text, **options):
		user = options.get("arg_user")
		channel = options.get("arg_channel")
		server = None
		if channel:
			server = channel.server
		
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
			
			if tag.lower() == "server" and server:
				tagOutput = server.name
			elif tag.lower() == "channel" and channel:
				tagOutput = channel.name
			elif tag.lower() == "@user" and user:
				tagOutput = user.mention
			elif tag.lower() == "user" and user:
				tagOutput = user.display_name
			
			formatedText = formatedText + tagOutput
		
		formatedText = formatedText + text[textIter:]
		
		return formatedText
	
	def find_channel(self, chan_name, server):
		if not chan_name:
			return None
		
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
		
		for m in server.members:
			if "<@"+m.id+">" == member_name:
				return m
			elif m.name+"#"+m.discriminator == member_name:
				return m
		
		return None
	
	def find_role(self, role_name, server):
		if not role_name:
			return None
		
		for r in server.roles:
			if "<@"+r.id+">" == role_name:
				return r
			elif r.name == role_name:
				return r
		
		return None
	
	def get_default_channel(self, server):
		for c in server.channels:
			if c.type == discord.ChannelType.text:
				return c
		return None
	
	def get_command_prefix(self, server):
		with self.dbcon:
			c = self.dbcon.cursor()
			c.execute("SELECT command_prefix FROM "+self.dbprefix+"servers WHERE discord_sid = ?", [int(server.id)])
			r = c.fetchone()
			if r:
				return r[0]
		return None
	
	def set_command_prefix(self, server, prefix):
		if not re.fullmatch('\S+', prefix):
			return False
		
		with self.dbcon:
			c = self.dbcon.cursor()
			c.execute("SELECT command_prefix FROM "+self.dbprefix+"servers WHERE discord_sid = ?", [int(server.id)])
			r = c.fetchone()
			if r:
				self.dbcon.execute("UPDATE "+self.dbprefix+"servers SET command_prefix = ? WHERE discord_sid = ?", [str(prefix), int(server.id)])
			else:
				self.dbcon.execute("INSERT INTO "+self.dbprefix+"servers (discord_sid, command_prefix) VALUES (?, ?)", [int(server.id), str(prefix)])
			return True
		
		return False
	
	async def send_message(self, channel, text):
		await self.client.send_message(channel, text)

	async def add_role(self, server, member_name, role_name):
		m = self.find_member(member_name, server)
		r = self.find_role(role_name, server)
		if r and m:
			await self.client.add_roles(m, r)
			return True
		return False
	
	async def remove_role(self, server, member_name, role_name):
		m = self.find_member(member_name, server)
		r = self.find_role(role_name, server)
		if r and m:
			await self.client.remove_roles(m, r)
			return True
		return False
