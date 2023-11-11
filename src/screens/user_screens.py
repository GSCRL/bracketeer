from flask import Blueprint, Response, redirect, render_template

user_screens = Blueprint(
    "user_screens", __name__, static_folder="./static", template_folder="./templates"
)


@user_screens.route("/")
def index():
    return redirect("/")


@user_screens.route("/<int:cageID>/timer")
def timerScreen(cageID: int):
    return render_template("stimer.html", cageID=cageID)


@user_screens.route("/<int:cageID>/timer/red")
def redScreenVertical(cageID: int):
    return render_template(
        "vert_timer.html", team_color="#b74444", team_color_name="red", cageID=cageID
    )


@user_screens.route("/<int:cageID>/timer/blue")
def blueScreenVertical(cageID: int):
    return render_template(
        "vert_timer.html", team_color="#1892ce", team_color_name="blue", cageID=cageID
    )


@user_screens.route("/<int:cageID>/judges")
def judgesScreen(cageID: int):
    return render_template("judges_timer.html", cageID=cageID)


# Stupid hack to get around relative pathing so it can be moved around. 0/10 do not do this.
@user_screens.route("fonts.css")
def getCSSPath():
    return Response(render_template("fonts.css"), mimetype="text/css")


@user_screens.route("/upcoming_test")
def judgesSfdfcreen():
    return render_template("_upcoming_match.html", cageID=99)
