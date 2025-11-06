from flask import Flask, request, jsonify, make_response
from flask_cors import CORS
import psycopg2
import os
from dotenv import load_dotenv
import jwt
from emailer import send_attendance_email
from twilioer import send_whatsapp
from logging_setup import setup_logger

log = setup_logger()

# I hate this code, it's chatgpt garbage but it works

# Load environment variables
load_dotenv()
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__, template_folder=os.path.join(BASE_DIR, "templates"))
CORS(app, resources={r"/*": {"origins": ["https://nanaandwahabwedding.com", "https://nanas-wedding.vercel.app", "http://localhost:3000"]}})  # Enable CORS for all routes

# Database connection function
def get_db_connection():
    conn = psycopg2.connect(
        host=os.getenv('DB_HOST'),
        database=os.getenv('DB_NAME'),
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD'),
        port=os.getenv('DB_PORT')
    )
    conn.autocommit = True
    return conn

# Initialize the database table if it doesn't exist
# def initialize_db():
#     conn = get_db_connection()
#     cur = conn.cursor()
    
#     # Create table if it doesn't exist
#     cur.execute('''
#     CREATE TABLE IF NOT EXISTS rsvp (
#         id SERIAL PRIMARY KEY,
#         name VARCHAR(255) NOT NULL,
#         email VARCHAR(255) NOT NULL,
#         attending BOOLEAN NOT NULL,
#         plus_one BOOLEAN,
#         plus_one_name VARCHAR(255),
#         dietary_restrictions TEXT,
#         message TEXT,
#         created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
#     )
#     ''')
    
#     cur.close()
#     conn.close()

# # Initialize database on startup
# initialize_db()

@app.route('/api/rsvp', methods=['POST'])
def submit_rsvp():
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['name', 'email', 'attending']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'Missing required field: {field}'}), 400
        
        # Convert attending to boolean if it comes as string
        if isinstance(data['attending'], str):
            data['attending'] = data['attending'].lower() == 'yes' or data['attending'].lower() == 'true'
        
        # Set default values for optional fields
        plus_one = data.get('plusOne', False)
        plus_one_name = data.get('plusOneName', '')
        dietary_restrictions = data.get('dietaryRestrictions', '')
        message = data.get('message', '')
        
        # Insert data into database using with statement
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    'INSERT INTO rsvp (name, email, attending, plus_one, plus_one_name, dietary_restrictions, message) VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id',
                    (data['name'], data['email'], data['attending'], plus_one, plus_one_name, dietary_restrictions, message)
                )
                # Get the generated ID
                id = cur.fetchone()[0]
        
        return jsonify({'success': True, 'id': id}), 201
    
    except Exception as e:
        
        return jsonify({'error': f'An error occurred processing your RSVP: {e}'}), 500

# Optional: Add an endpoint to get all RSVPs (password protected for admin use)
@app.route('/api/rsvps', methods=['GET'])
def get_rsvps():
    
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute('SELECT * FROM rsvp ORDER BY created_at DESC')
        rows = cur.fetchall()
        
        rsvps = []
        for row in rows:
            rsvp = {
                'id': row[0],
                'name': row[1],
                'email': row[2],
                'attending': row[3],
                'plusOne': row[4],
                'plusOneName': row[5],
                'dietaryRestrictions': row[6],
                'message': row[7],
                'createdAt': row[8].isoformat() if row[8] else None
            }
            rsvps.append(rsvp)
        
        cur.close()
        conn.close()
        
        return jsonify(rsvps)
    
    except Exception as e:
        print(f"Error: {str(e)}")
        return jsonify({'error': 'An error occurred retrieving RSVPs'}), 500
    
