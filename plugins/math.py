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

from subprocess import STDOUT, CalledProcessError, check_output
from sympy.utilities.misc import find_executable
from os.path import join
import tempfile
import shutil
import io
from io import BytesIO

from sympy import sympify
from sympy.parsing.sympy_parser import parse_expr
from sympy.printing.str import sstrrepr

import matplotlib as mpl
mpl.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from scipy import interpolate, signal
import matplotlib.font_manager as fm

import shlex
import argparse
import discord
import traceback
import praxisbot

def xkcd_line(x, y, xlim=None, ylim=None,
              mag=1.0, f1=30, f2=0.05, f3=15):
    """
    Mimic a hand-drawn line from (x, y) data

    Parameters
    ----------
    x, y : array_like
        arrays to be modified
    xlim, ylim : data range
        the assumed plot range for the modification.  If not specified,
        they will be guessed from the  data
    mag : float
        magnitude of distortions
    f1, f2, f3 : int, float, int
        filtering parameters.  f1 gives the size of the window, f2 gives
        the high-frequency cutoff, f3 gives the size of the filter

    Returns
    -------
    x, y : ndarrays
        The modified lines
    """
    x = np.asarray(x)
    y = np.asarray(y)

    # get limits for rescaling
    if xlim is None:
        xlim = (x.min(), x.max())
    if ylim is None:
        ylim = (y.min(), y.max())

    if xlim[1] == xlim[0]:
        xlim = ylim

    if ylim[1] == ylim[0]:
        ylim = xlim

    # scale the data
    x_scaled = (x - xlim[0]) * 1. / (xlim[1] - xlim[0])
    y_scaled = (y - ylim[0]) * 1. / (ylim[1] - ylim[0])

    # compute the total distance along the path
    dx = x_scaled[1:] - x_scaled[:-1]
    dy = y_scaled[1:] - y_scaled[:-1]
    dist_tot = np.sum(np.sqrt(dx * dx + dy * dy))

    # number of interpolated points is proportional to the distance
    Nu = int(200 * dist_tot)
    u = np.arange(-1, Nu + 1) * 1. / (Nu - 1)

    # interpolate curve at sampled points
    k = min(3, len(x) - 1)
    res = interpolate.splprep([x_scaled, y_scaled], s=0, k=k)
    x_int, y_int = interpolate.splev(u, res[0])

    # we'll perturb perpendicular to the drawn line
    dx = x_int[2:] - x_int[:-2]
    dy = y_int[2:] - y_int[:-2]
    dist = np.sqrt(dx * dx + dy * dy)

    # create a filtered perturbation
    coeffs = mag * np.random.normal(0, 0.01, len(x_int) - 2)
    b = signal.firwin(f1, f2 * dist_tot, window=('kaiser', f3))
    response = signal.lfilter(b, 1, coeffs)

    x_int[1:-1] += response * dy / dist
    y_int[1:-1] += response * dx / dist

    # un-scale data
    x_int = x_int[1:-1] * (xlim[1] - xlim[0]) + xlim[0]
    y_int = y_int[1:-1] * (ylim[1] - ylim[0]) + ylim[0]

    return x_int, y_int


