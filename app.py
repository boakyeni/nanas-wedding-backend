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
        writer.writerow(['id', 'name', 'email', 'attending', 'plusOne', 'plusOneName', 'dietaryRestrictions', 'message', 'createdAt'])
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





# Only for development, not production
if __name__ == '__main__':
    app.run(debug=True)