import os
import requests
import psycopg2
from psycopg2.extras import Json
from datetime import datetime, timezone
import time
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def get_env_variable(var_name, default=None):
    val = os.getenv(var_name, default)
    if val is None:
        logging.error(f"Environment variable {var_name} is not set.")
        exit(1)
    return val

def ms_to_datetime(epoch_ms):
    if epoch_ms is not None:
        return datetime.fromtimestamp(epoch_ms / 1000.0, tz=timezone.utc)
    return None

# Configuration
DB_CONN_STR = get_env_variable("DB_CONNECTION_STRING")
ABS_API_BASE_URL = get_env_variable("ABS_API_URL") # e.g., http://100.112.107.109:13378
ABS_API_TOKEN = get_env_variable("ABS_API_TOKEN")

def get_db_connection():
    try:
        conn = psycopg2.connect(DB_CONN_STR)
        return conn
    except Exception as e:
        logging.error(f"Failed to connect to database: {e}")
        exit(1)

def fetch_sessions(page=0, items_per_page=50):
    url = f"{ABS_API_BASE_URL}/api/users/root/listening-sessions" # Assuming root or fetching for specific user?
    # User prompt had "api/users/d1ec3606.../listening-sessions". 
    # I should probably make USER_ID configurable or fetch 'me'. 
    # But for now, let's extract user_id from the prompt example or make it an env var.
    # The prompt curl has a specific UUID. Let's start with an ENV VAR for USER_ID, or defaults to a hardcoded one if user didn't specify.
    # Actually, the best way is to query /api/me or similar, but let's stick to the URL structure in prompt.
    # I'll use an ENV var ABS_USER_ID.
    
    user_id = os.getenv("ABS_USER_ID")
    if not user_id:
        logging.warning("ABS_USER_ID not set, attempting to use user from token or failing.")
        # Re-using the ID from prompt as default/placeholder is risky. 
        # I'll update the script to require ABS_USER_ID or parsing it.
        # Let's assume the user will provide it.
        exit(1)
        
    url = f"{ABS_API_BASE_URL}/api/users/{user_id}/listening-sessions"
    
    params = {
        "page": page,
        "itemsPerPage": items_per_page
    }
    headers = {
        "Authorization": f"Bearer {ABS_API_TOKEN}"
    }
    
    try:
        response = requests.get(url, params=params, headers=headers)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logging.error(f"Failed to fetch sessions: {e}")
        exit(1)

def upsert_user(cur, user_data):
    cur.execute("""
        INSERT INTO users (id, username)
        VALUES (%s, %s)
        ON CONFLICT (id) DO UPDATE SET username = EXCLUDED.username
    """, (user_data['id'], user_data['username']))

def upsert_device(cur, device_data):
    # device_data map keys: id, clientName, deviceName, model, manufacturer, clientVersion
    # Note: JSON keys are camelCase, my DB is snake_case
    cur.execute("""
        INSERT INTO devices (id, client_name, device_name, model, manufacturer, client_version)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (id) DO UPDATE SET
            client_name = EXCLUDED.client_name,
            device_name = EXCLUDED.device_name,
            model = EXCLUDED.model,
            manufacturer = EXCLUDED.manufacturer,
            client_version = EXCLUDED.client_version
    """, (
        device_data.get('id'), # The inner deviceID or outer?
        # In JSON: "deviceInfo": { "id": "...", "clientName": "...", ... }
        # Wait, the JSON has `deviceInfo`.
        device_data.get('clientName'),
        device_data.get('deviceName'),
        device_data.get('model'),
        device_data.get('manufacturer'),
        device_data.get('clientVersion')
    ))

