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
from pytz import timezone
import praxisbot

class PollPlugin(praxisbot.Plugin):
	"""
	Poll commands
	"""

	name = "Poll"

	def __init__(self, shell):
		super().__init__(shell)

		self.shell.create_sql_table("polls", ["id INTEGER PRIMARY KEY", "discord_sid INTEGER", "discord_cid INTEGER", "discord_mid INTEGER", "end_time DATETIME", "description TEXT"])
		self.shell.create_sql_table("poll_choices", ["id INTEGER PRIMARY KEY", "poll INTEGER", "emoji TEXT", "description TEXT"])
		self.shell.create_sql_table("votes", ["id INTEGER PRIMARY KEY", "poll INTEGER", "discord_uid INTEGER", "choice INTEGER", "vote_time DATETIME"])

		self.add_command("start_poll", self.execute_start_poll)
		self.add_command("polls", self.execute_polls)

	def check_emoji(self, reaction, emoji):
		e = str(reaction.emoji)
		return e.startswith(emoji)

	async def on_loop(self, scope):
		with scope.shell.dbcon:
			c0 = scope.shell.dbcon.cursor()
			c1 = scope.shell.dbcon.cursor()
			for poll in c0.execute("SELECT id, discord_cid, discord_mid, description, end_time as 'end_time_ [timestamp]' FROM "+scope.shell.dbtable("polls")+" WHERE discord_sid = ?", [int(scope.server.id)]):
				chan = scope.shell.find_channel(str(poll[1]), scope.server)
				if not chan:
					continue

				msg = None
				try:
					msg = await scope.shell.client.get_message(chan, str(poll[2]))
				except:
					pass
				if not msg:
					continue

				end_time = timezone('UTC').localize(poll[4])
				current_time = datetime.datetime.now(timezone('UTC'))
				if end_time < current_time:

					text = poll[3]+"\n\n**Results:**"
					for choice in c1.execute("SELECT id, emoji FROM "+scope.shell.dbtable("poll_choices")+" WHERE poll = ?", [poll[0]]):
						counter = scope.shell.get_sql_data("votes", ["COUNT(id)"], {"poll": poll[0], "choice": choice[0]})
						text = text+"\n\n"+choice[1]+" : "+str(counter[0])

					await scope.shell.client.edit_message(msg, text)
					await scope.shell.client.clear_reactions(msg)

					scope.shell.delete_sql_data("votes", {"poll": poll[0]})
					scope.shell.delete_sql_data("poll_choices", {"poll": poll[0]})
					scope.shell.delete_sql_data("polls", {"id": poll[0]})

				else:
					changes = False
					choices = {}
					reaction_already_added = []

					text = poll[3]+"\n\n**To vote, please click on one of the following reactions:**"
					for choice in c1.execute("SELECT id, emoji, description FROM "+scope.shell.dbtable("poll_choices")+" WHERE poll = ?", [poll[0]]):
						choices[choice[0]] = choice[1]
						text = text+"\n\n"+choice[1]+" : "+str(choice[2])

					for r in msg.reactions:
						current_choice = None
						for c in choices:
							if self.check_emoji(r, choices[c]):
								current_choice = c
								break

						reaction_users = await scope.shell.client.get_reaction_users(r)
						for ru in reaction_users:
							if not current_choice:
								await scope.shell.client.remove_reaction(msg, r.emoji, ru)
							elif ru.id == scope.shell.client.user.id:
								reaction_already_added.append(choices[current_choice])
							else:
								try:
									await scope.shell.client.remove_reaction(msg, r.emoji, ru)
									vote_time = datetime.datetime.now(timezone('UTC'))
									vote = scope.shell.get_sql_data("votes", ["id", "choice"], {"poll": poll[0], "discord_uid": int(ru.id)})
									if not vote:
										scope.shell.add_sql_data("votes", {"poll": poll[0], "discord_uid": int(ru.id), "choice":current_choice, "vote_time":str(vote_time)})
										await scope.shell.client.send_message(ru, "Your vote on the server \""+scope.server.name+"\" is confirmed.\n - Vote added: "+choices[current_choice])
										changes = True
									elif choices[current_choice] != choices[vote[1]]:
										scope.shell.update_sql_data("votes", {"choice":current_choice}, {"id": vote[0]})
										await scope.shell.client.send_message(ru, "Your vote on the server \""+scope.server.name+"\" is confirmed.\n - Vote removed: "+choices[vote[1]]+"\n - Vote added: "+choices[current_choice])
									else:
										await scope.shell.client.send_message(ru, "Your vote on the server \""+scope.server.name+"\" is confirmed.")
								except:
									print(traceback.format_exc())
									await scope.shell.client.send_message(ru, ":no_entry: Your vote on the server \""+scope.server.name+"\" was lost due to a technical problem.")

					for c in choices:
						if choices[c] not in reaction_already_added:
							await scope.shell.client.add_reaction(msg, choices[c])

					if changes:
						counter = scope.shell.get_sql_data("votes", ["COUNT(id)"], {"poll": poll[0]})
						text = text+"\n\nVoters: "+str(counter[0])

						await scope.shell.client.edit_message(msg, text)

	@praxisbot.command
	async def execute_start_poll(self, scope, command, options, lines, **kwargs):
		"""
		Start a poll.
		"""

		parser = argparse.ArgumentParser(description=kwargs["description"], prog=command)
		parser.add_argument('--duration', help='Duration of the poll in hours.')
		args = await self.parse_options(scope, parser, options)
		if not args:
			return

		duration = 24
		if args.duration:
			try:
				duration = int(args.duration)
				if duration > 128:
					raise ValueError
				if duration < 1:
					raise ValueError
			except ValueError:
				scope.shell.print_error("Duration must be a number between 1 and 168")
				return

		choices = [
			{"emoji": "👎", "description": "\"I disagree\""},
			{"emoji": "🤷", "description": "Neutral"},
			{"emoji": "👍", "description": "\"I agree\""}
		]

		description = "\n".join(lines)
		text = description
		text = text+"\n\n**To vote, please click on one of the following reactions:**"
		for c in choices:
			text = text+"\n\n"+c["emoji"]+" : "+c["description"]
		text = text+"\n\nVoters: "+str(0)

		msg = await scope.shell.client.send_message(scope.channel, text)

		for c in choices:
			await scope.shell.client.add_reaction(msg, c["emoji"])

		end_time = datetime.datetime.now(timezone('UTC')) + datetime.timedelta(hours=duration)

		poll_id = scope.shell.add_sql_data("polls", {"discord_sid": int(msg.server.id), "discord_cid": int(msg.channel.id), "discord_mid": int(msg.id), "description": description, "end_time": str(end_time)})

		for c in choices:
			scope.shell.add_sql_data("poll_choices", {"poll": poll_id, "emoji": c["emoji"], "description": c["description"]})

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
		await stream.send("**List of polls**\n")

		with scope.shell.dbcon:
			c = scope.shell.dbcon.cursor()
			for row in c.execute("SELECT id, description, discord_cid, end_time as 'end_time_ [timestamp]' FROM "+scope.shell.dbtable("polls")+" WHERE discord_sid = ? ORDER BY end_time", [int(scope.server.id)]):
				chan = scope.shell.find_channel(str(row[2]), scope.server)
				if not chan:
					continue

				end_time = timezone('UTC').localize(row[3])
				time = (end_time - datetime.datetime.now(timezone('UTC')))

				await stream.send("\n**Poll #"+str(row[0])+" in "+chan.mention+"**\nClosed in "+str(time)+"```"+row[1]+"```")

		await stream.finish()
