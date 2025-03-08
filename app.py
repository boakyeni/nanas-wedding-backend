from flask import Flask, request, jsonify
from flask_cors import CORS
import psycopg2
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

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
def initialize_db():
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Create table if it doesn't exist
    cur.execute('''
    CREATE TABLE IF NOT EXISTS rsvp (
        id SERIAL PRIMARY KEY,
        name VARCHAR(255) NOT NULL,
        email VARCHAR(255) NOT NULL,
        attending BOOLEAN NOT NULL,
        plus_one BOOLEAN,
        plus_one_name VARCHAR(255),
        dietary_restrictions TEXT,
        message TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    cur.close()
    conn.close()

# Initialize database on startup
initialize_db()

@app.route('/rsvp', methods=['POST'])
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
        plus_one = data.get('plusOne', 0)
        plus_one_name = data.get('plusOneName', '')
        dietary_restrictions = data.get('dietaryRestrictions', '')
        message = data.get('message', '')
        
        # Insert data into database
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute(
            'INSERT INTO rsvp (name, email, attending, plus_one, plus_one_name, dietary_restrictions, message) VALUES (%s, %s, %s, %s, %s, %s) RETURNING id',
            (data['name'], data['email'], data['attending'], plus_one, plus_one_name, dietary_restrictions, message)
        )
        
        # Get the generated ID
        id = cur.fetchone()[0]
        
        cur.close()
        conn.close()
        
        return jsonify({'success': True, 'id': id}), 201
    
    except Exception as e:
        # Log the error for debugging (in production, use a proper logger)
        print(f"Error: {str(e)}")
        return jsonify({'error': 'An error occurred processing your RSVP'}), 500

# Optional: Add an endpoint to get all RSVPs (password protected for admin use)
@app.route('/rsvps', methods=['GET'])
def get_rsvps():
    # Simple API key validation - in production, use a more secure method
    api_key = request.headers.get('X-API-Key')
    if api_key != os.getenv('ADMIN_API_KEY'):
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute('SELECT id, name, email, attending, plus_one, plus_one_name, dietary_restrictions, message, created_at FROM rsvp ORDER BY created_at DESC')
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

# Health check endpoint
@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'healthy'}), 200

# Only for development, not production
if __name__ == '__main__':
    app.run(debug=True)