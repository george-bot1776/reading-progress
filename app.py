#!/usr/bin/env python3
"""
Reading Tracker - Local Flask App
"""

import sqlite3
import csv
import os
from flask import Flask, render_template, request, redirect, url_for, flash
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'reading-tracker-secret'
DB_PATH = 'reading_tracker.db'

def init_db():
    """Initialize the database."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS books (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            author TEXT,
            pages INTEGER,
            date_added TEXT,
            date_started TEXT,
            date_finished TEXT,
            rating INTEGER,
            format TEXT,
            read_count INTEGER DEFAULT 0
        )
    ''')
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS reading_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            book_id INTEGER,
            date TEXT,
            pages_read INTEGER,
            FOREIGN KEY (book_id) REFERENCES books (id)
        )
    ''')
    
    conn.commit()
    conn.close()

def get_db():
    """Get database connection."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/')
def index():
    """Main dashboard."""
    conn = get_db()
    c = conn.cursor()
    
    # Get all books
    c.execute('SELECT * FROM books ORDER BY date_added DESC')
    books = c.fetchAll()
    
    # Stats
    c.execute('SELECT COUNT(*) FROM books')
    total_books = c.fetchone()[0]
    
    c.execute('SELECT SUM(pages) FROM books WHERE pages IS NOT NULL')
    total_pages = c.fetchone()[0] or 0
    
    c.execute('SELECT SUM(read_count) FROM books')
    total_reads = c.fetchone()[0] or 0
    
    c.execute('SELECT COUNT(*) FROM books WHERE date_finished IS NOT NULL')
    books_finished = c.fetchone()[0]
    
    # This year's stats
    current_year = datetime.now().year
    c.execute('''SELECT SUM(pages) FROM books 
                 WHERE date_added LIKE ?''', (f'{current_year}%',))
    pages_this_year = c.fetchone()[0] or 0
    
    conn.close()
    
    return render_template('index.html', 
                         books=books,
                         total_books=total_books,
                         total_pages=total_pages,
                         total_reads=total_reads,
                         books_finished=books_finished,
                         pages_this_year=pages_this_year)

@app.route('/add', methods=['GET', 'POST'])
def add_book():
    """Add a new book."""
    if request.method == 'POST':
        title = request.form['title']
        author = request.form.get('author', '')
        pages = request.form.get('pages')
        pages = int(pages) if pages else None
        format_type = request.form.get('format', 'Paperback')
        
        conn = get_db()
        c = conn.cursor()
        c.execute('''INSERT INTO books (title, author, pages, date_added, format)
                     VALUES (?, ?, ?, ?, ?)''',
                  (title, author, pages, datetime.now().strftime('%Y-%m-%d'), format_type))
        conn.commit()
        conn.close()
        
        flash(f'Added "{title}"', 'success')
        return redirect(url_for('index'))
    
    return render_template('add.html')

