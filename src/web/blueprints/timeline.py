from flask import Blueprint, render_template, g
from src.web.db import get_db
import psycopg2.extras

bp = Blueprint('timeline', __name__, url_prefix='/timeline')

@bp.route('/')
def show_timeline():
    db = get_db()
    cur = db.cursor(cursor_factory=psycopg2.extras.DictCursor)
    
    query = """
        SELECT 
            li.title,
            MIN(ls.started_at) as first_listen,
            MAX(ls.started_at) as last_listen,
            COUNT(ls.id) as session_count,
            li.image_url
        FROM listening_sessions ls
        JOIN library_items li ON ls.library_item_id = li.id
        GROUP BY li.title, li.image_url
        ORDER BY MAX(ls.started_at) DESC
    """
    
    cur.execute(query)
    rows = cur.fetchall()
    cur.close()

    # Format data for chart
    chart_data = []
    for row in rows:
        if row['first_listen'] and row['last_listen']:
            chart_data.append({
                'x': row['title'],
                'y': [
                    int(row['first_listen'].timestamp() * 1000),
                    int(row['last_listen'].timestamp() * 1000)
                ],
                'session_count': row['session_count'],
                'image_url': row['image_url']
            })
    
    return render_template('timeline.html', chart_data=chart_data)