def XKCDify(ax, mag=1.0,
	f1=50, f2=0.01, f3=15,
	bgcolor='w',
	xaxis_loc=None,
	yaxis_loc=None,
	xaxis_arrow='+',
	yaxis_arrow='+',
	ax_extend=0.1,
	expand_axes=False):
	"""Make axis look hand-drawn

	This adjusts all lines, text, legends, and axes in the figure to look
	like xkcd plots.  Other plot elements are not modified.

	Parameters
	----------
	ax : Axes instance
	    the axes to be modified.
	mag : float
	    the magnitude of the distortion
	f1, f2, f3 : int, float, int
	    filtering parameters.  f1 gives the size of the window, f2 gives
	    the high-frequency cutoff, f3 gives the size of the filter
	xaxis_loc, yaxis_log : float
	    The locations to draw the x and y axes.  If not specified, they
	    will be drawn from the bottom left of the plot
	xaxis_arrow, yaxis_arrow : str
	    where to draw arrows on the x/y axes.  Options are '+', '-', '+-', or ''
	ax_extend : float
	    How far (fractionally) to extend the drawn axes beyond the original
	    axes limits
	expand_axes : bool
	    if True, then expand axes to fill the figure (useful if there is only
	    a single axes in the figure)
	"""
	# Get axes aspect
	ext = ax.get_window_extent().extents
	aspect = (ext[3] - ext[1]) / (ext[2] - ext[0])

	xlim = ax.get_xlim()
	ylim = ax.get_ylim()

	xspan = xlim[1] - xlim[0]
	yspan = ylim[1] - xlim[0]

	xax_lim = (xlim[0] - ax_extend * xspan, xlim[1] + ax_extend * xspan)
	yax_lim = (ylim[0] - ax_extend * yspan, ylim[1] + ax_extend * yspan)

	if xaxis_loc is None:
		xaxis_loc = ylim[0]

	if yaxis_loc is None:
		yaxis_loc = xlim[0]

    # Draw axes
	xaxis = plt.Line2D([xax_lim[0], xax_lim[1]], [xaxis_loc, xaxis_loc], linestyle='-', color='k')
	yaxis = plt.Line2D([yaxis_loc, yaxis_loc], [yax_lim[0], yax_lim[1]], linestyle='-', color='k')

	# Label axes3, 0.5, 'hello', fontsize=14)
	ax.text(xax_lim[1], xaxis_loc - 0.02 * yspan, ax.get_xlabel(), fontsize=14, ha='right', va='top', rotation=0)
	ax.text(yaxis_loc - 0.02 * xspan, yax_lim[1], ax.get_ylabel(), fontsize=14, ha='right', va='top', rotation=90)
	ax.set_xlabel('')
	ax.set_ylabel('')


	# Add title
	ax.text(0.5 * (xax_lim[1] + xax_lim[0]), yax_lim[1] + (yax_lim[1] - yax_lim[0])*0.1, ax.get_title(), ha='center', va='bottom', fontsize=16)
	ax.set_title('')

	Nlines = len(ax.lines)
	lines = [xaxis, yaxis] + [ax.lines.pop(0) for i in range(Nlines)]

	for line in lines:
		x, y = line.get_data()
		x_int, y_int = xkcd_line(x, y, xlim, ylim, mag, f1, f2, f3)

		# create foreground and background line
		lw = line.get_linewidth()
		line.set_linewidth(2 * lw)
		line.set_data(x_int, y_int)

		# don't add background line for axes
		if (line is not xaxis) and (line is not yaxis):
			line_bg = plt.Line2D(x_int, y_int, color=bgcolor, linewidth=8 * lw)

			ax.add_line(line_bg)
		ax.add_line(line)

	# Draw arrow-heads at the end of axes lines
	arr1 = 0.03 * np.array([-1, 0, -1])
	arr2 = 0.02 * np.array([-1, 0, 1])

	arr1[::2] += np.random.normal(0, 0.005, 2)
	arr2[::2] += np.random.normal(0, 0.005, 2)

	x, y = xaxis.get_data()
	if '+' in str(xaxis_arrow):
		ax.plot(x[-1] + arr1 * xspan * aspect, y[-1] + arr2 * yspan, color='k', lw=2)
	if '-' in str(xaxis_arrow):
		ax.plot(x[0] - arr1 * xspan * aspect, y[0] - arr2 * yspan, color='k', lw=2)

	x, y = yaxis.get_data()
	if '+' in str(yaxis_arrow):
		ax.plot(x[-1] + arr2 * xspan * aspect, y[-1] + arr1 * yspan, color='k', lw=2)
	if '-' in str(yaxis_arrow):
		ax.plot(x[0] - arr2 * xspan * aspect, y[0] - arr1 * yspan, color='k', lw=2)

	# Change all the fonts to humor-sans.
	prop = fm.FontProperties(fname='fonts/Humor-Sans.ttf', size=16)
	for text in ax.texts:
		text.set_fontproperties(prop)

	# modify legend
	leg = ax.get_legend()
	if leg is not None:
		leg.set_frame_on(False)

		for t in leg.get_texts():
			t.set_font_properties(prop)

	# Set the axis limits
	ax.set_xlim(xax_lim[0] - 0.1 * xspan, xax_lim[1] + 0.1 * xspan)
	ax.set_ylim(yax_lim[0] - 0.1 * yspan, yax_lim[1] + 0.1 * yspan)

	# adjust the axes
	ax.set_xticks([])
	ax.set_yticks([])

	ax.figure.set_facecolor(bgcolor)
	ax.set_axis_off()
	ax.set_position([0, 0.0, 1, 0.9])

	return ax