@app.get('/api/rsvps/download')
def download_rsvps():
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('SELECT * FROM rsvp ORDER BY created_at DESC')
        rows = cur.fetchall()
        cur.close()
        conn.close()

        # Convert to CSV
        from io import StringIO
        import csv

        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(['name', 'email', 'attending', 'plusOne', 'plusOneName', 'dietaryRestrictions', 'message', 'createdAt'])
        for row in rows:
            writer.writerow(row)

        output.seek(0)
        return make_response(output.read(), 200, {
            'Content-Disposition': 'attachment; filename=rsvps.csv',
            'Content-Type': 'text/csv'
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


# Health check endpoint
@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'healthy'}), 200



@app.post('/api/login')
def login():
    try:
        data = request.get_json()
        username = data.get('username')
        password = data.get('password')

        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Use `crypt($password, password)` to compare against hashed column
                cur.execute(
                    'SELECT id FROM users WHERE username = %s AND password = crypt(%s, password)',
                    (username, password)
                )
                user = cur.fetchone()

        if user:
            token = jwt.encode({'user': username}, os.getenv('SECRET'), algorithm='HS256')
            resp = make_response({'msg': 'ok'})
            resp.set_cookie('access_token', token, httponly=True)
            return resp
        else:
            return jsonify({'msg': 'unauthorized'}), 401

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.get('/api/guests')
def get_guests():
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT
                        g.id, g.title, g.party_id, g.first_name, g.last_name, g.display_name,
                        g.email, g.phone, g.attending, g.plus_one, g.plus_one_name,
                        g.dietary, g.message, g.attending_confirmation_sent, g.whatsapp_confirmation_sent, g.created_at,
                        p.label AS party_label, p.invite_code
                    FROM guests g
                    LEFT JOIN parties p ON p.id = g.party_id
                    ORDER BY g.last_name, g.first_name;
                """)
                cols = [c[0] for c in cur.description]
                rows = [dict(zip(cols, r)) for r in cur.fetchall()]

        # Convert to camelCase for frontend consistency
        guests = []
        for r in rows:
            guests.append({
                "id": r["id"],
                "title": r["title"],
                "partyId": r["party_id"],
                "partyLabel": r["party_label"],
                "inviteCode": r["invite_code"],
                "firstName": r["first_name"],
                "lastName": r["last_name"],
                "displayName": r["display_name"],
                "email": r["email"],
                "phone": r["phone"],
                "attending": r["attending"],
                "plusOne": r["plus_one"],
                "plusOneName": r["plus_one_name"],
                "dietary": r["dietary"],
                "message": r["message"],
                "attending_confirmation_sent": r["attending_confirmation_sent"],
                "whatsapp_confirmation_sent": r["whatsapp_confirmation_sent"],
                "createdAt": r["created_at"].isoformat() if r["created_at"] else None
            })

        return jsonify(guests), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.get('/api/parties')
def get_parties():
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT
                        p.id AS party_id, p.label, p.invite_code, p.notes, p.created_at,
                        g.id AS guest_id, g.title, g.first_name, g.last_name, g.display_name,
                        g.email, g.phone, g.attending, g.plus_one, g.plus_one_name,
                        g.dietary, g.message, g.attending_confirmation_sent, g.whatsapp_confirmation_sent, g.created_at AS guest_created_at
                    FROM parties p
                    LEFT JOIN guests g ON g.party_id = p.id
                    ORDER BY p.created_at DESC, g.last_name, g.first_name;
                """)
                rows = cur.fetchall()

        parties = {}
        for row in rows:
            (party_id, label, invite_code, notes, party_created_at,
             guest_id, title, first_name, last_name, display_name,
             email, phone, attending, plus_one, plus_one_name,
             dietary, message, attending_confirmation_sent, whatsapp_confirmation_sent, guest_created_at) = row

            if party_id not in parties:
                parties[party_id] = {
                    "id": party_id,
                    "label": label,
                    "inviteCode": invite_code,
                    "notes": notes,
                    "createdAt": party_created_at.isoformat() if party_created_at else None,
                    "members": []
                }

            if guest_id is not None:
                parties[party_id]["members"].append({
                    "id": guest_id,
                    "title": title,
                    "firstName": first_name,
                    "lastName": last_name,
                    "displayName": display_name,
                    "email": email,
                    "phone": phone,
                    "attending": attending,
                    "plusOne": plus_one,
                    "plusOneName": plus_one_name,
                    "dietary": dietary,
                    "message": message,
                    "attending_confirmation_sent": attending_confirmation_sent,
                    "whatsapp_confirmation_sent": whatsapp_confirmation_sent,
                    "createdAt": guest_created_at.isoformat() if guest_created_at else None
                })

        return jsonify(list(parties.values())), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.post('/api/guests')
