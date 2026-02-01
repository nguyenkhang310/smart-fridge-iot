"""
Database module for Smart Fridge IoT
MySQL database integration
"""

import mysql.connector
from mysql.connector import Error
from datetime import datetime
import os
from contextlib import contextmanager

# Database configuration
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': int(os.getenv('DB_PORT', 3306)),
    'user': os.getenv('DB_USER', 'root'),
    'password': os.getenv('DB_PASSWORD', ''),
    'database': os.getenv('DB_NAME', 'smart_fridge'),
    'charset': 'utf8mb4',
    'collation': 'utf8mb4_unicode_ci'
}

# Global connection pool
_connection_pool = None

def init_database():
    """Initialize database connection and create tables if not exist"""
    global _connection_pool
    
    try:
        # First, connect without database to create it if needed
        temp_config = DB_CONFIG.copy()
        temp_config.pop('database', None)
        
        conn = mysql.connector.connect(**temp_config)
        cursor = conn.cursor()
        
        # Create database if not exists
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS {DB_CONFIG['database']} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
        conn.commit()
        cursor.close()
        conn.close()
        
        # Now connect to the database
        _connection_pool = mysql.connector.pooling.MySQLConnectionPool(
            pool_name="smart_fridge_pool",
            pool_size=5,
            pool_reset_session=True,
            **DB_CONFIG
        )
        
        # Create tables
        create_tables()
        
        print("✓ Database initialized successfully")
        return True
        
    except Error as e:
        print(f"✗ Database initialization error: {e}")
        return False

def create_tables():
    """Create all necessary tables"""
    try:
        with get_connection() as (conn, cursor):
            # Sensors table - store temperature and humidity readings
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sensors (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    temperature DECIMAL(5,2) NOT NULL,
                    humidity DECIMAL(5,2) NOT NULL,
                    target_temperature DECIMAL(5,2) DEFAULT 4.0,
                    status VARCHAR(50) DEFAULT 'normal',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_created_at (created_at)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """)
            
            # Inventory table - store detected items
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS inventory (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    total_items INT DEFAULT 0,
                    fruit_count INT DEFAULT 0,
                    food_count INT DEFAULT 0,
                    other_count INT DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_created_at (created_at)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """)
            
            # Detections table - store individual object detections
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS detections (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    class_name VARCHAR(100) NOT NULL,
                    confidence DECIMAL(5,4) NOT NULL,
                    category VARCHAR(50) NOT NULL,
                    bbox_x INT,
                    bbox_y INT,
                    bbox_width INT,
                    bbox_height INT,
                    image_path VARCHAR(255),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_class_name (class_name),
                    INDEX idx_category (category),
                    INDEX idx_created_at (created_at)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """)
            
            # Detection sessions - group detections from same image
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS detection_sessions (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    total_items INT DEFAULT 0,
                    fruit_count INT DEFAULT 0,
                    food_count INT DEFAULT 0,
                    other_count INT DEFAULT 0,
                    image_path VARCHAR(255),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_created_at (created_at)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """)
            
            # Temperature settings - track temperature changes
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS temperature_settings (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    target_temperature DECIMAL(5,2) NOT NULL,
                    previous_temperature DECIMAL(5,2),
                    changed_by VARCHAR(100) DEFAULT 'system',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_created_at (created_at)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """)
            
            conn.commit()
            print("✓ Database tables created/verified")
            
    except Error as e:
        print(f"✗ Error creating tables: {e}")
        raise

@contextmanager
def get_connection():
    """Get database connection from pool"""
    conn = None
    cursor = None
    try:
        if _connection_pool is None:
            raise Error("Database not initialized. Call init_database() first.")
        
        conn = _connection_pool.get_connection()
        cursor = conn.cursor(dictionary=True)
        yield (conn, cursor)
        conn.commit()
    except Error as e:
        if conn:
            conn.rollback()
        print(f"✗ Database error: {e}")
        raise
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

# Sensor data functions
def save_sensor_reading(temperature, humidity, target_temperature=4.0, status='normal'):
    """Save sensor reading to database"""
    try:
        with get_connection() as (conn, cursor):
            cursor.execute("""
                INSERT INTO sensors (temperature, humidity, target_temperature, status)
                VALUES (%s, %s, %s, %s)
            """, (temperature, humidity, target_temperature, status))
            return cursor.lastrowid
    except Error as e:
        print(f"✗ Error saving sensor reading: {e}")
        return None

def get_latest_sensor_reading():
    """Get latest sensor reading"""
    try:
        with get_connection() as (conn, cursor):
            cursor.execute("""
                SELECT * FROM sensors 
                ORDER BY created_at DESC 
                LIMIT 1
            """)
            return cursor.fetchone()
    except Error as e:
        print(f"✗ Error getting sensor reading: {e}")
        return None

# Inventory functions
def save_inventory(total_items, fruit_count, food_count, other_count):
    """Save inventory data"""
    try:
        with get_connection() as (conn, cursor):
            cursor.execute("""
                INSERT INTO inventory (total_items, fruit_count, food_count, other_count)
                VALUES (%s, %s, %s, %s)
            """, (total_items, fruit_count, food_count, other_count))
            return cursor.lastrowid
    except Error as e:
        print(f"✗ Error saving inventory: {e}")
        return None

def get_latest_inventory():
    """Get latest inventory data"""
    try:
        with get_connection() as (conn, cursor):
            cursor.execute("""
                SELECT * FROM inventory 
                ORDER BY created_at DESC 
                LIMIT 1
            """)
            return cursor.fetchone()
    except Error as e:
        print(f"✗ Error getting inventory: {e}")
        return None

# Detection functions
def save_detection_session(total_items, fruit_count, food_count, other_count, image_path=None):
    """Save a detection session and return session ID"""
    try:
        with get_connection() as (conn, cursor):
            cursor.execute("""
                INSERT INTO detection_sessions (total_items, fruit_count, food_count, other_count, image_path)
                VALUES (%s, %s, %s, %s, %s)
            """, (total_items, fruit_count, food_count, other_count, image_path))
            return cursor.lastrowid
    except Error as e:
        print(f"✗ Error saving detection session: {e}")
        return None

def save_detection(session_id, class_name, confidence, category, bbox_x, bbox_y, bbox_width, bbox_height, image_path=None):
    """Save individual detection"""
    try:
        with get_connection() as (conn, cursor):
            # Note: session_id is stored implicitly via created_at timestamp
            # You can add a session_id column to detections table if needed
            cursor.execute("""
                INSERT INTO detections (class_name, confidence, category, bbox_x, bbox_y, bbox_width, bbox_height, image_path)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (class_name, confidence, category, bbox_x, bbox_y, bbox_width, bbox_height, image_path))
            return cursor.lastrowid
    except Error as e:
        print(f"✗ Error saving detection: {e}")
        return None

