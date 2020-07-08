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
import discord
import traceback
import datetime
import io
import sqlite3
from pytz import timezone
import praxisbot
import asyncio

class PollType:
	Default=0
	Short=1
	Live=2

class PollPlugin(praxisbot.Plugin):
	"""
	Poll commands
	"""

	name = "Poll"

	def __init__(self, shell):
		super().__init__(shell)

		self.shell.create_sql_table("polls", ["id INTEGER PRIMARY KEY", "discord_sid INTEGER", "discord_cid INTEGER", "discord_mid INTEGER", "end_time DATETIME", "description TEXT", "type INTEGER"])
		self.shell.create_sql_table("poll_choices", ["id INTEGER PRIMARY KEY", "poll INTEGER", "emoji TEXT", "description TEXT"])
		self.shell.create_sql_table("votes", ["id INTEGER PRIMARY KEY", "poll INTEGER", "discord_uid INTEGER", "choice INTEGER", "vote_time DATETIME"])

		self.add_command("start_poll", self.execute_start_poll)
		self.add_command("close_poll", self.execute_close_poll)
		self.add_command("polls", self.execute_polls)
		
		self.pollKillers = {}

	def check_emoji(self, reaction, emoji):
		e = str(reaction.emoji)
		return e.startswith(emoji)
		
	async def poll_autokiller(self, scope, poll_id, time):
		print("Je vais supprimer la poll {}_{} dans {} secondes".format(scope.guild.id,poll_id,time))
		await asyncio.sleep(time)
		await self.end_poll(scope,poll_id)
		
	async def end_poll(self, scope, poll_id):
		poll = scope.shell.get_sql_data("polls", ["id","discord_cid", "discord_mid", "description"], {"discord_sid":int(scope.guild.id), "id":int(poll_id)})
		chan = scope.shell.find_channel(str(poll[1]), scope.guild)
		msg = None
		if chan:
			try:
				msg = await chan.fetch_message(int(poll[2]))
			except:
				pass
		if msg:
			text = poll[3]+"\n\n**Results:**"
			choices = scope.shell.get_sql_data("poll_choices",["id","emoji","description"], {"poll":poll[0]},True)
			if choices:
				for choice in choices: #c1.execute("SELECT id, emoji, description FROM {} WHERE poll = {}".format(scope.shell.dbtable("poll_choices"),poll[0])):
					counter = scope.shell.get_sql_data("votes", ["COUNT(id)"], {"poll": poll[0], "choice": choice[0]})
					text = text+"\n\n{} {} : {}".format(choice[1],choice[2],counter[0])

			await msg.edit(content=text)
			await msg.clear_reactions()
			
		scope.shell.delete_sql_data("votes", {"poll": poll[0]})
		scope.shell.delete_sql_data("poll_choices", {"poll": poll[0]})
		scope.shell.delete_sql_data("polls", {"id": poll[0]})
		key = "{}_{}".format(scope.guild.id,poll_id)
		if key in self.pollKillers.keys():
			self.pollKillers.pop(key)
		
	async def on_reaction(self, scope, reaction=None):
		print("Reaction")
		with scope.shell.dbcon:
			if reaction:
				print("Reaction added on a message : {}".format(reaction.message.id))
				polls = scope.shell.get_sql_data("polls",["id","discord_cid","discord_mid","description","end_time as 'end_time_ [timestamp]'","type"],{"discord_sid":scope.guild.id,"discord_mid":reaction.message.id},True)
			else:
				polls = scope.shell.get_sql_data("polls",["id","discord_cid","discord_mid","description","end_time as 'end_time_ [timestamp]'","type"],{"discord_sid":scope.guild.id},True)
			for poll in polls:
				if reaction:
					msg = reaction.message
				else:
					print("No Reaction !")
					chan = scope.shell.find_channel(str(poll[1]), scope.guild)
					msg = None
					if chan:
						try:
							msg = await chan.fetch_message(int(poll[2]))
						except:
							pass
				if msg:
					changes = False
					choices = {}
					reaction_already_added = []
					
					entries = scope.shell.get_sql_data("poll_choices",["id","emoji","description"],{"poll":poll[0]},True)
					for entry in entries:
						choices[entry[0]] = [entry[1],entry[2]]

					for r in msg.reactions:
						choice_id = None
						for c in choices:
							if self.check_emoji(r, choices[c][0]):
								choice_id = c
								break

						async for ru in r.users():
							choice_id = choice_id
							choice_emoji = choices[choice_id][0]
							choice_desc = choices[choice_id][1]
							if not choice_id:
								await msg.remove_reaction(r.emoji, ru)
							elif ru.id == scope.shell.client.user.id:
								reaction_already_added.append(choice_emoji)
							else:
								try:
									await msg.remove_reaction(r.emoji, ru)
									vote_time = datetime.datetime.now(timezone('UTC'))
									vote = scope.shell.get_sql_data("votes", ["id", "choice"], {"poll": poll[0], "discord_uid": int(ru.id)})
									if vote:
										previous_choice_emoji = choices[vote[1]][0]
										previous_choice_desc = choices[vote[1]][1]
									if not vote: #Si c'est le premier vote de voter
										scope.shell.add_sql_data("votes", {"poll": poll[0], "discord_uid": int(ru.id), "choice":choice_id})
										await ru.send("Your vote on the server \"{}\" is confirmed.\n – Vote added: {} : {}".format(scope.guild.name,choice_emoji,choice_desc))
										changes = True
									elif choice_emoji != previous_choice_emoji: #Sinon si le vote est différent du précédent
										scope.shell.update_sql_data("votes", {"choice":choice_id}, {"id": vote[0]})
										await ru.send("Your vote on the server \"{}\" is confirmed.\n – Vote removed: {} : {}\n – Vote added: {} : {}".format(scope.guild.name,previous_choice_emoji,previous_choice_desc,choice_emoji,choice_desc))
										changes = True
									else:
										await ru.send("Your vote on the server \"{}\" is confirmed.".format(scope.guild.name))
								except:
									print(traceback.format_exc())
									await ru.send(":no_entry: Your vote on the server \"{}\" was lost due to a technical issue.".format(scope.guild.name))

					print("I'll add not already added reactions")
					for c in choices:
						if choices[c] not in reaction_already_added:
							await msg.add_reaction(choices[c][0])
							
					if changes:
						text = poll[3]
						end_time_readable = poll[4].astimezone(timezone('Europe/Paris'))
						print("Text :\n{}".format(text))
						if poll[5] != PollType.Short:
							text = text+"\n\n**Poll closing at {}.\nTo vote, please click on one of the following reactions:**".format(end_time_readable.strftime("%Y-%m-%d %H:%M:%S"))
						
						choices = self.shell.get_sql_data("poll_choices",["id","emoji","description"],{"poll":poll[0]},True)
						for choice in choices:
							if poll[5] != PollType.Short:
								text = text+"\n\n{} : {}".format(choice[1],choice[2])
							if poll[5] == PollType.Live:
								counter = scope.shell.get_sql_data("votes", ["COUNT(id)"], {"poll": poll[0], "choice": choice[0]})
								text = text+" ({})".format(counter[0])

						if poll[5] != PollType.Short:
							counter = scope.shell.get_sql_data("votes", ["COUNT(id)"], {"poll": poll[0]})
							text = text+"\n\nVoters: {}".format(counter[0])
						await msg.edit(content=text)
	
	async def on_ready(self, scope):
		print("Poll plugin getting ready")
		polls = scope.shell.get_sql_data("polls",["id","discord_cid","discord_mid","description","end_time as 'end_time_ [timestamp]'","type"],{"discord_sid":scope.guild.id},True)
		print("Il y a {} polls dans la guilde {}".format(len(polls),scope.guild.id))
		for poll in polls:
			print("Poll suivante {}".format(poll))
			chan = scope.shell.find_channel(poll[1], scope.guild)
			print("Je viens de chercher le salon")
			msg = None
			if chan:
				try:
					print("Je suis dans un salon : {}".format(chan.name))
					msg = await chan.fetch_message(int(poll[2]))
				except:
					pass

			end_time = timezone('UTC').localize(poll[4])
			end_time_readable = end_time.astimezone(timezone('Europe/Paris'))
			current_time = datetime.datetime.now(timezone('UTC'))
			task_key = "{}_{}".format(scope.guild.id,poll[0])
			if current_time > end_time:
				print("Je dois terminé la poll {}_{}".format(scope.guild.id,poll[0]))
				await self.end_poll(scope, poll[0])
			elif not task_key in self.pollKillers.keys():
				remaining_time = end_time - current_time
				remaining_seconds = int(remaining_time.total_seconds())
				print("Dans {} secondes, la poll {}_{} doit mourir.".format(remaining_seconds,scope.guild.id,poll[0]))
				self.pollKillers[task_key] = asyncio.create_task(self.poll_autokiller(scope,poll[0],remaining_seconds))
			else:
				print("Tout est en ordre")
			#await scope.guild.me.fetch_message(poll[2])
		await self.on_reaction(scope)

	@praxisbot.command
	async def execute_start_poll(self, scope, command, options, lines, **kwargs):
		"""
		Start a poll.
		"""

		parser = argparse.ArgumentParser(description=kwargs["description"], prog=command)
		parser.add_argument('--duration', help='Duration of the poll in hours.')
		parser.add_argument('--description', help='Description of the poll.')
		parser.add_argument('--channel', help='Channel where the poll will be created.')
		parser.add_argument('--short', action='store_true', help='Remove all explanations except the description.')
		parser.add_argument('--live', action='store_true', help='Display results in real time.')
		parser.add_argument('--choices', nargs='*', help='List of emoji and decriptions. Ex: `👎 "No" 🤷 "Neutral" 👍 "Yes".`', default=["👎", "I disagree", "🤷", "Neutral", "👍", "I agree"])
		args = await self.parse_options(scope, parser, options)
		if not args:
			return

		if args.channel:
			chan = scope.shell.find_channel(scope.format_text(args.channel).strip(), scope.guild)
		else:
			chan = scope.channel

		if not chan:
			await scope.shell.print_error(scope, "Unknown channel.")
			return

		if scope.permission < praxisbot.UserPermission.Script and not chan.permissions_for(scope.user).send_messages:
			await scope.shell.print_permission(scope, "You don't have write permission in this channel.")
			return

		poll_type = PollType.Default
		if args.live and args.short:
			await scope.shell.print_error(scope, "You can only choose one option between `--short` and `--live`, not both.")
			return
		elif args.live:
			poll_type = PollType.Live
		elif args.short:
			poll_type = PollType.Short

		duration = 24
		if args.duration and not args.duration == "test":
			try:
				duration = int(args.duration)
				if duration > 128:
					raise ValueError
				if duration < 1:
					raise ValueError
			except ValueError:
				await scope.shell.print_error(scope, "Duration must be a number between 1 and 168")
				return

		choices = []
		choice_emoji = None
		for c in args.choices:
			if not choice_emoji:
				choice_emoji = c
			else:
				choices.append({"emoji":choice_emoji, "description":c})
				choice_emoji = None

		if args.description:
			description = scope.format_text(args.description)
		else:
			description = scope.format_text("\n".join(lines))

		current_time = datetime.datetime.now(timezone('UTC'))
		if args.duration == "test":
			end_time = current_time + datetime.timedelta(seconds=10)
		else:
			end_time = current_time + datetime.timedelta(hours=duration)
		end_time_readable = end_time.astimezone(timezone('Europe/Paris'))

		text = description
		if poll_type != PollType.Short:
			text = text+"\n\n**Poll closing at {}.\nTo vote, please click on one of the following reactions:**".format(end_time_readable.strftime("%Y-%m-%d %H:%M:%S"))
			for c in choices:
				text = text+"\n\n{} : {}".format(c["emoji"],c["description"])
			text = text+"\n\nVoters: 0"

		msg = await chan.send(text)
		

		for c in choices:
			try:
				await msg.add_reaction(c["emoji"])
			except:
				await scope.shell.print_error(scope, "\"{}\" is not a valid emoji.".format(c["emoji"]))
				return

		poll_id = scope.shell.add_sql_data("polls", {"discord_sid": int(msg.guild.id), "discord_cid": int(chan.id), "discord_mid": int(msg.id), "description": description, "end_time": str(end_time), "type":int(poll_type)})
		remaining_time = end_time - current_time
		remaining_seconds = int(remaining_time.total_seconds())
		task_key = "{}_{}".format(scope.guild.id,poll_id)
		asyncio.create_task(self.poll_autokiller(scope,poll_id,remaining_seconds))

		for c in choices:
			scope.shell.add_sql_data("poll_choices", {"poll": poll_id, "emoji": c["emoji"], "description": c["description"]})

	@praxisbot.command
	async def execute_close_poll(self, scope, command, options, lines, **kwargs):
		"""
		Close a poll.
		"""

		parser = argparse.ArgumentParser(description=kwargs["description"], prog=command)
		parser.add_argument('poll', help='ID of the poll to close.')
		args = await self.parse_options(scope, parser, options)
		if not args:
			return

		self.ensure_object_id("Poll ID", args.poll)

		poll = scope.shell.get_sql_data("polls", ["id"], {"discord_sid":int(scope.guild.id), "id":int(args.poll)})
		if not poll:
			await scope.shell.print_error(scope, "Poll #"+args.poll+"not found.")
			return

		await self.end_poll(scope, poll[0])
		await scope.shell.print_success(scope, "Poll closed.")

	@praxisbot.command
	async def execute_polls(self, scope, command, options, lines, **kwargs):
		"""
		List all current polls.
		"""

		parser = argparse.ArgumentParser(description=kwargs["description"], prog=command)
		args = await self.parse_options(scope, parser, options)
		if not args:
			return

		stream = praxisbot.MessageStream(scope)
		await stream.send("__**List of polls**__")

		with scope.shell.dbcon:
			c0 = scope.shell.dbcon.cursor()
			c1 = scope.shell.dbcon.cursor()
			for row in c0.execute("SELECT id, description, discord_cid, end_time as 'end_time_ [timestamp]' FROM "+scope.shell.dbtable("polls")+" WHERE discord_sid = ? ORDER BY end_time", [int(scope.guild.id)]):
				chan = scope.shell.find_channel(str(row[2]), scope.guild)
				chan_name = "an unknown channel"
				if chan:
					chan_name = chan.mention

				end_time = timezone('UTC').localize(row[3])
				end_time = end_time.astimezone(timezone('Europe/Paris'))

				counter = scope.shell.get_sql_data("votes", ["COUNT(id)"], {"poll": row[0]})

				await stream.send("\n\n:bar_chart: **Poll #"+str(row[0])+" in "+chan_name+"**")
				await stream.send("\n - Closing time: "+end_time.strftime("%Y-%m-%d %H:%M:%S"))
				choices = []
				for choice in c1.execute("SELECT emoji, description FROM "+scope.shell.dbtable("poll_choices")+" WHERE poll = ?", [row[0]]):
					choices.append(choice[0]+" "+choice[1])
				await stream.send("\n - Voters: "+str(counter[0]))
				await stream.send("\n - Choices: "+", ".join(choices))
				if len(row[1]) > 0:
					description = "```\n"+row[1]+"\n```"

		await stream.finish()