def upsert_library_item(cur, item_data, library_id, media_type):
    
    meta = item_data.get('mediaMetadata', {})
    
    # Handle Author (could be string 'author' or list 'authors')
    author = meta.get('author')
    if not author and 'authors' in meta:
        authors_list = meta.get('authors', [])
        if authors_list:
            # Extract names from list of dicts or strings
            # Example: [{"id": "...", "name": "Naomi Alderman"}]
            names = []
            for a in authors_list:
                if isinstance(a, dict):
                    names.append(a.get('name', ''))
                elif isinstance(a, str):
                    names.append(a)
            author = ", ".join(filter(None, names))

    # Parse dates
    release_date_str = meta.get('releaseDate') or meta.get('publishedDate')
    # If it's a string, we might need parsing if it's not handled by driver. 
    # Usually psycopg2 handles ISO strings for timestamps.
    # If empty string, set to None
    if not release_date_str:
        release_date_str = None
        
    cur.execute("""
        INSERT INTO library_items (
            id, library_id, media_type, title, subtitle, author, narrators, 
            description, genres, release_date, published_year, 
            feed_url, image_url, explicit, language, publisher, isbn, asin
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (id) DO UPDATE SET
            title = EXCLUDED.title,
            subtitle = EXCLUDED.subtitle,
            author = EXCLUDED.author,
            narrators = EXCLUDED.narrators,
            description = EXCLUDED.description,
            genres = EXCLUDED.genres,
            image_url = EXCLUDED.image_url,
            publisher = EXCLUDED.publisher,
            isbn = EXCLUDED.isbn,
            asin = EXCLUDED.asin
    """, (
        item_data.get('libraryItemId'),
        item_data.get('libraryId'),
        item_data.get('mediaType'),
        meta.get('title'),
        meta.get('subtitle'),
        author,
        meta.get('narrators'), # Array
        meta.get('description'),
        meta.get('genres'),
        release_date_str,
        meta.get('publishedYear'),
        meta.get('feedUrl'),
        meta.get('imageUrl'),
        meta.get('explicit'),
        meta.get('language'),
        meta.get('publisher'),
        meta.get('isbn'),
        meta.get('asin')
    ))

def session_exists(cur, session_id):
    cur.execute("SELECT 1 FROM listening_sessions WHERE id = %s", (session_id,))
    return cur.fetchone() is not None

def process_synced_sessions(conn):
    try:
        conn.set_client_encoding('UTF8')
    except Exception as e:
        logging.warning(f"Could not set client encoding to UTF8: {e}")

    cur = conn.cursor()
    
    # Check for REFRESH
    if os.getenv("REFRESH", "").lower() == "true":
        logging.warning("REFRESH=True detected. Truncating listening_sessions table...")
        try:
            cur.execute("TRUNCATE TABLE listening_sessions CASCADE;")
            conn.commit()
            logging.info("Table truncated. Starting fresh fetch.")
        except Exception as e:
            logging.error(f"Failed to truncate table: {e}")
            conn.rollback()
    
    page = 0
    items_per_page = 20 # Can increase
    stop_fetching = False
    
    while not stop_fetching:
        logging.info(f"Fetching page {page}...")
        data = fetch_sessions(page, items_per_page)
        sessions = data.get('sessions', [])
        
        if not sessions:
            logging.info("No more sessions found.")
            break
            
        for session in sessions:
            # We use a savepoint or explicit transaction handling per session to avoid 
            # one failure ruining the batch.
            try:
                # Check if we have seen this session
                # This check should be safe as it's a SELECT.
                if session_exists(cur, session['id']):
                    logging.info(f"Found existing session {session['id']}. Stopping fetch.")
                    stop_fetching = True
                    break
                
                # Upsert dependencies
                if 'user' in session:
                    upsert_user(cur, session['user'])
                
                if 'deviceInfo' in session:
                    upsert_device(cur, session['deviceInfo'])
                    
                if 'libraryItemId' in session:
                    upsert_library_item(cur, session, session.get('libraryId'), session.get('mediaType'))
                
                # Insert Session
                cur.execute("""
                    INSERT INTO listening_sessions (
                        id, user_id, library_item_id, episode_id, device_id,
                        display_title, display_author, duration, time_listening,
                        start_offset, media_progress, started_at, updated_at,
                        date_log, day_of_week
                    ) VALUES (
                        %s, %s, %s, %s, %s,
                        %s, %s, %s, %s,
                        %s, %s, %s, %s,
                        %s, %s
                    )
                """, (
                    session['id'],
                    session.get('userId'),
                    session.get('libraryItemId'),
                    session.get('episodeId'),
                    session.get('deviceInfo', {}).get('id'),
                    session.get('displayTitle'),
                    session.get('displayAuthor'),
                    session.get('duration'),
                    session.get('timeListening'),
                    session.get('startTime'),
                    session.get('currentTime'),
                    ms_to_datetime(session.get('startedAt')),
                    ms_to_datetime(session.get('updatedAt')),
                    session.get('date') or None,
                    session.get('dayOfWeek')
                ))
                
                # Commit successful session
                conn.commit()
                
            except Exception as e:
                logging.error(f"Error processing session {session.get('id')}: {e}")
                conn.rollback() 
                # Provide more context if possible
                continue

        if stop_fetching:
            break
            
        page += 1
        # Safety break for huge history
        if page > 1000:
            logging.warning("Reached page 1000, creating safety stop.")
            break
            
    cur.close()

if __name__ == "__main__":
    logging.info("Starting ABS Fetch Service")
    conn = get_db_connection()
    process_synced_sessions(conn)
    conn.close()
    logging.info("Finished sync.")