# Temperature settings
def save_temperature_setting(target_temperature, previous_temperature=None, changed_by='system'):
    """Save temperature setting change"""
    try:
        with get_connection() as (conn, cursor):
            cursor.execute("""
                INSERT INTO temperature_settings (target_temperature, previous_temperature, changed_by)
                VALUES (%s, %s, %s)
            """, (target_temperature, previous_temperature, changed_by))
            return cursor.lastrowid
    except Error as e:
        print(f"✗ Error saving temperature setting: {e}")
        return None

# Statistics functions
def get_sensor_history(limit=100):
    """Get sensor reading history"""
    try:
        with get_connection() as (conn, cursor):
            cursor.execute("""
                SELECT * FROM sensors 
                ORDER BY created_at DESC 
                LIMIT %s
            """, (limit,))
            return cursor.fetchall()
    except Error as e:
        print(f"✗ Error getting sensor history: {e}")
        return []

def get_detection_history(limit=50):
    """Get detection history"""
    try:
        with get_connection() as (conn, cursor):
            cursor.execute("""
                SELECT ds.*, 
                       COUNT(d.id) as detection_count
                FROM detection_sessions ds
                LEFT JOIN detections d ON ds.id = d.id
                GROUP BY ds.id
                ORDER BY ds.created_at DESC 
                LIMIT %s
            """, (limit,))
            return cursor.fetchall()
    except Error as e:
        print(f"✗ Error getting detection history: {e}")
        return []

def get_statistics():
    """Get overall statistics"""
    try:
        with get_connection() as (conn, cursor):
            stats = {}
            
            # Total sensor readings
            cursor.execute("SELECT COUNT(*) as count FROM sensors")
            stats['total_sensor_readings'] = cursor.fetchone()['count']
            
            # Total detections
            cursor.execute("SELECT COUNT(*) as count FROM detections")
            stats['total_detections'] = cursor.fetchone()['count']
            
            # Total detection sessions
            cursor.execute("SELECT COUNT(*) as count FROM detection_sessions")
            stats['total_sessions'] = cursor.fetchone()['count']
            
            # Average temperature
            cursor.execute("SELECT AVG(temperature) as avg_temp FROM sensors")
            result = cursor.fetchone()
            stats['avg_temperature'] = float(result['avg_temp']) if result['avg_temp'] else 0
            
            # Average humidity
            cursor.execute("SELECT AVG(humidity) as avg_humidity FROM sensors")
            result = cursor.fetchone()
            stats['avg_humidity'] = float(result['avg_humidity']) if result['avg_humidity'] else 0
            
            return stats
    except Error as e:
        print(f"✗ Error getting statistics: {e}")
        return {}