@app.route('/import', methods=['GET', 'POST'])
def import_goodreads():
    """Import from Goodreads CSV."""
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('No file selected', 'error')
            return redirect(request.url)
        
        file = request.files['file']
        if file.filename == '':
            flash('No file selected', 'error')
            return redirect(request.url)
        
        if file:
            try:
                # Read CSV
                content = file.read().decode('utf-8')
                lines = content.split('\n')
                
                # Find header row
                header_idx = -1
                for i, line in enumerate(lines[:10]):
                    if 'Title' in line and 'Author' in line:
                        header_idx = i
                        break
                
                if header_idx == -1:
                    flash('Could not find Goodreads format', 'error')
                    return redirect(request.url)
                
                # Parse headers
                headers = lines[header_idx].strip().split(',')
                headers = [h.strip().replace('"', '') for h in headers]
                
                title_idx = next((i for i, h in enumerate(headers) if 'Title' in h), -1)
                author_idx = next((i for i, h in enumerate(headers) if 'Author' in h), -1)
                pages_idx = next((i for i, h in enumerate(headers) if 'Number of Pages' in h), -1)
                rating_idx = next((i for i, h in enumerate(headers) if 'Average Rating' in h), -1)
                date_idx = next((i for i, h in enumerate(headers) if 'Date Added' in h), -1)
                
                # Import books
                conn = get_db()
                c = conn.cursor()
                imported = 0
                
                for line in lines[header_idx + 1:]:
                    if not line.strip():
                        continue
                    
                    # Simple CSV parse
                    cols = line.strip().split(',')
                    
                    # Try to extract fields
                    title = cols[title_idx].strip().replace('"', '') if title_idx >= 0 and title_idx < len(cols) else 'Unknown'
                    author = cols[author_idx].strip().replace('"', '') if author_idx >= 0 and author_idx < len(cols) else ''
                    
                    pages = None
                    if pages_idx >= 0 and pages_idx < len(cols):
                        try:
                            pages = int(cols[pages_idx].strip().replace('"', ''))
                        except:
                            pass
                    
                    rating = None
                    if rating_idx >= 0 and rating_idx < len(cols):
                        try:
                            rating = int(float(cols[rating_idx].strip().replace('"', '')))
                        except:
                            pass
                    
                    date_added = datetime.now().strftime('%Y-%m-%d')
                    if date_idx >= 0 and date_idx < len(cols):
                        date_str = cols[date_idx].strip().replace('"', '')
                        try:
                            # Try various date formats
                            for fmt in ['%m/%d/%Y', '%Y/%m/%d', '%m/%d/%y']:
                                try:
                                    date_added = datetime.strptime(date_str, fmt).strftime('%Y-%m-%d')
                                    break
                                except:
                                    pass
                        except:
                            pass
                    
                    if title and title != 'Unknown':
                        c.execute('''INSERT INTO books (title, author, pages, date_added, rating)
                                     VALUES (?, ?, ?, ?, ?)''',
                                  (title, author, pages, date_added, rating))
                        imported += 1
                
                conn.commit()
                conn.close()
                
                flash(f'Imported {imported} books!', 'success')
                return redirect(url_for('index'))
                
            except Exception as e:
                flash(f'Error: {str(e)}', 'error')
                return redirect(request.url)
    
    return render_template('import.html')

@app.route('/book/<int:book_id>')
def book_detail(book_id):
    """Book detail page."""
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT * FROM books WHERE id = ?', (book_id,))
    book = c.fetchone()
    conn.close()
    
    if not book:
        flash('Book not found', 'error')
        return redirect(url_for('index'))
    
    return render_template('book.html', book=book)

@app.route('/book/<int:book_id>/start', methods=['POST'])
def start_book(book_id):
    """Mark book as started."""
    conn = get_db()
    c = conn.cursor()
    c.execute('UPDATE books SET date_started = ? WHERE id = ?',
              (datetime.now().strftime('%Y-%m-%d'), book_id))
    conn.commit()
    conn.close()
    return redirect(url_for('book_detail', book_id=book_id))

@app.route('/book/<int:book_id>/finish', methods=['POST'])
def finish_book(book_id):
    """Mark book as finished."""
    conn = get_db()
    c = conn.cursor()
    c.execute('UPDATE books SET date_finished = ?, read_count = read_count + 1 WHERE id = ?',
              (datetime.now().strftime('%Y-%m-%d'), book_id))
    conn.commit()
    conn.close()
    return redirect(url_for('book_detail', book_id=book_id))

@app.route('/book/<int:book_id>/delete', methods=['POST'])
def delete_book(book_id):
    """Delete a book."""
    conn = get_db()
    c = conn.cursor()
    c.execute('DELETE FROM books WHERE id = ?', (book_id,))
    conn.commit()
    conn.close()
    flash('Book deleted', 'success')
    return redirect(url_for('index'))

# Vercel handler
app.debug = True

def handler(environ, start_response):
    return app(environ, start_response)

if __name__ == '__main__':
    init_db()
    print("Reading Tracker running at http://localhost:5000")
    app.run(debug=True, port=5000)
