from flask import Flask, request, jsonify, make_response
from flask_cors import CORS
import psycopg2
import os
from dotenv import load_dotenv
import jwt

# Load environment variables
load_dotenv()

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": ["https://nanas-wedding.vercel.app", "http://localhost:3000"]}})  # Enable CORS for all routes

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
                        g.dietary, g.message, g.created_at,
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
                        g.dietary, g.message, g.created_at AS guest_created_at
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
             dietary, message, guest_created_at) = row

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
            "message": "message"
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




# Only for development, not production
if __name__ == '__main__':
    app.run(debug=True)