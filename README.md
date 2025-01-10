# Bracketeer - for fun and glory.

A work-in-progress tool to run the timers for matches for combat robotics, as well as some stream overlay stuff.

This was initially built for the [Garden State Combat Robotics League](https://www.gscrl.org) but much of it is portable to other organizing bodies.

## Integrations

This tool right now polls TrueFinals, with the intent to also push to TrueFinals down the line.

There will also be the ability to import some data from RobotCombatEvents should there be a want / need for that.

## Needs

This system is written in python and managed with poetry.

To install you'll need python 3.9 or greater, then to install `pipx` per the install guide [here.](https://github.com/pypa/pipx?tab=readme-ov-file#install-pipx)

You'll also need to make use of the python package 

Then, install poetry via the steps [here.](https://python-poetry.org/docs/)

Afterwards, you should `cd` to your install location, `poetry install`.

Please then run `poetry self add [poetry-plugin-shell](https://github.com/python-poetry/poetry-plugin-shell)` to ensure you can use the shell command for rapid development and iteration. 

After installation, run `poetry shell`.

`cd` to the `src` folder, and then run `python app.py`

## Networking

Note: Please be sure to change your IP to something static for consistency with the timer clients for reconnects.

We typically use `192.168.8.250` and set the travel router to have a DNS override for that to `arena.gscrl.org`.

This is done on a specific-use travel router, like [this one.](https://www.amazon.com/GL-iNet-GL-SFT1200-Secure-Travel-Router/dp/B09N72FMH5)