def create_guest():
    try:
        data = request.get_json(force=True)
        with get_db_connection() as conn, conn.cursor() as cur:
            cur.execute("""
                INSERT INTO guests
                  (party_id, title, first_name, last_name, email, phone,
                   attending, plus_one, plus_one_name, dietary, message, source)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'admin')
                RETURNING id
            """, (
                data.get('partyId'),
                data.get('title'),
                data['firstName'], data['lastName'],
                data.get('email'), data.get('phone'),
                data.get('attending'),
                data.get('plusOne', False),
                data.get('plusOneName'),
                data.get('dietary'),
                data.get('message')
            ))
            new_id = cur.fetchone()[0]
        return jsonify({"id": new_id}), 201
    except KeyError as e:
        return jsonify({"error": f"Missing field: {e}"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.patch('/api/guests/<int:guest_id>')
def update_guest(guest_id):
    try:
        data = request.get_json(force=True)
        fields = {
            "party_id": "partyId",
            "title": "title",
            "first_name": "firstName",
            "last_name": "lastName",
            "email": "email",
            "phone": "phone",
            "attending": "attending",
            "plus_one": "plusOne",
            "plus_one_name": "plusOneName",
            "dietary": "dietary",
            "attending_confirmation_sent": "attending_confirmation_sent",
            "message": "message",
            "whatsapp_confirmation_sent": "whatsapp_confirmation_sent"
        }
        sets, params = [], []
        for col, key in fields.items():
            if key in data:
                sets.append(f"{col} = %s")
                params.append(data[key])
        if not sets:
            return jsonify({"error": "No updatable fields provided"}), 400
        params.append(guest_id)

        with get_db_connection() as conn, conn.cursor() as cur:
            cur.execute(f"UPDATE guests SET {', '.join(sets)} WHERE id = %s RETURNING id", params)
            row = cur.fetchone()
        if not row:
            return jsonify({"error": "Guest not found"}), 404
        return jsonify({"id": row[0]}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.post('/api/parties')
def create_party():
    try:
        data = request.get_json(force=True)
        with get_db_connection() as conn, conn.cursor() as cur:
            cur.execute("""
                INSERT INTO parties (label, invite_code, notes)
                VALUES (%s,%s,%s) RETURNING id
            """, (data.get('label'), data.get('inviteCode'), data.get('notes')))
            new_id = cur.fetchone()[0]
        return jsonify({"id": new_id}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.patch('/api/parties/<int:party_id>')
def update_party(party_id):
    try:
        data = request.get_json(force=True)
        fields = {"label": "label", "invite_code": "inviteCode", "notes": "notes"}
        sets, params = [], []
        for col, key in fields.items():
            if key in data:
                sets.append(f"{col} = %s")
                params.append(data[key])
        if not sets:
            return jsonify({"error": "No updatable fields provided"}), 400
        params.append(party_id)

        with get_db_connection() as conn, conn.cursor() as cur:
            cur.execute(f"UPDATE parties SET {', '.join(sets)} WHERE id = %s RETURNING id", params)
            row = cur.fetchone()
        if not row:
            return jsonify({"error": "Party not found"}), 404
        return jsonify({"id": row[0]}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.post('/api/parties/<int:party_id>/assign')
def assign_guests_to_party(party_id):
    try:
        data = request.get_json(force=True)
        guest_ids = data.get('guestIds', [])
        if not guest_ids:
            return jsonify({"error": "guestIds must be a non-empty array"}), 400

        with get_db_connection() as conn, conn.cursor() as cur:
            cur.execute("SELECT id FROM parties WHERE id = %s", (party_id,))
            if cur.fetchone() is None:
                return jsonify({"error": "Party not found"}), 404

            cur.execute(
                "UPDATE guests SET party_id = %s WHERE id = ANY(%s) RETURNING id",
                (party_id, guest_ids)
            )
            updated = [r[0] for r in cur.fetchall()]
        return jsonify({"updated": updated}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.post('/api/guests/unassign')
def unassign_guests():
    try:
        data = request.get_json(force=True)
        guest_ids = data.get('guestIds', [])
        if not guest_ids:
            return jsonify({"error": "guestIds must be a non-empty array"}), 400
        with get_db_connection() as conn, conn.cursor() as cur:
            cur.execute(
                "UPDATE guests SET party_id = NULL WHERE id = ANY(%s) RETURNING id",
                (guest_ids,)
            )
            updated = [r[0] for r in cur.fetchall()]
        return jsonify({"updated": updated}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.post('/api/upload/csv')
def upload_csv():
    try:
        if 'file' not in request.files:
            return jsonify({"error": "No file part"}), 400
        file = request.files['file']
        if file.filename == '':
            return jsonify({"error": "No selected file"}), 400

        import csv, io
        stream = io.StringIO(file.stream.read().decode('utf-8'))
        reader = csv.DictReader(stream)

        created_parties, created_guests = [], []
        with get_db_connection() as conn, conn.cursor() as cur:
            for raw in reader:
                # normalize keys (lowercase)
                row = { (k or '').strip().lower(): (v or '').strip() for k,v in raw.items() }

                party_id = None
                invite_code = row.get('invite_code') or None
                party_label = row.get('party_label') or None

                if invite_code:
                    # try reuse by code
                    cur.execute("SELECT id FROM parties WHERE invite_code = %s", (invite_code,))
                    r = cur.fetchone()
                    if r:
                        party_id = r[0]
                    else:
                        cur.execute(
                            "INSERT INTO parties (label, invite_code, notes) VALUES (%s,%s,%s) RETURNING id",
                            (party_label, invite_code, 'csv import')
                        )
                        party_id = cur.fetchone()[0]
                        created_parties.append(party_id)
                elif party_label:
                    # try reuse by label
                    cur.execute("SELECT id FROM parties WHERE label = %s", (party_label,))
                    r = cur.fetchone()
                    if r:
                        party_id = r[0]
                    else:
                        cur.execute(
                            "INSERT INTO parties (label, notes) VALUES (%s,%s) RETURNING id",
                            (party_label, 'csv import')
                        )
                        party_id = cur.fetchone()[0]
                        created_parties.append(party_id)
                # else: leave unassigned

                def to_bool(v):
                    v = (v or '').strip().lower()
                    return True if v in ('true','yes','y','1') else False if v in ('false','no','n','0') else None

                cur.execute("""
                    INSERT INTO guests
                      (party_id, title, first_name, last_name, email, phone,
                       attending, plus_one, plus_one_name, dietary, message, source)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'csv')
                    RETURNING id
                """, (
                    party_id,
                    row.get('title') or None,
                    row.get('first_name') or '',
                    row.get('last_name') or '',
                    row.get('email') or None,
                    row.get('phone') or None,
                    to_bool(row.get('attending')),
                    to_bool(row.get('plus_one')) or False,
                    row.get('plus_one_name') or None,
                    row.get('dietary') or None,
                    row.get('message') or None
                ))
                created_guests.append(cur.fetchone()[0])

        return jsonify({
            "createdParties": created_parties,
            "createdGuests": created_guests,
            "count": len(created_guests)
        }), 201

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
@app.post("/api/send-confirmation")
def send_confirmation():
    data = request.get_json(force=True, silent=True) or {}

    required = [
        "to", "guestName", "seats", "venueName",
        "venueAddress", "mapsUrl", "websiteUrl", "guideUrl"
    ]
    missing = [k for k in required if not data.get(k)]
    if missing:
        return jsonify({"ok": False, "error": f"Missing fields: {', '.join(missing)}"}), 400

    try:
        send_attendance_email(
            to_email=data["to"],
            guest_name=data["guestName"],
            seats=int(data["seats"]),
            venue_name=data["venueName"],
            venue_address=data["venueAddress"],
            maps_url=data["mapsUrl"],
            website_url=data["websiteUrl"],
            guide_url=data["guideUrl"],
            reply_to=data.get("replyTo"),
            subject=data.get("subject")
        )
        return jsonify({"ok": True}), 200

    except Exception as e:
        log.error("Email Error:", str(e))
        return jsonify({"ok": False, "error": str(e)}), 500
    
@app.post("/api/send_whatsapp_message")
def send_whatsapp_message():
    data = request.get_json() or {}

    try:
        sid = send_whatsapp(
            guest_name=data.get("guest_name"),
            phone_number=data.get("phone_number"),
            attending=bool(data.get("attending")),
            seats=data.get("seats"),
            rsvp_link=data.get("rsvp_link"),
        )
        return jsonify({"status": "sent", "sid": sid}), 200

    except Exception as e:
        print("WhatsApp error:", e)
        return jsonify({"error": str(e)}), 500
    
@app.post("/api/guests/<int:guest_id>/send_confirmations")
def send_confirmations(guest_id: int):
    """
    Uses current DB state.
    Body (all optional):
    {
      "email": "optional new email",    # optional contact update
      "phone": "+15551234567",          # optional contact update
      "send_email_if_needed": true,
      "send_whatsapp_if_needed": true,

      "email_payload": {                # required fields for your email sender
        "guest_name": "...",
        "venue_name": "...",
        "venue_address": "...",
        "maps_url": "...",
        "website_url": "...",
        "guide_url": "...",
        "reply_to": "optional",
        "subject": "optional"
      },
      "whatsapp_payload": {
        "guest_name": "...",
        "attending": true,              # defaults to DB value if omitted
        "rsvp_link": "..."
      }
    }
    """
    log.info("Call made to send confirmations")
    data = request.get_json(force=True, silent=True) or {}
    try:
        conn = get_db_connection()
        conn.autocommit = False
        try:
            with conn.cursor() as cur:
                # 1) Lock the guest row (we need party_id, contact, flags, plus_one, attending, name)
                cur.execute("""
                    SELECT party_id, email, phone, plus_one,
                           attending, attending_confirmation_sent, whatsapp_confirmation_sent, display_name
                    FROM guests
                    WHERE id = %s
                    FOR UPDATE
                """, (guest_id,))
                row = cur.fetchone()
                if not row:
                    conn.rollback()
                    return jsonify({"error": "guest_not_found"}), 404

                (party_id, db_email, db_phone, plus_one,
                 db_attending, email_sent, wa_sent,
                 display_name) = row

                # 2) Optional contact update (still under lock)
                new_email = data.get("email") or db_email
                new_phone = data.get("phone") or db_phone
                if (new_email != db_email) or (new_phone != db_phone):
                    cur.execute("""
                        UPDATE guests
                        SET email = %s, phone = %s
                        WHERE id = %s
                    """, (new_email, new_phone, guest_id))
                    if cur.rowcount == 0:
                        conn.rollback()
                        log.warning(f"No guest updated for id={guest_id} (email={new_email}, phone={new_phone})")
                        return jsonify({"error": "contact_update_failed"}), 500
                    db_email, db_phone = new_email, new_phone
                    

                # 3) Compute seats from current DB state
                #    Party seats: SUM over attending members of (1 + (plus_one?1:0))
                if party_id is not None:
                    cur.execute("""
                    SELECT id, attending, plus_one
                    FROM guests
                    WHERE party_id = %s
                    FOR UPDATE
                    """, (party_id,))
                    members = cur.fetchall()
                    # members: [(id, attending, plus_one), ...]
                    seats = 0
                    for _, attending, plus_one_m in members:
                        if attending:
                            seats += 1 + (1 if plus_one_m else 0)
                else:
                    seats = (1 + (1 if plus_one else 0)) if db_attending else 0

                # 4) Decide what to send based on flags + contact
                want_email = bool(data.get("send_email_if_needed", True))
                want_wa = bool(data.get("send_whatsapp_if_needed", True))

                is_attending = bool(db_attending)

                will_send_email = bool(want_email and is_attending and db_email and not email_sent)
                will_send_wa = bool(want_wa and is_attending and db_phone and not wa_sent)
                email_ok = False
                # 5) Perform sends (raise on failure to abort & keep flags unchanged)
                if will_send_email:
                    ep = data.get("email_payload") or {}
                    # validate required keys for your email helper
                    required_email_keys = ["venue_name", "venue_address",
                                           "maps_url", "website_url", "guide_url"]
                    missing = [k for k in required_email_keys if not ep.get(k)]
                    if missing:
                        conn.rollback()
                        return jsonify({"error": f"missing_email_payload: {', '.join(missing)}"}), 400

                    try:
                        _ = send_attendance_email(
                            to_email=db_email,
                            guest_name=display_name,
                            seats=int(seats),
                            venue_name=ep["venue_name"],
                            venue_address=ep["venue_address"],
                            maps_url=ep["maps_url"],
                            website_url=ep["website_url"],
                            guide_url=ep["guide_url"],
                            reply_to=ep.get("reply_to"),
                            subject=ep.get("subject"),
                        )
                        email_ok=True# got past raise_for_status() => 2xx
                        cur.execute(
                            "UPDATE guests SET attending_confirmation_sent = TRUE WHERE id = %s",
                            (guest_id,),
                        )
                        conn.commit()
                    except Exception as e:
                        conn.rollback()
                        log.warning("Email failed for %s: %s", db_email, e)
                        return jsonify({"error": f"{e}"}), 400
                    
                wa_ok=False
                if will_send_wa:
                    wp = data.get("whatsapp_payload") or {}
                    try:
                        send_whatsapp(
                            guest_name=display_name,
                            phone_number=db_phone,
                            attending=bool(wp.get("attending", db_attending)),
                            seats=int(seats),
                            rsvp_link=wp.get("rsvp_link"),
                        )
                        wa_ok = True
                        cur.execute(
                        "UPDATE guests SET whatsapp_confirmation_sent = TRUE WHERE id = %s",
                        (guest_id,),
                        )
                        conn.commit()
                    except Exception as e:
                        conn.rollback()
                        log.warning("WhatsApp failed for %s: %s", db_phone, e)
                        return jsonify({"error": f"{e}"}), 400

            conn.commit()
            cur.execute("""
                SELECT attending_confirmation_sent, whatsapp_confirmation_sent
                FROM guests WHERE id = %s
            """, (guest_id,))
            att_sent_db, wa_sent_db = cur.fetchone()
            return jsonify({
                "id": guest_id,
                "party_id": party_id,
                "seats": int(seats),
                "attending": bool(db_attending),
                "attending_confirmation_sent": bool(att_sent_db),
                "whatsapp_confirmation_sent": bool(wa_sent_db),
                "sent": {
                    "email": bool(will_send_email and email_ok),   # sent in this call
                    "whatsapp": bool(will_send_wa and wa_ok)
                }
            }), 200

        except Exception as e:
            conn.rollback()
            return jsonify({"error": str(e)}), 500
        finally:
            conn.autocommit = True
            conn.close()

    except Exception as e:
        return jsonify({"error": str(e)}), 500





# Only for development, not production
if __name__ == '__main__':
    app.run(debug=True)