class MathPlugin(praxisbot.Plugin):
	"""
	Math commands
	"""

	name = "Math"

	def __init__(self, shell):
		super().__init__(shell)

		self.add_command("latex", self.execute_latex)
		self.add_command("math", self.execute_math)
		self.add_command("chemfig", self.execute_chemfig)
		self.add_command("xkcd_plot", self.execute_xkcd_plot)

	def latex_to_png(self, latex_code, stream):

		try:
			workdir = tempfile.mkdtemp()

			with io.open(join(workdir, 'texput.tex'), 'w', encoding='utf-8') as fh:
				fh.write(latex_code)

			if not find_executable('pdflatex'):
				raise RuntimeError("pdflatex program is not installed")

			if not find_executable('convert'):
				raise RuntimeError("convert program is not installed")

			try:
				check_output(['pdflatex', '-halt-on-error', '-interaction=nonstopmode', 'texput.tex', '-o', 'texput.pdf'], cwd=workdir, stderr=STDOUT)
			except CalledProcessError as e:
				raise RuntimeError(
				"'pdflatex' exited abnormally with the following output:\n%s" %
				e.output)

			try:
				check_output(['convert', '-density', '200', '-flatten', 'texput.pdf', '-quality', '90', 'texput.png'], cwd=workdir, stderr=STDOUT)
			except CalledProcessError as e:
				raise RuntimeError(
				"'convert' exited abnormally with the following output:\n%s" %
				e.output)

			with open(join(workdir, 'texput.png'), 'rb') as fh:
				stream.write(fh.read())

		finally:
			try:
				shutil.rmtree(workdir) # delete directory
			except OSError as e:
				if e.errno != 2: # code 2 - no such file or directory
					raise

	@praxisbot.command
	async def execute_math(self, scope, command, options, lines, **kwargs):
		"""
		Evaluate math expressions.
		"""

		input = options+"\n".join(lines)

		try:
			expr = parse_expr(scope.format_text(input))
		except:
			await scope.shell.print_error(scope, "Invalid math expression.")
			return

		try:
			res = sstrrepr(expr)
			scope.vars["results"] = res
			await scope.shell.print_info(scope, "```\n"+res+"```")
		except:
			await scope.shell.print_error(scope, "Impossible to generate text from the result.")
			return

	@praxisbot.command
	async def execute_latex(self, scope, command, options, lines, **kwargs):
		"""
		Latex expressions.
		"""

		latex_begin = r"""
\documentclass[preview, border=4pt]{standalone}
\usepackage{amsmath}
\usepackage{amsfonts}
\begin{document}
$\displaystyle
"""

		latex_end = r"""
$
\end{document}
"""

		latex_code = latex_begin+options+"\n".join(lines)+latex_end

		stream = BytesIO()
		try:
			self.latex_to_png(latex_code, stream)
			stream.seek(0)
			await scope.shell.client.send_file(scope.channel, stream, filename="math.png")
			stream.close()
		except:
			print(traceback.format_exc())
			await scope.shell.print_error(scope, "Invalid latex expression")
			return

	@praxisbot.command
	async def execute_chemfig(self, scope, command, options, lines, **kwargs):
		"""
		Generate chimical figure.
		"""

		latex_begin = r"""
\documentclass[preview, border=4pt]{standalone}
\usepackage{amsmath}
\usepackage{amsfonts}
\usepackage{chemfig}
\begin{document}
$\displaystyle
"""

		latex_end = r"""
$
\end{document}
"""

		latex_code = latex_begin+"\\chemfig{"+options+"}"+latex_end

		stream = BytesIO()
		try:
			self.latex_to_png(latex_code, stream)
			stream.seek(0)
			await scope.shell.client.send_file(scope.channel, stream, filename="figchem.png")
			stream.close()
		except:
			print(traceback.format_exc())
			await scope.shell.print_error(scope, "Invalid latex expression")
			return

	@praxisbot.command
	async def execute_xkcd_plot(self, scope, command, options, lines, **kwargs):
		"""
		Plot curves with xkcd style.
		"""

		parser = argparse.ArgumentParser(description=kwargs["description"], prog=command)
		parser.add_argument('--title', help='Plot title')
		parser.add_argument('--xlabel', help='X axis label')
		parser.add_argument('--ylabel', help='Y axis label')
		parser.add_argument('--bluecurve', nargs='+', help='Plot a blue curve', metavar='VALUE')
		parser.add_argument('--redcurve', nargs='+', help='Plot a blue curve', metavar='VALUE')
		parser.add_argument('--orangecurve', nargs='+', help='Plot a blue curve', metavar='VALUE')
		parser.add_argument('--greencurve', nargs='+', help='Plot a blue curve', metavar='VALUE')
		args = await self.parse_options(scope, parser, options)
		if not args:
			return

		stream = BytesIO()

		try:
			ax = plt.axes()

			if args.title:
				ax.set_title(scope.format_text(args.title))

			if args.xlabel:
				ax.set_xlabel(scope.format_text(args.xlabel))

			if args.ylabel:
				ax.set_ylabel(scope.format_text(args.ylabel))

			curves = {}

			if args.redcurve:
				curves["red"] = {"data":[], "title":None}
				for e in args.redcurve:
					try:
						y = float(e)
						curves["red"]["data"].append(y)
					except:
						curves["red"]["title"]=e

			if args.bluecurve:
				curves["blue"] = {"data":[], "title":None}
				for e in args.bluecurve:
					try:
						y = float(e)
						curves["blue"]["data"].append(y)
					except:
						curves["blue"]["title"]=e

			if args.orangecurve:
				curves["orange"] = {"data":[], "title":None}
				for e in args.orangecurve:
					try:
						y = float(e)
						curves["orange"]["data"].append(y)
					except:
						curves["orange"]["title"]=e

			if args.greencurve:
				curves["green"] = {"data":[], "title":None}
				for e in args.greencurve:
					try:
						y = float(e)
						curves["green"]["data"].append(y)
					except:
						curves["green"]["title"]=e

			for c in curves:
				size = len(curves[c]["data"])
				if size < 2:
					continue
				data_x = []
				data_y = []
				counter = 0
				for y in curves[c]["data"]:
					data_x.append(counter/(size-1))
					data_y.append(y)
					counter = counter+1
				ax.plot(data_x, data_y, label=curves[c]["title"], color=c)

			ax.legend(loc='best')

			XKCDify(ax)

			my_dpi = 72
			plt.savefig(stream, figsize=(800/my_dpi, 600/my_dpi), dpi=my_dpi)
			plt.close()

			stream.seek(0)
			await scope.shell.client.send_file(scope.channel, stream, filename="plot.png")
			stream.close()
		except:
			print(traceback.format_exc())
			await scope.shell.print_error(scope, "Plot generation failed")
			return
