from flask import Flask, render_template, request, jsonify, redirect, url_for
import mysql.connector
from mysql.connector import Error
import os
from dotenv import load_dotenv
import requests
import json
from datetime import datetime, timedelta

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'fallback-secret-key')

# Database configuration
db_config = {
    'host': os.getenv('MYSQL_HOST', 'localhost'),
    'user': os.getenv('MYSQL_USER', 'root'),
    'password': os.getenv('MYSQL_PASSWORD', ''),
    'database': os.getenv('MYSQL_DB', 'mood_journal')
}

def get_db_connection():
    try:
        connection = mysql.connector.connect(**db_config)
        return connection
    except Error as e:
        print(f"Error connecting to MySQL: {e}")
        return None

# Hugging Face API configuration
API_URL = "https://api-inference.huggingface.co/models/j-hartmann/emotion-english-distilroberta-base"
HEADERS = {"Authorization": "Bearer 694a69bbd54ad829a4c7d9162e615e647db1e950a5cb34ba"} 

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/journal', methods=['GET', 'POST'])
def journal():
    if request.method == 'POST':
        content = request.form['content']
        
        # Get sentiment analysis from Hugging Face API
        payload = {"inputs": content}
        try:
            response = requests.post(API_URL, headers=HEADERS, json=payload)
            result = response.json()
            
            # Process the result
            if isinstance(result, list):
                sentiment_data = result[0]
                # Get the emotion with highest score
                top_emotion = max(sentiment_data, key=lambda x: x['score'])
                sentiment = top_emotion['label']
                score = top_emotion['score']
            else:
                sentiment = "unknown"
                score = 0
        except Exception as e:
            print(f"Error with Hugging Face API: {e}")
            sentiment = "error"
            score = 0
        
        # Save to database
        connection = get_db_connection()
        if connection:
            try:
                cursor = connection.cursor()
                cursor.execute(
                    "INSERT INTO entries (content, sentiment, score) VALUES (%s, %s, %s)",
                    (content, sentiment, score)
                )
                connection.commit()
                cursor.close()
                connection.close()
            except Error as e:
                print(f"Error saving to database: {e}")
        
        return redirect(url_for('dashboard'))
    
    return render_template('journal.html')

@app.route('/dashboard')
def dashboard():
    dates = []
    scores = []
    sentiments = []
    
    connection = get_db_connection()
    if connection:
        try:
            cursor = connection.cursor(dictionary=True)
            
            # Get last 7 days of entries
            seven_days_ago = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d %H:%M:%S')
            cursor.execute("SELECT sentiment, score, created_at FROM entries WHERE created_at >= %s ORDER BY created_at", (seven_days_ago,))
            entries = cursor.fetchall()
            
            for entry in entries:
                dates.append(entry['created_at'].strftime('%Y-%m-%d'))
                scores.append(entry['score'])
                sentiments.append(entry['sentiment'])
            
            cursor.close()
            connection.close()
        except Error as e:
            print(f"Error fetching data: {e}")
    
    return render_template('dashboard.html', dates=dates, scores=scores, sentiments=sentiments)

@app.route('/api/entries')
def api_entries():
    entries = []
    connection = get_db_connection()
    if connection:
        try:
            cursor = connection.cursor(dictionary=True)
            cursor.execute("SELECT * FROM entries ORDER BY created_at DESC")
            entries = cursor.fetchall()
            cursor.close()
            connection.close()
        except Error as e:
            print(f"Error fetching entries: {e}")
    
    return jsonify(entries)

if __name__ == '__main__':
    app.run(debug=True)