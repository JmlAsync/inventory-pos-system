"""Help (v0.32.0, F29, DEC-034): the ? button's side panel on every page, and the Help page with every topic.
The words and pictures are in help_topics.py and static/help/. These pages only read."""
from flask import Blueprint, render_template, request, url_for
from flask_login import login_required, current_user
from werkzeug.routing import BuildError
from help_topics import BY_ENDPOINT, topics_for, steps_for

bp = Blueprint('help', __name__)


@bp.app_template_global()
def help_for_page():
    """The help topic for the page being shown, with only the steps this person can do, or None when the page has
    none (the ? button is then left out). A cashier never gets an admin page's topic (v0.32.0)."""
    topic = BY_ENDPOINT.get(request.endpoint)
    if topic is None or topic not in topics_for(current_user):
        return None
    return dict(topic, steps=steps_for(topic, current_user))


@bp.route('/help')
@login_required
def help_page():
    """Every topic this person may read, each with its picture, so the whole system can be shown page by page."""
    topics = [dict(topic, steps=steps_for(topic, current_user), link=page_link(topic)) for topic in topics_for(current_user)]
    return render_template('help.html', topics=topics)


def page_link(topic):
    """An "Open this page" address for the topic, or None for pages that need a number (a receipt, a recipe) or that
    only make sense before logging in."""
    if topic['key'] == 'login':
        return None
    try:
        return url_for(topic['endpoints'][0])
    except BuildError:
        return None
